"""Paths and limits for the web server; every value can be overridden by an environment variable."""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")


def _default_parallel_jobs() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def host_name(name: str) -> str:
    """A name from WIZSAT_ALLOWED_HOSTS as a Host header carries it: lower case, IPv6 short and in brackets."""

    bare = name.strip().lower().strip("[]")
    try:
        address = ipaddress.ip_address(bare)
    except ValueError:
        # Names are compared exactly, so an entry with a port, a URL or a
        # wildcard would never match: refuse it instead of ignoring it.
        if not re.fullmatch(r"[a-z0-9._-]+", bare):
            raise ValueError(
                f"WIZSAT_ALLOWED_HOSTS: {name.strip()!r} is not a host name or an IP address (no port, no URL, no wildcard)"
            ) from None
        return bare
    return f"[{address.compressed}]" if address.version == 6 else address.compressed


def _extra_hosts() -> tuple[str, ...]:
    names = os.environ.get("WIZSAT_ALLOWED_HOSTS", "").split(",")
    return tuple(host_name(name) for name in names if name.strip())


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("WIZSAT_DATA_DIR", ROOT / "output")))
    max_parallel_jobs: int = field(default_factory=lambda: int(os.environ.get("WIZSAT_MAX_JOBS", _default_parallel_jobs())))
    frontend_dist: Path = field(default_factory=lambda: Path(os.environ.get("WIZSAT_FRONTEND_DIST", ROOT / "frontend" / "dist")))
    assets_dir: Path = ROOT / "assets"
    visualisations_dir: Path = ROOT / "docs" / "visualisations"
    log_lines_per_job: int = 5000
    extra_hosts: tuple[str, ...] = field(default_factory=_extra_hosts)

    @property
    def allowed_hosts(self) -> list[str]:
        """Names the server answers for, in Host and Origin headers (any port)."""

        return [*LOCAL_HOSTS, *self.extra_hosts]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wizsat.db"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
