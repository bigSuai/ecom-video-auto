#!/usr/bin/env python3
"""Portable ecommerce skill runner. Browser/media providers belong to the host agent."""
import argparse
import importlib
import importlib.util
import json
import platform
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

from common import digest, expand_job, json_text, load_json, save_json, utc_now, write_outputs

SKILL_ROOT = Path(__file__).resolve().parents[1]


def registry():
    return load_json(SKILL_ROOT / 'modules.json')


def module_for(name):
    entry = registry()['modules'].get(name.upper())
    if not entry:
        raise ValueError('未知模块: ' + name)
    if not re.fullmatch('[a-z][a-z_0-9]*', entry['entrypoint']):
        raise ValueError('模块入口无效')
    return entry, importlib.import_module(entry['entrypoint'])


def doctor():
    optional = {name: bool(importlib.util.find_spec(name)) for name in ('openpyxl', 'PIL')}
    return {'python': sys.version.split()[0], 'core_ready': sys.version_info >= (3, 10),
            'optional': optional, 'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe'),
            'browser': '由宿主提供浏览器工具；或按references/browser.md检测Kimi桥接',
            'media': 'AI生成使用宿主已授权工具；模板PNG需Pillow，MP4另需FFmpeg',
            'network_or_credentials_used': False}


def run_job(module_name, input_path, output_root, state=None):
    module_name = module_name.upper()
    output_root = Path(output_root).expanduser().resolve()
    if output_root == SKILL_ROOT or SKILL_ROOT in output_root.parents:
        raise ValueError('运行结果请存放在用户任务目录，不写入已安装skill')
    run_id = module_name + '-' + time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + uuid.uuid4().hex[:8]
    out = output_root / run_id
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    record = {'run_id': run_id, 'module': module_name, 'started_at': utc_now(), 'status': 'running',
              'input_file': str(Path(input_path).resolve()), 'output': str(out)}
    save_json(out / 'run.json', record)

    def emit(event):
        item = {**event, 'run_id': run_id, 'at': utc_now()}
        line = json.dumps(item, ensure_ascii=False, allow_nan=False)
        with (out / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')
        print(line, flush=True)

    emit({'stage': 'started'})
    result = None
    try:
        entry, module = module_for(module_name)
        input_path = Path(input_path).resolve()
        record['input_sha256'] = digest(input_path.read_bytes())
        job = expand_job(load_json(input_path), input_path.parent, entry.get('tables', []))
        job['_job_dir'] = str(input_path.parent)
        if job.get('queue_path'):
            durable = Path(job['queue_path']).expanduser()
            job['queue_path'] = str((durable if durable.is_absolute() else input_path.parent / durable).resolve())
        if job.get('state_file'):
            state_path = Path(job['state_file']).expanduser()
            job['state'] = load_json(state_path if state_path.is_absolute() else input_path.parent / state_path)
        if state is not None:
            job['state'] = state
        record['data_kind'] = job.get('data_kind', 'user_provided')
        record['input_sources'] = job.get('_sources', [])
        # Only installed modules are executable; job values remain data.
        process_start = time.perf_counter()
        result = module.run(job, out, emit)
        record['processing_seconds'] = round(time.perf_counter() - process_start, 6)
        result['run_id'] = run_id
        result['data_kind'] = record['data_kind']
        result['module'] = module_name
        result['source_audit'] = record['input_sources']
        write_outputs(out, result)
        if 'state' in result:
            save_json(out / 'state.json', result['state'])
        record.update(status='completed', summary=result.get('summary', {}),
                      result_file=str(out / 'result.json'), report_file=str(out / 'report.html'))
        emit({'stage': 'completed', 'summary': result.get('summary', {}), 'report': str(out / 'report.html')})
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        emit({'stage': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)})
    finally:
        record['ended_at'] = utc_now()
        record['execution_seconds'] = round(time.perf_counter() - started, 6)
        record['timing_scope'] = 'input_read + processing + file_output; browser/provider time only when explicitly supplied as evidence'
        save_json(out / 'run.json', record)
        print(json.dumps({'run': str(out / 'run.json'), 'status': record['status'],
                          'execution_seconds': record['execution_seconds']}, ensure_ascii=False), flush=True)
    return record, result


