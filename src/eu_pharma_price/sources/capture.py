"""Source capture and verification logic."""

import hashlib
import json
from pathlib import Path

from .models import FileEntry, SnapshotManifest

DATA_RAW_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw"


def compute_file_hash(file_path: Path) -> str:
    sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return f"sha256:{sha}"


def verify_snapshot(snapshot_dir: Path) -> tuple[bool, list[str]]:
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json not found"]

    manifest = SnapshotManifest.model_validate_json(manifest_path.read_text())
    errors: list[str] = []

    for entry in manifest.files:
        file_path = snapshot_dir / entry.filename
        if not file_path.exists():
            errors.append(f"File missing: {entry.filename}")
            continue
        actual_hash = compute_file_hash(file_path)
        if actual_hash != entry.file_hash:
            errors.append(
                f"Hash mismatch for {entry.filename}: "
                f"expected {entry.file_hash}, got {actual_hash}"
            )

    return len(errors) == 0, errors


def snapshot_exists(country_code: str, snapshot_date: str) -> bool:
    snapshot_dir = DATA_RAW_DIR / country_code.lower() / snapshot_date
    return snapshot_dir.exists() and (snapshot_dir / "manifest.json").exists()


def write_manifest(snapshot_dir: Path, manifest: SnapshotManifest) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = snapshot_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            f"Snapshot already exists at {snapshot_dir}. "
            "Immutability rule: never overwrite a dated snapshot."
        )
    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return manifest_path


def load_register(register_path: Path | None = None) -> list[dict]:
    if register_path is None:
        register_path = (
            Path(__file__).parent.parent.parent.parent / "data" / "sources" / "register.json"
        )
    if not register_path.exists():
        return []
    return json.loads(register_path.read_text(encoding="utf-8"))
