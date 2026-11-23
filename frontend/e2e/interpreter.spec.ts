import { expect, test } from "./fixtures";

// The e2e server is started with a stand-in PyPy (playwright.config.ts): it reports PyPy 3.10.14 and
// runs no solver, so a job on PyPy shows that interpreter and its runs end as ERROR.

test("the Solve page starts on Python and a solve on PyPy runs there", async ({ page }) => {
  await page.goto("/solve/n_queens");
  await expect(page.getByRole("radio", { name: "Python", exact: true })).toBeChecked();
  await expect(page.getByRole("radio", { name: /PyPy 3\.10\.14/ })).toBeEnabled();

  // Not chosen: the job runs in its own process and solves for real.
  const python = page.waitForRequest((request) => request.url().endsWith("/api/jobs") && request.method() === "POST");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  expect((await python).postDataJSON().request.interpreter).toBe("python");
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();

  await page.getByText(/PyPy 3\.10\.14/).click();
  const created = page.waitForResponse((response) => response.url().endsWith("/api/jobs") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Solve", exact: true }).click();
  const response = await created;
  expect(response.request().postDataJSON().request.interpreter).toBe("pypy");

  const id = (await response.json()).id;
  await expect
    .poll(async () => (await (await page.request.get(`/api/jobs/${id}`)).json()).environment?.python_implementation)
    .toBe("PyPy");
  const detail = await (await page.request.get(`/api/jobs/${id}`)).json();
  expect(detail.request.interpreter).toBe("pypy");
  expect(detail.environment.python_version).toBe("3.10.14");

  // The job list marks it (INTERP-4).
  await page.goto("/jobs");
  await expect(page.getByRole("row", { name: new RegExp(`\\bJ${id}\\b`) }).getByText("PyPy", { exact: true })).toBeVisible();
});

test("the benchmark builder starts on Python and sends the choice", async ({ page }) => {
  await page.goto("/benchmarks/new");
  await expect(page.getByRole("radio", { name: "Python", exact: true })).toBeChecked();

  await page.getByText(/PyPy 3\.10\.14/).click();
  await expect(page.getByRole("radio", { name: /PyPy 3\.10\.14/ })).toBeChecked();
  const started = page.waitForRequest((request) => request.url().endsWith("/api/jobs") && request.method() === "POST");
  await page.getByRole("button", { name: "Start benchmark" }).click();
  expect((await started).postDataJSON().request.interpreter).toBe("pypy");
  await expect(page).toHaveURL(/\/benchmarks\/\d+$/);
  await page.getByRole("tab", { name: /Setup/ }).click();
  await expect(page.getByText("Run with", { exact: true })).toBeVisible();
  await expect(page.getByText("PyPy", { exact: true })).toBeVisible(); // the "Run with" fact

  // Leaving and coming back starts on Python again: the choice is not remembered.
  await page.goto("/benchmarks/new");
  await expect(page.getByRole("radio", { name: "Python", exact: true })).toBeChecked();
});