def parser():
    main = argparse.ArgumentParser(description='电商自动化skill辅助工具；使用说明见SKILL.md')
    commands = main.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    commands.add_parser('modules')
    for name in ('run', 'watch'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--module', required=True)
        cmd.add_argument('--input', required=True)
        cmd.add_argument('--output', required=True)
        if name == 'watch':
            cmd.add_argument('--interval', type=float, default=15)
            cmd.add_argument('--max-runs', type=int, default=0, help='0为持续前台运行，Ctrl+C结束')
    field = commands.add_parser('listing-field')
    field.add_argument('--queue', required=True)
    field.add_argument('--item', required=True)
    field.add_argument('--field', required=True)
    field.add_argument('--value', required=True)
    field.add_argument('--evidence', required=True)
    status = commands.add_parser('listing-result')
    status.add_argument('--queue', required=True)
    status.add_argument('--item', required=True)
    status.add_argument('--status', required=True)
    status.add_argument('--external-id', default='')
    status.add_argument('--evidence', required=True)
    start = commands.add_parser('session-start')
    start.add_argument('--output', required=True)
    start.add_argument('--label', required=True)
    finish = commands.add_parser('session-finish')
    finish.add_argument('--session', required=True)
    finish.add_argument('--processed', type=int, required=True)
    finish.add_argument('--evidence', required=True)
    for name in ('media-select', 'media-redo', 'media-import', 'media-export'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--manifest', required=True)
        if name in {'media-select', 'media-redo'}:
            cmd.add_argument('--item', required=True)
        if name == 'media-select':
            cmd.add_argument('--action', choices=['keep', 'reject'], required=True)
        if name in {'media-redo', 'media-import'}:
            cmd.add_argument('--ffmpeg')
        if name == 'media-redo':
            cmd.add_argument('--font')
        if name == 'media-import':
            cmd.add_argument('--input', required=True)
            cmd.add_argument('--base')
        if name == 'media-export':
            cmd.add_argument('--destination', required=True)
    return main


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'doctor':
            print(json_text(doctor()))
        elif args.command == 'modules':
            print(json_text(registry()))
        elif args.command == 'listing-field':
            from listing import record_field
            print(json_text(record_field(Path(args.queue), args.item, args.field, args.value, args.evidence)))
        elif args.command == 'listing-result':
            from listing import record_result
            print(json_text(record_result(Path(args.queue), args.item, args.status, args.external_id, args.evidence)))
        elif args.command == 'session-start':
            path = Path(args.output).resolve()
            if path.exists():
                raise ValueError('session文件已存在，避免覆盖计时证据')
            record = {'label': args.label, 'started_at': utc_now(), 'monotonic_start': time.perf_counter(),
                      'machine_hash': digest(platform.node().encode('utf-8')), 'status': 'running',
                      'timing_scope': 'same-machine elapsed span; includes interaction and waits'}
            save_json(path, record)
            print(json_text(record))
        elif args.command == 'session-finish':
            record = load_json(args.session)
            if record.get('status') != 'running' or args.processed < 0 or not args.evidence.strip():
                raise ValueError('session已结束、数量无效或缺少证据')
            elapsed = time.perf_counter() - record['monotonic_start']
            if record['machine_hash'] != digest(platform.node().encode('utf-8')) or elapsed < 0:
                raise ValueError('计时须在同一电脑同一启动周期内完成')
            record.update(status='completed', ended_at=utc_now(), elapsed_seconds=round(elapsed, 6),
                          processed=args.processed, evidence=args.evidence)
            save_json(args.session, record)
            print(json_text(record))
        elif args.command.startswith('media-'):
            import media
            if args.command == 'media-select':
                result = media.select_item(args.manifest, args.item, args.action == 'keep')
            elif args.command == 'media-redo':
                result = media.redo_item(args.manifest, args.item, ffmpeg=args.ffmpeg, font=args.font)
            elif args.command == 'media-import':
                result = media.append_generated(args.manifest, load_json(args.input),
                                                job_dir=args.base or Path(args.input).resolve().parent, ffmpeg=args.ffmpeg)
            else:
                result = media.export_selected(args.manifest, args.destination)
            print(json_text(result))
        elif args.command == 'run':
            record, _ = run_job(args.module, args.input, args.output)
            return 0 if record['status'] == 'completed' else 1
        elif args.command == 'watch':
            if args.module.upper() not in {'C', 'F', 'G'} or args.interval < .1 or args.max_runs < 0:
                raise ValueError('watch仅支持C/F/G；interval>=0.1，max-runs>=0')
            count, state, failed = 0, None, False
            while True:
                record, result = run_job(args.module, args.input, args.output, state)
                failed = failed or record['status'] != 'completed'
                if record['status'] == 'completed' and result:
                    state = result.get('state', state)
                count += 1
                if args.max_runs and count >= args.max_runs:
                    break
                time.sleep(args.interval)
            return 1 if failed else 0
        return 0
    except KeyboardInterrupt:
        print('已停止前台监听；已完成运行记录仍保留。')
        return 130
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'error_type': type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
