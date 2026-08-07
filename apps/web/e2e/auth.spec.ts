import { test, expect, type Page } from "@playwright/test";

// Helper: authenticate via demo-login route (bypasses Supabase entirely)
async function mockLogin(page: Page) {
  // Hit the demo-login API route directly — sets cookie + redirects
  await page.goto("/auth/demo-login");
  // demo-login returns a redirect; follow it to /dashboard
  await page.waitForURL(/\/dashboard$/);
  await page.waitForLoadState("networkidle");
}

test.describe("Auth flow", () => {
  test("signin page renders with expected elements", async ({ page }) => {
    await page.goto("/auth/signin");
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /try demo/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /continue with google/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("signup page renders", async ({ page }) => {
    await page.goto("/auth/signup");
    await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
  });

  test("demo-login redirects to dashboard", async ({ page }) => {
    await mockLogin(page);
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("protected route redirects to signin when not logged in", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/auth\/signin/);
    await expect(page).toHaveURL(/\/auth\/signin/);
  });

  test("sign out returns to signin", async ({ page }) => {
    await mockLogin(page);
    // Sign out button lives in the nav bar on app pages
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(/\/auth\/signin/);
    await expect(page).toHaveURL(/\/auth\/signin/);
  });
});
