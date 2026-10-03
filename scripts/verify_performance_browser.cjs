// Synthetic local server only. Never click a Provider connection-test/AI button.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require(process.env.C2C_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.C2C_BASE_URL || 'http://127.0.0.1:8855';
const localHosts = new Set(['localhost', '127.0.0.1', '[::1]']);
assert(localHosts.has(new URL(base).hostname), 'Requires a synthetic local server');
const results = [];
let stage = 'startup';

// Read only top-level message types; do not retain any WebSocket business payload.
function fields(buf) {
  const out = []; let i = 0;
  function v() {
    let n = 0, s = 0;
    while (i < buf.length) {
      const b = buf[i++]; n += (b & 127) * 2 ** s;
      if (!(b & 128)) return n;
      s += 7; if (s > 49) throw Error('varint');
    }
    throw Error('varint');
  }
  try {
    while (i < buf.length) {
      const k = v(); out.push(k >> 3);
      const t = k & 7;
      if (t === 0) v(); else if (t === 1) i += 8;
      else if (t === 2) { const size = v(); i += size; } else if (t === 5) i += 4; else break;
    }
  } catch {}
  return out;
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.C2C_CHROMIUM ? { executablePath: process.env.C2C_CHROMIUM } : {}),
  });
  try {
    const context = await browser.newContext();
    await context.route('**/*', route => localHosts.has(new URL(route.request().url()).hostname)
      ? route.continue() : route.abort());
    function track(page) {
      const events = []; page._runEvents = events;
      page.on('websocket', ws => ws.on('framereceived', frame => {
        if (!Buffer.isBuffer(frame.payload)) return;
        const kinds = fields(frame.payload);
        if (kinds.includes(4)) events.push('start');
        if (kinds.includes(6)) events.push('finish');
      }));
    }
    async function idle(page) {
      await page.locator('[data-testid="stSidebarNav"]').waitFor();
      let n = -1, same = 0;
      for (let i = 0; i < 150; i++) {
        const now = page._runEvents.length;
        same = now === n ? same + 1 : 0; n = now;
        if (same >= 4 && page._runEvents.at(-1) === 'finish') break;
        await page.waitForTimeout(100);
      }
      assert.equal(await page.locator('[data-testid="stException"]').count(), 0, 'Application exception');
    }
    async function nav(page, label, single = false) {
      const before = page._runEvents.length;
      await page.locator('[data-testid="stSidebarNav"]').getByText(label, { exact: true }).click();
      await idle(page);
      if (single) {
        const events = page._runEvents.slice(before);
        assert.equal(events.filter(x => x === 'start').length, 1, 'Normal navigation starts');
        assert.equal(events.filter(x => x === 'finish').length, 1, 'Normal navigation finishes');
      }
    }
    async function login(page, username) {
      await nav(page, '登录');
      await page.getByRole('textbox', { name: '用户名', exact: true }).first().fill(username);
      await page.getByRole('textbox', { name: '密码', exact: true }).first().fill('synthetic-password-123');
      await page.getByRole('button', { name: '登录', exact: true }).click();
      await page.getByRole('button', { name: '退出登录', exact: true }).waitFor();
      await idle(page);
    }
    async function check(name, fn) {
      stage = name; await fn(); results.push({ test: name, result: 'PASS' });
    }
    const page = await context.newPage(); track(page);
    await page.goto(base + '/analysis'); await idle(page);
    await check('GUEST_DEEP_LINK', async () => {
      assert.equal(await page.getByRole('heading', { name: '个人分析', exact: true }).count(), 1);
      assert.equal(await page.getByRole('heading', { name: '使用流程', exact: true }).count(), 0);
    });
    await check('NORMAL_NAVIGATION_SINGLE_RUN_AND_NO_STALE_BODY', async () => {
      for (let run = 0; run < 3; run++) {
        for (const label of ['登录', '个人分析', '我的 AI Provider', 'AI额度', '会员方案', '首页']) {
          stage = `NORMAL_NAVIGATION_${label}_${run}`;
          await nav(page, label, true);
          if (label !== '首页') assert.equal(await page.getByRole('heading', { name: '使用流程', exact: true }).count(), 0);
          if (label !== '个人分析') assert.equal(await page.getByRole('textbox', { name: '目标岗位JD', exact: true }).count(), 0);
        }
      }
    });
    await login(page, 'audit_byok');
    await check('AUTHENTICATED_DEEP_LINK_F5_NEW_TAB', async () => {
      const tab = await context.newPage(); track(tab);
      await tab.goto(base + '/analysis'); await idle(tab);
      assert.equal(await tab.getByRole('button', { name: '退出登录', exact: true }).count(), 1);
      assert.equal(await tab.getByRole('heading', { name: '个人分析', exact: true }).count(), 1);
      await tab.reload(); await idle(tab);
      assert.equal(await tab.getByRole('button', { name: '退出登录', exact: true }).count(), 1);
      await tab.close();
    });
    await check('A_GUEST_B_ACCOUNT_AND_INPUT_ISOLATION', async () => {
      await nav(page, '个人分析');
      await page.getByRole('textbox', { name: '目标岗位JD', exact: true }).fill('synthetic-private-A-JD');
      await page.getByRole('heading', { name: '个人分析', exact: true }).click(); await idle(page);
      await nav(page, '我的 AI Provider');
      assert.equal(await page.getByText('状态：已配置', { exact: true }).count(), 10);
      await page.getByRole('textbox', { name: '模型 ID', exact: true }).first().fill('synthetic-private-A-model');
      await page.getByRole('button', { name: '退出登录', exact: true }).click(); await idle(page);
      assert.equal(await page.getByText('状态：已配置', { exact: true }).count(), 0);
      await nav(page, '个人分析');
      assert.equal(await page.getByRole('textbox', { name: '目标岗位JD', exact: true }).inputValue(), '');
      await login(page, 'audit_user');
      await nav(page, '个人分析');
      assert.equal(await page.getByRole('textbox', { name: '目标岗位JD', exact: true }).inputValue(), '');
      await nav(page, '我的 AI Provider');
      if (await page.getByRole('button', { name: '启用开发者模式', exact: true }).count()) {
        await page.getByRole('button', { name: '启用开发者模式', exact: true }).click(); await idle(page);
      }
      assert.equal(await page.getByText('状态：已配置', { exact: true }).count(), 0);
      const models = await page.getByRole('textbox', { name: '模型 ID', exact: true }).evaluateAll(nodes => nodes.map(node => node.value));
      assert(!models.includes('synthetic-private-A-model'));
      await page.getByRole('button', { name: '关闭开发者模式', exact: true }).click(); await idle(page);
      await page.getByRole('button', { name: '退出登录', exact: true }).click(); await idle(page);
    });
    await login(page, 'audit_byok');
    await check('BYOK_DISABLE_AND_REENABLE', async () => {
      await nav(page, '我的 AI Provider');
      await page.getByRole('button', { name: '关闭开发者模式', exact: true }).click(); await idle(page);
      await nav(page, '个人分析');
      assert.equal(await page.getByText('开发者API Key', { exact: true }).count(), 0);
      await nav(page, '我的 AI Provider');
      await page.getByRole('button', { name: '启用开发者模式', exact: true }).click(); await idle(page);
      assert.equal(await page.getByText('状态：已配置', { exact: true }).count(), 10);
    });
    await check('DUAL_TAB_LOGOUT_REJECTED_ON_NEXT_ACTION', async () => {
      const tab = await context.newPage(); track(tab);
      await tab.goto(base + '/analysis'); await idle(tab);
      assert.equal(await tab.getByRole('button', { name: '退出登录', exact: true }).count(), 1);
      await page.getByRole('button', { name: '退出登录', exact: true }).click(); await idle(page);
      await nav(tab, '我的 AI Provider');
      await tab.getByRole('button', { name: '退出登录', exact: true }).waitFor({ state: 'hidden', timeout: 15000 });
      await idle(tab);
      assert.equal(await tab.getByText('状态：已配置', { exact: true }).count(), 0);
      await tab.reload(); await idle(tab);
      assert.equal(await tab.getByRole('button', { name: '退出登录', exact: true }).count(), 0);
      await tab.close();
    });
    await check('INVALID_TOKEN_FAILS_CLOSED', async () => {
      const invalid = await browser.newContext();
      await invalid.addInitScript(() => localStorage.setItem('c2c_auth_session', 'A'.repeat(43)));
      const tab = await invalid.newPage(); track(tab);
      await tab.goto(base + '/developer'); await idle(tab);
      assert.equal(await tab.getByRole('button', { name: '退出登录', exact: true }).count(), 0);
      assert.equal(await tab.getByText('状态：已配置', { exact: true }).count(), 0);
      await invalid.close();
    });
  } catch (error) {
    results.push({ test: stage, result: 'FAIL', error: error.name, reason: error.code === 'ERR_ASSERTION' ? error.message : 'Browser action failed' }); process.exitCode = 1;
  } finally {
    await browser.close();
    const report = JSON.stringify(results, null, 2);
    if (process.env.C2C_BROWSER_REPORT) fs.writeFileSync(process.env.C2C_BROWSER_REPORT, report);
    console.log(report);
  }
})();
