"""Offline DOM + real ASGI router smoke. Fixtures do not establish live evidence."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI
from importlib import import_module
from typing import Any

from proofops.decision.market import REVIEWED, SnapshotCache
from proofops.decision.routes import make_router


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".data/champion-browser"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    async def fixture() -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {"source": "synthetic_browser_fixture", "observed_at": now, "endpoint_reachable": True,
                "operator": "Synthetic test supplier", "agents": [
                    {"token_id": token, "skill_id": skill, "name": f"TEST FIXTURE — {skill}",
                     "category": rule[0], "description": "Synthetic browser-test record. Not a live verified service.",
                     "currently_callable": True, "created_tx_hash": "0x" + "a"*64,
                     "market_signals": {"available": True, "owner_address": "0x" + "b"*40,
                                        "endpoint_last_checked_at": now}}
                    for (token, skill), rule in REVIEWED.items()]}
    app = FastAPI()
    app.include_router(make_router(root, SnapshotCache(fixture)))
    failure = [False]
    async def dispatch(path: str, body: str | None) -> dict[str, Any]:
        if failure[0] and path == "/api/decision/market":
            return {"status": 503, "body": {"detail": "Synthetic failure"}}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.request("POST" if body else "GET", path, json=json.loads(body) if body else None)
            return {"status": response.status_code, "body": response.json()}
    async def binding(_source: Any, path: str, body: str | None) -> dict[str, Any]:
        return await dispatch(path, body)
    html = (root / "apps/web/decision.html").read_text()
    html = html.replace('<script src="/assets/decision.js" defer></script>', "")
    html = html.replace('<link rel="stylesheet" href="/assets/decision.css">', "")
    html = html.replace("<body>", '<body><div style="padding:8px;text-align:center;background:#6a431d;color:#fff">OFFLINE UI TEST · SYNTHETIC FIXTURES · NO LIVE PAYMENT</div>')
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    sync_playwright = import_module("playwright.sync_api").sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=shutil.which("chromium"), headless=True, args=["--no-sandbox"])
        for width, height in ((1440, 1000), (390, 844)):
            failure[0] = False
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.expose_binding("fixtureApi", binding)
            page.set_content(html)
            page.add_style_tag(content=(root / "apps/web/assets/decision.css").read_text())
            page.evaluate("""() => {window.fetch = async (path, options={}) => {
                const response = await window.fixtureApi(path, options.body || null);
                return {ok: response.status >= 200 && response.status < 300,
                        status: response.status, json: async () => response.body};
            };};""")
            page.add_script_tag(content=(root / "apps/web/assets/decision.js").read_text())
            page.wait_for_selector(".card")
            assert page.locator("#categories button").count() == 4
            assert page.locator("#compare").is_disabled()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.locator("#categories button").filter(has_text="Grid Trading").click()
            page.locator("#previewForm button").click()
            page.wait_for_function("document.querySelector('#previewResult').textContent.includes('round_trip_costs_missing')")
            payload = json.loads(page.locator("#previewInput").input_value())
            payload.update(fee_bps_per_side=30, slippage_bps_per_side=20, gas_usd_per_order=100)
            page.locator("#previewInput").fill(json.dumps(payload))
            page.locator("#previewForm button").click()
            page.wait_for_function("document.querySelector('#previewResult').textContent.includes('costs_exceed_grid_spread')")
            page.locator("#search").fill("no-such-provider")
            assert page.locator(".card").count() == 0
            page.locator("#search").fill("")
            assert page.locator(".card").count() == 1
            page.screenshot(path=str(args.output / f"decision-{width}.png"), full_page=True)
            failure[0] = True
            page.locator("#refresh").click()
            page.wait_for_function("document.querySelector('#probeState').textContent === 'UNAVAILABLE'")
            assert page.locator("a.cta").count() == 0 and page.locator("#compare").is_disabled()
            checks.append({"viewport": [width,height], "four_categories": True, "one_provider_no_fake_comparison": True,
                           "grid_cost_gate": True, "search": True, "refresh_failure_disables_hire": True,
                           "horizontal_overflow": False})
            page.close()
        browser.close()
    assert not errors, errors
    report = {"mode": "offline_DOM_and_isolated_ASGI_router_synthetic_fixture", "checks": checks,
              "javascript_errors": errors, "full_application_lifespan_tested": False,
              "native_browser_network_tested": False, "live_provider_or_wallet_tested": False}
    (args.output / "browser-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
