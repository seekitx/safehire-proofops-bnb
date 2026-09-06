#!/usr/bin/env python3
"""Loopback-only analysis server. Not the production marketplace or a chain test."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from proofops.arena.routes import ArenaBoundaryMiddleware, make_router
from proofops.arena.store import TaskStore


def build_local_app(root: Path, database: Path) -> FastAPI:
    os.environ['SAFEHIRE_PROVIDER_QUOTES_ENABLED'] = 'false'
    app = FastAPI(title='SafeHire local analysis only')
    app.add_middleware(ArenaBoundaryMiddleware)
    app.include_router(make_router(root, store=TaskStore(database), enabled=True))
    app.mount('/assets', StaticFiles(directory=root/'apps/web/assets'), name='arena-assets')

    @app.get('/', include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse('/arena')

    @app.get('/arena', include_in_schema=False)
    def page() -> HTMLResponse:
        html = (root/'apps/web/arena.html').read_text()
        html = html.replace('<body>', '<body><div role="note" style="padding:12px;text-align:center;background:#5d3c13;color:#fff">LOCAL ANALYSIS SERVER · SYNTHETIC EXAMPLES · NO LIVE WALLET OR PAYMENT · Marketplace links require the full application.</div>')
        return HTMLResponse(html, headers={'Cache-Control':'no-store'})

    return app


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8092)
    parser.add_argument('--db', type=Path, default=root/'.data/arena-local.sqlite3')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in 1024..65535')
    uvicorn.run(build_local_app(root, args.db), host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
