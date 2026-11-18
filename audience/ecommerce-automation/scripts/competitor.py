"""Source-backed offline competitor comparisons and persistent local alerts.

All prices are Decimal values. Matching is explicit, conditions stay separate,
and no website, account, scheduler, or price-changing API is called here.
"""

import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


OWN_KEY = ("platform", "shop_id", "sku")
OWN_FIELDS = (*OWN_KEY, "name", "currency", "price", "spec", "price_type")
COMPETITOR_KEY = (*OWN_KEY, "competitor_id", "currency", "spec", "price_type")
SNAPSHOT_FIELDS = (*COMPETITOR_KEY, "price", "available", "match_confirmed", "observed_at", "changed_at")


def _text(value):
    return "" if value is None else str(value).strip()


def _time(value):
    result = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware ISO timestamp required")
    return result.astimezone(timezone.utc)


def _number(value, field, optional=False):
    if optional and (value is None or _text(value) == ""):
        return None
    try:
        number = Decimal(_text(value)) if not isinstance(value, bool) else Decimal("NaN")
    except (ValueError, InvalidOperation):
        raise ValueError(f"{field} is not a decimal") from None
    if not number.is_finite() or number < 0 or number > Decimal("1e18") or number.as_tuple().exponent < -12:
        raise ValueError(f"{field} must be finite, nonnegative, <= 1e18, with <= 12 decimal places")
    return number


