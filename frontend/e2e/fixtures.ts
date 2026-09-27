import { test as base, expect } from "@playwright/test";

// The browser logs every failed request as a console error. A 422 is the API
// rejecting a form, which the page shows next to the fields, so it is expected.
const EXPECTED = /Failed to load resource: the server responded with a status of 422/;

/** Every test fails if the page throws or logs an unexpected console error. */
export const test = base.extend<{ browserErrors: string[] }>({
  browserErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
      page.on("console", (message) => {
        if (message.type() === "error" && !EXPECTED.test(message.text())) errors.push(`console: ${message.text()}`);
      });
      await use(errors);
      expect(errors, "browser errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
