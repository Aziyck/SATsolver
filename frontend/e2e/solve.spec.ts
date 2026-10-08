import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "./fixtures";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("the home page lists the problems", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/solve$/);
  for (const title of ["Graph Coloring", "Sudoku", "N-Queens", "Random 3-SAT"]) {
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
});

test("solve graph coloring and check the answer", async ({ page }) => {
  await page.goto("/solve/graph_coloring");
  await page.getByRole("button", { name: "Solve", exact: true }).click();

  await expect(page.getByText("Verified", { exact: true })).toBeVisible();
  await expect(page.getByText("Solver time")).toBeVisible();
  await expect(page).toHaveURL(/job=\d+/);

  await page.getByRole("tab", { name: /CNF/ }).click();
  await expect(page.getByText(/^p cnf \d+ \d+$/).first()).toBeVisible();
  await page.getByRole("tab", { name: /Log/ }).click();
  await expect(page.getByText(/Job done/)).toBeVisible();
});

test("solve a sudoku and an N-Queens board", async ({ page }) => {
  await page.goto("/solve/sudoku");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();

  await page.goto("/solve/n_queens");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();
  await expect(page.getByText("SAT", { exact: true }).first()).toBeVisible();
});

test("open a DIMACS file", async ({ page }) => {
  await page.goto("/solve/dimacs");
  await page.locator('input[type="file"]').setInputFiles(path.join(REPO, "input/examples/sudoku_4x4.cnf"));
  await expect(page.getByText("sudoku_4x4.cnf", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText("Solver time")).toBeVisible();
  await expect(page.getByText("SAT", { exact: true }).first()).toBeVisible();
});

test("invalid input shows a field error instead of starting a job", async ({ page }) => {
  await page.goto("/solve/dimacs");
  await page.getByLabel("DIMACS text").fill("p cnf 2 1\n1 x 0\n");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText(/line 2/i).first()).toBeVisible();
  await expect(page).not.toHaveURL(/job=/);
});

test("a solve job has a full page with the log", async ({ page }) => {
  await page.goto("/solve/n_queens");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Full page" }).click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  await page.getByRole("tab", { name: /Log/ }).click();
  await expect(page.getByText(/Job done/)).toBeVisible();

  // The Jobs list opens the same page, and Edit goes back to the form.
  await page.goto("/jobs");
  await page.getByRole("row").filter({ hasText: "N-Queens" }).first().click();
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  await page.getByRole("button", { name: "Edit" }).click();
  await expect(page).toHaveURL(/\/solve\/n_queens$/);
  await expect(page.getByRole("button", { name: "Solve", exact: true })).toBeVisible();
});

test("solver options reset to their defaults and show up in the job's settings", async ({ page }) => {
  await page.goto("/solve/n_queens");
  await page.locator('label[for$="-walksat"]').click();
  const noise = page.getByRole("textbox", { name: "Noise" });
  await noise.fill("0.3");
  await page.getByRole("button", { name: "Reset 1 changed option" }).click();
  await expect(noise).toHaveValue("0.567");
  await expect(page.getByRole("button", { name: /Reset \d+ changed/ })).toHaveCount(0);

  await noise.fill("0.3");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Settings" }).click();
  const row = page.getByRole("row", { name: /^Noise / });
  await expect(row).toContainText("0.3");
  await expect(row).toContainText("changed");
  await expect(row).toContainText("0.567");
});
