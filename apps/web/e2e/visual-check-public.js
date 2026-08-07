const { chromium } = require('playwright');
const path = require('path');

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
const BASE = 'http://localhost:3000';

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  // Public pages (no auth needed)
  const publicPages = [
    { name: 'home', url: '/' },
    { name: 'contact', url: '/contact' },
    { name: 'terms', url: '/terms' },
    { name: 'demo', url: '/demo' },
    { name: 'signin2', url: '/auth/signin' },
  ];

  for (const p of publicPages) {
    const page = await context.newPage();
    await page.goto(`${BASE}${p.url}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${p.name}.png`), fullPage: true });
    console.log(`Screenshot: ${p.name}.png`);
    await page.close();
  }

  await browser.close();
  console.log('Done');
})();
