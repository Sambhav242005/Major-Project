import { test, expect, type Page } from "@playwright/test";

// Fail the test on any uncaught page error or console error — this is what
// catches swallowed runtime issues like the LazyMotion/motion strict-mode throw.
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

// Real account credentials are provided only via the test environment.
async function signIn(page: Page) {
  await page.goto("/auth/signin");
  await page.getByLabel("Email", { exact: true }).fill(process.env.E2E_EMAIL!);
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/dashboard$/);
  await page.getByRole("heading", { name: "Dashboard" }).waitFor();
}

test.describe("Auth flow", () => {
  test("signin page renders with expected elements", async ({ page }) => {
    await page.goto("/auth/signin");
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /try demo/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("signup page renders", async ({ page }) => {
    await page.goto("/auth/signup");
    await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
  });

  test("demo authentication cannot issue a session", async ({ request }) => {
    const response = await request.post("/auth/demo-login");
    expect(response.status()).toBe(404);
    expect(response.headers()["set-cookie"]).toBeUndefined();
  });

  test("real account signs in", async ({ page }) => {
    test.skip(!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD, "Supply a real test account through environment variables.");
    await signIn(page);
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("protected route redirects to signin when not logged in", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/auth\/signin/);
    await expect(page).toHaveURL(/\/auth\/signin/);
  });

  test("sign out returns to signin", async ({ page }) => {
    test.skip(!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD, "Supply a real test account through environment variables.");
    await signIn(page);
    // Sign out button lives in the nav bar on app pages
    await page.getByRole("button", { name: /sign out/i }).click();
    await page.waitForURL(/\/auth\/signin/);
    await expect(page).toHaveURL(/\/auth\/signin/);
  });
});
