/* Local presentation QA, not a production or Provider test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.C2C_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.C2C_SHOWCASE_URL || 'http://127.0.0.1:8765';
assert(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const out = process.env.C2C_HOME_CAPTURE || 'output/playwright/homepage';
fs.mkdirSync(out, { recursive:true });
const widths = [1440,1280,1024,768,430,390,360];
(async () => {
  const browser = await chromium.launch({ headless:true, ...(process.env.C2C_CHROMIUM ? {executablePath:process.env.C2C_CHROMIUM} : {}) });
  const result = { widths:[], checks:[], errors:[], externalRequests:[] };
  try {
    const context = await browser.newContext();
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== new URL(base).origin) {
        result.externalRequests.push(route.request().url()); return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => result.errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') result.errors.push(message.text()); });
    await page.addInitScript(() => {
      window.qaPerformance = { lcp:0, cls:0, longTasks:0 };
      new PerformanceObserver(list => { window.qaPerformance.lcp = list.getEntries().at(-1).startTime; }).observe({type:'largest-contentful-paint', buffered:true});
      new PerformanceObserver(list => { for (const e of list.getEntries()) if (!e.hadRecentInput) window.qaPerformance.cls += e.value; }).observe({type:'layout-shift', buffered:true});
      new PerformanceObserver(list => { window.qaPerformance.longTasks += list.getEntries().length; }).observe({type:'longtask', buffered:true});
    });
    for (const width of widths) {
      await page.setViewportSize({width,height:width <= 430 ? 844 : 900});
      await page.goto(base, {waitUntil:'networkidle'});
      await page.locator('#case-select:not([disabled])').waitFor();
      await page.waitForTimeout(1000);
      const initialPerformance = await page.evaluate(() => window.qaPerformance);
      const overflow = await page.evaluate(() => ({viewport:innerWidth,scroll:document.documentElement.scrollWidth,headings:[...document.querySelectorAll('h1,h2,h3')].filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)}));
      assert(overflow.scroll <= width, 'Horizontal overflow at ' + width);
      assert.equal(overflow.headings.length,0,'Heading overflow at '+width);
      assert.equal(await page.locator('h1').count(),1);
      await page.screenshot({path:path.join(out,`${width}-hero.png`)});
      for (const section of ['method','example','trust']) {
        await page.locator('#'+section).scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(out,`${width}-${section}.png`)});
      }
      await page.locator('footer').scrollIntoViewIfNeeded();
      await page.locator('.product-view img').evaluate(img => img.decode());
      await page.screenshot({path:path.join(out,`${width}-end.png`)});
      await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
      await page.waitForTimeout(100);
      await page.screenshot({path:path.join(out,`${width}-full.png`),fullPage:true});
      result.widths.push({width,overflow,performance:initialPerformance});
    }
    await page.setViewportSize({width:390,height:844}); await page.goto(base,{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'Python',exact:true}).click();
    assert.equal(await page.locator('.translation-stage').getAttribute('data-selected'),'python');
    assert.equal(await page.getByRole('button',{name:'Python',exact:true}).getAttribute('aria-pressed'),'true');
    assert((await page.locator('[data-trace-caption]').innerText()).includes('Python程序设计'));
    result.checks.push('TRACE_SELECTION');
    for (const [id,score,eligibility] of [['ai-solutions','39.8','未设置／待确认'],['digital-support','41.2','部分满足或待确认'],['data-analysis','50.3','存在硬性门槛']]) {
      await page.selectOption('#case-select',id);
      assert.equal(await page.locator('[data-score]').innerText(),score);
      assert.equal(await page.locator('[data-eligibility]').innerText(),eligibility);
      assert.equal(await page.locator('.evidence-rows details').count(),5);
    }
    result.checks.push('THREE_REAL_RULE_FIXTURES');
    const row = page.locator('.evidence-rows details').nth(1);
    await row.locator('summary').click(); assert(await row.getAttribute('open') !== null);
    result.checks.push('EVIDENCE_EXPAND');
    await page.locator('.mobile-nav summary').click(); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.mobile-nav').getAttribute('open'),null);
    assert.equal(await page.locator('.mobile-nav summary').evaluate(e=>e===document.activeElement),true);
    await page.locator('.mobile-nav summary').click();
    await page.locator('.mobile-nav a[href="#trust"]').click();
    assert.equal(await page.locator('.mobile-nav').getAttribute('open'),null);
    result.checks.push('MOBILE_MENU_ANCHOR_ESCAPE');
    await page.goto(base,{waitUntil:'networkidle'}); await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.className),'skip-link');
    assert.notEqual(await page.locator('.skip-link').evaluate(e=>getComputedStyle(e).outlineStyle),'none');
    await page.keyboard.press('Enter');
    result.checks.push('KEYBOARD_SKIP_FOCUS');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.getByRole('button',{name:'Excel',exact:true}).click();
    assert.equal(await page.locator('.route-signal').evaluate(e=>getComputedStyle(e).animationName),'none');
    result.checks.push('REDUCED_MOTION');
    const nojs = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const fallback=await nojs.newPage(); await fallback.goto(base);
    assert.equal(await fallback.locator('[data-score]').innerText(),'50.3');
    assert.equal(await fallback.locator('#case-select').isDisabled(),true);
    assert.equal(await fallback.getByRole('link',{name:/开始一次分析/}).count(),1);
    result.checks.push('NO_JS_DEFAULT_AND_CTA'); await nojs.close();
    const failure = await context.newPage(); await failure.route('**/demo.json',route=>route.abort());
    await failure.goto(base,{waitUntil:'networkidle'});
    assert.equal(await failure.locator('[data-score]').innerText(),'50.3');
    assert((await failure.locator('[data-example-notice]').innerText()).includes('暂不可用'));
    result.checks.push('DEMO_FETCH_FAILURE_FALLBACK'); await failure.close();
    assert.equal(result.errors.length,0); assert.equal(result.externalRequests.length,0);
    result.checks.push('NO_EXTERNAL_REQUESTS_OR_PAGE_ERRORS');
    result.status='PASS';
  } catch(error) { result.status='FAIL'; result.failure=error.message; process.exitCode=1; }
  finally { fs.writeFileSync(path.join(out,'qa.json'),JSON.stringify(result,null,2)); await browser.close(); console.log(JSON.stringify(result,null,2)); }
})();
