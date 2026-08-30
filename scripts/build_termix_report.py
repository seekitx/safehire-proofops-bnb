from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofops.evidence import build_termix_report

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evidence" / "termix" / "agent-advantage-report.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a strict TermiX manual-vs-agent evidence report."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_termix_report(args.manifest.resolve(), project_root=ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    print(f"mode={report['evidence_mode']} tasks={report['task_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