def _string(number):
    if number is None:
        return None
    result = format(number, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _identifier(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _boolean(value, field):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError(f"{field} must be a boolean or explicit true/false text")


def run(job: dict, out: Path, emit=None) -> dict:
    """Return tables/state; alert JSON files are written only under ``out``.

    Supply the returned state unchanged in the next call. The runner owns its
    durable storage; a first run establishes baselines, never past platform time.
    """
    with localcontext() as context:
        context.prec = 60
        return _run(job, Path(out), emit)


def _run(job, out, emit):
    actual_started_monotonic = time.monotonic_ns()
    actual_detected = datetime.now(timezone.utc)
    scenario_clock = bool(job.get("now"))
    now = _time(job["now"]) if scenario_clock else actual_detected
    timing = {"actual_detected_at": actual_detected.isoformat(), "timing_basis": "scenario_clock" if scenario_clock else "system_clock", "processing_delay_basis": "monotonic_clock", "source_delay_basis": "scenario_supplied_timestamps" if scenario_clock else "supplied_source_timestamps"}
    percent_threshold = _number(job.get("drop_threshold_percent", 5), "drop_threshold_percent")
    absolute_threshold = _number(job.get("absolute_threshold"), "absolute_threshold", optional=True)
    stale_after = _number(job.get("stale_after_hours", 24), "stale_after_hours")
    previous = job.get("state") or {}
    if not isinstance(previous, dict) or previous.get("schema_version", 1) != 1 or not isinstance(previous.get("baselines", {}), dict):
        raise ValueError("state must be the schema_version=1 state returned by this module")
    baselines = json.loads(_json(previous.get("baselines", {})))
    checkpoints = json.loads(_json(previous.get("latest_snapshots", baselines)))
    if not isinstance(checkpoints, dict):
        raise ValueError("state latest_snapshots must be an object")
    seen_snapshots = set(previous.get("seen_snapshot_ids", []))
    seen_alerts = set(previous.get("seen_alert_ids", []))
    # A seen observation may not yet have been compared if an own-product
    # dependency was missing. Older states can recover completed current IDs
    # from their successfully established baselines.
    compared_snapshots = set(previous.get("compared_snapshot_ids", [row.get("snapshot_id") for row in baselines.values() if isinstance(row, dict) and row.get("snapshot_id")]))
    if any(not isinstance(item, str) for item in (*seen_snapshots, *seen_alerts, *compared_snapshots)):
        raise ValueError("state seen IDs must be strings")
    for key, row in (*baselines.items(), *checkpoints.items()):
        if not isinstance(row, dict) or not all(_text(row.get(field)) for field in COMPETITOR_KEY):
            raise ValueError("state baseline has invalid composite key")
        _number(row.get("price"), "state.price")
        _time(row.get("observed_at"))
        if key != _json([row[field] for field in COMPETITOR_KEY]):
            raise ValueError("state baseline key does not match its source record")
    inputs = [(kind, row) for kind in ("products", "snapshots", "industry") for row in job.get(kind, [])]
    facts, issues, comparisons, alerts = [], [], [], []
    product_groups, snapshot_groups = defaultdict(list), defaultdict(list)
    industry_rows = []
    counters = dict(duplicate_rows=0, superseded_rows=0, rejected_rows=0)

    def issue(fact, code, message, severity="warning"):
        issues.append({"table": fact.get("input_table", "state"), "input_index": fact.get("input_index", 0), "code": code, "severity": severity, "message": message, **{key: value for key, value in fact.items() if key.startswith("source_")}})

    for index, (kind, original) in enumerate(inputs, 1):
        row = dict(original) if isinstance(original, dict) else {"raw_value": original}
        fact = {**row, "input_table": kind, "input_index": index, "record_status": "accepted"}
        facts.append(fact)
        try:
            if not isinstance(original, dict):
                raise ValueError("each input row must be an object")
            required = ("category", "product", "currency") if kind == "industry" else (*OWN_KEY, "currency", "spec", "price_type")
            if kind == "snapshots":
                required += ("competitor_id",)
            for field in required:
                row[field] = _text(row.get(field))
                if not row[field]:
                    raise ValueError(f"{field} is required")
            row["currency"] = row["currency"].upper()
            if len(row["currency"]) != 3 or not row["currency"].isascii() or not row["currency"].isalpha():
                raise ValueError("currency needs a three-letter code")
            try:
                if kind == "industry":
                    for field in ("units", "revenue"):
                        row[field] = _string(_number(row.get(field), field, optional=True))
                else:
                    row["price"] = _string(_number(row.get("price"), "price"))
            except ValueError as exc:
                issue(fact, "invalid_number", str(exc), "error")
                raise ValueError("invalid numeric input") from None
            if kind == "products":
                product_groups[tuple(row[field] for field in OWN_KEY)].append((row, fact))
            elif kind == "industry":
                industry_rows.append(row)
            else:
                try:
                    observed = _time(row.get("observed_at"))
                    changed = _time(row["changed_at"]) if row.get("changed_at") else None
                    row["observed_at"] = observed.isoformat()
                    row["changed_at"] = changed.isoformat() if changed else None
                except (ValueError, TypeError, OverflowError):
                    issue(fact, "invalid_time", "Supply an explicit timezone-aware observed_at and optional changed_at.", "error")
                    raise ValueError("invalid source time") from None
                if observed > now or (changed and changed > observed):
                    issue(fact, "negative_delay", "Source timestamps imply a negative changed→observed or observed→detected delay.", "error")
                    raise ValueError("invalid time order")
                try:
                    row["available"], row["match_confirmed"] = _boolean(row.get("available"), "available"), _boolean(row.get("match_confirmed"), "match_confirmed")
                except ValueError as exc:
                    issue(fact, "invalid_boolean", str(exc), "error")
                    raise ValueError("invalid boolean input") from None
                if not _text(row.get("source_url")) and not any(_text(value) for field, value in row.items() if field.startswith("source_") and field != "source_row"):
                    issue(fact, "missing_source", "Supply the authorized page/export reference for the observed price.")
                snapshot_groups[tuple(row[field] for field in COMPETITOR_KEY)].append((row, fact))
        except (ValueError, TypeError) as exc:
            fact["record_status"] = "rejected"
            counters["rejected_rows"] += 1
            if str(exc) not in ("invalid numeric input", "invalid source time", "invalid time order", "invalid boolean input"):
                issue(fact, "invalid_row", str(exc), "error")
        if emit:
            emit({"module": "G", "stage": "input", "table": kind, "input_index": index, "processed_rows": index, "input_rows": len(inputs), "status": fact["record_status"]})

    products = {}
    for key, rows in product_groups.items():
        signatures = {_json({field: row.get(field) for field in OWN_FIELDS}) for row, _ in rows}
        if len(signatures) != 1:
            for _, fact in rows:
                fact["record_status"] = "conflict"
                issue(fact, "product_conflict", "Conflicting current own-product facts have no explicit timestamp; no price chosen.", "error")
            continue
        products[key] = rows[0][0]
        for _, fact in rows[1:]:
            fact["record_status"] = "duplicate"
            counters["duplicate_rows"] += 1

    for key, rows in snapshot_groups.items():
        newest = max(_time(row["observed_at"]) for row, _ in rows)
        current = [(row, fact) for row, fact in rows if _time(row["observed_at"]) == newest]
        for row, fact in rows:
            if _time(row["observed_at"]) < newest:
                fact["record_status"] = "superseded"
                counters["superseded_rows"] += 1
        signatures = {_json({field: row.get(field) for field in SNAPSHOT_FIELDS}) for row, _ in current}
        if len(signatures) != 1:
            for _, fact in current:
                fact["record_status"] = "conflict"
                issue(fact, "snapshot_conflict", "Different competitor facts share the newest observed_at; baseline and alerts are withheld.", "error")
            continue
        row, fact = current[0]
        for _, duplicate_fact in current[1:]:
            duplicate_fact["record_status"] = "duplicate"
            counters["duplicate_rows"] += 1
        state_key = _json(list(key))
        prior = baselines.get(state_key)
        checkpoint = checkpoints.get(state_key)
        snapshot_id = _identifier({field: row.get(field) for field in SNAPSHOT_FIELDS})
        old_or_duplicate = False
        duplicate_observation = False
        if checkpoint and _time(checkpoint["observed_at"]) > newest:
            counters["superseded_rows"] += 1
            fact["record_status"] = "superseded"
            old_or_duplicate = True
            issue(fact, "out_of_order", "An older export cannot overwrite the saved newer competitor baseline.")
        elif snapshot_id in seen_snapshots:
            counters["duplicate_rows"] += 1
            fact["record_status"] = "duplicate"
            old_or_duplicate = True
            duplicate_observation = True
        elif checkpoint and _time(checkpoint["observed_at"]) == newest and checkpoint.get("snapshot_id") != snapshot_id:
            fact["record_status"] = "conflict"
            old_or_duplicate = True
            issue(fact, "snapshot_conflict", "New data conflicts with the saved baseline at the same observed_at.", "error")
        own = products.get(key[:3])
        reasons = []
        if not own:
            reasons.append("own_product_missing_or_conflicted")
        else:
            reasons += [f"{field}_mismatch" for field in ("currency", "spec", "price_type") if row[field] != own[field]]
        if not row["match_confirmed"]:
            reasons.append("match_not_confirmed")
        if not row["available"]:
            reasons.append("unavailable")
        age = Decimal(str((now - newest).total_seconds())) / Decimal(3600)
        stale = age > stale_after
        if stale:
            issue(fact, "stale_source", "The newest supplied competitor snapshot is stale; refresh before acting.")
        comparable = not reasons
        price = Decimal(row["price"])
        own_price = Decimal(own["price"]) if own else None
        gap = own_price - price if comparable else None
        comparison = {**row, **timing, "snapshot_id": snapshot_id, "comparable": comparable, "comparison_reasons": reasons, "own_price": _string(own_price), "own_price_gap": _string(gap), "own_price_gap_percent": _string(gap * 100 / own_price) if gap is not None and own_price else None, "stale": stale, "age_hours": _string(age), "record_status": fact["record_status"], "detected_at": now.isoformat()}
        comparisons.append(comparison)
        dependency_repaired = duplicate_observation and comparable and snapshot_id not in compared_snapshots
        if old_or_duplicate and not dependency_repaired:
            continue
        seen_snapshots.add(snapshot_id)
        # An unavailable/unmatched latest observation still prevents an older
        # available export from being mistaken for a newly observed price drop.
        checkpoints[state_key] = {**row, "snapshot_id": snapshot_id}
        # Only eligible same-condition observations establish a comparison baseline.
        if not comparable:
            continue
        drop = Decimal(prior["price"]) - price if prior else None
        drop_percent = drop * 100 / Decimal(prior["price"]) if prior and Decimal(prior["price"]) else None
        alert_type = None
        if not stale and prior and drop > 0 and ((drop_percent is not None and drop_percent >= percent_threshold) or (absolute_threshold is not None and drop >= absolute_threshold)):
            alert_type = "price_drop"
        elif not stale and not prior and gap is not None and gap > 0:
            alert_type = "initial_price_gap"
        if alert_type:
            alert_id = _identifier([alert_type, state_key, prior.get("snapshot_id") if prior else None, snapshot_id])
            if alert_id not in seen_alerts:
                changed = _time(row["changed_at"]) if row["changed_at"] else None
                alert = {**row, **timing, "alert_id": alert_id, "alert_type": alert_type, "snapshot_id": snapshot_id, "previous_price": prior["price"] if prior else None, "drop_amount": _string(drop), "drop_percent": _string(drop_percent), "own_price": own["price"], "own_price_gap": _string(gap), "detected_at": now.isoformat(), "change_to_observe_seconds": _string(Decimal(str((newest - changed).total_seconds()))) if changed else None, "observe_to_detect_seconds": _string(Decimal(str((now - newest).total_seconds()))), "action": "review_only_no_price_change"}
                directory = out / "alerts"
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"{alert_id}.json"
                written = datetime.now(timezone.utc)
                delay = Decimal(time.monotonic_ns() - actual_started_monotonic) / Decimal(1_000_000_000)
                if written < actual_detected:
                    issue(fact, "negative_delay", "Actual wall clock moved backward between detection and writing; processing interval uses the monotonic clock.", "error")
                alert.update(written_at=written.isoformat(), detected_to_write_seconds=_string(delay), alert_file=str(path.resolve()))
                temporary = path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(path)
                seen_alerts.add(alert_id)
                alerts.append(alert)
        baselines[state_key] = {**row, "snapshot_id": snapshot_id}
        compared_snapshots.add(snapshot_id)

    industry_summary, industry_products = [], []
    for dimensions, target in ((("category", "currency"), industry_summary), (("category", "product", "currency"), industry_products)):
        groups = defaultdict(list)
        for row in industry_rows:
            groups[tuple(row[field] for field in dimensions)].append(row)
        for key, rows in sorted(groups.items()):
            group = {**dict(zip(dimensions, key)), "input_rows": len(rows), "sources": [row.get("source_url") for row in rows if row.get("source_url")]}
            for field in ("units", "revenue"):
                known = sum((Decimal(row[field]) for row in rows if row[field] is not None), Decimal(0))
                missing = sum(row[field] is None for row in rows)
                group[f"known_{field}"] = _string(known)
                group[f"missing_{field}_rows"] = missing
                group[field] = None if missing else _string(known)
            target.append(group)
    state = {"schema_version": 1, "baselines": baselines, "latest_snapshots": checkpoints, "seen_snapshot_ids": sorted(seen_snapshots), "compared_snapshot_ids": sorted(compared_snapshots), "seen_alert_ids": sorted(seen_alerts)}
    return {"summary": {"input_rows": len(inputs), "processed_rows": len(inputs), "issue_rows": len({row["input_index"] for row in issues if row["input_index"]}), "issue_count": len(issues), "comparable_rows": sum(row["comparable"] for row in comparisons), "alert_rows": len(alerts), **counters}, "tables": {"products": list(products.values()), "comparisons": comparisons, "alerts": alerts, "industry_summary": industry_summary, "industry_products": industry_products, "industry_rows": industry_rows, "source_rows": facts}, "issues": issues, "state": state}
