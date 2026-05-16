# Snapshot Layout

Snapshots are the immutable, dated captures of source documents. This spec defines the directory structure and manifest format.

## Directory Structure

```
data/raw/<country_code>/<snapshot_date>/
├── manifest.json          # Metadata about this snapshot
├── <original_filename>    # The source file as downloaded
└── ...                    # Additional files if source is multi-file
```

- `<country_code>`: lowercase ISO 3166-1 alpha-2 (e.g., `ie`, `pl`, `fr`)
- `<snapshot_date>`: ISO 8601 date (e.g., `2024-06-15`)

## Manifest Format

Each snapshot directory contains a `manifest.json`:

```json
{
  "snapshot_id": "uuid",
  "source_id": "uuid (references source register)",
  "country_code": "IE",
  "snapshot_date": "2024-06-15",
  "fetched_at": "2024-06-15T10:30:00Z",
  "fetch_method": "automated",
  "files": [
    {
      "filename": "reimbursement-list-june-2024.xlsx",
      "file_hash": "sha256:abc123...",
      "file_size_bytes": 1048576,
      "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
  ],
  "source_url": "https://www.example.ie/reimbursement-list",
  "robots_txt_compliant": true,
  "tos_reviewed": true,
  "notes": null
}
```

## Manifest Fields

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | `str` (UUID) | Unique identifier for this snapshot |
| `source_id` | `str` (UUID) | Reference to source register entry |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country |
| `snapshot_date` | `str` (ISO 8601 date) | Effective date of this capture |
| `fetched_at` | `str` (ISO 8601 datetime, UTC) | Exact fetch timestamp |
| `fetch_method` | `str` (enum: `automated`, `manual`) | How the file was obtained |
| `files` | `list[FileEntry]` | Files in this snapshot |
| `source_url` | `str` (URL) | Where the file was fetched from |
| `robots_txt_compliant` | `bool` | robots.txt compliance |
| `tos_reviewed` | `bool` | ToS review status |
| `notes` | `str` (nullable) | Additional context |

### FileEntry

| Field | Type | Description |
|-------|------|-------------|
| `filename` | `str` | Name of the file in the snapshot directory |
| `file_hash` | `str` | `sha256:<hex_digest>` |
| `file_size_bytes` | `int` | File size |
| `media_type` | `str` | MIME type |

## Immutability Rules

1. **Never overwrite a dated snapshot.** If a source is re-fetched on the same date and the content differs, create a new snapshot with a suffix (e.g., `2024-06-15_v2`) and file an anomaly report.
2. **Never modify files after creation.** The `file_hash` in the manifest is the contract.
3. **Hash verification**: `sha256(<file_content>)` must equal the `file_hash` field (without the `sha256:` prefix).
4. **Manifests are append-only metadata.** Once written, a manifest is never edited. Corrections create a new snapshot.

## Verification

To verify a snapshot's integrity:

```python
import hashlib
from pathlib import Path

def verify_snapshot(snapshot_dir: Path) -> bool:
    manifest = json.loads((snapshot_dir / "manifest.json").read_text())
    for entry in manifest["files"]:
        file_path = snapshot_dir / entry["filename"]
        expected = entry["file_hash"].removeprefix("sha256:")
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual != expected:
            return False
    return True
```
