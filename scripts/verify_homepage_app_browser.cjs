/* Synthetic local accounts only; no AI or Provider actions. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.C2C_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.C2C_BASE_URL || 'http://127.0.0.1:8866';
assert(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const out = process.env.C2C_APP_CAPTURE || 'output/playwright/app';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.C2C_CHROMIUM?{executablePath:process.env.C2C_CHROMIUM}:{})});
 const result={checks:[],errors:[],externalRequests:[]};
 let page;
 try{
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  await context.route('**/*',route=>{
   if(new URL(route.request().url()).origin!==new URL(base).origin){result.externalRequests.push(route.request().url());return route.abort()}
   return route.continue();
  });
  page=await context.newPage();page.on('pageerror',e=>result.errors.push(e.message));
  async function ready(){await page.locator('[data-testid="stSidebarNav"]').waitFor();await page.waitForTimeout(1800);assert.equal(await page.locator('[data-testid="stException"]').count(),0)}
  async function openSidebar(){
   const toggle=page.locator('[data-testid="stExpandSidebarButton"]');
   if(await toggle.isVisible()){await toggle.click();await page.waitForTimeout(400)}
  }
  async function closeSidebar(){
   const toggle=page.locator('[data-testid="stSidebarCollapseButton"]').getByRole('button');
   const box=await toggle.boundingBox();
   if(box && box.x>=0 && box.x+box.width<=page.viewportSize().width){await toggle.click();await page.waitForTimeout(400)}
  }
  async function nav(label){await openSidebar();await page.locator('[data-testid="stSidebarNav"]').getByText(label,{exact:true}).click();await ready()}
  await page.goto(base);await page.getByRole('heading',{name:'把学过的课程，翻译成求职能力',exact:true}).waitFor();await ready();
  await page.screenshot({path:out+'/home-desktop.png',fullPage:true});
  await page.getByText('开始一次个人分析',{exact:true}).click();await ready();
  await page.getByRole('heading',{name:'个人分析',exact:true}).waitFor();result.checks.push('NATIVE_HOME_CTA');
  await page.getByText('三个求职方向合成演示（无需登录或AI）',{exact:true}).click();
  const cases=[['数字化实施／信息化支持','41.2'],['AI应用／解决方案','39.8'],['数据分析','50.3']];
  for (const [name,score] of cases){
   const combo=page.getByRole('combobox',{name:'选择合成案例',exact:true});await combo.waitFor();
   if ((await combo.inputValue()).trim() !== name) {
    await combo.focus();await combo.press('ArrowDown');
    await page.getByRole('listbox').waitFor();
    await page.getByRole('option',{name,exact:true}).click();await ready();
   }
   await page.getByRole('button',{name:'运行合成规则演示',exact:true}).click();await ready();
   const values=await page.locator('[data-testid="stMetricValue"]').allTextContents();
   assert(values.some(value=>value.includes(score)),'Rule score '+score);
   const jd=page.getByRole('textbox',{name:'目标岗位JD',exact:true});assert.equal(await jd.inputValue(),'');
  }
  result.checks.push('THREE_LOCAL_RULE_CASES_AND_INPUT_ISOLATION');
  await page.screenshot({path:out+'/analysis-rules-desktop.png'});
  await nav('登录');await page.screenshot({path:out+'/login-desktop.png'});
  await page.getByRole('textbox',{name:'用户名',exact:true}).first().fill('audit_byok');
  await page.getByRole('textbox',{name:'密码',exact:true}).first().fill('synthetic-password-123');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByRole('button',{name:'退出登录',exact:true}).waitFor();await ready();
  await nav('我的 AI Provider');
  await page.getByText('状态：已配置',{exact:true}).first().waitFor();
  assert.equal(await page.getByText('状态：已配置',{exact:true}).count(),10);
  await page.screenshot({path:out+'/developer-synthetic-desktop.png'});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(800);await closeSidebar();await page.screenshot({path:out+'/developer-synthetic-mobile.png'});
  await nav('个人分析');await page.screenshot({path:out+'/analysis-mobile.png'});
  await openSidebar();await page.getByRole('button',{name:'退出登录',exact:true}).click();await ready();
  await page.reload();await ready();assert.equal(await page.getByRole('button',{name:'退出登录',exact:true}).count(),0);
  await nav('首页');await closeSidebar();await page.screenshot({path:out+'/home-mobile.png',fullPage:true});
  await nav('登录');await closeSidebar();await page.screenshot({path:out+'/login-mobile.png'});
  result.checks.push('DESKTOP_MOBILE_AUTH_ANALYSIS_DEVELOPER_LOGOUT_F5');
  assert.equal(result.errors.length,0);assert.equal(result.externalRequests.length,0);result.status='PASS';
 }catch(error){result.status='FAIL';result.failure=error.message;process.exitCode=1;if(page){await page.screenshot({path:out+'/failed.png'});result.ui=await page.locator('[role="combobox"]').evaluateAll(nodes=>nodes.map(x=>({tag:x.tagName,value:x.value,expanded:x.getAttribute('aria-expanded'),text:x.textContent})));result.listboxes=await page.getByRole('listbox').count()}}
 finally{fs.writeFileSync(out+'/qa.json',JSON.stringify(result,null,2));await browser.close();console.log(JSON.stringify(result,null,2))}
})();
