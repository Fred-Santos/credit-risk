from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid
from src.utils.paths import load_paths


@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at_utc: str
    repo_root: Path
    raw_dir: Path
    bronze_dir: Path
    silver_dir: Path
    gold_dir: Path
    sample_dir: Path
    events_dir: Path
    docs_root: Path
    data_dictionary_dir: Path
    data_quality_dir: Path
    lineage_dir: Path
    observability_dir: Path
    input_dir: Path | None = None
    selection_id: str | None = None

    @property
    def ingestion_dir(self) -> Path:
        """Origem imediata da ingestão; raw_dir mantém a origem original."""
        return self.input_dir if self.input_dir is not None else self.raw_dir

    @staticmethod
    def create(repo_root: Path) -> "RunContext":
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        started = datetime.now(timezone.utc).isoformat()
        repo_root = repo_root.resolve()
        return RunContext(
            run_id=run_id,
            started_at_utc=started,
            repo_root=repo_root,
            **load_paths(repo_root),
        )
