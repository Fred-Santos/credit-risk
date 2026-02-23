from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid


@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at_utc: str
    repo_root: Path
    raw_dir: Path
    docs_root: Path

    @staticmethod
    def create(repo_root: Path) -> "RunContext":
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        started = datetime.now(timezone.utc).isoformat()
        raw_dir = repo_root / "data" / "raw"
        docs_root = repo_root / "docs"
        return RunContext(
            run_id=run_id,
            started_at_utc=started,
            repo_root=repo_root,
            raw_dir=raw_dir,
            docs_root=docs_root,
        )
