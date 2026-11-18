"""Self-contained offline ecommerce ledger and period review.

Amounts are recognized on payment/refund dates. Only accepted, deduplicated
facts enter calculations; every original row remains available in ``facts``.
No currency conversion, tax inference, fee recovery, or ad allocation to SKUs
is inferred. This module performs no platform or network operations.
"""

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


COSTS = ("unit_cost", "shipping_cost", "packing_cost", "platform_fee")
AMOUNTS = ("paid_amount", "refund_amount", "procurement_cost", "shipping_cost", "packing_cost", "platform_fee", "recovered_cost", "ad_spend")
KEYS = {
    "orders": ("platform", "shop_id", "order_id", "line_id"),
    "refunds": ("platform", "shop_id", "refund_id", "line_id"),
    "ads": ("platform", "shop_id", "ad_id", "date", "currency"),
}
METRIC_DEFINITIONS = {
    "paid_amount": "Sum accepted paid order-line receipts by payment date; cancelled orders do not recognize receipts or costs.",
    "refund_amount": "Sum accepted refunds by refund date, linked through platform/shop_id/order_id/line_id to a paid original line, including original orders outside the reporting period.",
    "net_sales": "paid_amount - refund_amount, separately for each currency; a cross-period refund may make period net sales negative.",
    "contribution": "net_sales - quantity*unit_cost - shipping_cost - packing_cost - platform_fee + recovered_cost - ad_spend. Original purchase and line fees use payment date; recovered_cost uses refund date. This is contribution, not accounting net profit.",
    "sku_contribution": "Same recognized receipt/cost/refund formula before shop ads; shop ads have no reliable SKU allocation and are never apportioned. SKU contribution_basis is before_shop_ads.",
    "cost_scope": "unit_cost is per unit; shipping_cost, packing_cost and platform_fee are already allocated line TOTALS. Do not repeat whole-order fees on every order line. Currency is explicit; no conversion is performed.",
    "ad_coverage": "For every included shop/currency, every calendar day in the requested inclusive period requires at least one accepted ad row. An explicit spend=0 row establishes zero-spend coverage. Missing coverage makes ad_spend and contribution null; known_ad_spend is the observed partial subtotal.",
    "missing_values": "Missing costs or recovered_cost make contribution null, never zero. Known component subtotals remain inspectable. Explicit zero means known zero.",
    "duplicates": "Identical normalized defined business fields with the same composite key are counted once; raw, mapped alias columns and all provenance are ignored. Differing business content quarantines the entire key. Ads use platform/shop/ad_id/date/currency; refunds use platform/shop/refund_id/line_id.",
    "refund_validation": "All supplied accepted refund facts, including outside-period facts, count toward the original line lifetime refund cap. If their sum exceeds paid_amount the entire refund set for that line is quarantined. This cannot check omitted historical refunds.",
    "precision": "Finite nonnegative inputs <= 1e18, <= 6 fractional places; quantity > 0 and <= 1e9. Decimal arithmetic uses 60-digit precision and outputs exact decimal strings with no implicit cent rounding.",
    "date_scope": "Strict YYYY-MM-DD supplied business dates; dates are not shifted across timezones. Inclusive period must contain 1..366 days. Supply original orders and lifetime refunds needed for cross-period checks.",
    "completeness": "Totals cover accepted supplied facts. Excluded facts make their scope incomplete and contribution null; unknown excluded scope conservatively affects all scopes. Accepted monetary subtotals remain visible. Completeness outside supplied inputs is not asserted.",
}


def _text(value):
    return "" if value is None else str(value).strip()


def _day(value):
    text = _text(value)
    parsed = date.fromisoformat(text)
    if text != parsed.isoformat():
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


def _number(value, field, optional=False):
    if value is None or _text(value) == "":
        if optional:
            return None
        raise ValueError(f"{field}: required numeric value")
    if isinstance(value, bool):
        raise ValueError(f"{field}: boolean is not numeric")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}: invalid decimal") from None
    if not number.is_finite() or number < 0 or number > Decimal("1e18"):
        raise ValueError(f"{field}: must be finite, nonnegative and <= 1e18")
    if number.as_tuple().exponent < -6:
        raise ValueError(f"{field}: at most six fractional places")
    if field == "quantity" and (number <= 0 or number > Decimal("1e9")):
        raise ValueError("quantity: must be > 0 and <= 1e9")
    return number


def _string(number):
    if number is None:
        return None
    result = format(number, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, (Decimal, date, datetime, float)):
        return str(value)
    return value


