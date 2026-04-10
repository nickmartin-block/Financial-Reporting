/**
 * E2E test for Finance Copilot dashboard
 * Tests the deployed CDN URL and the local file for rendering issues.
 * Run: node tests/e2e.mjs
 */
import { chromium } from 'playwright';

const CDN_URL = 'https://finance-copilot-v2.vibeplatstage.squarecdn.com/';
const LOCAL_URL = `file://${process.cwd()}/public/index.html`;

const results = { passed: 0, failed: 0, errors: [] };

function pass(name) { results.passed++; console.log(`  ✓ ${name}`); }
function fail(name, err) { results.failed++; results.errors.push({ name, err }); console.log(`  ✗ ${name}: ${err}`); }

async function runTests() {
  const browser = await chromium.launch({ headless: true });

  for (const [label, url] of [['CDN', CDN_URL], ['Local', LOCAL_URL]]) {
    console.log(`\n--- Testing ${label}: ${url} ---`);
    const context = await browser.newContext();
    const page = await context.newPage();

    // Collect console messages and errors
    const logs = [];
    const jsErrors = [];
    page.on('console', msg => logs.push({ type: msg.type(), text: msg.text() }));
    page.on('pageerror', err => jsErrors.push(err.message));

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
    } catch(e) {
      await page.goto(url, { waitUntil: 'load', timeout: 15000 });
    }

    // Wait for init to complete
    await page.waitForTimeout(3000);

    // Test 1: Page title
    const title = await page.title();
    title === 'Finance Copilot' ? pass(`${label}: Page title correct`) : fail(`${label}: Page title`, `Got "${title}"`);

    // Test 2: No JS errors
    if (jsErrors.length === 0) {
      pass(`${label}: No JavaScript errors`);
    } else {
      fail(`${label}: JavaScript errors`, jsErrors.join('; '));
    }

    // Test 3: Chart.js loaded
    const chartLoaded = await page.evaluate(() => typeof Chart === 'function');
    chartLoaded ? pass(`${label}: Chart.js loaded`) : fail(`${label}: Chart.js not loaded`);

    // Test 4: Loading overlay hidden
    const overlayHidden = await page.evaluate(() => {
      const el = document.getElementById('loadingOverlay');
      return el && el.classList.contains('hidden');
    });
    overlayHidden ? pass(`${label}: Loading overlay hidden`) : fail(`${label}: Loading overlay visible`);

    // Test 5: All key DOM elements exist
    const elements = ['kpi-gpv-value', 'kpi-actives-value', 'chart-rule-of-40',
                       'chart-vp-gp-yoy', 'chart-aoi-margin', 'chart-inflows-build',
                       'chart-inflows-weekly', 'chart-actives-weekly', 'chart-banking-actives',
                       'card-digest', 'card-stock', 'card-goals', 'card-news',
                       'chart-gpv-country', 'chart-gpv-weekly-yoy'];
    const missing = [];
    for (const id of elements) {
      const exists = await page.evaluate(id => !!document.getElementById(id), id);
      if (!exists) missing.push(id);
    }
    missing.length === 0 ? pass(`${label}: All 15 tile DOM elements exist`) : fail(`${label}: Missing elements`, missing.join(', '));

    // Test 6: Navigation tabs work
    await page.click('button:has-text("CHAT")');
    const chatVisible = await page.evaluate(() => document.getElementById('tab-chat').classList.contains('active'));
    chatVisible ? pass(`${label}: Chat tab navigation works`) : fail(`${label}: Chat tab not activated`);

    await page.click('button:has-text("DASHBOARD")');
    const dashVisible = await page.evaluate(() => document.getElementById('tab-dashboard').classList.contains('active'));
    dashVisible ? pass(`${label}: Dashboard tab navigation works`) : fail(`${label}: Dashboard tab not activated`);

    // Test 6b: Chat tab has query cards
    await page.click('button:has-text("CHAT")');
    const queryCards = await page.evaluate(() => document.querySelectorAll('.query-card').length);
    queryCards >= 4 ? pass(`${label}: Chat tab has ${queryCards} query cards`) : fail(`${label}: Chat tab missing query cards (found ${queryCards})`);

    // Test 6c: IR Hub tab has Glean link
    await page.click('button:has-text("IR HUB")');
    const gleanLink = await page.evaluate(() => {
      const links = document.querySelectorAll('#tab-irhub a');
      return Array.from(links).some(a => a.href && a.href.includes('glean.com'));
    });
    gleanLink ? pass(`${label}: IR Hub tab has Glean agent link`) : fail(`${label}: IR Hub tab missing Glean link`);

    // Test 6d: Feedback form elements
    const feedbackElements = await page.evaluate(() => {
      return {
        textarea: !!document.getElementById('feedback-description'),
        submit: !!document.getElementById('feedback-submit'),
      };
    });
    (feedbackElements.textarea && feedbackElements.submit) ? pass(`${label}: Feedback form elements present`) : fail(`${label}: Missing feedback form elements`);

    await page.click('button:has-text("DASHBOARD")');

    // Test 7: Key functions defined
    const functions = ['snowflakeQuery', 'parseSnowflakeRows', 'fetchSquareGPV',
                       'fetchMMA', 'fetchHexagonFinancial', 'refreshData', 'renderFromData',
                       'renderLineChart', 'renderBarLineChart', 'buildKPIFromRows',
                       'fetchDigest', 'fetchGoals', 'fetchStock', 'fetchNews',
                       'renderDigest', 'renderStock', 'renderGoals', 'renderNews',
                       'submitQuery', 'renderQueryResult', 'submitFeedback'];
    const missingFns = [];
    for (const fn of functions) {
      const exists = await page.evaluate(fn => typeof window[fn] === 'function', fn);
      if (!exists) missingFns.push(fn);
    }
    missingFns.length === 0 ? pass(`${label}: All ${functions.length} functions defined`) : fail(`${label}: Missing functions`, missingFns.join(', '));

    // Test 8: STS meta tag present and replaced
    const stsContent = await page.evaluate(() => {
      const meta = document.querySelector('meta[name="sts-client-id"]');
      return meta ? meta.getAttribute('content') : null;
    });
    if (stsContent && stsContent.indexOf('__') !== 0) {
      pass(`${label}: STS client ID injected (${stsContent.slice(0, 8)}...)`);
    } else if (stsContent === '__STS_CLIENT_ID__') {
      pass(`${label}: STS placeholder present (not yet deployed — expected for local)`);
    } else {
      fail(`${label}: STS meta tag missing`);
    }

    // Test 9: Error banner state
    const errorBanner = await page.evaluate(() => {
      const el = document.getElementById('errorBanner');
      return { display: el.style.display, text: el.textContent };
    });
    console.log(`  ℹ ${label}: Error banner: display="${errorBanner.display}", text="${errorBanner.text.slice(0, 100)}"`);

    // Test 10: Console log analysis
    const bootLog = logs.find(l => l.text.includes('[Boot]'));
    bootLog ? pass(`${label}: Boot log present`) : fail(`${label}: Boot log missing — init() may not have run`);

    const stsLog = logs.find(l => l.text.includes('[STS]'));
    if (stsLog) console.log(`  ℹ ${label}: STS: ${stsLog.text}`);

    const initLog = logs.find(l => l.text.includes('[Init]'));
    if (initLog) console.log(`  ℹ ${label}: Init: ${initLog.text}`);

    const refreshLog = logs.find(l => l.text.includes('[Refresh]'));
    if (refreshLog) console.log(`  ℹ ${label}: Refresh: ${refreshLog.text}`);

    const queryLogs = logs.filter(l => l.text.includes('[Query'));
    if (queryLogs.length > 0) {
      console.log(`  ℹ ${label}: Query results:`);
      queryLogs.forEach(l => console.log(`      ${l.text}`));
    }

    const errorLogs = logs.filter(l => l.type === 'error');
    if (errorLogs.length > 0) {
      console.log(`  ℹ ${label}: Console errors:`);
      errorLogs.forEach(l => console.log(`      ${l.text}`));
    }

    // Screenshot
    await page.screenshot({ path: `/tmp/copilot-e2e-${label.toLowerCase()}.png`, fullPage: true });
    console.log(`  ℹ ${label}: Screenshot saved to /tmp/copilot-e2e-${label.toLowerCase()}.png`);

    await context.close();
  }

  await browser.close();

  // Summary
  console.log(`\n${'='.repeat(50)}`);
  console.log(`Results: ${results.passed} passed, ${results.failed} failed`);
  if (results.errors.length > 0) {
    console.log('\nFailures:');
    results.errors.forEach(e => console.log(`  ✗ ${e.name}: ${e.err}`));
  }

  process.exit(results.failed > 0 ? 1 : 0);
}

runTests().catch(e => { console.error('Fatal:', e); process.exit(1); });
