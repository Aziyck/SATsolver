import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run the real app: the Python server serving the built UI.
// Build first (npm run build), then: npm run test:e2e
// WIZSAT_PYTHON picks the interpreter (default: python); it needs requirements.txt installed.
const port = Number(process.env.WIZSAT_E2E_PORT ?? 8799);
const python = process.env.WIZSAT_PYTHON ?? "python";
// A fresh, throwaway job database for every run. Set once so test workers reuse it.
const dataDir = (process.env.WIZSAT_E2E_DATA ??= fs.mkdtempSync(path.join(os.tmpdir(), "wizsat-e2e-")));

// A stand-in for PyPy (INTERP-3): it answers the server's probe with ["PyPy", "3.10.14"] and runs no
// solver, so a job that chooses PyPy shows that interpreter and its runs end as ERROR. Like
// tests/fake_python.py; the file ends in .cmd on Windows, where Popen cannot start a bare script.
const fakePypy = path.join(dataDir, process.platform === "win32" ? "fake-pypy.cmd" : "fake-pypy");
const fakePypyScript =
  process.platform === "win32" ? `@echo ["PyPy", "3.10.14"]${os.EOL}` : `#!/bin/sh${os.EOL}echo '["PyPy", "3.10.14"]'${os.EOL}`;
fs.writeFileSync(fakePypy, fakePypyScript, { mode: 0o755 });

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: `"${python}" -m sat_web --skip-build --no-browser --strict-port --port ${port}`,
    cwd: "..",
    url: `http://127.0.0.1:${port}/api/health`,
    env: { WIZSAT_DATA_DIR: dataDir, WIZSAT_SOLVER_PYTHON: fakePypy },
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
