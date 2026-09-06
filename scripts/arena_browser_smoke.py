#!/usr/bin/env python3
"""Chromium + real loopback HTTP + isolated Arena ASGI; synthetic inputs, no chain."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import asyncio

import httpx
from pathlib import Path


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.data/arena-browser'))
    parser.add_argument('--offline-asgi', action='store_true', help='Inject browser fetch into real ASGI; use when browser loopback HTTP is blocked. Does not test native browser network.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    errors, checks = [], []
    with tempfile.TemporaryDirectory() as temporary:
        from arena_local_server import build_local_app
        asgi_app = build_local_app(root, Path(temporary)/'offline.sqlite3') if args.offline_asgi else None
        async def binding(_source, path, options):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(asgi_app), base_url='http://test') as client:
                response = await client.request(options.get('method', 'GET'), path,
                    headers=options.get('headers', {}), content=options.get('body'))
                return {'status':response.status_code, 'body':response.json()}
        env = os.environ | {'PYTHONPATH':str(root/'src'), 'SAFEHIRE_PROVIDER_QUOTES_ENABLED':'false'}
        log = open(args.output/'isolated-server.log', 'w')
        process = subprocess.Popen([sys.executable, str(root/'scripts/arena_local_server.py'),
                                    '--port', str(port), '--db', str(Path(temporary)/'test.sqlite3')],
                                   env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        try:
            origin = f'http://127.0.0.1:{port}'
            for _ in range(60):
                try:
                    urllib.request.urlopen(origin+'/api/arena/capabilities', timeout=1).read()
                    break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError('local analysis server failed; inspect isolated-server.log')
                    time.sleep(.1)
            else:
                raise RuntimeError('local analysis server did not start')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                for width, height in [(1440, 1000), (390, 844)]:
                    page = browser.new_page(viewport={'width':width,'height':height}, accept_downloads=True)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.offline_asgi:
                        html = (root/'apps/web/arena.html').read_text()
                        html = html.replace('<script src="/assets/arena.js" defer></script>', '')
                        for css in ('decision.css', 'arena.css'):
                            html = html.replace(f'<link rel="stylesheet" href="/assets/{css}">', '')
                        html = html.replace('<body>', '<body><div style="padding:12px;text-align:center;background:#5d3c13;color:#fff">OFFLINE BROWSER + ASGI TEST · SYNTHETIC PLANS · NO LIVE PAYMENT OR NATIVE BROWSER NETWORK</div>')
                        page.expose_binding('isolatedArenaASGI', binding)
                        page.set_content(html)
                        for css in ('decision.css', 'arena.css'):
                            page.add_style_tag(content=(root/f'apps/web/assets/{css}').read_text())
                        page.evaluate("""() => {window.fetch = async (path, options={}) => {
                            const r = await window.isolatedArenaASGI(path, options);
                            return {ok:r.status >= 200 && r.status < 300, status:r.status, json:async()=>r.body};
                        };}""")
                        page.add_script_tag(content=(root/'apps/web/assets/arena.js').read_text())
                    else:
                        page.goto(origin+'/arena', wait_until='networkidle')
                    page.wait_for_function("document.querySelector('#task-input').value.includes('SYNTHETIC')")
                    assert page.locator('#categories button').count() == 4
                    assert page.locator('#quote').is_disabled()
                    for index in range(4):
                        page.locator('#categories button').nth(index).click()
                        page.wait_for_function("document.querySelector('#status').textContent.includes('SYNTHETIC EXAMPLE loaded')")
                        page.locator('#walkthrough').click()
                        page.wait_for_function("document.querySelector('#walkthrough-result').querySelectorAll('.report-card').length === 2")
                        titles = page.locator('#walkthrough-result h3').all_text_contents()
                        assert 'CONSTRAINTS PASS' in titles[0] and 'BLOCKED' in titles[1], titles
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
                    # Persist exact valid and invalid plans against one frozen grid task.
                    page.locator('#categories button').nth(1).click()
                    page.wait_for_function("document.querySelector('#task-title').textContent === 'Grid trading'")
                    page.locator('#preview').click()
                    page.wait_for_function("document.querySelector('#proposal-input').value.includes('local:reference-v2')")
                    original = page.locator('#proposal-input').input_value()
                    page.locator('#create').click()
                    page.wait_for_function("document.querySelector('#task-meta').textContent.includes('version 1')")
                    page.locator('#submit').click()
                    page.wait_for_function("document.querySelectorAll('.saved-row').length === 1")
                    altered = json.loads(original)
                    altered['agent_ref'] = 'local:browser-adversarial-fixture'
                    altered['parameters']['stop_price'] = 999
                    page.locator('#proposal-input').fill(json.dumps(altered))
                    page.locator('#submit').click()
                    page.wait_for_function("document.querySelectorAll('.saved-row').length === 2")
                    page.locator('.saved-row input').nth(0).check()
                    page.locator('.saved-row input').nth(1).check()
                    page.locator('#compare').click()
                    page.wait_for_function("document.querySelector('#comparison-result').querySelectorAll('.report-card').length === 2")
                    assert 'BLOCKED' in page.locator('#comparison-result h3').nth(1).text_content()
                    with page.expect_download() as download_info:
                        page.locator('#export').click()
                    download = download_info.value
                    bundle_path = Path(temporary)/f'bundle-{width}.json'
                    download.save_as(str(bundle_path))
                    bundle = json.loads(bundle_path.read_text())
                    assert bundle['integrity']['valid'] and not bundle['paid_delivery_verified']
                    # No task capability or wallet secret is exported.
                    assert 'task_token' not in bundle_path.read_text()
                    page.locator('#refresh-task').click()
                    page.wait_for_function("document.querySelector('#status').textContent.includes('version refreshed')")
                    assert not page.locator('#export').is_disabled()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    page.screenshot(path=str(args.output/f'arena-{width}.png'), full_page=True)
                    page.evaluate('window.scrollTo(0, 0)')
                    page.screenshot(path=str(args.output/f'arena-overview-{width}.png'))
                    checks.append({'viewport':[width,height], 'four_guided_categories':True,
                                   'valid_and_invalid_plan_distinguished':True, 'native_http_calls':not args.offline_asgi,
                                   'capability_save_compare_export_refresh':True,
                                   'quotes_disabled':True, 'horizontal_overflow':False})
                    page.close()
                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            log.close()
    report = {'mode':'offline_browser_ASGI_synthetic_tasks' if args.offline_asgi else 'real_browser_HTTP_isolated_ASGI_synthetic_tasks', 'checks':checks,
              'javascript_errors':errors, 'full_marketplace_lifespan_tested':False,
              'mainnet_transactions_tested':False, 'external_providers_tested':False}
    (args.output/'browser-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
