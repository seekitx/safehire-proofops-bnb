"""Browser checks with synthetic answers; never creates human competition evidence."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path


def main() -> None:
    sync_playwright = importlib.import_module('playwright.sync_api').sync_playwright
    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.getenv('SAFEHIRE_BROWSER_EXECUTABLE'))
        page = browser.new_page()
        page.route('https://benchmark.test/**', lambda route: route.fulfill(
            status=200, content_type='text/html', body='<html></html>'))
        page.goto('https://benchmark.test/')
        html = (root / 'apps/web/benchmark.html').read_text().replace(
            '<script src="/assets/benchmark.js" defer></script>', '')
        page.set_content(html)
        page.route('**/api/evidence/termix/tasks/**', lambda route: route.fulfill(
            json={'task_id': 'synthetic-browser-task', 'task_description': 'Test only'}))
        page.add_script_tag(content=(root / 'apps/web/assets/benchmark.js').read_text())
        page.wait_for_function('task !== null')
        page.locator('#operatorName').fill('SYNTHETIC TEST OPERATOR')
        page.locator('#startTimer').click()
        page.locator('#manualOutput').fill('SYNTHETIC TEST ANSWER')
        page.locator('#finishManual').click()
        assert 'Confirm the real run' in page.locator('#toast').inner_text()
        page.evaluate('''() => {
          agentRaw = {task_id: 'one', output: 'answer'};
          manualRaw = {task_id: 'two', output: 'answer'};
          buildPacket();
        }''')
        assert 'same explicit task_id' in page.locator('#toast').inner_text()
        page.evaluate('''() => {
          window.testDownloads = [];
          downloadJson = (name, data) => window.testDownloads.push({name, data});
          agentRaw = {task_id: 'one', endpoint: 'SECRET-ORIGIN',
            response: {result: {agent_result: {agent_id: 'IDENTITY', result: {answer: 4},
              risk_checks: ['review'], source_labels: ['test']}}}};
          manualRaw = {task_id: 'one', operator: 'TEST-OPERATOR', output: 'answer 4'};
          buildPacket();
        }''')
        downloads = page.evaluate('window.testDownloads')
        packet, key = downloads[0]['data'], downloads[1]['data']
        assert set(packet['outputs']) == {'A', 'B'}
        assert not any(value in json.dumps(packet) for value in ('SECRET-ORIGIN', 'IDENTITY', 'TEST-OPERATOR'))
        assert key['original_outputs']['agent']['endpoint'] == 'SECRET-ORIGIN'
        page.evaluate('packet = window.testDownloads[0].data')
        page.locator('#reviewerName').fill('SYNTHETIC TEST REVIEWER')
        page.evaluate('downloadReview()')
        assert 'Confirm the review' in page.locator('#toast').inner_text()
        browser.close()
    print('PASS: synthetic browser checks for task binding, metadata separation and explicit attestations; no human evidence generated')


if __name__ == '__main__':
    main()
