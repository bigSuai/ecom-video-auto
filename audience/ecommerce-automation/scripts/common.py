"""Portable job input/output. No account, browser, database or network dependency."""
import copy
import csv
import hashlib
import html
import io
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000
MAX_COLUMNS = 100


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reject_constant(value):
    raise ValueError('JSON不接受非有限数字: ' + value)


def load_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('JSON超过10MB')
    def unique_object(pairs):
        result = {}
        for key, val in pairs:
            if key in result:
                raise ValueError('JSON字段重复: ' + key)
            result[key] = val
        return result
    return json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant, object_pairs_hook=unique_object)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text(value), encoding='utf-8')


def _rows_valid(rows):
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError('输入必须为不超过10000行的对象列表')
    if any(not isinstance(row, dict) or len(row) > MAX_COLUMNS for row in rows):
        raise ValueError('每行必须是最多100列的对象')
    return rows


def read_rows(path, sheet=None):
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('输入超过10MB，请拆分')
    suffix = path.suffix.lower()
    if suffix == '.json':
        rows = load_json(path)
    elif suffix == '.csv':
        text = None
        for enc in ('utf-8-sig', 'gb18030'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                pass
        if text is None or '\x00' in text:
            raise ValueError('CSV编码或内容无效')
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        headers = next(reader, [])
        if not headers or any(not x.strip() for x in headers) or len(set(headers)) != len(headers):
            raise ValueError('CSV表头不能缺失、为空或重复')
        rows = []
        previous_line = reader.line_num
        for values in reader:
            source_row = previous_line + 1
            previous_line = reader.line_num
            if not any(values):
                continue
            if len(values) != len(headers):
                raise ValueError('CSV列数与表头不一致')
            rows.append({**dict(zip(headers, values)), '_source_row': source_row})
            if len(rows) > MAX_ROWS:
                raise ValueError('超过10000行')
    elif suffix == '.xlsx':
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError('XLSX需要openpyxl；可改用CSV/JSON') from exc
        import zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError('XLSX解压体积超过100MB')
        book = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
        try:
            visible = [ws for ws in book.worksheets if ws.sheet_state == 'visible']
            if not visible:
                raise ValueError('没有可见工作表')
            ws = book[sheet] if sheet else visible[0]
            if ws not in visible:
                raise ValueError('不能读取隐藏工作表')
            iterator = ws.iter_rows()
            first = next(iterator, ())
            headers = [str(c.value or '') for c in first]
            if not headers or len(headers) > MAX_COLUMNS or any(not x for x in headers) or len(set(headers)) != len(headers):
                raise ValueError('XLSX表头为空、重复或超过100列')
            rows = []
            for n, cells in enumerate(iterator, 2):
                if n > 50000:
                    raise ValueError('工作表扫描范围超过50000行')
                if any(c.data_type == 'f' for c in cells):
                    raise ValueError('XLSX含公式，请核对结果后粘贴为确定值')
                values = [c.value.isoformat() if isinstance(c.value, (date, datetime)) else c.value for c in cells]
                if not any(v is not None and str(v).strip() for v in values):
                    continue
                if len(values) > len(headers) and any(v is not None for v in values[len(headers):]):
                    raise ValueError('XLSX有未命名数据列')
                row = dict(zip(headers, values))
                row['_excel_numeric_columns'] = [headers[i] for i, c in enumerate(cells[:len(headers)]) if c.data_type == 'n' and c.value is not None]
                row['_source_row'] = n
                rows.append(row)
                if len(rows) > MAX_ROWS:
                    raise ValueError('超过10000行')
        finally:
            book.close()
    else:
        raise ValueError('仅支持CSV、JSON、XLSX')
    return _rows_valid(rows)


def expand_job(job, base, table_names):
    if not isinstance(job, dict):
        raise ValueError('job必须为对象')
    result = copy.deepcopy(job)
    sources = []
    for name in table_names:
        value = job.get(name, [])
        mapping, defaults, scales = {}, {}, {}
        if isinstance(value, dict):
            if 'file' not in value:
                raise ValueError(name + '需要file或对象列表')
            path = Path(value['file']).expanduser()
            path = path if path.is_absolute() else Path(base) / path
            rows = read_rows(path, value.get('sheet'))
            fingerprint, source = digest(path.read_bytes()), str(path.resolve())
            mapping = value.get('mapping', {})
            defaults, scales = value.get('defaults', {}), value.get('scales', {})
            if not all(isinstance(x, dict) for x in (mapping, defaults, scales)):
                raise ValueError('mapping/defaults/scales必须为对象')
            if len(set(mapping.values())) != len(mapping):
                raise ValueError('同一原始列不能映射多个字段')
            sources.append({'table': name, 'file': source, 'sha256': fingerprint,
                            'mapping': mapping, 'defaults': defaults, 'scales': scales})
        else:
            rows = _rows_valid(copy.deepcopy(value))
            fingerprint = digest(json_text(rows).encode('utf-8'))
            source = str(Path(base).resolve()) + ' [inline:' + name + ']'
        expanded = []
        for i, raw in enumerate(rows, 2):
            row = copy.deepcopy(raw)
            for canonical, original in mapping.items():
                if original not in raw:
                    raise ValueError(f'{name}映射列不存在: {original}')
                if canonical != original and canonical in raw and raw[canonical] != raw[original]:
                    raise ValueError('映射覆盖不同现有值: ' + canonical)
                row[canonical] = raw[original]
            for key, val in defaults.items():
                if key in row and row[key] not in (None, '') and str(row[key]) != str(val):
                    raise ValueError('默认上下文与行值冲突: ' + key)
                if row.get(key) in (None, ''):
                    row[key] = val
            for key, factor in scales.items():
                if row.get(key) in (None, ''):
                    continue
                try:
                    with localcontext() as ctx:
                        ctx.prec = 50
                        number, scale = Decimal(str(row[key])), Decimal(str(factor))
                        if not number.is_finite() or not scale.is_finite() or scale <= 0 or len(str(row[key])) > 40:
                            raise ValueError('非法换算值')
                        row[key] = format(number * scale, 'f')
                except InvalidOperation as exc:
                    raise ValueError('不能换算字段: ' + key) from exc
            numeric = raw.get('_excel_numeric_columns', [])
            row['numeric_identifier_warning'] = bool(row.get('numeric_identifier_warning')) or any(mapping.get(k, k) in numeric for k in ('sku', 'order_id', 'line_id'))
            row.update(source_file=source, source_row=raw.get('_source_row', i), source_hash=fingerprint)
            row.setdefault('data_kind', job.get('data_kind', 'user_provided'))
            row['_raw'] = {k: v for k, v in raw.items() if not k.startswith('_')}
            expanded.append(row)
        result[name] = expanded
    result['_sources'] = sources
    return result


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return str(value)


def csv_safe(value):
    val = _cell(value)
    return "'" + val if val.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else val


def write_outputs(out, result):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tables = result.get('tables', {})
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', str(name)) for name in tables):
        raise ValueError('输出表名称无效')
    save_json(out / 'result.json', result)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>电商自动化执行结果</title><style>body{font:16px system-ui;max-width:1400px;margin:32px auto;padding:16px;background:#f6f8fa;color:#172a3a}table{border-collapse:collapse;background:white}td,th{padding:10px;border:1px solid #ccd6df;text-align:left;max-width:440px;overflow-wrap:anywhere}section{overflow:auto;margin:24px 0}pre{white-space:pre-wrap}h1{font-size:28px}</style>',
             '<h1>电商自动化执行结果</h1><p>此页为静态结果；执行范围与数据性质见运行记录。真实动作仍由智能体按当前任务执行。</p>',
             '<pre>' + html.escape(json_text(result.get('summary', {}))) + '</pre>']
    for name, rows in tables.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError('输出表必须为对象列表: ' + name)
        headers = list(dict.fromkeys(key for row in rows for key in row))
        with (out / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow([csv_safe(h) for h in headers])
            for row in rows:
                values = []
                for key in headers:
                    values.append(csv_safe(row.get(key)))
                writer.writerow(values)
        parts.append('<section><h2>' + html.escape(name) + f'（{len(rows)}）</h2><table><thead><tr>')
        parts.extend('<th>' + html.escape(str(k)) + '</th>' for k in headers)
        parts.append('</tr></thead><tbody>')
        for row in rows[:1000]:
            parts.append('<tr>' + ''.join('<td>' + html.escape(_cell(row.get(k))) + '</td>' for k in headers) + '</tr>')
        parts.append('</tbody></table>')
        if len(rows) > 1000:
            parts.append('<p>此预览显示前1000行，完整数据见CSV/JSON。</p>')
        parts.append('</section>')
    parts.append('<h2>问题与指标定义</h2><pre>' + html.escape(json_text({k: result[k] for k in ('issues', 'metric_definitions') if k in result})) + '</pre></html>')
    (out / 'report.html').write_text(''.join(parts), encoding='utf-8')
