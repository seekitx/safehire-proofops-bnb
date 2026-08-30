from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "safehire-proofops-bnb-release"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".data",
    ".studio",
    ".claude",
    ".playwright-cli",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "artifacts",
    "cache",
    "typechain-types",
}
EXCLUDED_NAMES = {".env", ".env.local", ".coverage", "ARTIFACT_MANIFEST.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def releasable_files() -> list[Path]:
    return sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path.name not in EXCLUDED_NAMES
            and path.suffix not in {".pyc", ".pyo"}
            and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
            and not any(part.endswith(".egg-info") for part in path.relative_to(ROOT).parts)
        ),
        key=lambda path: path.as_posix(),
    )


def write_project_manifest(files: list[Path]) -> Path:
    manifest_path = ROOT / "ARTIFACT_MANIFEST.json"
    manifest = {
        "project": "SafeHire ProofOps for BNB Chain",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "file_count_excluding_manifest": len(files),
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    files = releasable_files()
    manifest_path = write_project_manifest(files)
    archive_path = OUT.with_suffix(".zip")
    temporary_path = archive_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(
        temporary_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in [*files, manifest_path]:
            relative = path.relative_to(ROOT)
            archive.write(path, arcname=(Path(ROOT.name) / relative).as_posix())
    os.replace(temporary_path, archive_path)
    manifest = {
        "artifact": archive_path.name,
        "sha256": sha256(archive_path),
        "created_at": datetime.now(UTC).isoformat(),
        "source_file_count_excluding_manifest": len(files),
        "excluded": sorted(EXCLUDED_PARTS | EXCLUDED_NAMES),
        "warning": "Mainnet execution is disabled and contracts are not audited.",
    }
    release_manifest_path = archive_path.with_suffix(".manifest.json")
    release_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(archive_path)
    print(release_manifest_path)


if __name__ == "__main__":
    main()
