"""Every execution leaves a lineage record: no record, no comparison in CI."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from rag.config import Config


def git_sha() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                      stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], stderr=subprocess.DEVNULL) != 0
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def write_run(kind: str, cfg: Config, extra: dict, runs_dir: str = "runs") -> Path:
    ts = time.strftime("%Y%m%dT%H%M%S")
    out = Path(runs_dir) / f"{ts}-{kind}-{cfg.full_hash()[:8]}"
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "kind": kind,
        "timestamp": ts,
        "git_sha": git_sha(),
        "config_hash": cfg.full_hash(),
        "index_hash": cfg.index_hash(),
        "config": cfg.to_dict(),
        **extra,
    }
    (out / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True))
    return out
