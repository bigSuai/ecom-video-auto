"""Prepare a listing queue and record browser observations; never controls a browser.

This module uses only the Python standard library and is portable with its skill.
Queue identities are scoped to platform + shop + SKU. External outcomes are facts
recorded by the host after inspecting a real receipt or product page.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile


REQUIRED_FIELDS = ("title", "category", "spec", "price", "stock")
IDENTITY_FIELDS = ("platform", "shop_id", "sku")
RESULT_STATUSES = {"draft", "submitted_review", "on_sale", "rejected", "result_unknown"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _safe(part) for key, part in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(part) for part in value]
    return value


def _canonical(value):
    return json.dumps(_safe(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _number(value):
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise ValueError("not a number")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise ValueError("not a number") from error
    if not number.is_finite():
        raise ValueError("number must be finite")
    return number


def _present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value) if isinstance(value, (dict, list, tuple)) else True


def _equivalent(field, expected, observed):
    if field in ("price", "stock"):
        try:
            return _number(expected) == _number(observed)
        except ValueError:
            return False
    if isinstance(expected, str) and isinstance(observed, str):
        return expected.strip() == observed.strip()
    return _canonical(expected) == _canonical(observed)


def _issue(item_id, row, field, code, message, **details):
    return {"item_id": item_id, "row": row, "field": field, "code": code,
            "severity": "error", "message": message, **details}


def _validate(expected, item_id, row):
    issues = []
    for field in IDENTITY_FIELDS + REQUIRED_FIELDS:
        if not _present(expected.get(field)):
            issues.append(_issue(item_id, row, field, "required", f"缺少必填字段：{field}"))
    for field in ("price", "stock"):
        if not _present(expected.get(field)):
            continue
        try:
            number = _number(expected[field])
            if field == "price" and number <= 0:
                raise ValueError("price must be positive")
            if field == "stock" and (number < 0 or number != number.to_integral_value()):
                raise ValueError("stock must be a non-negative integer")
        except ValueError:
            message = "价格必须为大于0的有限数值" if field == "price" else "库存必须为非负整数"
            issues.append(_issue(item_id, row, field, "invalid_number", message))
    return issues


def _derive(item):
    item["issues"] = deepcopy(item.get("validation_issues", []))
    for field, check in item.get("checks", {}).items():
        if not check.get("matched"):
            item["issues"].append(_issue(item["id"], item["row"], field, "readback_mismatch",
                                         "网页读回值与商品资料不一致", expected=item["expected"].get(field),
                                         observed=check.get("observed")))
    if item["issues"]:
        item["status"] = "blocked"
        return
    result = item.get("last_result", {})
    if result.get("source_fingerprint") == item["source_fingerprint"]:
        item["status"] = result["status"]
        return
    complete = all(item.get("checks", {}).get(field, {}).get("matched") and
                   item["checks"][field].get("evidence", "").strip() for field in REQUIRED_FIELDS)
    item["status"] = "awaiting_confirmation" if complete else "prepared"


def _write(path, queue):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    queue["updated_at"] = _now()
    queue["issues"] = [*queue.get("task_issues", []),
                       *(issue for item in queue["items"] for issue in item["issues"])]
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(_safe(queue), stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        queue = json.load(stream)
    if queue.get("schema_version") != 1 or not isinstance(queue.get("items"), list):
        raise ValueError("unsupported or invalid listing queue; preserve the file and inspect it")
    return queue


def run(job: dict, out: Path, emit=None) -> dict:
    """Validate products and persist preparation, resuming an explicit queue_path.

    The optional queue_path names the durable queue across independently created
    run directories. Otherwise the queue is out/queue.json. Invalid existing JSON
    raises rather than silently discarding observations or draft identifiers.
    """
    if not isinstance(job, dict):
        raise TypeError("job must be an object")
    out = Path(out)
    queue_path = Path(job["queue_path"]).expanduser() if job.get("queue_path") else out / "queue.json"
    queue_path = queue_path.resolve()
    previous = _read(queue_path) if queue_path.exists() else {"items": [], "retired_items": []}
    old_by_id = {item["id"]: item for item in [*previous.get("retired_items", []), *previous["items"]]}
    products = job.get("products", [])
    task_issues = []
    if not isinstance(products, list):
        products = []
        task_issues.append(_issue("", None, "products", "invalid_products", "products必须是商品对象数组"))
    if not products and not task_issues:
        task_issues.append(_issue("", None, "products", "empty_products", "没有商品输入，尚未准备上架队列"))
    identities = []
    for product in products:
        source = product if isinstance(product, dict) else {}
        identity = [str(source[field]).strip() if source.get(field) is not None else ""
                    for field in IDENTITY_FIELDS]
        identities.append(identity)
    identity_counts = Counter(_canonical(identity) for identity in identities)
    seen = Counter()
    items = []
    for row, (product, identity) in enumerate(zip(products, identities), 1):
        expected = _safe(deepcopy(product)) if isinstance(product, dict) else {}
        for field, value in zip(IDENTITY_FIELDS, identity):
            expected[field] = value
        identity_key = _canonical(identity)
        seen[identity_key] += 1
        item_id = "listing-" + _fingerprint(identity)[:20]
        if seen[identity_key] > 1:
            item_id += f"-duplicate-{seen[identity_key]}"
        old = deepcopy(old_by_id.get(item_id, {}))
        # Per-product business identity must survive relocation or edits to other
        # source rows. Whole-file hashes and raw audit values are not editable facts.
        business = {key: value for key, value in expected.items()
                    if not key.startswith(('_', 'source_'))
                    and key not in {'raw', 'data_kind', 'numeric_identifier_warning'}}
        source_fingerprint = _fingerprint(business)
        checks = old.get("checks", {})
        invalidated = old.get("invalidated_checks", [])
        changes = sorted(field for field in set(old.get("expected", {})) | set(expected)
                         if _canonical(old.get("expected", {}).get(field)) != _canonical(expected.get(field)))
        for field in changes:
            if field in checks:
                invalidated.append({"field": field, "check": checks.pop(field), "invalidated_at": _now(),
                                    "reason": "source_changed", "new_expected": expected.get(field)})
        validation = _validate(expected, item_id, row)
        if not isinstance(product, dict):
            validation.append(_issue(item_id, row, "product", "invalid_product", "商品行必须是对象"))
        if identity_counts[identity_key] > 1:
            validation.append(_issue(item_id, row, "sku", "duplicate_identity", "同一平台、店铺、SKU重复，先消除歧义"))
        item = {**old, "id": item_id, "row": row,
                **dict(zip(IDENTITY_FIELDS, identity)), "scope": dict(zip(IDENTITY_FIELDS, identity)),
                "expected": expected, "source_fingerprint": source_fingerprint,
                "required_fields": list(REQUIRED_FIELDS), "checks": checks,
                "invalidated_checks": invalidated, "validation_issues": validation,
                "draft_id": old.get("draft_id", ""), "external_id": old.get("external_id", ""),
                "result_history": old.get("result_history", []), "prepared_at": old.get("prepared_at", _now())}
        if old and old.get("source_fingerprint") != source_fingerprint:
            item.setdefault("source_changes", []).append({"changed_at": _now(), "fields": changes,
                                                           "previous_fingerprint": old.get("source_fingerprint")})
        _derive(item)
        items.append(item)
        if emit:
            emit({"event": "listing_prepared", "processed_rows": row, "input_rows": len(products),
                  "item_id": item_id, "status": item["status"]})
    active_ids = {item["id"] for item in items}
    queue = {"schema_version": 1, "operation": "A", "required_fields": list(REQUIRED_FIELDS),
             "items": items, "task_issues": task_issues,
             "retired_items": [item for key, item in old_by_id.items() if key not in active_ids]}
    _write(queue_path, queue)
    rows = [{"item_id": item["id"], "platform": item["platform"], "shop_id": item["shop_id"],
             "sku": item["sku"], "status": item["status"], "draft_id": item["draft_id"],
             "external_id": item["external_id"],
             "verified_fields": sum(bool(check.get("matched") and check.get("evidence", "").strip())
                                    for field, check in item["checks"].items() if field in REQUIRED_FIELDS),
             "required_fields": len(REQUIRED_FIELDS)} for item in items]
    return {"summary": {"input_rows": len(products), "processed_rows": len(items),
                        "issue_rows": sum(bool(item["issues"]) for item in items)},
            "tables": {"queue": rows, "issues": queue["issues"]}, "issues": queue["issues"],
            "queue_path": str(queue_path)}


def _find(queue, item_id):
    for item in queue["items"]:
        if item["id"] == item_id:
            return item
    raise KeyError(f"active listing item not found: {item_id}")


def record_field(queue_path, item_id, field, observed, evidence="") -> dict:
    """Record a value actually read from the selected product's current page."""
    queue = _read(queue_path)
    item = _find(queue, item_id)
    if field not in item["expected"] or field in IDENTITY_FIELDS:
        raise ValueError("field must be a known editable product field; identity is immutable")
    check = {"observed": _safe(observed), "expected": deepcopy(item["expected"][field]),
             "matched": _equivalent(field, item["expected"][field], observed),
             "checked_at": _now(), "evidence": str(evidence or "").strip(),
             "scope": deepcopy(item["scope"]), "source_fingerprint": item["source_fingerprint"]}
    if field in item["checks"]:
        item.setdefault("check_history", []).append({"field": field, **deepcopy(item["checks"][field])})
    item["checks"][field] = check
    _derive(item)
    _write(queue_path, queue)
    return deepcopy(item)


def record_result(queue_path, item_id, status, external_id, evidence) -> dict:
    """Record an observed external state, never initiate or infer a submission."""
    if status not in RESULT_STATUSES:
        raise ValueError(f"unsupported observed result status: {status}")
    evidence = str(evidence or "").strip()
    external_id = str(external_id or "").strip()
    if not evidence:
        raise ValueError("an observed external outcome requires page/receipt evidence")
    if status != "result_unknown" and not external_id:
        raise ValueError("an observed external outcome requires its actual draft/product id")
    queue = _read(queue_path)
    item = _find(queue, item_id)
    result = {"status": status, "external_id": external_id, "evidence": evidence,
              "recorded_at": _now(), "source_fingerprint": item["source_fingerprint"],
              "scope": deepcopy(item["scope"])}
    item["result_history"].append(result)
    item["last_result"] = result
    if status == "draft":
        item["draft_id"] = external_id
    elif external_id:
        item["external_id"] = external_id
    item["status"] = status
    _write(queue_path, queue)
    return deepcopy(item)
