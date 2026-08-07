import { test, expect, type Page } from "@playwright/test";

// Helper: set mock session cookie for the test context
async function mockLogin(page: Page) {
  await page.context().addCookies([
    { name: "mock-session", value: "mock-user-001", url: "http://localhost:3000" },
  ]);
}

test.describe("App pages", () => {
  test.describe.configure({ mode: "serial" });

  test("dashboard renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("AI Knowledge Graph Builder")).toBeVisible();
  });

  test("documents page renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/documents");
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/documents$/);
    await expect(page.getByRole("heading", { name: "Document Library" })).toBeVisible();
  });

  test("graph page renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/graph");
    await expect(page).toHaveURL(/\/graph$/);
  });

  test("agents page renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/agents");
    await expect(page).toHaveURL(/\/agents$/);
  });

  test("mcp page renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/mcp");
    await expect(page).toHaveURL(/\/mcp$/);
  });

  test("chat page renders", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/chat$/);
  });

  test("sidebar navigation works", async ({ page }) => {
    await mockLogin(page);
    await page.goto("/dashboard");

    // Go to documents via sidebar link
    await page.getByRole("link", { name: /documents/i }).first().click();
    await page.waitForURL(/\/documents$/);
    await expect(page).toHaveURL(/\/documents$/);
  });
});