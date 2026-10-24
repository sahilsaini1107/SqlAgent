/* Real browser -> HTTP -> LangGraph -> SQLite checks with the SCRIPTED model fixture.
 * Start scripts.e2e_fixture on port 8012 first. No real model accuracy is claimed.
 * PLAYWRIGHT_MODULE may point to an existing Playwright installation.
 */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8012';
const output = path.resolve(__dirname, '../../../tmp/browser-audit');
fs.mkdirSync(output, { recursive: true });
const checks = [];
let page;
async function check(name, fn) {
  try { await fn(); checks.push({ name, status: 'PASS' }); }
  catch (e) {
    checks.push({ name, status: 'FAIL', error: String(e) });
    await page.screenshot({ path: path.join(output, `failure-${checks.length}.png`) });
  }
  console.log(JSON.stringify(checks.at(-1)));
}
async function send(text) {
  await page.locator('textarea').fill(text);
  const response = page.waitForResponse(r => r.url().endsWith('/api/chat/stream'));
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  const body = await (await response).text();
  assert.match(body, /event: start/);
  assert.match(body, /event: stage/);
  const block = body.split('\n\n').find(s => s.startsWith('event: result'));
  assert(block, 'stream must end with a result event');
  await page.getByRole('button', { name: 'Send', exact: true }).waitFor();
  return JSON.parse(block.split('\ndata: ')[1]);
}
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] });
  page = await context.newPage();
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  try {
    await page.goto(base);
    await check('Initial UI and API connectivity', async () => {
      await page.getByText('Connected', { exact: true }).waitFor();
      assert.equal(await page.title(), 'SQL Agent');
    });
    let first;
    await check('Streaming, loading, generation, explanation and real database results', async () => {
      first = await send('List warehouses');
      assert.equal(first.status, 'executed');
      assert(first.validation.passed);
      assert(first.result.row_count > 3);
      assert(first.explanation);
      await page.getByText(first.explanation, { exact: true }).waitFor();
      await page.locator('.group\\/sql').first().getByRole('button', { name: 'Copy', exact: true }).waitFor();
    });
    await check('SQL clipboard', async () => {
      await page.locator('.group\\/sql').first().getByRole('button', { name: 'Copy', exact: true }).click();
      assert.match(await page.evaluate(() => navigator.clipboard.readText()), /SELECT/);
    });
    await check('SQL download', async () => {
      const download = page.waitForEvent('download');
      await page.locator('.group\\/sql').first().getByRole('button', { name: 'Download', exact: true }).click();
      const item = await download;
      assert.equal(item.suggestedFilename(), 'query.sql');
      await item.saveAs(path.join(output, 'query.sql'));
      assert.match(fs.readFileSync(path.join(output, 'query.sql'), 'utf8'), /warehouses/);
    });
    await check('CSV results download', async () => {
      const download = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download', exact: true }).last().click();
      const item = await download;
      await item.saveAs(path.join(output, 'results.csv'));
      assert.match(fs.readFileSync(path.join(output, 'results.csv'), 'utf8'), /id,name/);
    });
    await check('Follow-up modifies query and preserves conversation ID', async () => {
      const follow = await send('Only the first three');
      assert.equal(follow.conversation_id, first.conversation_id);
      assert.equal(follow.result.row_count, 3);
      assert.match(follow.sql, /LIMIT 3/);
    });
    await check('SQL-only mode skips execution', async () => {
      await page.getByRole('switch').click();
      const r = await send('List warehouses');
      assert.equal(r.status, 'validated');
      assert.equal(r.result, null);
    });
    await check('History survives reload and can be reopened', async () => {
      await page.reload();
      await page.getByRole('button', { name: /^List warehouses/ }).click();
      await page.getByText('Only the first three', { exact: true }).first().waitFor();
    });
    await check('Theme toggles', async () => {
      const before = await page.locator('html').getAttribute('class');
      await page.getByRole('button', { name: 'Toggle theme' }).click();
      assert.notEqual(await page.locator('html').getAttribute('class'), before);
    });
    await check('Out-of-scope refusal', async () => {
      const r = await send('Who won the world cup?');
      assert.equal(r.status, 'refused');
      assert.equal(r.sql, null);
    });
    await check('Destructive request refusal', async () => {
      const r = await send('Delete customers');
      assert.equal(r.status, 'refused');
      assert.equal(r.sql, null);
    });
    await check('Invalid model SQL is blocked after bounded repair', async () => {
      const r = await send('invalid model output');
      assert.equal(r.status, 'validation_failed');
      assert.equal(r.sql, null);
      await page.getByText('FORBIDDEN_OPERATION', { exact: true }).first().waitFor();
    });
    await check('Ambiguity asks a visible question', async () => {
      const r = await send('ambiguous');
      assert.equal(r.status, 'clarification_required');
      assert(r.clarification, 'Missing clarification question');
    });
    await check('Stop button cancels request and displays stopped message', async () => {
      await page.locator('textarea').fill('slow request');
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      await page.getByRole('button', { name: 'Stop', exact: true }).click();
      await page.getByText('Stopped before an answer came back.', { exact: true }).waitFor();
    });
    await check('Provider failure surfaces an error and retry action', async () => {
      await page.locator('textarea').fill('simulate provider failure');
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      await page.getByRole('button', { name: 'Retry', exact: true }).last().waitFor();
      await page.getByRole('button', { name: 'Send', exact: true }).waitFor();
    });
    await check('Cleanly truncated SSE stream displays an error', async () => {
      const before = await page.getByRole('button', { name: 'Retry', exact: true }).count();
      await page.route('**/api/chat/stream', route => route.fulfill({
        status: 200, contentType: 'text/event-stream',
        body: 'event: start\ndata: {"conversation_id":"truncated-stream-test"}\n\n',
      }), { times: 1 });
      await page.locator('textarea').fill('Truncated stream test');
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      await page.getByRole('button', { name: 'Send', exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Retry', exact: true }).count(), before + 1,
        'Stream ended without a result and the UI reported no error');
    });
    await check('Mobile composer and sidebar remain usable', async () => {
      const desktop = page;
      page = await context.newPage();
      page.setDefaultTimeout(10000);
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(base);
      assert(await page.locator('textarea').isVisible());
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const r = await send('List warehouses on mobile');
      assert.equal(r.status, 'validated');
      await page.getByRole('button', { name: /Toggle sidebar/ }).click();
      await page.getByRole('button', { name: 'Close sidebar', exact: true }).click();
      await page.screenshot({ path: path.join(output, 'mobile.png') });
      await page.close();
      page = desktop;
    });
    await check('No browser runtime exceptions', async () => assert.deepEqual(errors, []));
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: path.join(output, 'desktop.png') });
  } finally {
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(checks, null, 2));
    await browser.close();
  }
  process.exitCode = checks.some(c => c.status === 'FAIL') ? 1 : 0;
})().catch(e => { console.error(e); process.exitCode = 1; });
