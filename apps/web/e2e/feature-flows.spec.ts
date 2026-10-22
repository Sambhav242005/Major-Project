import { expect, test, type BrowserContext, type Page } from "@playwright/test";

test.describe("Real deployed feature flows", () => {
  test.describe.configure({ mode: "serial" });
  let cookies: Awaited<ReturnType<BrowserContext["cookies"]>> = [];
  const projectName = `Release QA ${Date.now()}`;

  async function openOwnProject(page: Page, route: string) {
    await page.goto("/projects");
    await page.locator(".glow-card p").filter({ hasText: projectName }).first().click();
    if (route !== "/projects") await page.locator(`a[href="${route}"]`).first().click();
  }

  test.beforeAll(async ({ browser }) => {
    test.skip(!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD, "Real private credentials are required.");
    const context = await browser.newContext({ ignoreHTTPSErrors: process.env.E2E_ALLOW_SELF_SIGNED === "true" });
    const page = await context.newPage();
    const base = process.env.E2E_BASE_URL || "http://localhost:3000";
    await page.goto(`${base}/auth/signin`);
    await page.getByLabel("Email", { exact: true }).fill(process.env.E2E_EMAIL!);
    await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD!);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL(/\/dashboard$/);
    await page.goto(`${base}/projects`);
    await page.getByRole("button", { name: "New Project", exact: true }).first().click();
    await page.getByPlaceholder("Project name", { exact: true }).fill(projectName);
    const created = page.waitForResponse((response) => response.url().includes("/projects") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    expect((await created).ok()).toBeTruthy();
    await expect(page.getByText(projectName, { exact: true }).last()).toBeVisible();
    cookies = await context.cookies();
    await context.close();
  });

  test.beforeEach(async ({ page, context }) => {
    await context.addCookies(cookies);
    page.on("pageerror", (error) => { throw error; });
  });

  test("every protected feature route renders against the real backend", async ({ page }) => {
    const routes: [string, string][] = [["/dashboard", "AI Knowledge Graph Builder"], ["/projects", "Projects"], ["/documents", "Document Library"], ["/chat", "Chat"], ["/graph", "Knowledge Graph Explorer"], ["/agents", "Agents"], ["/meetings", "Meetings"], ["/mcp", "MCP Connections"], ["/webhooks", "Webhooks"]];
    for (const [route, heading] of routes) {
      await openOwnProject(page, route);
      await expect(page.getByRole("heading", { name: heading, exact: true, level: 1 })).toBeVisible();
      await expect(page.getByText("Application error", { exact: false })).toHaveCount(0);
    }
    await openOwnProject(page, "/dashboard");
    await expect(page.getByText("Document Processing", { exact: true })).toBeVisible();
    await expect(page.getByText("All systems operational", { exact: true })).toHaveCount(0);
  });

  test("project rename persists and unsupported deletion stays disabled", async ({ page }) => {
    await openOwnProject(page, "/projects");
    const card = page.locator(".glow-card").filter({ has: page.getByText(projectName, { exact: true }) });
    await expect(card.getByRole("button", { name: "Project deletion unavailable" })).toBeDisabled();
    await card.getByRole("button").first().click();
    const editor = page.locator(".glow-card").filter({ has: page.getByRole("heading", { name: "Rename Project", exact: true }) });
    await editor.getByRole("textbox").fill(`${projectName} reviewed`);
    const saved = page.waitForResponse((response) => response.url().includes("/projects/") && response.request().method() === "PATCH");
    await editor.getByRole("button", { name: "Save", exact: true }).click();
    expect((await saved).ok()).toBeTruthy();
    await page.reload();
    await expect(page.getByText(`${projectName} reviewed`, { exact: true }).last()).toBeVisible();
  });

  test("MCP configuration creates, edits, and deletes with real response envelopes", async ({ page }) => {
    await openOwnProject(page, "/mcp");
    await expect(page.getByRole("heading", { name: "AKGB read-only MCP endpoint" })).toBeVisible();
    await page.getByRole("button", { name: "Add Connection" }).click();
    await page.getByRole("button", { name: "Receiver", exact: true }).click();
    await page.getByPlaceholder("Connection name", { exact: true }).fill("Release QA receiver");
    const created = page.waitForResponse((response) => response.url().includes("/mcp/connections") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    const record = await (await created).json();
    expect(record.connection.direction).toBe("receiver");
    let card = page.locator(".glow-card").filter({ has: page.getByRole("heading", { name: "Release QA receiver", exact: true }) });
    await expect(card.getByRole("button", { name: "Test connection" })).toBeDisabled();
    await card.getByRole("button", { name: "Edit", exact: true }).click();
    await card.getByPlaceholder("Connection name").fill("Release QA receiver edited");
    await card.getByRole("button", { name: "Save", exact: true }).click();
    card = page.locator(".glow-card").filter({ has: page.getByRole("heading", { name: "Release QA receiver edited", exact: true }) });
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "Delete Release QA receiver edited", exact: true }).click();
    await expect(card).toHaveCount(0);
  });

  test("agent configuration creates and deletes without claiming a model run", async ({ page }) => {
    await openOwnProject(page, "/agents");
    await page.getByRole("button", { name: "New Agent", exact: true }).click();
    await page.getByPlaceholder("e.g. Research Bot").fill("Release QA summarizer");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Release QA summarizer", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Delete Release QA summarizer", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Release QA summarizer", exact: true })).toHaveCount(0);
  });

  test("meeting history loads and unsupported automatic import is explained", async ({ page }) => {
    await openOwnProject(page, "/meetings");
    await expect(page.getByRole("heading", { name: "Saved meeting analyses", exact: true })).toBeVisible();
    await expect(page.getByText("No saved analyses in this project yet.", { exact: true })).toBeVisible();
    const refreshed = page.waitForResponse((response) => response.url().includes("/api/meetings?") && response.request().method() === "GET");
    await page.getByRole("button", { name: "Refresh history", exact: true }).click();
    expect((await refreshed).ok()).toBeTruthy();
    await page.goto("/mcp");
    await expect(page.getByText(/Automatic Google Meet import is unavailable/)).toBeVisible();
  });

  test("webhook form only advertises emitted events and rejects insecure destinations", async ({ page }) => {
    await openOwnProject(page, "/webhooks");
    await page.getByRole("button", { name: "Add Subscription", exact: true }).click();
    await expect(page.locator("select option")).toHaveText(["document.processed", "document.failed", "chat.completed", "entity.extracted"]);
    await page.getByPlaceholder("https://your-webhook-url.com/hook").fill("http://example.com/hook");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Use a public HTTPS endpoint." })).toBeVisible();
    const destination = "https://example.com/akgb-release-qa";
    await page.getByPlaceholder("https://your-webhook-url.com/hook").fill(destination);
    const created = page.waitForResponse((response) => response.url().includes("/webhooks/subscriptions") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Create", exact: true }).click();
    expect((await created).ok()).toBeTruthy();
    const card = page.locator(".glow-card").filter({ has: page.getByText(destination, { exact: true }) });
    await expect(card).toBeVisible();
    const toggled = page.waitForResponse((response) => response.url().includes("/webhooks/subscriptions/") && response.request().method() === "PATCH");
    await card.getByRole("button").first().click();
    expect((await toggled).ok()).toBeTruthy();
    // Remove the subscription before generating events; this test sends no
    // delivery to the external destination.
    await card.getByRole("button").last().click();
    await expect(card).toHaveCount(0);
  });

  test("real document upload reaches processed status with chunks", async ({ page }) => {
    test.skip(process.env.E2E_RUN_GENERATION !== "true", "Requires completed model authorization.");
    test.setTimeout(240000);
    await openOwnProject(page, "/documents");
    const uploaded = page.waitForResponse((response) => response.url().includes("/documents") && response.request().method() === "POST");
    await page.locator('input[type="file"]').setInputFiles({ name: "release-qa-source.txt", mimeType: "text/plain", buffer: Buffer.from("Orion is the codename of the Release QA project. Mira Patel owns the Orion launch. The approved launch date is 22 October 2026. Nebula Research maintains the documentation. Its office is in Indore. This is a synthetic release-validation fixture, not research evidence.") });
    const response = await uploaded;
    expect(response.ok()).toBeTruthy();
    const { id } = await response.json();
    const projectId = new URL(response.url()).searchParams.get("project_id");
    expect(projectId).toBeTruthy();
    const sessionResponse = await page.request.get("/auth/local-session");
    const session = (await sessionResponse.json()).session;
    await expect.poll(async () => {
      const result = await page.request.get(`/api/documents/${id}?project_id=${encodeURIComponent(projectId!)}`, { headers: { Authorization: `Bearer ${session.access_token}` } });
      return (await result.json()).status;
    }, { timeout: 180000, intervals: [3000] }).toBe("processed");
    await page.locator(`a[href="/documents/${id}"]`).click();
    await expect(page.locator('[data-slot="card-title"]').filter({ hasText: /Chunks \([1-9]/ })).toBeVisible();
    await expect(page.getByText("Processing Error", { exact: true })).toHaveCount(0);
    const graphLoaded = page.waitForResponse((response) => response.url().includes("/kb/graph?") && response.request().method() === "GET");
    await page.getByRole("link", { name: "Graph", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Knowledge Graph Explorer", level: 1 })).toBeVisible();
    await expect(page.locator("canvas")).toBeVisible({ timeout: 30000 });
    const graph = await (await graphLoaded).json();
    expect(graph.nodes.length).toBeGreaterThan(0);
    await page.getByPlaceholder("Entity name...").fill(graph.nodes[0].name);
    await page.getByRole("button", { name: "Go", exact: true }).click();
    await expect(page.getByText(/Source sections \([1-9]/)).toBeVisible();
    await expect(page.getByText("release-qa-source.txt", { exact: true }).last()).toBeVisible();
    await page.getByRole("button", { name: "Clear graph", exact: true }).click();
    await expect(page.locator("canvas")).toHaveCount(0);
  });

  test("chat receives an explicit completion from the configured model", async ({ page }) => {
    test.skip(process.env.E2E_RUN_GENERATION !== "true", "Requires completed model authorization.");
    test.setTimeout(180000);
    await openOwnProject(page, "/chat");
    await expect(page.getByRole("textbox")).toBeEnabled();
    await page.getByRole("textbox").fill("What is the codename of the Release QA project in release-qa-source.txt?");
    const completed = page.waitForResponse((response) => response.url().includes("/messages") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const response = await completed;
    expect(response.ok()).toBeTruthy();
    const body = await response.text();
    expect(body).toMatch(/"type"\s*:\s*"done"/);
    expect(body).not.toMatch(/"type"\s*:\s*"error"/);
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible();
    await expect(page.getByText(/Orion/).last()).toBeVisible();
  });
});
