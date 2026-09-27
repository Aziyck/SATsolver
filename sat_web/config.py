"""Paths and limits for the web server; every value can be overridden by an environment variable."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _default_parallel_jobs() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("WIZSAT_DATA_DIR", ROOT / "output")))
    max_parallel_jobs: int = field(default_factory=lambda: int(os.environ.get("WIZSAT_MAX_JOBS", _default_parallel_jobs())))
    frontend_dist: Path = field(default_factory=lambda: Path(os.environ.get("WIZSAT_FRONTEND_DIST", ROOT / "frontend" / "dist")))
    assets_dir: Path = ROOT / "assets"
    visualisations_dir: Path = ROOT / "docs" / "visualisations"
    log_lines_per_job: int = 5000

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wizsat.db"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
