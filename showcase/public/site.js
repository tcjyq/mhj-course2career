/* Presentation only. No accounts, storage, Provider requests or tracking. */
'use strict';
const stage = document.querySelector('.translation-stage');
const captions = {
  sql: '“SQL数据库原理” → SQL：课程名称命中数据库规则。',
  python: '“Python程序设计” → Python：课程名称明确提及技能。',
  excel: '“Excel数据分析” → Excel：材料支持来自课程名称。',
};
document.querySelectorAll('[data-trace]').forEach(button => {
  button.disabled = false;
  button.addEventListener('click', () => {
    stage.dataset.selected = button.dataset.trace;
    stage.querySelector('.route-signal').setAttribute('d', stage.querySelector('.route-' + button.dataset.trace).getAttribute('d'));
    document.querySelectorAll('[data-trace]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelector('[data-trace-caption]').textContent = captions[button.dataset.trace];
    stage.classList.remove('is-tracing');
    requestAnimationFrame(() => requestAnimationFrame(() => stage.classList.add('is-tracing')));
  });
});
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      stage.classList.add('is-tracing');
      observer.disconnect();
    }
  }, { threshold: .4 });
  observer.observe(stage);
}
const mobileMenu = document.querySelector('.mobile-nav');
mobileMenu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => { mobileMenu.open = false; }));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && mobileMenu.open) {
    mobileMenu.open = false;
    mobileMenu.querySelector('summary').focus();
  }
});
document.addEventListener('click', event => {
  if (!mobileMenu.contains(event.target)) mobileMenu.open = false;
});
const selector = document.querySelector('#case-select');
selector.disabled = true;
const format = value => Number(value).toFixed(1);
function renderCase(item) {
  document.querySelector('[data-case-title]').textContent = item.title;
  document.querySelector('[data-score]').textContent = format(item.score);
  document.querySelector('[data-eligibility]').textContent = item.eligibility;
  document.querySelector('[data-gate-reason]').textContent = item.checks.map(check => check.reason).join('；') || '当前 JD 未设置可结构化核验的硬门槛，不能解释为已经满足。';
  document.querySelectorAll('[data-dimension]').forEach(row => {
    const value = item.dimensions[row.dataset.dimension];
    const meter = row.querySelector('meter');
    meter.value = value; meter.textContent = format(value);
    meter.setAttribute('aria-label', row.querySelector('span').textContent + ' ' + format(value) + ' / 100');
    row.querySelector('b').textContent = format(value);
  });
  const rows = document.querySelector('[data-evidence-rows]');
  rows.replaceChildren();
  const order = skill => { const index = ['SQL','Python','Excel'].indexOf(skill); return index < 0 ? 10 : index; };
  const matches = item.matches.slice().sort((a,b) => order(a.skill) - order(b.skill));
  matches.forEach((match,index) => {
    const detail = document.createElement('details'); detail.open = index === 0;
    const summary = document.createElement('summary');
    const skill = document.createElement('span'); skill.textContent = match.skill;
    const status = document.createElement('span'); status.className = 'evidence-status'; status.textContent = match.status;
    const support = document.createElement('b'); support.textContent = format(match.support) + ' ';
    const unit = document.createElement('small'); unit.textContent = '/ 100'; support.append(unit);
    const symbol = document.createElement('span'); symbol.className = 'expand-symbol'; symbol.setAttribute('aria-hidden','true'); symbol.textContent = '＋';
    summary.append(skill,status,support,symbol); detail.append(summary);
    match.sources.forEach(source => { const text = document.createElement('p'); text.textContent = source; detail.append(text); });
    rows.append(detail);
  });
  document.querySelector('[data-next-task]').textContent = item.learning.length
    ? item.learning[0].task + '。交付：' + item.learning[0].evidence_goal + '。'
    : '当前没有需要优先补齐的技能。先核对岗位的毕业年份条件，再决定是否继续申请。';
  document.querySelector('[data-completeness]').textContent = format(item.completeness);
  document.querySelector('[data-confidence]').textContent = item.confidence;
  document.querySelector('[data-example-notice]').textContent = item.boundary;
}
fetch('/demo.json', { credentials:'omit' }).then(response => {
  if (!response.ok) throw new Error('demo unavailable');
  return response.json();
}).then(data => {
  const names = {technical:'技术',education:'教育',project:'项目',internship:'实习',potential:'潜力'};
  document.querySelector('[data-weights]').textContent = '加权计算：' + Object.entries(data.weights).map(([key,value]) => names[key] + Math.round(value * 100) + '%').join(' · ');
  const cases = new Map(data.cases.map(item => [item.id,item]));
  renderCase(cases.get(selector.value)); selector.disabled = false;
  selector.addEventListener('change', () => renderCase(cases.get(selector.value)));
}).catch(() => {
  document.querySelector('[data-example-notice]').textContent = '当前展示离线数据分析示例。方向切换暂不可用，可进入应用运行合成案例。';
});
