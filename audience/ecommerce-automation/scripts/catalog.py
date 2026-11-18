"""Format-only product normalization and checks, with all source rows retained.

Prices must be positive, have at most two effective decimal places, and be no
greater than 999999999999.99; stock must be an integer in 0..999999999999.
Only numeric fields translate fullwidth digits/punctuation. Identifiers keep
their case, width and leading zeroes. No inventory or missing values are guessed.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import re


MAX_PRICE = Decimal("999999999999.99")
MAX_STOCK = 999999999999
FIELDS = ("name", "sku", "spec", "price", "stock")
NUMERIC_TRANSLATION = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
NUMBER = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?\Z")
PRICE_ERROR = "价格须为正数、最多两位有效小数，且不超过 999999999999.99；不接受非有限值、科学计数文本或未知币种符号。"
STOCK_ERROR = "库存须为 0 至 999999999999 的整数；不接受非有限值或科学计数文本。"


def _json_value(value):
    """Detach evidence and make exceptional Python numeric values readable."""
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, Decimal):
        return str(value)
    # Python itself cannot stringify an unbounded integer under its digit guard.
    if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > 4096:
        return f"<integer with {value.bit_length()} bits>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _text(value):
    if value is None:
        return None
    return (value if isinstance(value, str) else str(_json_value(value))).strip()


def _missing(value):
    return value is None or value == ""


def _formatted_numeric(value, *, price=False, currency=None):
    if not isinstance(value, str):
        return _json_value(value)
    text = value.strip().translate(NUMERIC_TRANSLATION)
    if price and text.startswith(("¥", "￥")):
        if (_text(currency) or "").upper() in ("", "CNY", "RMB", "人民币"):
            text = text[1:].strip()
    return text.replace(",", "") if NUMBER.fullmatch(text) else text


def _numeric_text(value, *, price=False, currency=None):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if abs(value) > MAX_PRICE:
            return None
    text = str(_formatted_numeric(value, price=price, currency=currency)).strip()
    if len(text) > 128:
        return None
    if not NUMBER.fullmatch(text):
        return None
    return text.replace(",", "")


def _number(value, *, price=False, currency=None):
    text = _numeric_text(value, price=price, currency=currency)
    if text is None:
        return None
    try:
        number = Decimal(text)
        if price:
            if not number.is_finite() or not 0 < number <= MAX_PRICE:
                return None
            cents = number.quantize(Decimal("0.01"))
            return format(cents, ".2f") if cents == number else None
        if not number.is_finite() or not 0 <= number <= MAX_STOCK:
            return None
        return int(number) if number == number.to_integral_value() else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def run(job: dict, out: Path, emit=None) -> dict:
    """Check one local job; caller owns input parsing, output files and reporting."""
    if not isinstance(job, dict) or not isinstance(job.get("products"), list):
        raise ValueError("job.products must be a list of product objects")
    products = job["products"]
    if not all(isinstance(row, dict) for row in products):
        raise ValueError("Every product must be an object")
    normalized, changes, issues = [], [], []
    affected_rows = set()
    groups = defaultdict(list)
    valid_prices = {}

    def issue(index, category, field, message):
        row = normalized[index]
        issues.append(dict(category=category, source_row=row["source_row"],
                           sku=row["sku"], field=field, message=message))
        affected_rows.add(index)

    for index, original in enumerate(products):
        raw = _json_value(original)
        row = _json_value(original)
        row["raw"] = raw
        row["source_row"] = _json_value(original.get("source_row", index + 1))
        for field in FIELDS:
            value = original.get(field)
            if field in ("name", "sku", "spec"):
                row[field] = _text(value)
            else:
                row[field] = _formatted_numeric(value, price=field == "price", currency=original.get("currency"))
        normalized.append(row)
        if original.get('numeric_identifier_warning'):
            issue(index, 'numeric_identifier', 'sku', '来源Excel编码为数字类型；前导零或长编码可能已丢失，须对照原始编码核实，不能自动补零。')
        for field in FIELDS:
            if _missing(row[field]):
                issue(index, "missing_required", field, f"缺少必填字段：{field}")
                continue
            if field in ("price", "stock"):
                parsed = _number(original.get(field), price=field == "price", currency=original.get("currency"))
                if parsed is None:
                    issue(index, "invalid_" + field, field, PRICE_ERROR if field == "price" else STOCK_ERROR)
                else:
                    row[field] = parsed
                    if field == "price":
                        valid_prices[index] = parsed
        for field in FIELDS:
            before, after = raw.get(field), row[field]
            if type(before) is not type(after) or before != after:
                changes.append(dict(source_row=row["source_row"], sku=row["sku"],
                                    field=field, before=before, after=after))
        if not _missing(row["sku"]):
            scope = (_text(original.get("platform")) or "", _text(original.get("shop_id")) or "")
            groups[scope + (row["sku"],)].append(index)
        if emit is not None:
            emit(dict(stage="normalized", item=row["sku"], processed=index + 1, total=len(products)))

    for indices in groups.values():
        if len(indices) < 2:
            continue
        conflicting = len({valid_prices[index] for index in indices if index in valid_prices}) > 1
        for index in indices:
            issue(index, "duplicate_sku", "sku", "同一平台及店铺范围内商品编码重复，所有原行均保留。")
            if conflicting:
                issue(index, "conflicting_price", "price", "同一平台及店铺的相同编码存在不同有效价格，需人工核对。")

    categories = sorted({item["category"] for item in issues})
    return dict(summary=dict(input_rows=len(products), processed_rows=len(normalized),
                             issue_rows=len(affected_rows), issue_categories=categories),
                tables=dict(normalized=normalized, changes=changes, issues=issues), issues=issues)
