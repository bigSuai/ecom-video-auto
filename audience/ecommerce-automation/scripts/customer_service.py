"""Offline customer-service facts, reply evidence, and freshness review.

The caller supplies authorized exports. This module neither reads accounts nor
sends replies, changes orders, or claims that an export is a live synchronization.
"""

import json
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


KEYS = {
    "orders": ("platform", "shop_id", "order_id", "line_id"),
    "inventory": ("platform", "shop_id", "sku"),
    "cases": ("platform", "shop_id", "case_id"),
}
BUSINESS_FIELDS = {
    "orders": (*KEYS["orders"], "sku", "status", "quantity", "updated_at"),
    "inventory": (*KEYS["inventory"], "stock", "updated_at"),
    "cases": (*KEYS["cases"], "order_id", "sku", "customer_alias", "subject", "received_at", "replied_at", "sent_evidence", "local_status", "draft", "updated_at"),
}


def _text(value):
    return "" if value is None else str(value).strip()


def _time(value):
    stamp = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("a timezone-aware ISO timestamp is required")
    return stamp.astimezone(timezone.utc)


def _number(value, field, integral=False):
    try:
        number = Decimal(str(value)) if not isinstance(value, bool) else Decimal("NaN")
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be a nonnegative finite number") from None
    if not number.is_finite() or number < 0 or number > Decimal("1e18"):
        raise ValueError(f"{field} must be a nonnegative finite number <= 1e18")
    if integral and number != number.to_integral_value():
        raise ValueError(f"{field} must be an integer")
    return int(number) if integral else number


def _decimal_text(value):
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _signature(row, kind):
    # File mapping deliberately retains original alias columns and audit fields.
    # Only canonical, normalized facts determine whether snapshots conflict.
    return json.dumps({field: row.get(field) for field in BUSINESS_FIELDS[kind]}, sort_keys=True, ensure_ascii=False, default=str)


def _present(value):
    return bool(value) and (not isinstance(value, str) or bool(value.strip()))


