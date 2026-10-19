#!/usr/bin/env python3
"""Directory backups with manifests and rotation."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict:
    manifest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            manifest[str(path.relative_to(root))] = sha256_file(path)
    return manifest


def create_backup(source: Path, dest: Path, name: str) -> Path:
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    archive = dest / f"{name}-{stamp}.tar.gz"
    manifest = dest / f"{name}-{stamp}.manifest.json"

    manifest_data = build_manifest(source)
    with tempfile.NamedTemporaryFile(delete=False, dir=dest, suffix=".tmp") as tmp:
        tmp_path = Path(tmp.name)
    with tarfile.open(tmp_path, "w:gz") as tar:
        tar.add(source, arcname=source.name)
    tmp_path.replace(archive)
    manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return archive


def verify_backup(archive: Path, workdir: Path | None = None) -> dict:
    stem = archive.name.replace(".tar.gz", "")
    manifest_path = archive.with_name(f"{stem}.manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"manifest not found: {manifest_path}")
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        with tarfile.open(archive, "r:gz") as tar:
            # noqa: S202 - extracting our own archive inside a temporary directory
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:  # Python < 3.12
                tar.extractall(tmp)
        root = Path(tmp)
        roots = [p for p in root.iterdir()]
        if len(roots) != 1 or not roots[0].is_dir():
            raise ValueError("unexpected archive layout")
        actual = build_manifest(roots[0])

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(k for k in expected if k in actual and expected[k] != actual[k])
    return {"files": len(expected), "missing": missing, "extra": extra, "changed": changed,
            "ok": not missing and not extra and not changed}


def rotate(dest: Path, keep: int) -> list:
    if keep < 1:
        raise ValueError("keep must be >= 1")
    archives = sorted(dest.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for archive in archives[keep:]:
        manifest = archive.with_name(archive.name.replace(".tar.gz", ".manifest.json"))
        archive.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        removed.append(archive)
    return removed


def list_backups(dest: Path):
    rows = []
    for archive in sorted(dest.glob("*.tar.gz")):
        stat = archive.stat()
        rows.append({"file": archive.name, "bytes": stat.st_size,
                     "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")})
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backup helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create")
    p.add_argument("source", type=Path)
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--name", default="backup")

    p = sub.add_parser("verify")
    p.add_argument("archive", type=Path)

    p = sub.add_parser("rotate")
    p.add_argument("dest", type=Path)
    p.add_argument("--keep", type=int, default=5)

    p = sub.add_parser("list")
    p.add_argument("dest", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            archive = create_backup(args.source, args.dest, args.name)
            print(f"created {archive}")
        elif args.command == "verify":
            result = verify_backup(args.archive)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        elif args.command == "rotate":
            removed = rotate(args.dest, args.keep)
            print(f"removed {len(removed)} archive(s)")
        else:
            print(json.dumps(list_backups(args.dest), indent=2))
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
