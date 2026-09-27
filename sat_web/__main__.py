"""
Start WizSAT in the browser.

    python -m sat_web              build the web UI if needed, start the server, open the browser
    python -m sat_web --no-browser
    python -m sat_web --port 8080
    python -m sat_web --build      force a rebuild of the web UI first
    python -m sat_web --dev        auto-reload the Python server (run `npm run dev` in frontend/ for the UI)

The server only listens on 127.0.0.1 (this machine) unless --host is given.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"
SOURCE_PATHS = ("src", "public", "index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json")


def _newest_mtime(paths) -> float:
    newest = 0.0
    for path in paths:
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    newest = max(newest, child.stat().st_mtime)
    return newest


def frontend_is_stale() -> bool:
    if not DIST_INDEX.is_file():
        return True
    sources = [FRONTEND / name for name in SOURCE_PATHS] + [ROOT / "docs" / "algorithms"]
    return _newest_mtime(sources) > DIST_INDEX.stat().st_mtime


def build_frontend() -> bool:
    npm = shutil.which("npm")
    if npm is None:
        print(
            "\n[wizsat] Node.js was not found, so the web interface cannot be built.\n"
            "         Install Node.js 20 or newer from https://nodejs.org and run this command again.\n"
            "         The server will still start, but the page will ask you to build the UI.\n"
        )
        return False
    node_modules = FRONTEND / "node_modules"
    lock = FRONTEND / "package-lock.json"
    needs_install = not node_modules.is_dir() or (lock.is_file() and lock.stat().st_mtime > node_modules.stat().st_mtime)
    try:
        if needs_install:
            print("[wizsat] Installing web UI dependencies (first run only, this can take a minute)...")
            subprocess.run([npm, "ci" if lock.is_file() else "install", "--no-audit", "--no-fund"], cwd=FRONTEND, check=True)
            node_modules.touch()
        print("[wizsat] Building the web UI...")
        subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"\n[wizsat] Building the web UI failed ({exc}). See the npm output above.\n")
        return False


def free_port(host: str, port: int, attempts: int = 20) -> int:
    for candidate in range(port, port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, candidate))
            except OSError:
                continue
            return candidate
    raise SystemExit(f"[wizsat] No free port between {port} and {port + attempts - 1}.")


def main(argv: list[str] | None = None) -> None:
    if sys.version_info < (3, 10):
        raise SystemExit("WizSAT needs Python 3.10 or newer.")

    parser = argparse.ArgumentParser(prog="python -m sat_web", description="Start the WizSAT web app.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to listen on (default: 127.0.0.1, this machine only)")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on (default: 8000, or the next free one)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    parser.add_argument("--build", action="store_true", help="rebuild the web UI before starting")
    parser.add_argument("--skip-build", action="store_true", help="never build the web UI")
    parser.add_argument("--dev", action="store_true", help="auto-reload the server when Python files change")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        raise SystemExit("[wizsat] Missing dependencies. Run: python -m pip install -r requirements.txt") from None

    if not args.skip_build and (args.build or frontend_is_stale()):
        build_frontend()

    port = free_port(args.host, args.port)
    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{shown_host}:{port}"
    print(f"\n[wizsat] WizSAT is starting at {url}  (press Ctrl+C to stop)\n")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()

    uvicorn.run(
        "sat_web.api:create_app",
        factory=True,
        host=args.host,
        port=port,
        reload=args.dev,
        reload_dirs=[str(ROOT / name) for name in ("sat_web", "sat_core", "problems", "solvers")] if args.dev else None,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