def _new_group(dimensions):
    return {**dimensions, "_values": {field: Decimal(0) for field in AMOUNTS}, "_missing": set(), "paid_lines": 0, "refund_lines": 0, "missing_cost_rows": 0, "missing_recovered_cost_rows": 0, "missing_ad_days": 0}


def _serialize_group(group, sku=False):
    values = group["_values"]
    missing = group["_missing"]
    result = {key: value for key, value in group.items() if not key.startswith("_")}
    result.update({field: _string(value) for field, value in values.items()})
    result["known_ad_spend"] = _string(values["ad_spend"])
    for field in ("procurement_cost", "shipping_cost", "packing_cost", "platform_fee", "recovered_cost"):
        missing_name = "unit_cost" if field == "procurement_cost" else field
        if missing_name in missing:
            result[field] = None
    result["ad_spend"] = None if sku or "ad_coverage" in missing else result["ad_spend"]
    result["net_sales"] = _string(values["paid_amount"] - values["refund_amount"])
    result["missing_fields"] = sorted(missing)
    result["complete"] = not missing
    result["has_excluded_facts"] = 'excluded_facts' in missing
    result["totals_basis"] = 'accepted_supplied_facts'
    contribution = values["paid_amount"] - values["refund_amount"] - values["procurement_cost"] - values["shipping_cost"] - values["packing_cost"] - values["platform_fee"] + values["recovered_cost"]
    if not sku:
        contribution -= values["ad_spend"]
    result["contribution"] = None if missing else _string(contribution)
    result["contribution_basis"] = "before_shop_ads" if sku else "after_shop_ads"
    if sku:
        result["known_ad_spend"] = None
    return result


def _merge(target, source):
    for field in AMOUNTS:
        target["_values"][field] += source["_values"][field]
    target["_missing"].update(source["_missing"])
    for field in ("paid_lines", "refund_lines", "missing_cost_rows", "missing_recovered_cost_rows", "missing_ad_days"):
        target[field] += source[field]


def run(job: dict, out: Path, emit=None) -> dict:
    """Return ledger tables; the caller owns output persistence under ``out``."""
    start, end = _day(job.get("start_date")), _day(job.get("end_date"))
    days = (end - start).days + 1
    if not 1 <= days <= 366:
        raise ValueError("report period must contain 1..366 inclusive days")
    with localcontext() as context:
        context.prec = 60
        return _run(job, start, end, days, emit)


