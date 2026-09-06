#!/usr/bin/env python3
"""Validate reviewed provider manifest offline; never approves identity or calls provider."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from proofops.arena.providers import ProviderCatalog

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(ProviderCatalog.load(args.manifest).public(),indent=2))
    except (OSError, ValueError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(2)
