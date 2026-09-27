import { expect, test } from "./fixtures";

test("run a preset benchmark and read the results", async ({ page }) => {
  await page.goto("/benchmarks");
  await expect(page.getByText("Random 3-SAT phase transition").first()).toBeVisible();

  await page.goto("/benchmarks/new?preset=3sat_phase_transition");
  await expect(page.getByText("Solver runs").first()).toBeVisible();
  await page.getByRole("button", { name: "Start benchmark" }).click();

  await expect(page).toHaveURL(/\/benchmarks\/\d+$/);
  await expect(page.getByText("Done", { exact: true }).first()).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("canvas").first()).toBeVisible();

  await page.getByRole("tab", { name: /Runs/ }).click();
  const runs = page.getByRole("table", { name: "Solver runs" });
  await expect(runs.getByRole("row")).not.toHaveCount(0);
  await runs.getByRole("row").nth(1).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: /CSV/ }).first().click()]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
});

test("jobs and learn pages", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: "Jobs" })).toBeVisible();

  await page.goto("/learn");
  await page.locator('main a[href="/learn/cdcl"]').first().click();
  await expect(page).toHaveURL(/\/learn\/cdcl$/);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
});
