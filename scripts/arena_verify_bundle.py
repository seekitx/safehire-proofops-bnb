#!/usr/bin/env python3
"""Offline local bundle integrity check; no network, keys or chain claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from proofops.arena.store import verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--trusted-head', help='Previously preserved journal head from an independent location')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.bundle.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('bundle exceeds 2 MiB')
        result = verify_bundle(json.loads(args.bundle.read_text()), trusted_head=args.trusted_head)
    except (OSError, ValueError) as exc:
        result = {'valid': False, 'error': str(exc)}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + '\n')
    print(text)
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
