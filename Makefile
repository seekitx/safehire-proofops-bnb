.PHONY: install test lint typecheck contracts agent-studio run seed gate package

install:
	python -m pip install -e '.[dev]'

test:
	python -m pytest -q

lint:
	ruff check src apps tests scripts

typecheck:
	mypy src apps scripts

contracts:
	cd contracts && npm run compile && npm test && npm audit --omit=dev

agent-studio:
	cd agent-studio/safehireagents && corepack pnpm install --frozen-lockfile && corepack pnpm --dir app/agent build

run:
	uvicorn apps.api.main:app --reload --port 8000

seed:
	python scripts/seed_demo.py

gate:
	python scripts/submission_gate.py

package:
	python scripts/build_release.py
