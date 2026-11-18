"""Local template drafts and host-generated asset registration; no provider API calls."""
from __future__ import annotations

import base64
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TYPES = {'main_image': '.png', 'graphic': '.png', 'detail': '.html', 'video': '.mp4'}
RIGHTS = {'original', 'licensed', 'authorized', 'public_domain'}
PALETTES = {
    'minimal': [('white', '#122e3b', '#0e7490', '#edf5f6'),
                ('#f2f6fa', '#182f43', '#3157a4', '#dde8f7')],
    'warm': [('#fff0df', '#663b28', '#bd532b', '#f7d7b4'),
             ('#fff6e6', '#573626', '#9a5839', '#efd2ae')],
}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def _save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def _load(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('不支持的素材manifest')
    return data


def _local(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('manifest素材路径必须位于运行目录内')
    resolved = (root / path).resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError('manifest素材路径越界')
    return resolved


def _input_path(value, job_dir):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else Path(job_dir) / path).resolve()


def _rights(value):
    if value is None:
        return {'status': 'unknown', 'evidence': ''}
    if not isinstance(value, dict):
        raise ValueError('rights必须包含status和evidence的对象')
    return {'status': str(value.get('status', 'unknown')).strip().lower(),
            'evidence': str(value.get('evidence', '') or '').strip()}


def _rights_ok(value):
    return isinstance(value, dict) and value.get('status') in RIGHTS and bool(str(value.get('evidence', '')).strip())


def _identity(product):
    return tuple(str(product.get(field, '')).strip() for field in ('platform', 'shop_id', 'sku'))


def _product(raw):
    if not isinstance(raw, dict):
        raise ValueError('products每项必须是对象')
    result = {key: str(raw.get(key, '') or '').strip() for key in ('platform', 'shop_id', 'sku', 'name', 'spec')}
    for key, value in result.items():
        if not value or len(value) > 300:
            raise ValueError('商品字段缺失或超过300字符: ' + key)
    value = raw.get('price')
    try:
        price = Decimal(str(value))
        if isinstance(value, bool) or not price.is_finite() or price <= 0 or len(str(value)) > 30:
            raise ValueError('商品price须为正有限金额')
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('商品price须为正有限金额') from exc
    result['price'] = format(price, 'f')
    points = raw.get('selling_points', [])
    if isinstance(points, str):
        points = [points]
    if not isinstance(points, list) or len(points) > 12 or any(not isinstance(x, str) or len(x) > 300 for x in points):
        raise ValueError('selling_points须为最多12项、每项300字符的文字列表')
    result['selling_points'] = [x.strip() for x in points if x.strip()]
    result['rights'] = _rights(raw.get('rights'))
    return result


def _ffmpeg(value=None):
    found = str(value) if value else shutil.which('ffmpeg')
    if not found:
        raise ValueError('MP4模板需要FFmpeg；安装后加入PATH或用ffmpeg指定真实可执行文件')
    if Path(found).suffix.lower() in {'.cmd', '.bat', '.ps1'}:
        raise ValueError('FFmpeg是wrapper；请使用真实ffmpeg.exe或本机可执行文件路径，不能执行脚本wrapper')
    resolved = shutil.which(found) or (str(Path(found).resolve()) if Path(found).is_file() else None)
    if not resolved:
        raise ValueError('FFmpeg可执行文件不存在，请提供真实exe路径')
    return resolved


def _font_path(supplied=None):
    if supplied:
        path = Path(supplied).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in {'.ttf', '.ttc', '.otf'}:
            raise ValueError('font须为存在的TTF/TTC/OTF字体')
        return path
    roots = []
    if os.environ.get('SystemRoot'):
        roots.append(Path(os.environ['SystemRoot']) / 'Fonts')
    if os.environ.get('LOCALAPPDATA'):
        roots.append(Path(os.environ['LOCALAPPDATA']) / 'Microsoft' / 'Windows' / 'Fonts')
    if sys.platform == 'darwin':
        roots.extend([Path('/System/Library/Fonts'), Path('/Library/Fonts')])
    elif sys.platform != 'win32':
        roots.extend([Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.local/share/fonts'])
    files = [p for root in roots if root.is_dir() for p in root.rglob('*')
             if p.is_file() and p.suffix.lower() in {'.ttf', '.ttc', '.otf'}]
    names = ('msyh', 'simhei', 'simsun', 'notosanscjk', 'notosanssc', 'pingfang', 'heiti', 'wenquanyi')
    for name in names:
        found = next((p for p in files if name in p.stem.lower().replace('-', '')), None)
        if found:
            return found
    raise ValueError('未发现中文字体，请通过font提供有使用权的TTF/TTC/OTF字体')


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as exc:
        raise ValueError('PNG模板需要Pillow；请安装Pillow或使用import_generated登记文件') from exc
    return Image, ImageDraw, ImageFont, ImageOps


def _validate_image(path):
    Image, _, _, _ = _pillow()
    try:
        with Image.open(path) as picture:
            picture.verify()
        # verify() checks structure and invalidates its decoder. Reopen and decode
        # pixels as well: a truncated JPEG can have a valid header but unusable data.
        with Image.open(path) as picture:
            picture.load()
    except (OSError, ValueError, SyntaxError) as exc:
        raise ValueError('图片无法完整解码: ' + str(exc)) from exc


def _snapshot_image(raw, product, root, job_dir):
    if not raw.get('image'):
        return
    path = _input_path(raw['image'], job_dir)
    if not path.is_file():
        raise ValueError('商品image文件不存在: ' + str(raw['image']))
    _validate_image(path)
    fingerprint = _sha256(path)
    suffix = path.suffix.lower() if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'} else '.image'
    relative = 'sources/' + fingerprint + suffix
    destination = _local(root, relative)
    destination.parent.mkdir(exist_ok=True)
    if not destination.exists():
        shutil.copyfile(path, destination)
    product['image'] = relative
    product['image_sha256'] = fingerprint


def _wrapped(draw, text, font, width):
    lines, current = [], ''
    for char in str(text):
        if char == '\n':
            lines.append(current)
            current = ''
        elif current and draw.textlength(current + char, font=font) > width:
            lines.append(current)
            current = char
        else:
            current += char
    return lines + ([current] if current else [])


def _draw_png(product, kind, style, version, destination, root, font_path):
    Image, ImageDraw, ImageFont, ImageOps = _pillow()
    w, h = (720, 720) if kind == 'main_image' else (720, 980)
    bg, ink, accent, panel = PALETTES[style][(version - 1) % 2]
    picture = Image.new('RGB', (w, h), bg)
    draw = ImageDraw.Draw(picture)
    font = lambda size: ImageFont.truetype(str(font_path), size)
    text_font, small_font = font(24), font(17)
    left = 48 + ((version - 1) * 11) % 32
    if style == 'warm':
        draw.rounded_rectangle((20, 20, w - 20, h - 20), radius=44, outline=accent, width=3)
        draw.ellipse((w - 160, -50, w + 60, 170), fill=panel)
    else:
        draw.rectangle((0, 0, w, 14), fill=accent)
    draw.text((left, 38), '商品资料 · 模板初稿', fill=accent, font=small_font)
    y = 85 + ((version - 1) * 7) % 42
    # Fit complete source facts, without silently truncating or adding sales claims.
    for title_size in (38, 32, 26, 21, 17, 14, 12):
        title_font = font(title_size)
        title_lines = _wrapped(draw, product['name'], title_font, w - left - 45)
        if len(title_lines) * (title_size + 9) <= 150:
            break
    for title in title_lines:
        draw.text((left, y), title, fill=ink, font=title_font)
        y += title_size + 9
    photo_top = max(175, y + 12)
    photo_bottom = min(photo_top + (250 if kind == 'main_image' else 350), h - 230)
    draw.rounded_rectangle((left, photo_top, w - left, photo_bottom), radius=24 if style == 'warm' else 3, fill=panel)
    if product.get('image'):
        with Image.open(_local(root, product['image'])) as source:
            source = ImageOps.exif_transpose(source).convert('RGBA')
            source.thumbnail((w - 2 * left - 32, max(32, photo_bottom - photo_top - 24)))
            picture.paste(source, ((w - source.width) // 2, photo_top + (photo_bottom - photo_top - source.height) // 2), source)
    else:
        draw.text((left + 22, photo_top + 25), '待提供商品实拍图', fill=ink, font=text_font)
        draw.text((left + 22, photo_top + 68), '此区域为排版占位', fill=ink, font=small_font)
    y = photo_bottom + 22
    lines = [product['spec'], '¥ ' + product['price']]
    if kind == 'graphic':
        lines += product['selling_points']
    # Longer provided facts are kept in HTML/snapshot. Adapt PNG text font to fit.
    for size in (24, 21, 18, 15, 12):
        chosen = font(size)
        wrapped = [(line, line.startswith('¥ ')) for fact in lines for line in _wrapped(draw, fact, chosen, w - 2 * left)]
        if y + len(wrapped) * (size + 9) <= h - 55:
            break
    for line, is_price in wrapped:
        if y + size + 9 > h - 55:
            draw.text((left, h - 85), '完整资料见详情页', fill=accent, font=small_font)
            break
        draw.text((left, y), line, fill=accent if is_price else ink, font=chosen)
        y += size + 9
    draw.text((left, h - 58), f'模板初稿  {style}  v{version:02d} · 请审核后使用', fill=accent, font=small_font)
    picture.save(destination, format='PNG')


def _detail(product, style, version, destination, root):
    bg, ink, accent, panel = PALETTES[style][(version - 1) % 2]
    photo = ''
    if product.get('image'):
        # Embed source image so exporting only the chosen detail remains usable.
        Image, _, _, _ = _pillow()
        import io
        stream = io.BytesIO()
        with Image.open(_local(root, product['image'])) as image:
            image.convert('RGB').save(stream, format='JPEG', quality=88)
        photo = '<img alt="商品来源图" src="data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode('ascii') + '">'
    facts = [product['spec']] + product['selling_points']
    if version % 2 == 0:
        facts = list(reversed(facts))
    escaped = lambda value: html.escape(str(value), quote=True)
    text = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + escaped(product['name']) + '</title><style>body{font:18px system-ui;max-width:860px;margin:40px auto;padding:'
            + str(24 + (version - 1) * 3 % 24) + 'px;'
            f'background:{bg};color:{ink}' + '}article{padding:32px;border:2px solid ' + accent + ';border-radius:'
            + ('28px' if style == 'warm' else '3px') + '}img{width:100%;max-height:480px;object-fit:contain;background:' + panel + '}'
            + 'strong{color:' + accent + ';font-size:32px}li{margin:16px 0}</style><article><p>商品资料 · 模板初稿</p><h1>'
            + escaped(product['name']) + '</h1>' + photo + '<strong>¥ ' + escaped(product['price'])
            + '</strong><ul>' + ''.join('<li>' + escaped(fact) + '</li>' for fact in facts)
            + '</ul><p>SKU: ' + escaped(product['sku']) + '</p><footer>模板初稿 · ' + escaped(style)
            + ' · v' + str(version) + ' · 仅使用输入商品资料，请审核后使用</footer></article></html>')
    Path(destination).write_text(text, encoding='utf-8')


def _video(product, style, version, destination, root, font_path, ffmpeg, duration):
    still = destination.with_suffix('.frame.png')
    _draw_png(product, 'main_image', style, version, still, root, font_path)
    try:
        command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                   '-loop', '1', '-framerate', '12', '-i', str(still), '-t', str(duration),
                   '-vf', 'scale=640:640,fade=t=in:st=0:d=0.25', '-an', '-c:v', 'libx264',
                   '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)]
        process = subprocess.run(command, capture_output=True, timeout=120, shell=False)
        if process.returncode or not destination.is_file() or not destination.stat().st_size:
            detail = process.stderr.decode('utf-8', errors='replace')[-1500:]
            raise ValueError('FFmpeg生成失败: ' + detail)
    finally:
        if still.is_file():
            still.unlink()


def _make_item(root, product, kind, style, version, font_path, ffmpeg, duration, previous=None):
    key = _json_hash(list(_identity(product)))[:20]
    item_id = f'{key}-{kind}-v{version:03d}'
    relative = f'assets/{key}/{kind}-v{version:03d}{TYPES[kind]}'
    destination = _local(root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('素材版本文件已存在，不能覆盖: ' + relative)
    if kind in {'main_image', 'graphic'}:
        _draw_png(product, kind, style, version, destination, root, font_path)
    elif kind == 'detail':
        _detail(product, style, version, destination, root)
    else:
        _video(product, style, version, destination, root, font_path, ffmpeg, duration)
    source = {'sha256': _json_hash(product), 'rights': copy.deepcopy(product['rights']),
              'evidence': product['rights']['evidence'], 'inputs': []}
    if product.get('image'):
        source['inputs'].append({'path': product['image'], 'sha256': product['image_sha256'],
                                 'rights': copy.deepcopy(product['rights'])})
    item = {'id': item_id, 'product': {k: product[k] for k in ('platform', 'shop_id', 'sku', 'name')},
            'type': kind, 'style': style, 'version': version, 'path': relative,
            'sha256': _sha256(destination), 'source': source, 'rights': copy.deepcopy(product['rights']),
            'selected': False, 'status': 'draft',
            'generation': {'mode': 'template', 'provider': 'local-template', 'job_id': '', 'duration': duration if kind == 'video' else None}}
    if previous:
        item['previous_id'] = previous
    return item


def _decode_video(path, ffmpeg):
    process = subprocess.run([_ffmpeg(ffmpeg), '-v', 'error', '-nostdin', '-i', str(path),
                              '-map', '0:v:0', '-f', 'null', '-'],
                             capture_output=True, timeout=120, shell=False)
    if process.returncode:
        raise ValueError('宿主视频无法解码播放: ' + process.stderr.decode('utf-8', errors='replace')[-1000:])


def _import_asset(raw, products, root, job_dir, style, previous_items, ffmpeg=None, copy_file=True):
    if not isinstance(raw, dict):
        raise ValueError('generated每项必须是对象')
    identity = _identity(raw)
    product = next((p for p in products if _identity(p) == identity), None)
    if not product:
        raise ValueError('generated必须匹配唯一platform/shop_id/sku商品')
    kind = raw.get('type')
    if kind not in TYPES or not str(raw.get('provider', '')).strip() or not str(raw.get('job_id', '')).strip():
        raise ValueError('generated需要有效type、provider、job_id')
    path = _input_path(raw.get('path', ''), job_dir)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('宿主生成文件不存在或为空')
    suffix = path.suffix.lower()
    if kind in {'main_image', 'graphic'}:
        if suffix not in {'.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('生成图片仅支持PNG/JPG/WebP')
        _validate_image(path)
    elif suffix != TYPES[kind]:
        raise ValueError('生成文件类型与type不符')
    if kind == 'video':
        _decode_video(path, ffmpeg)
    input_rights = raw.get('input_rights', [])
    if not isinstance(input_rights, list):
        raise ValueError('input_rights必须为列表')
    # Always include original product input rights; a generator license does not license its inputs.
    input_rights = [copy.deepcopy(product['rights'])] + [_rights(r) for r in input_rights]
    rights = _rights(raw.get('rights'))
    version = 1 + max((i['version'] for i in previous_items if _identity(i['product']) == identity and i['type'] == kind), default=0)
    key = _json_hash(list(identity))[:20]
    relative = f'assets/{key}/{kind}-v{version:03d}{suffix}'
    destination = _local(root, relative)
    if destination.exists():
        raise ValueError('导入素材路径已存在，不能覆盖')
    fingerprint = _sha256(path)
    if any(_identity(i['product']) == identity and i['type'] == kind and i['sha256'] == fingerprint for i in previous_items):
        raise ValueError('生成文件与已有版本相同，重做必须产生真实变化')
    if copy_file:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    inputs = []
    if product.get('image'):
        inputs.append({'path': product['image'], 'sha256': product['image_sha256'],
                       'rights': copy.deepcopy(product['rights'])})
    return {'id': f'{key}-{kind}-v{version:03d}', 'product': {k: product[k] for k in ('platform', 'shop_id', 'sku', 'name')},
            'type': kind, 'style': style, 'version': version, 'path': relative, 'sha256': fingerprint,
            'source': {'sha256': fingerprint, 'product_sha256': _json_hash(product), 'rights': rights, 'evidence': rights['evidence'],
                       'input_rights': input_rights, 'inputs': inputs},
            'rights': rights, 'selected': False, 'status': 'draft',
            'generation': {'mode': 'import_generated', 'provider': str(raw['provider']), 'job_id': str(raw['job_id'])}}


def run(job: dict, out: Path, emit=None) -> dict:
    """Create a fresh media manifest. Existing manifests require append_generated()."""
    mode = job.get('mode')
    if mode not in {'template', 'import_generated'}:
        raise ValueError('mode须显式选择template或import_generated')
    style = job.get('style', 'minimal')
    if style not in PALETTES:
        raise ValueError('style须为minimal或warm')
    duration = job.get('duration', 2)
    if isinstance(duration, bool) or not isinstance(duration, int) or duration not in range(2, 16):
        raise ValueError('duration默认2秒演示；自定义须为3至15的整数秒')
    raw_products = job.get('products', [])
    if not isinstance(raw_products, list) or len(raw_products) > 1000:
        raise ValueError('products必须为最多1000项的对象列表')
    out = Path(out).resolve()
    if (out / 'manifest.json').exists():
        raise ValueError('manifest已存在；请使用新运行目录，导入重做结果可用append_generated')
    products = [_product(p) for p in raw_products]
    if len({_identity(p) for p in products}) != len(products):
        raise ValueError('同平台店铺SKU重复，请先去重')
    ffmpeg = _ffmpeg(job.get('ffmpeg')) if mode == 'template' and products else None
    font = _font_path(job.get('font')) if mode == 'template' and products else None
    if mode == 'template' and products:
        _pillow()
    out.mkdir(parents=True, exist_ok=True)
    for raw, product in zip(raw_products, products):
        _snapshot_image(raw, product, out, job.get('_job_dir', '.'))
    manifest = {'schema_version': 1, 'module': 'E', 'mode': mode, 'style': style,
                'label': '本地模板初稿' if mode == 'template' else '宿主生成文件',
                'options': {'duration': duration}, 'products': products, 'items': []}
    if mode == 'template':
        for index, product in enumerate(products, 1):
            for kind in TYPES:
                manifest['items'].append(_make_item(out, product, kind, style, 1, font, ffmpeg, duration))
            if emit:
                emit({'stage': 'media_product', 'processed_rows': index, 'sku': product['sku'], 'shop_id': product['shop_id']})
    else:
        generated = job.get('generated', [])
        if not isinstance(generated, list) or not generated:
            raise ValueError('import_generated需要宿主收集真实生成文件到generated列表')
        for raw in generated:
            manifest['items'].append(_import_asset(raw, products, out, job.get('_job_dir', '.'), style, manifest['items'],
                                                  ffmpeg=job.get('ffmpeg'), copy_file=False))
        for raw, item in zip(generated, manifest['items']):
            target = _local(out, item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_input_path(raw['path'], job.get('_job_dir', '.')), target)
    _save(out / 'manifest.json', manifest)
    issues = [{'sku': p['sku'], 'shop_id': p['shop_id'], 'code': 'rights_unverified',
               'message': '可预览；选中导出前需提供来源权利和依据'} for p in products if not _rights_ok(p['rights'])]
    if not products:
        issues.append({'code': 'no_products', 'message': '未提供商品，未生成素材'})
    processed = len({_identity(i['product']) for i in manifest['items']})
    return {'summary': {'input_rows': len(products), 'processed_rows': processed,
                        'issue_rows': len(issues), 'asset_count': len(manifest['items']), 'mode': mode},
            'tables': {'media_items': manifest['items']}, 'issues': issues,
            'artifacts': {'manifest': str(out / 'manifest.json')}}


def select_item(manifest_path, item_id, selected: bool) -> dict:
    if not isinstance(selected, bool):
        raise ValueError('selected必须为布尔值')
    manifest = _load(manifest_path)
    item = next((i for i in manifest['items'] if i['id'] == item_id), None)
    if not item:
        raise ValueError('素材id不存在')
    item['selected'] = selected
    item['status'] = 'selected' if selected else 'draft'
    _save(manifest_path, manifest)
    return copy.deepcopy(item)


def redo_item(manifest_path, item_id, emit=None, *, ffmpeg=None, font=None) -> dict:
    """Create changed local template layout; host-generated redo must be generated by host."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _load(manifest_path)
    old = next((i for i in manifest['items'] if i['id'] == item_id), None)
    if not old:
        raise ValueError('素材id不存在')
    if old.get('generation', {}).get('mode') != 'template':
        raise ValueError('import_generated素材须由宿主工具真正重新生成，再用append_generated登记新文件')
    product = next((p for p in manifest['products'] if _identity(p) == _identity(old['product'])), None)
    if not product:
        raise ValueError('缺少商品输入快照，无法重做')
    root = manifest_path.parent
    for source in old['source'].get('inputs', []):
        path = _local(root, source['path'])
        if not path.is_file() or _sha256(path) != source['sha256']:
            raise ValueError('来源图片缺失或校验失败，不能重做')
    version = 1 + max(i['version'] for i in manifest['items'] if _identity(i['product']) == _identity(old['product']) and i['type'] == old['type'])
    tool = _ffmpeg(ffmpeg) if old['type'] == 'video' else None
    font_path = _font_path(font) if old['type'] != 'detail' else None
    item = _make_item(root, product, old['type'], old['style'], version, font_path, tool,
                      manifest['options']['duration'], previous=old['id'])
    manifest['items'].append(item)
    _save(manifest_path, manifest)
    if emit:
        emit({'stage': 'media_redone', 'id': item['id'], 'previous_id': old['id']})
    return item


def append_generated(manifest_path, generated: list, job_dir=None, *, ffmpeg=None) -> dict:
    """Register actual replacements; preserve prior choices and reject byte-identical redo."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _load(manifest_path)
    if not isinstance(generated, list) or not generated:
        raise ValueError('generated须为非空列表')
    base, root = job_dir or manifest_path.parent, manifest_path.parent
    additions = []
    # Validate every input before writing any new media file.
    for raw in generated:
        item = _import_asset(raw, manifest['products'], root, base, manifest['style'],
                             manifest['items'], ffmpeg=ffmpeg, copy_file=False)
        manifest['items'].append(item)
        additions.append(item)
    for raw, item in zip(generated, additions):
        target = _local(root, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_input_path(raw['path'], base), target)
    _save(manifest_path, manifest)
    return {'items': additions, 'registered_count': len(additions)}


def export_selected(manifest_path, destination) -> dict:
    """Validate all selected rights and bytes before copying only selected deliverables."""
    manifest_path = Path(manifest_path).resolve()
    manifest = _load(manifest_path)
    root, destination = manifest_path.parent, Path(destination).expanduser().resolve()
    selected = [i for i in manifest['items'] if i.get('selected') is True]
    if not selected:
        raise ValueError('未选中素材')
    if destination == root or root in destination.parents or destination in root.parents:
        raise ValueError('导出目录须与运行目录分开')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('导出目录必须为空，防止混入未选素材')
    checked = []
    for item in selected:
        source = item.get('source', {})
        rights_records = [item.get('rights'), source.get('rights')]
        rights_records.extend(source.get('input_rights', []))
        rights_records.extend(s.get('rights') for s in source.get('inputs', []))
        if any(not _rights_ok(right) for right in rights_records):
            raise ValueError('选中素材权利rights或授权依据未核实: ' + item['id'])
        path = _local(root, item['path'])
        if not path.is_file():
            raise ValueError('选中素材文件不存在/缺失: ' + item['id'])
        if _sha256(path) != item.get('sha256'):
            raise ValueError('选中素材文件被修改，hash校验失败: ' + item['id'])
        checked.append((item, path))
    destination.mkdir(parents=True, exist_ok=True)
    for item, path in checked:
        target = _local(destination, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    _save(destination / 'sources.json', {'schema_version': 1, 'items': copy.deepcopy(selected),
                                        'exported_count': len(selected)})
    return {'exported_count': len(selected), 'destination': str(destination),
            'sources': str(destination / 'sources.json')}
