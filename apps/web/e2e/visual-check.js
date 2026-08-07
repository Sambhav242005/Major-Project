const { chromium } = require('playwright');
const path = require('path');

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
const BASE = 'http://localhost:3000';

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  // Set mock session cookie
  await context.addCookies([
    { name: 'mock-session', value: 'mock-user-001', url: BASE },
  ]);

  const pages = [
    { name: 'signin', url: '/auth/signin', auth: false },
    { name: 'signup', url: '/auth/signup', auth: false },
    { name: 'dashboard', url: '/dashboard', auth: true },
    { name: 'documents', url: '/documents', auth: true },
    { name: 'graph', url: '/graph', auth: true },
    { name: 'agents', url: '/agents', auth: true },
    { name: 'mcp', url: '/mcp', auth: true },
    { name: 'chat', url: '/chat', auth: true },
  ];

  for (const p of pages) {
    const page = await context.newPage();
    await page.goto(`${BASE}${p.url}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    const filePath = path.join(SCREENSHOT_DIR, `${p.name}.png`);
    await page.screenshot({ path: filePath, fullPage: true });
    console.log(`Screenshot: ${p.name}.png`);
    await page.close();
  }

  await browser.close();
  console.log('Done - all screenshots saved to e2e/screenshots/');
})();
