/* Review #9: real fixture context, bidirectional trace, keyboard and motion. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.C2C_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.C2C_SHOWCASE_URL || 'http://127.0.0.1:8765';
assert(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const out = process.env.C2C_TRACE_CAPTURE || 'output/playwright/pr9-trace';
fs.mkdirSync(out,{recursive:true});
const fixtures = JSON.parse(fs.readFileSync('showcase/public/demo.json','utf8'));
(async()=>{
 const browser = await chromium.launch({headless:true,...(process.env.C2C_CHROMIUM ? {executablePath:process.env.C2C_CHROMIUM} : {})});
 const result = {checks:[],widths:[],errors:[],externalRequests:[]};
 try {
  const context = await browser.newContext();
  await context.route('**/*', route => {
   if(new URL(route.request().url()).origin !== new URL(base).origin){ result.externalRequests.push(route.request().url());return route.abort(); }
   return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error=>result.errors.push(error.message));
  page.on('console', msg=>{if(msg.type()==='error') result.errors.push(msg.text());});
  for(const width of [1440,1280,1024,768,430,390,360]){
   await page.setViewportSize({width,height:width<=430?844:900});
   await page.goto(base,{waitUntil:'networkidle'});await page.locator('#case-select:not([disabled])').waitFor();
   assert.equal(await page.locator('.mobile-translation').isVisible(),width<=430);
   assert.equal(await page.locator('.translation-stage').isVisible(),width>430);
   const readability = await page.locator('body').evaluate(body=>{
    const selector = '.source-label,.source-type,.target-label span,.confirmation-label,.gate-foot,.desktop-nav a,.header-action,.mobile-nav summary,.rail-label,.mobile-rail p,.translation figcaption,.report-kind,.dimension-name small,.dimension-note,.evidence-status,.source-return,.evidence-rows small,.report-foot,.footer-note,.site-footer nav a';
    return [...body.querySelectorAll(selector)].filter(e=>e.checkVisibility()).map(e=>({text:e.textContent.trim().slice(0,70),size:parseFloat(getComputedStyle(e).fontSize)}));
   });
   assert(readability.every(item=>item.size>=13),'Tiny text at '+width+': '+JSON.stringify(readability.filter(item=>item.size<13)));
   for(const item of fixtures.cases){
    await page.selectOption('#case-select',item.id);
    const dimensions = await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,headings:[...document.querySelectorAll('h1,h2,h3')].filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)}));
    assert(dimensions.scroll<=width && dimensions.headings.length===0,'Case title or content overflow: '+item.id+' at '+width);
   }
   result.widths.push({width,readability});
  }
  result.checks.push('DEDICATED_MOBILE_COMPOSITION_AND_READABLE_LABELS');
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Python',exact:true}).focus();await page.keyboard.press('Space');
  assert.equal(await page.locator('[data-mobile-source]').innerText(),'Python程序设计');
  assert.equal(await page.locator('[data-mobile-target]').innerText(),'Python');
  assert.equal(await page.getByRole('button',{name:'Python',exact:true}).getAttribute('aria-pressed'),'true');
  await page.locator('.translation').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
  await page.waitForTimeout(1100);await page.screenshot({path:path.join(out,'mobile-python-route.png')});
  await page.selectOption('#case-select','digital-support');
  await page.locator('[data-trace-report]').focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#case-select').inputValue(),'data-analysis');
  const python = page.locator('.evidence-rows details[data-skill="Python"]');
  assert.notEqual(await python.getAttribute('open'),null);
  assert.equal(await python.locator('summary').evaluate(e=>e===document.activeElement),true);
  assert((await python.locator('.evidence-body').innerText()).includes('Python程序设计'));
  await page.waitForTimeout(800);await page.screenshot({path:path.join(out,'mobile-python-evidence.png')});
  await python.locator('[data-return-trace]').focus();await page.keyboard.press('Enter');
  assert.equal(await page.getByRole('button',{name:'Python',exact:true}).evaluate(e=>e===document.activeElement),true);
  assert.equal(await page.locator('.translation-stage').getAttribute('data-selected'),'python');
  result.checks.push('KEYBOARD_SOURCE_REPORT_RETURN_WITH_CASE_RECOVERY');
  for(const item of fixtures.cases){
   await page.selectOption('#case-select',item.id);
   assert.equal(await page.locator('[data-score]').innerText(),item.score.toFixed(1));
   assert.equal(await page.locator('[data-eligibility]').innerText(),item.eligibility);
   for(const [key,value] of Object.entries(item.dimensions)){
    const dimension = page.locator('[data-dimension="'+key+'"]');
    await dimension.locator('summary').focus();await page.keyboard.press('Enter');
    assert.notEqual(await dimension.getAttribute('open'),null);
    assert.equal(Number(await dimension.locator('meter').getAttribute('value')),value);
    assert.equal(await dimension.locator('b').innerText(),value.toFixed(1));
    const text = await dimension.locator('.dimension-context').innerText();
    const entries = item.contributions.filter(entry=>entry.dimension===key);
    for(const entry of entries) assert(text.includes(entry.reason),'Missing actual contribution reason');
    if(key==='technical') for(const match of item.matches) assert(text.includes(match.skill),'Contribution context must name its skill');
    if(!entries.length) assert(text.includes('未提供'),'Unknown explanation must remain explicit');
    await dimension.locator('summary').click();
   }
   const details = page.locator('.evidence-rows details');
   for(let i=0;i<await details.count();i++){
    const detail = details.nth(i);if(await detail.getAttribute('open')===null) await detail.locator('summary').click();
    const skill = await detail.getAttribute('data-skill');
    const match = item.matches.find(match=>match.skill===skill);
    for(const source of match.sources) assert((await detail.locator('.evidence-body').innerText()).includes(source));
    const back = detail.locator('[data-return-trace]');
    if(await back.count()) {
     const sourceName = {sql:'SQL数据库原理',python:'Python程序设计',excel:'Excel数据分析'}[await back.getAttribute('data-return-trace')];
     assert(match.sources.some(source=>source.includes(sourceName)));
    }
   }
  }
  result.checks.push('ALL_CASE_DIMENSION_CONTEXT_AND_SOURCE_LINEAGE_MATCH_FIXTURE');
  await page.selectOption('#case-select','data-analysis');
  await page.locator('[data-dimension="technical"] summary').click();
  await page.locator('[data-evidence-skill="SQL"]').focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('.evidence-rows details[data-skill="SQL"] summary').evaluate(e=>e===document.activeElement),true);
  assert.notEqual(await page.locator('.evidence-rows details[data-skill="SQL"]').getAttribute('open'),null);
  result.checks.push('DIMENSION_SKILL_LINK_OPENS_EXACT_SOURCE_AND_TRANSFERS_FOCUS');
  await page.selectOption('#case-select','data-analysis');await page.selectOption('#case-select','ai-solutions');await page.selectOption('#case-select','digital-support');
  assert.equal(await page.locator('[data-score]').innerText(),'41.2');
  assert((await page.locator('[data-next-task]').innerText()).includes('字段字典'));
  result.checks.push('RAPID_CASE_CHANGE_LATEST_STATE_AND_REAL_NEXT_ACTION');
  await page.setViewportSize({width:1440,height:900});
  await page.locator('#trust').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));await page.waitForTimeout(200);
  assert.equal(await page.locator('.desktop-nav a[href="#trust"]').getAttribute('aria-current'),'location');
  await page.locator('#top').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));await page.waitForTimeout(200);
  assert.equal(await page.locator('.desktop-nav a[aria-current]').count(),0);
  result.checks.push('CHAPTER_CONTEXT_CLEARS_ON_RETURN_TO_HERO');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.getByRole('button',{name:'Excel',exact:true}).click();
  await page.selectOption('#case-select','data-analysis');
  await page.locator('[data-dimension="project"] summary').click();
  await page.waitForTimeout(100);
  assert.equal(await page.locator('.mobile-route-signal').evaluate(e=>getComputedStyle(e).animationName),'none');
  assert.equal(await page.locator('.report').evaluate(e=>e.getAnimations({subtree:true}).filter(a=>a.playState==='running').length),0);
  assert.equal(await page.locator('[data-mobile-target]').innerText(),'Excel');
  assert((await page.locator('[data-dimension="project"] .dimension-context').innerText()).includes('20.0'));
  result.checks.push('REDUCED_MOTION_PRESERVES_CONTEXT_AND_CANCELS_MOVEMENT');
  assert.equal(result.errors.length,0);assert.equal(result.externalRequests.length,0);
  result.status='PASS';
 }catch(error){result.status='FAIL';result.failure=error.stack;process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'qa.json'),JSON.stringify(result,null,2));await browser.close();console.log(JSON.stringify({status:result.status,checks:result.checks,failure:result.failure,errors:result.errors,externalRequests:result.externalRequests}));}
})();
