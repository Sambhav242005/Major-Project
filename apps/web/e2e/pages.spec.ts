import { test, expect, type Page } from "@playwright/test";

// Fail the test on any uncaught page error or console error.
test.beforeEach(async ({ page }) => {
  page.on("pageerror", (err) => {
    throw new Error(`Uncaught page error: ${err.message}`);
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      throw new Error(`Console error: ${msg.text()}`);
    }
  });
});

// Use an actual account; forged development cookies must not authenticate.
async function signIn(page: Page) {
  test.skip(!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD, "Supply a real test account through environment variables.");
  await page.goto("/auth/signin");
  await page.getByLabel("Email", { exact: true }).fill(process.env.E2E_EMAIL!);
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/dashboard$/);
}

test.describe("App pages", () => {
  test.describe.configure({ mode: "serial" });

  test("dashboard renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("AI Knowledge Graph Builder")).toBeVisible();
  });

  test("documents page renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/documents");
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/documents$/);
    await expect(page.getByRole("heading", { name: "Document Library" })).toBeVisible();
  });

  test("graph page renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/graph");
    await expect(page).toHaveURL(/\/graph$/);
  });

  test("agents page renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/agents");
    await expect(page).toHaveURL(/\/agents$/);
  });

  test("mcp page renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/mcp");
    await expect(page).toHaveURL(/\/mcp$/);
  });

  test("chat page renders", async ({ page }) => {
    await signIn(page);
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/chat$/);
  });

  test("header navigation works", async ({ page }) => {
    await signIn(page);
    await page.goto("/dashboard");

    // Go to documents via header link
    await page.getByRole("link", { name: /documents/i }).first().click();
    await page.waitForURL(/\/documents$/);
    await expect(page).toHaveURL(/\/documents$/);
  });
});
