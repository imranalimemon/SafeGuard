// Reproduce: node tools/qa_security.cjs <playwright-module-dir> <temporary-auth.json>
const { chromium } = require(process.argv[2]);
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const auth = JSON.parse(fs.readFileSync(process.argv[3], 'utf8').replace(/^\uFEFF/, ''));
  const output = path.resolve('docs/evidence/phase1');
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'SafeGuard sign in' }).waitFor();
    await page.screenshot({ path: path.join(output, 'login.png') });
    await page.getByLabel('Username').fill('admin');
    await page.getByLabel('Password').fill(auth.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByRole('button', { name: 'Sign out' }).waitFor();
    await page.waitForTimeout(1500);
    const health = await page.request.get('http://127.0.0.1:5173/api/health');
    if (health.status() !== 200) throw Error('Authenticated health failed');
    await page.screenshot({ path: path.join(output, 'authenticated.png') });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Sign out' }).waitFor();
    await page.getByRole('button', { name: 'Sign out' }).click();
    await page.getByRole('heading', { name: 'SafeGuard sign in' }).waitFor();
    const denied = await page.request.get('http://127.0.0.1:5173/api/violations');
    if (denied.status() !== 401 || errors.length) throw Error(JSON.stringify({ denied: denied.status(), errors }));
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify({ command: 'node tools/qa_security.cjs <Playwright directory> <temporary auth.json>', login: 'pass', authenticated_health: await health.json(), reload_session: 'pass', logout_revokes_access: 'pass', page_errors: errors }, null, 2));
    console.log('PASS: real-browser login, authenticated health, reload, logout and access denial; no page errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
