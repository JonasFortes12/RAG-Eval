"""Download a pinned subset of kubernetes/website and write data/corpus_manifest.json.

First run:   uv run python scripts/fetch_corpus.py            (takes current HEAD, records SHA)
Reproduce:   uv run python scripts/fetch_corpus.py            (reuses SHA from existing manifest)
Advance:     uv run python scripts/fetch_corpus.py --ref <sha> --update
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag.corpus import corpus_digest  # noqa: E402

REPO = "https://github.com/kubernetes/website.git"
SUBDIRS = ["content/en/docs/concepts", "content/en/docs/tasks"]
DEST = Path("data/raw/k8s")
MANIFEST = Path("data/corpus_manifest.json")


def run(*cmd: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="commit sha to fetch (default: manifest sha, else HEAD)")
    ap.add_argument("--update", action="store_true", help="allow overwriting an existing manifest")
    args = ap.parse_args()

    pinned = json.loads(MANIFEST.read_text())["commit"] if MANIFEST.exists() else None
    if args.ref and pinned and args.ref != pinned and not args.update:
        raise SystemExit("Manifest already pins another commit. Pass --update to move it.")
    ref = args.ref or pinned or "HEAD"

    if not (DEST / ".git").exists():
        DEST.mkdir(parents=True, exist_ok=True)
        run("git", "init", "-q", cwd=DEST)
        run("git", "remote", "add", "origin", REPO, cwd=DEST)
        run("git", "sparse-checkout", "set", *SUBDIRS, cwd=DEST)
    run("git", "fetch", "--depth", "1", "--filter=blob:none", "origin", ref, cwd=DEST)
    run("git", "checkout", "-q", "FETCH_HEAD", cwd=DEST)
    commit = run("git", "rev-parse", "HEAD", cwd=DEST)

    # markdown only, relative to DEST, skip generated/empty section indexes
    files = sorted(
        str(p.relative_to(DEST))
        for sub in SUBDIRS
        for p in (DEST / sub).rglob("*.md")
        if p.stat().st_size > 200
    )
    manifest = {
        "name": "kubernetes-docs",
        "repo": REPO,
        "commit": commit,
        "subdirs": SUBDIRS,
        "license": "CC BY 4.0",
        "files": files,
        "content_digest": corpus_digest(DEST, files),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"commit {commit[:10]}  {len(files)} files  digest {manifest['content_digest'][:12]}")


if __name__ == "__main__":
    main()