def run(job: dict, out: Path, emit=None) -> dict:
    """Return inspectable tables and issues; the runner persists these tables."""
    now = _time(job["now"]) if job.get("now") else datetime.now(timezone.utc)
    sla = _number(job.get("reply_sla_hours", 24), "reply_sla_hours")
    stale_after = _number(job.get("stale_after_hours", 24), "stale_after_hours")
    inputs = [(kind, row) for kind in (*KEYS, "questions") for row in job.get(kind, [])]
    facts, issues = [], []
    candidates = {kind: defaultdict(list) for kind in KEYS}
    questions = defaultdict(list)
    counters = dict(duplicate_rows=0, superseded_rows=0, rejected_rows=0)

    def issue(fact, code, message, severity="warning"):
        issues.append({"table": fact["input_table"], "input_index": fact["input_index"], "code": code, "severity": severity, "message": message, **{k: v for k, v in fact.items() if k.startswith("source_")}})

    for index, (kind, original) in enumerate(inputs, 1):
        row = dict(original) if isinstance(original, dict) else {"raw_value": original}
        fact = {**row, "input_table": kind, "input_index": index, "record_status": "accepted"}
        facts.append(fact)
        if not any(_present(v) for k, v in row.items() if k.startswith("source_") and k not in ("source_row", "source_index")) and not _present(row.get("source")):
            issue(fact, "missing_source", "Supply the authorized source file, page, or system export reference.")
        try:
            if not isinstance(original, dict):
                raise ValueError("each input row must be an object")
            required = ("platform", "shop_id", "question") if kind == "questions" else KEYS[kind]
            for field in required:
                row[field] = _text(row.get(field))
                if not row[field]:
                    raise ValueError(f"{field} is required")
            if kind == "questions":
                normalized = "".join(char for char in unicodedata.normalize("NFKC", row["question"]).casefold() if not char.isspace() and not unicodedata.category(char).startswith("P"))
                if not normalized:
                    raise ValueError("question needs content beyond punctuation")
                questions[(row["platform"], row["shop_id"], normalized)].append((row, fact))
            else:
                if kind == "inventory":
                    try:
                        row["stock"] = _number(row.get("stock"), "stock", integral=True)
                    except ValueError as exc:
                        issue(fact, "invalid_stock", str(exc), "error")
                        raise ValueError("invalid stock") from None
                if kind == "orders":
                    for field in ("sku", "status"):
                        row[field] = _text(row.get(field))
                        if not row[field]:
                            raise ValueError(f"{field} is required")
                    row["quantity"] = _number(row.get("quantity"), "quantity", integral=True)
                    if row["quantity"] == 0:
                        raise ValueError("quantity must be positive")
                try:
                    if kind == "cases":
                        received = _time(row.get("received_at"))
                        row["received_at"] = received.isoformat()
                        stamp = _time(row["updated_at"]) if row.get("updated_at") else received
                        if row.get("updated_at"):
                            row["updated_at"] = stamp.isoformat()
                        if row.get("replied_at"):
                            replied = _time(row["replied_at"])
                            row["replied_at"] = replied.isoformat()
                            if not row.get("updated_at"):
                                stamp = max(stamp, replied)
                    else:
                        stamp = _time(row.get("updated_at"))
                        row["updated_at"] = stamp.isoformat()
                except (ValueError, TypeError, OverflowError):
                    issue(fact, "invalid_time", "A valid timezone-aware source timestamp is required.", "error")
                    raise ValueError("invalid source time") from None
                key = tuple(row[field] for field in KEYS[kind])
                candidates[kind][key].append((stamp, row, fact))
        except (ValueError, TypeError) as exc:
            fact["record_status"] = "rejected"
            counters["rejected_rows"] += 1
            if str(exc) not in ("invalid stock", "invalid source time"):
                issue(fact, "invalid_row", str(exc), "error")
        if emit:
            emit({"module": "F", "stage": "input", "table": kind, "processed_rows": index, "input_rows": len(inputs), "input_index": index, "status": fact["record_status"]})

    latest = {kind: {} for kind in KEYS}
    staleness = []
    for kind, groups in candidates.items():
        for key, rows in groups.items():
            newest = max(stamp for stamp, _, _ in rows)
            current = [(row, fact) for stamp, row, fact in rows if stamp == newest]
            for stamp, _, fact in rows:
                if stamp < newest:
                    fact["record_status"] = "superseded"
                    counters["superseded_rows"] += 1
            distinct = {_signature(row, kind) for row, _ in current}
            if len(distinct) > 1:
                for _, fact in current:
                    fact["record_status"] = "conflict"
                    issue(fact, "snapshot_conflict", "Different facts share the latest source timestamp; no value was chosen.", "error")
                row = {**dict(zip(KEYS[kind], key)), "snapshot_status": "conflict", "conflict_count": len(current), "stock": None} if kind == "inventory" else {**dict(zip(KEYS[kind], key)), "snapshot_status": "conflict", "conflict_count": len(current)}
            else:
                row = {**current[0][0], "snapshot_status": "current"}
                for _, fact in current[1:]:
                    fact["record_status"] = "duplicate"
                    counters["duplicate_rows"] += 1
            latest[kind][key] = row
            age = Decimal(str((now - newest).total_seconds())) / Decimal(3600)
            stale = age > stale_after
            if age < 0:
                issue(current[0][1], "future_source_time", "Source timestamp is later than detection time; freshness is unknown.", "error")
            elif stale:
                issue(current[0][1], "stale_source", "Latest supplied export exceeds stale_after_hours; refresh its source.")
            staleness.append({"table": kind, "key": list(key), "source_timestamp": newest.isoformat(), "checked_at": now.isoformat(), "age_hours": _decimal_text(age) if age >= 0 else None, "stale": stale if age >= 0 else None, "snapshot_status": row["snapshot_status"]})

    after_sales = []
    for key, row in latest["cases"].items():
        if row["snapshot_status"] == "conflict":
            after_sales.append({**row, "reply_status": "unknown_conflict", "sla_overdue": None, "order_status": None, "stock": None})
            continue
        fact = next(f for _, candidate, f in candidates["cases"][key] if _signature(candidate, "cases") == _signature(row, "cases"))
        received = _time(row["received_at"])
        replied = _time(row["replied_at"]) if row.get("replied_at") else None
        valid_reply = bool(replied and _present(row.get("sent_evidence")))
        if replied and not _present(row.get("sent_evidence")):
            issue(fact, "reply_evidence_missing", "replied_at alone does not establish a sent reply; supply source send evidence.")
        if _present(row.get("sent_evidence")) and not replied:
            issue(fact, "reply_time_missing", "Send evidence needs a source replied_at timestamp.")
        if replied and (replied < received or replied > now):
            valid_reply = False
            issue(fact, "invalid_reply_time", "Reply timestamp falls before receipt or after detection time.", "error")
        elapsed = Decimal(str(((replied if valid_reply else now) - received).total_seconds())) / Decimal(3600)
        if received > now:
            issue(fact, "future_received_time", "Case receipt is later than detection time; SLA is unknown.", "error")
        prefix = (row["platform"], row["shop_id"])
        orders = [item for okey, item in latest["orders"].items() if okey[:3] == (*prefix, _text(row.get("order_id"))) and (_text(row.get("sku")) == _text(item.get("sku")) or not _text(row.get("sku")))]
        order_statuses = sorted({_text(item.get("status")) for item in orders if item["snapshot_status"] == "current"})
        stock = latest["inventory"].get((*prefix, _text(row.get("sku"))))
        if not orders:
            issue(fact, "order_not_found", "No matching order exists in the supplied platform/shop export.")
        if not stock:
            issue(fact, "inventory_not_found", "No matching inventory exists in the supplied platform/shop export.")
        after_sales.append({**row, "reply_status": "replied" if valid_reply else ("unverified_reply" if replied or _present(row.get("sent_evidence")) else "unreplied"), "reply_verified": valid_reply, "local_status": row.get("local_status"), "draft": row.get("draft"), "elapsed_hours": _decimal_text(elapsed) if elapsed >= 0 else None, "sla_overdue": elapsed > sla and not valid_reply if received <= now else None, "reply_sla_breached": elapsed > sla if valid_reply else None, "order_status": ", ".join(order_statuses) if order_statuses else None, "matched_order_lines": len(orders), "stock": stock.get("stock") if stock and stock["snapshot_status"] == "current" else None, "checked_at": now.isoformat()})

    faq = []
    for (platform, shop, normalized), rows in questions.items():
        confirmed = []
        for row, fact in rows:
            answer, source = _text(row.get("answer")), _text(row.get("source"))
            if answer and not source:
                issue(fact, "answer_source_missing", "An answer without a confirmed policy/source reference stays unverified.")
            if answer and source and {"answer": answer, "source": source} not in confirmed:
                confirmed.append({"answer": answer, "source": source})
        answers = {item["answer"] for item in confirmed}
        faq.append({"platform": platform, "shop_id": shop, "normalized_question": normalized, "question": rows[0][0]["question"], "count": len(rows), "confirmed_answers": confirmed, "answer_status": "conflict" if len(answers) > 1 else ("confirmed" if answers else "pending"), "next_action": "核对来源中相互冲突的答案" if len(answers) > 1 else ("使用已核对答案前确认政策仍有效" if answers else "待补：核对店铺政策与答案出处"), "sources": [{k: v for k, v in row.items() if k.startswith("source_") or k == "source"} for row, _ in rows]})
    after_sales.sort(key=lambda row: (row.get("sla_overdue") is not True, _text(row.get("received_at")), _text(row.get("case_id"))))
    tables = {"after_sales": after_sales, "orders": list(latest["orders"].values()), "inventory": list(latest["inventory"].values()), "faq": faq, "staleness": staleness, "source_rows": facts}
    return {"summary": {"input_rows": len(inputs), "processed_rows": len(inputs), "issue_rows": len({item["input_index"] for item in issues}), "issue_count": len(issues), "after_sales_cases": len(after_sales), "overdue_cases": sum(row.get("sla_overdue") is True for row in after_sales), "verified_replies": sum(row.get("reply_verified") is True for row in after_sales), **counters}, "tables": tables, "issues": issues}
