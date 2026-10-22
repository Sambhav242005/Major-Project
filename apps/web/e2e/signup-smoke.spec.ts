import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("new user signs up, creates a workspace, reaches dashboard, and signs out", async ({ page }) => {
  const email = `release-signup-${randomUUID()}@akgb.invalid`;
  const password = `${randomUUID()}-Akgb!`;
  page.on("pageerror", (error) => { throw error; });
  await page.goto("/auth/signup");
  await page.getByLabel("Full name", { exact: true }).fill("Release signup validation");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  const registered = page.waitForResponse((response) => response.url().endsWith("/auth/local-signup") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  expect((await registered).ok()).toBeTruthy();
  await page.waitForURL(/\/dashboard$/);
  await page.getByRole("link", { name: "Create your first project", exact: true }).click();
  await page.getByRole("button", { name: "New Project", exact: true }).first().click();
  await page.getByPlaceholder("Project name", { exact: true }).fill("Signup validation workspace");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByText("Signup validation workspace", { exact: true }).last()).toBeVisible();
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.waitForURL(/\/auth\/signin/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/auth\/signin/);
});
