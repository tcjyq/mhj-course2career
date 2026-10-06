/* Presentation only. No accounts, storage, Provider requests or tracking. */
'use strict';
const stage = document.querySelector('.translation-stage');
const mobileRail = document.querySelector('.mobile-translation');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const traces = {
  sql: { source:'SQL数据库原理', target:'SQL', reason:'名称命中数据库规则 · 直接材料', caption:'“SQL数据库原理” → SQL：课程名称命中数据库规则。' },
  python: { source:'Python程序设计', target:'Python', reason:'名称明确提及技能 · 直接材料', caption:'“Python程序设计” → Python：课程名称明确提及技能。' },
  excel: { source:'Excel数据分析', target:'Excel', reason:'名称明确提及技能 · 直接材料', caption:'“Excel数据分析” → Excel：材料支持来自课程名称。' },
};
let selectedTrace = 'sql';
function followTrace(key, animate = true) {
  selectedTrace = key;
  const trace = traces[key];
  stage.dataset.selected = key;
  mobileRail.dataset.selected = key;
  stage.querySelector('.route-signal').setAttribute('d', stage.querySelector('.route-' + key).getAttribute('d'));
  document.querySelectorAll('[data-trace]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.trace === key)));
  document.querySelector('[data-trace-caption]').textContent = trace.caption;
  document.querySelector('[data-mobile-source]').textContent = trace.source;
  document.querySelector('[data-mobile-target]').textContent = trace.target;
  document.querySelector('[data-mobile-reason]').textContent = trace.reason;
  document.querySelector('[data-trace-report]').firstChild.textContent = '在数据分析示例中追查 ' + trace.target + ' ';
  if (!animate || reducedMotion.matches) return;
  [stage,mobileRail].forEach(element => {
    element.classList.remove('is-tracing');
    requestAnimationFrame(() => requestAnimationFrame(() => element.classList.add('is-tracing')));
  });
}
document.querySelectorAll('[data-trace]').forEach(button => {
  button.disabled = false;
  button.addEventListener('click', () => followTrace(button.dataset.trace));
});
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) { followTrace(selectedTrace); observer.disconnect(); }
  }, {threshold:.5});
  observer.observe(document.querySelector('.translation'));
  const chapters = new IntersectionObserver(entries => {
    entries.filter(entry => entry.isIntersecting).forEach(entry => {
      document.querySelectorAll('.desktop-nav a,.mobile-nav a').forEach(link => {
        if (link.hash === '#' + entry.target.id) link.setAttribute('aria-current','location');
        else link.removeAttribute('aria-current');
      });
    });
  }, {rootMargin:'-15% 0px -55% 0px'});
  document.querySelectorAll('#top,#method,#example,#trust,#start').forEach(section => chapters.observe(section));
}
const mobileMenu = document.querySelector('.mobile-nav');
mobileMenu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => { mobileMenu.open = false; }));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && mobileMenu.open) { mobileMenu.open = false; mobileMenu.querySelector('summary').focus(); }
});
document.addEventListener('click', event => { if (!mobileMenu.contains(event.target)) mobileMenu.open = false; });
const selector = document.querySelector('#case-select');
const rows = document.querySelector('[data-evidence-rows]');
const cases = new Map();
const format = value => Number(value).toFixed(1);
const scrollBehavior = () => reducedMotion.matches ? 'instant' : 'smooth';
function contextMotion(element, distance = -8) {
  if (reducedMotion.matches || !element.animate) return;
  element.getAnimations().forEach(animation => animation.cancel());
  element.animate([{transform:`translateX(${distance}px)`,opacity:.7},{transform:'none',opacity:1}], {duration:260,easing:'cubic-bezier(.16,1,.3,1)'});
}
reducedMotion.addEventListener('change', event => {
  if (!event.matches) return;
  document.querySelectorAll('.report,.translation').forEach(element => element.getAnimations({subtree:true}).forEach(animation => animation.cancel()));
  [stage,mobileRail].forEach(element => element.classList.remove('is-tracing'));
});
function returnToMaterial(key) {
  followTrace(key);
  document.querySelector('[data-trace="' + key + '"]').focus({preventScroll:true});
  document.querySelector('.translation').scrollIntoView({block:'start',behavior:scrollBehavior()});
}
function showEvidence(skill) {
  const match = [...rows.querySelectorAll('details')].find(detail => detail.dataset.skill === skill);
  if (!match) { rows.scrollIntoView({block:'start',behavior:scrollBehavior()}); return; }
  match.open = true; match.querySelector('summary').focus({preventScroll:true});
  match.scrollIntoView({block:'center',behavior:scrollBehavior()}); contextMotion(match.querySelector('.evidence-body'));
}
document.querySelector('.dimension-bars').addEventListener('click', event => {
  const link = event.target.closest('[data-evidence-skill]');
  if (!link) return;
  event.preventDefault(); showEvidence(link.dataset.evidenceSkill);
});
rows.addEventListener('click', event => {
  const link = event.target.closest('[data-return-trace]');
  if (!link) return;
  event.preventDefault(); returnToMaterial(link.dataset.returnTrace);
});
document.addEventListener('toggle', event => {
  if (event.target.tagName !== 'DETAILS' || !event.target.open) return;
  const context = event.target.querySelector('.evidence-body,.dimension-context');
  if (context) contextMotion(context);
}, true);
function renderCase(item, animate = false) {
  document.querySelector('[data-case-title]').textContent = item.title;
  document.querySelector('[data-score]').textContent = format(item.score);
  document.querySelector('[data-eligibility]').textContent = item.eligibility;
  document.querySelector('[data-gate-reason]').textContent = item.checks.map(check => check.reason).join('；') || '当前 JD 未设置可结构化核验的硬门槛，不能解释为已经满足。';
  document.querySelectorAll('[data-dimension]').forEach(row => {
    const key = row.dataset.dimension;
    const value = item.dimensions[key];
    row.open = false; row.style.setProperty('--value', value / 100);
    const meter = row.querySelector('meter');
    meter.value = value; meter.textContent = format(value);
    meter.setAttribute('aria-label', row.querySelector('.dimension-name').firstChild.textContent + ' ' + format(value) + ' / 100');
    row.querySelector('b').textContent = format(value);
    const context = row.querySelector('.dimension-context'); context.replaceChildren();
    const entries = item.contributions.filter(entry => entry.dimension === key);
    if (entries.length) {
      if (key !== 'technical') {
        const evidence = [...new Set(entries.flatMap(entry => entry.evidence))];
        if (evidence.length) {
          const material = document.createElement('p'); material.textContent = '合成材料：' + evidence.join('、'); context.append(material);
        }
      }
      entries.forEach(entry => {
        const text = document.createElement('p');
        const match = key === 'technical' && item.matches.find(match => entry.label.endsWith('支持' + match.skill));
        if (match) {
          text.className = 'dimension-trace-row';
          const link = document.createElement('a'); link.href = '#evidence-ledger'; link.dataset.evidenceSkill = match.skill; link.textContent = match.skill;
          const reason = document.createElement('span'); reason.textContent = entry.reason;
          text.append(link,reason);
        } else { text.textContent = entry.label + '：' + entry.reason; }
        context.append(text);
      });
    } else {
      const text = document.createElement('p');
      text.textContent = '此示例未提供该维度的解释条目。结果与完整输入见下载文件；分数不代表外部验证。';
      context.append(text);
    }
    if (key === 'technical') {
      const link = document.createElement('a'); link.href = '#evidence-ledger'; link.textContent = '追查每项技能来源 ↓'; context.append(link);
    }
  });
  rows.replaceChildren();
  const order = skill => { const index = ['SQL','Python','Excel'].indexOf(skill); return index < 0 ? 10 : index; };
  item.matches.slice().sort((a,b) => order(a.skill) - order(b.skill)).forEach((match,index) => {
    const detail = document.createElement('details'); detail.open = index === 0; detail.dataset.skill = match.skill;
    const summary = document.createElement('summary');
    const skill = document.createElement('span'); skill.className = 'evidence-skill'; skill.textContent = match.skill;
    const status = document.createElement('span'); status.className = 'evidence-status'; status.textContent = match.status;
    const support = document.createElement('b'); support.textContent = format(match.support);
    const unit = document.createElement('small'); unit.textContent = '/ 100'; support.append(unit);
    const symbol = document.createElement('span'); symbol.className = 'expand-symbol'; symbol.setAttribute('aria-hidden','true'); symbol.textContent = '＋';
    summary.append(skill,status,support,symbol); detail.append(summary);
    const body = document.createElement('div'); body.className = 'evidence-body';
    match.sources.forEach(source => { const text = document.createElement('p'); text.className = 'source-return'; text.textContent = source; body.append(text); });
    const key = Object.keys(traces).find(key => traces[key].target === match.skill && match.sources.some(source => source.includes(traces[key].source)));
    if (key) {
      const link = document.createElement('a'); link.href = '#top'; link.className = 'evidence-return'; link.dataset.returnTrace = key;
      link.textContent = '回到首屏课程材料 ';
      const arrow = document.createElement('span'); arrow.setAttribute('aria-hidden','true'); arrow.textContent = '↖'; link.append(arrow); body.append(link);
    }
    detail.append(body); rows.append(detail);
  });
  document.querySelector('[data-next-task]').textContent = item.learning.length
    ? item.learning[0].task + '。交付：' + item.learning[0].evidence_goal + '。'
    : '当前没有需要优先补齐的技能。先核对岗位的毕业年份条件，再决定是否继续申请。';
  document.querySelector('[data-completeness]').textContent = format(item.completeness);
  document.querySelector('[data-confidence]').textContent = item.confidence;
  document.querySelector('[data-example-notice]').textContent = (animate ? '已切换为' + item.title + '。' : '') + item.boundary;
  if (animate) { contextMotion(document.querySelector('[data-score]'),12); contextMotion(document.querySelector('[data-case-title]'),12); }
}
document.querySelector('[data-trace-report]').addEventListener('click', event => {
  event.preventDefault();
  if (cases.has('data-analysis') && selector.value !== 'data-analysis') { selector.value = 'data-analysis'; renderCase(cases.get('data-analysis'),true); }
  showEvidence(traces[selectedTrace].target);
});
fetch('/demo.json', {credentials:'omit'}).then(response => {
  if (!response.ok) throw new Error('demo unavailable');
  return response.json();
}).then(data => {
  const names = {technical:'技术',education:'教育',project:'项目',internship:'实习',potential:'潜力'};
  document.querySelector('[data-weights]').textContent = '加权计算：' + Object.entries(data.weights).map(([key,value]) => names[key] + Math.round(value * 100) + '%').join(' · ');
  Object.entries(data.weights).forEach(([key,value]) => document.querySelector('[data-dimension="' + key + '"] .dimension-name small').textContent = '权重 ' + Math.round(value * 100) + '%');
  data.cases.forEach(item => cases.set(item.id,item));
  renderCase(cases.get(selector.value)); selector.disabled = false;
  selector.addEventListener('change', () => renderCase(cases.get(selector.value),true));
}).catch(() => { document.querySelector('[data-example-notice]').textContent = '当前展示离线数据分析示例。方向切换暂不可用，可进入应用运行合成案例。'; });
