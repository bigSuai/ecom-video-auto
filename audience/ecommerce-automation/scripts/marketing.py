"""Offline activity review and advertising arithmetic; no platform operations.

All numeric arithmetic uses Decimal. Ratios are fractions (CTR 0.02 means 2%),
rounded to eight decimal places only for presentation. Missing observations are
never silently treated as zero and incompatible attribution scopes stay apart.
"""

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path


MEASURES = ("impressions", "clicks", "spend", "conversions", "attributed_revenue")
SCOPES = ("platform", "shop_id", "currency", "attribution_window", "metric_basis")
METRIC_DEFINITIONS = {
    "ctr": "sum(clicks) / sum(impressions); fraction, not percentage; missing or zero denominator => null",
    "cpc": "sum(spend) / sum(clicks); missing or zero denominator => null",
    "cvr": "sum(conversions) / sum(clicks); fraction, not percentage; missing or zero denominator => null",
    "roas": "sum(attributed_revenue) / sum(spend); missing or zero denominator => null",
    "aggregation": "Only matching platform, shop_id, currency, attribution_window and metric_basis combine. Any missing component keeps that summed measure and its derived ratios null. Ratios use summed counts/amounts, never mean row ratios.",
    "deadline_status": "Deadline and now must have explicit UTC offsets. Compare UTC instants; deadline <= now is expired. Eligibility and source links are supplied facts, not verified approval.",
    "precision": "Nonnegative finite decimal inputs <= 1e18 and <= 6 fractional places. Counts impressions/clicks are integral. Monetary totals are exact decimal strings; ratios rounded half up to 8 fractional places.",
}


def _text(value):
    return "" if value is None else str(value).strip()


def _number(value, field):
    if value is None or _text(value) == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field}: boolean is not a number")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}: invalid decimal") from None
    if not number.is_finite() or number < 0 or number > Decimal("1e18"):
        raise ValueError(f"{field}: must be finite, nonnegative and <= 1e18")
    if number.as_tuple().exponent < -6:
        raise ValueError(f"{field}: at most six fractional places")
    if field in ("impressions", "clicks") and number != number.to_integral_value():
        raise ValueError(f"{field}: must be integral")
    return number


def _string(value):
    if value is None:
        return None
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _instant(value):
    instant = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("explicit timezone offset is required")
    return instant.astimezone(timezone.utc)


def _ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _string((numerator / denominator).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def _metrics(values):
    return {
        "ctr": _ratio(values["clicks"], values["impressions"]),
        "cpc": _ratio(values["spend"], values["clicks"]),
        "cvr": _ratio(values["conversions"], values["clicks"]),
        "roas": _ratio(values["attributed_revenue"], values["spend"]),
    }


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return value


def run(job: dict, out: Path, emit=None) -> dict:
    """Return inspectable tables. ``out`` is owned by the calling CLI writer."""
    now = _instant(job["now"]) if job.get("now") else datetime.now(timezone.utc)
    activities, keywords, facts, issues = [], [], [], []
    groups = {}
    source = [("activities", row) for row in job.get("activities", [])]
    source += [("keywords", row) for row in job.get("keywords", [])]
    with localcontext() as context:
        context.prec = 60
        for index, (kind, original) in enumerate(source, 1):
            metadata = {k: v for k, v in _safe(original).items() if k.startswith("source_")} if isinstance(original, dict) else {}
            fact = {**(_safe(original) if isinstance(original, dict) else {"raw_value": _safe(original)}), "fact_type": kind, "record_status": "invalid", "input_index": index}
            facts.append(fact)
            try:
                if not isinstance(original, dict):
                    raise ValueError("each row must be an object")
                row = dict(original)
                required = ("platform", "shop_id", "activity_id", "name") if kind == "activities" else (*SCOPES, "date", "keyword")
                for field in required:
                    row[field] = _text(row.get(field))
                    if not row[field]:
                        raise ValueError(f"{field}: required")
                if kind == "activities":
                    try:
                        deadline = _instant(row.get("deadline"))
                    except (ValueError, TypeError):
                        issues.append({"code": "invalid_deadline", "severity": "error", "table": kind, "input_index": index, "message": "deadline must be an ISO timestamp with a timezone offset", **{k: v for k, v in _safe(original).items() if k.startswith("source_")}})
                        continue
                    row["deadline_utc"] = deadline.isoformat().replace("+00:00", "Z")
                    row["deadline_status"] = "expired" if deadline <= now else "upcoming"
                    row["eligibility_status"] = "provided_unverified"
                    activities.append(_safe(row))
                else:
                    date.fromisoformat(row["date"])
                    row["currency"] = row["currency"].upper()
                    if not re.fullmatch(r"[A-Z]{3}", row["currency"]):
                        raise ValueError("currency: three-letter currency code required")
                    values = {field: _number(row.get(field), field) for field in MEASURES}
                    row.update({field: _string(value) for field, value in values.items()})
                    row.update(_metrics(values))
                    row["missing_fields"] = [field for field, value in values.items() if value is None]
                    keywords.append(_safe(row))
                    key = tuple(row[field] for field in SCOPES)
                    if key not in groups:
                        groups[key] = {field: Decimal(0) for field in MEASURES}
                    sums = groups[key]
                    for field, value in values.items():
                        sums[field] = None if sums[field] is None or value is None else sums[field] + value
                fact["record_status"] = "accepted"
            except (ValueError, TypeError) as error:
                message = str(error)
                numeric_error = any(message.startswith(field + ":") for field in MEASURES)
                issues.append({"code": "invalid_number" if numeric_error else "invalid_row", "severity": "error", "table": kind, "input_index": index, "message": message, **metadata})
            finally:
                if emit:
                    emit({"stage": "marketing", "completed": index, "total": len(source), "table": kind})
        totals = []
        for key, values in sorted(groups.items()):
            row = dict(zip(SCOPES, key))
            row.update({field: _string(value) for field, value in values.items()})
            row.update(_metrics(values))
            row["missing_fields"] = [field for field, value in values.items() if value is None]
            totals.append(row)
    activities.sort(key=lambda row: (_instant(row["deadline_utc"]), row["platform"], row["shop_id"], row["activity_id"]))
    processed = len(activities) + len(keywords)
    return {
        "summary": {"input_rows": len(source), "processed_rows": processed, "rejected_rows": len(source) - processed, "activity_rows": len(activities), "keyword_rows": len(keywords), "expired_activities": sum(row["deadline_status"] == "expired" for row in activities), "issue_count": len(issues), "now_utc": now.isoformat().replace("+00:00", "Z")},
        "tables": {"activities": activities, "keywords": keywords, "ad_totals": totals, "facts": facts},
        "issues": issues,
        "metric_definitions": METRIC_DEFINITIONS.copy(),
    }