def _run(job, start, end, days, emit):
    facts, records, issues = [], {kind: [] for kind in KEYS}, []
    source = [(kind, row) for kind in KEYS for row in job.get(kind, [])]

    def issue(record, code, message):
        fact = record["fact"]
        issues.append({"code": code, "severity": "error", "table": fact["fact_type"], "input_index": fact["input_index"], "message": message, "key": list(record.get("key", ())), **{key: value for key, value in fact.items() if key.startswith("source_")}})
        fact["record_status"] = "rejected"
        fact["exclusion_reason"] = code
        record["active"] = False

    # Validate facts before arithmetic; retain original values and source metadata.
    for index, (kind, original) in enumerate(source, 1):
        fact = {**(_safe(original) if isinstance(original, dict) else {"raw_value": _safe(original)}), "fact_type": kind, "input_index": index, "record_status": "rejected"}
        facts.append(fact)
        record = {"fact": fact, "active": True}
        numeric_fields = []
        try:
            if not isinstance(original, dict):
                raise ValueError("each fact must be an object")
            row = dict(original)
            required = ("platform", "shop_id", "date", "currency", *KEYS[kind])
            if kind == "orders":
                required += ("sku", "status")
                numeric_fields = ["quantity", "paid_amount", *COSTS]
            elif kind == "refunds":
                required += ("order_id",)
                numeric_fields = ["amount", "recovered_cost"]
            else:
                numeric_fields = ["spend"]
            for field in required:
                row[field] = _text(row.get(field))
                if not row[field]:
                    raise ValueError(f"{field}: required")
            row["currency"] = row["currency"].upper()
            if not re.fullmatch(r"[A-Z]{3}", row["currency"]):
                raise ValueError("currency: three-letter currency code required")
            row["date"] = _day(row["date"]).isoformat()
            if kind == "orders" and row["status"] not in ("paid", "cancelled"):
                raise ValueError("status: must be paid or cancelled")
            numbers = {field: _number(row.get(field), field, optional=field in COSTS or field == "recovered_cost") for field in numeric_fields}
            row.update({field: _string(number) for field, number in numbers.items()})
            record.update(row=row, numbers=numbers, key=tuple(row[field] for field in KEYS[kind]))
            fact["record_status"] = "accepted"
            records[kind].append(record)
        except (ValueError, TypeError) as error:
            code = "invalid_number" if any(str(error).startswith(field + ":") for field in numeric_fields) else "invalid_row"
            issue(record, code, str(error))
        finally:
            if emit:
                emit({"stage": "reporting", "completed": index, "total": len(source), "table": kind})

    duplicate_rows, conflict_keys, conflict_rows = 0, 0, 0
    for kind, rows in records.items():
        grouped = {}
        for record in rows:
            grouped.setdefault(record["key"], []).append(record)
        for key, same_key in grouped.items():
            signatures = {}
            for record in same_key:
                fields = set(KEYS[kind]) | {'date', 'currency'}
                if kind == 'orders':
                    fields.update(('sku', 'status', 'quantity', 'paid_amount', *COSTS))
                elif kind == 'refunds':
                    fields.update(('order_id', 'amount', 'recovered_cost'))
                else:
                    fields.add('spend')
                payload = {field: record['row'].get(field) for field in sorted(fields)}
                signature = json.dumps(_safe(payload), sort_keys=True, ensure_ascii=False)
                if signature in signatures:
                    duplicate_rows += 1
                    record["active"] = False
                    record["fact"]["record_status"] = "duplicate"
                    record["fact"]["duplicate_of_input_index"] = signatures[signature]["fact"]["input_index"]
                else:
                    signatures[signature] = record
            if len(signatures) > 1:
                conflict_keys += 1
                conflict_rows += len(same_key)
                for record in same_key:
                    issue(record, "conflicting_duplicate", "Different business facts share a composite key; the entire key is excluded pending review")

    order_lookup = {record["key"]: record for record in records["orders"] if record["active"]}
    refund_sets = {}
    for record in records["refunds"]:
        if not record["active"]:
            continue
        row = record["row"]
        order_key = tuple(row[field] for field in KEYS["orders"])
        original = order_lookup.get(order_key)
        if original is None:
            issue(record, "refund_order_missing", "No unambiguous original order line in the same platform and shop")
        elif original["row"]["status"] == "cancelled":
            issue(record, "refund_cancelled_order", "Refund cannot link to a cancelled order line")
        elif original["row"]["currency"] != row["currency"]:
            issue(record, "refund_currency_mismatch", "Refund currency differs from the original paid currency")
        elif row["date"] < original["row"]["date"]:
            issue(record, "refund_before_payment", "Refund date precedes payment date")
        else:
            record["original"] = original
            refund_sets.setdefault(order_key, []).append(record)
    for order_key, rows in refund_sets.items():
        paid = order_lookup[order_key]["numbers"]["paid_amount"]
        if sum((record["numbers"]["amount"] for record in rows), Decimal(0)) > paid:
            for record in rows:
                issue(record, "refund_exceeds_paid", "Cumulative supplied refunds exceed the original line paid amount; all supplied refunds for this line are excluded")

    def in_period(record):
        return start.isoformat() <= record["row"]["date"] <= end.isoformat()

    active = {kind: [record for record in rows if record["active"]] for kind, rows in records.items()}
    period = {kind: [record for record in rows if in_period(record) and (kind != "orders" or record["row"]["status"] == "paid")] for kind, rows in active.items()}
    shop_scopes = {tuple(record["row"][field] for field in ("platform", "shop_id", "currency")) for rows in period.values() for record in rows}
    excluded_scopes, unscoped_excluded = set(), False
    for fact in facts:
        if fact['record_status'] != 'rejected':
            continue
        scope = tuple(_text(fact.get(field)) for field in ('platform', 'shop_id', 'currency'))
        if all(scope) and re.fullmatch('[A-Z]{3}', scope[2].upper()):
            excluded_scopes.add((*scope[:2], scope[2].upper()))
        else:
            unscoped_excluded = True
        if fact.get('fact_type') == 'refunds':
            original_key = tuple(_text(fact.get(field)) for field in KEYS['orders'])
            related = order_lookup.get(original_key)
            if related:
                original_row = related['row']
                excluded_scopes.add(tuple(original_row[field] for field in ('platform', 'shop_id', 'currency')))
    shop_scopes.update(excluded_scopes)
    daily, skus = {}, {}
    for platform, shop_id, currency in sorted(shop_scopes):
        for offset in range(days):
            day = (start + timedelta(days=offset)).isoformat()
            daily[(platform, shop_id, currency, day)] = _new_group(dict(platform=platform, shop_id=shop_id, currency=currency, date=day))

    def groups_for(record, sku):
        row = record["row"]
        shop_key = tuple(row[field] for field in ("platform", "shop_id", "currency"))
        day_group = daily[(*shop_key, row["date"])]
        sku_key = (*shop_key, sku)
        if sku_key not in skus:
            skus[sku_key] = _new_group(dict(platform=shop_key[0], shop_id=shop_key[1], currency=shop_key[2], sku=sku))
        return day_group, skus[sku_key]

    for record in period["orders"]:
        row, numbers = record["row"], record["numbers"]
        for group in groups_for(record, row["sku"]):
            group["paid_lines"] += 1
            group["_values"]["paid_amount"] += numbers["paid_amount"]
            missing = [field for field in COSTS if numbers[field] is None]
            group["_missing"].update(missing)
            group["missing_cost_rows"] += bool(missing)
            if numbers["unit_cost"] is not None:
                group["_values"]["procurement_cost"] += numbers["unit_cost"] * numbers["quantity"]
            for field in COSTS[1:]:
                if numbers[field] is not None:
                    group["_values"][field] += numbers[field]
    for record in period["refunds"]:
        for group in groups_for(record, record["original"]["row"]["sku"]):
            numbers = record["numbers"]
            group["refund_lines"] += 1
            group["_values"]["refund_amount"] += numbers["amount"]
            if numbers["recovered_cost"] is None:
                group["_missing"].add("recovered_cost")
                group["missing_recovered_cost_rows"] += 1
            else:
                group["_values"]["recovered_cost"] += numbers["recovered_cost"]

    covered_days = set()
    for record in period["ads"]:
        row = record["row"]
        key = tuple(row[field] for field in ("platform", "shop_id", "currency", "date"))
        daily[key]["_values"]["ad_spend"] += record["numbers"]["spend"]
        covered_days.add(key)
    stores, overview = {}, {}
    for key, group in daily.items():
        if unscoped_excluded or key[:3] in excluded_scopes:
            group['_missing'].add('excluded_facts')
    for key, group in skus.items():
        if unscoped_excluded or key[:3] in excluded_scopes:
            group['_missing'].add('excluded_facts')
    for key, group in sorted(daily.items()):
        if key not in covered_days:
            group["_missing"].add("ad_coverage")
            group["missing_ad_days"] = 1
        shop_key = key[:3]
        if shop_key not in stores:
            stores[shop_key] = _new_group(dict(platform=key[0], shop_id=key[1], currency=key[2]))
        _merge(stores[shop_key], group)
    for key, group in sorted(stores.items()):
        currency = key[2]
        if currency not in overview:
            overview[currency] = _new_group(dict(currency=currency))
        _merge(overview[currency], group)

    conclusions = []
    for key, group in sorted(stores.items()):
        scope = dict(platform=key[0], shop_id=key[1], currency=key[2])
        if group["_missing"]:
            conclusions.append({**scope, "rule": "contribution_unavailable", "status": "needs_review", "message": "Contribution is unavailable because required facts are missing", "missing_fields": sorted(group["_missing"]), "cause": None})
        if group["_values"]["refund_amount"] > group["_values"]["paid_amount"]:
            conclusions.append({**scope, "rule": "period_refunds_exceed_payments", "status": "needs_review", "message": "Refund-date amounts exceed payment-date receipts in this period; inspect original-order and refund timing", "cause": None})
    if issues:
        conclusions.append({"rule": "excluded_input_facts", "status": "needs_review", "message": "Some input facts were excluded; inspect issues and original facts before relying on totals", "issue_count": len(issues), "cause": None})

    processed = sum(len(rows) for rows in active.values())
    recognized = sum(len(rows) for rows in period.values())
    return {
        "summary": {"input_rows": len(source), "processed_rows": processed, "period_rows": recognized, "duplicate_rows": duplicate_rows, "conflicting_keys": conflict_keys, "conflicting_rows": conflict_rows, "rejected_rows": sum(fact["record_status"] == "rejected" for fact in facts), "issue_count": len(issues), "start_date": start.isoformat(), "end_date": end.isoformat(), "period_days": days, "currencies": sorted(overview), "has_input_issues": bool(issues)},
        "tables": {"overview": [_serialize_group(group) for _, group in sorted(overview.items())], "stores": [_serialize_group(group) for _, group in sorted(stores.items())], "daily": [_serialize_group(group) for _, group in sorted(daily.items())], "skus": [_serialize_group(group, sku=True) for _, group in sorted(skus.items())], "facts": facts, "conclusions": conclusions},
        "issues": issues,
        "metric_definitions": METRIC_DEFINITIONS.copy(),
    }
