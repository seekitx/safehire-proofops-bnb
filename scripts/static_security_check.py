from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    ".data",
    ".studio",
    ".claude",
    "dist",
    "build",
    "node_modules",
    "artifacts",
    "cache",
}
PATTERNS = {
    # A transaction hash and an Ethereum private key are both 32-byte hex
    # strings.  Treating every 0x-prefixed 64-character value as a secret
    # makes legitimate deployment evidence fail the scan.  Require a
    # secret-bearing field name so public transaction hashes remain valid.
    "ethereum_private_key_assignment": re.compile(
        r"(?i)[\"']?(private[_-]?key|wallet[_-]?key)[\"']?\s*[:=]\s*"
        r"[\"']?0x[a-fA-F0-9]{64}[\"']?"
    ),
    "generic_api_key_assignment": re.compile(
        r"(?i)[\"']?(api[_-]?key|private[_-]?key|wallet[_-]?password)[\"']?"
        r"\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    ),
}
ALLOWLIST_FILES = {".env.example"}
ALLOWLIST_TEST_VALUES = {"do-not-store"}


def main() -> int:
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.parts):
            continue
        if path.name in ALLOWLIST_FILES or path.suffix.lower() not in {
            ".py",
            ".json",
            ".md",
            ".toml",
            ".yml",
            ".yaml",
            ".js",
            ".sol",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for placeholder in ALLOWLIST_TEST_VALUES:
            text = text.replace(placeholder, "<x>")
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append((str(path.relative_to(ROOT)), name))
    if findings:
        for finding in findings:
            print(f"possible secret: {finding[0]} ({finding[1]})", file=sys.stderr)
        return 1
    print("static security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
