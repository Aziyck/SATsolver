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

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
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
    env: { WIZSAT_DATA_DIR: dataDir },
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
