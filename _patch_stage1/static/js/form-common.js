
// form-common.js — Stage 1
(function(){
  const $ = (sel, ctx=document)=>ctx.querySelector(sel);
  const $$ = (sel, ctx=document)=>Array.from(ctx.querySelectorAll(sel));

  // Toast
  function toast(msg, type='ok') {
    const el = $('#toast');
    el.textContent = msg;
    el.style.background = (type==='ok') ? '#111827' : (type==='err' ? '#dc2626' : '#111827');
    el.classList.add('show');
    setTimeout(()=>el.classList.remove('show'), 2200);
  }

  // number helpers: display with thousand separators, but keep English digits only
  function cleanNumberInput(el){
    // remove non-digits except .
    const val = (el.value || '').toString().replace(/[^\d.]/g, '');
    el.value = val;
  }
  function formatWithSep(x){
    if (x === '' || x === null || x === undefined) return '';
    const parts = x.toString().split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return parts.join('.');
  }
  function parseNumber(x){
    if (x === '' || x === null || x === undefined) return 0;
    return parseFloat((x+'').replace(/,/g,'')) || 0;
  }

  // debounce
  function debounce(fn, delay){
    let t;
    return function(...args){
      clearTimeout(t);
      t = setTimeout(()=>fn.apply(this,args), delay);
    }
  }

  // elements
  const form = $('#tx-form');
  if (!form) return;

  const opType = document.title.includes('خرید') ? 'خرید' : (document.title.includes('فروش') ? 'فروش' : '');

  const qty = $('#id_quantity');
  const unit = $('#id_unit_price');
  const total = $('#id_total_price');
  const recentCount = $('#recent_count');
  const resetBtn = $('#btn-reset');

  // initial formatting
  [unit, total].forEach(el=>{
    if (!el) return;
    el.addEventListener('input', ()=>cleanNumberInput(el));
    el.addEventListener('blur', ()=>{ el.value = formatWithSep(el.value); });
  });

  if (qty) {
    qty.addEventListener('input', ()=>cleanNumberInput(qty));
  }

  // reactive calculations
  function recalcFromUnit(){
    const q = parseNumber(qty?.value);
    const u = parseNumber(unit?.value);
    if (total) total.value = formatWithSep((q * u).toFixed(0));
  }
  function recalcFromTotal(){
    const q = parseNumber(qty?.value);
    const t = parseNumber(total?.value);
    const u = q ? Math.round(t / q) : 0;
    if (unit) unit.value = formatWithSep(u);
  }

  if (opType === 'فروش') {
    [qty, unit].forEach(el=> el && el.addEventListener('input', recalcFromUnit));
    total && total.setAttribute('readonly','readonly');
  } else if (opType === 'خرید') {
    [qty, total].forEach(el=> el && el.addEventListener('input', recalcFromTotal));
    total && total.removeAttribute('readonly');
  }

  // form submit: strip commas before submit
  form.addEventListener('submit', (e)=>{
    // allow normal submit; just cleanup values
    [unit, total, qty].forEach(el=>{
      if (!el) return;
      el.value = (el.value || '').replace(/,/g,'');
    });
  });

  // reset
  resetBtn && resetBtn.addEventListener('click', ()=>{
    form.reset();
    [unit,total,qty].forEach(el=> el && (el.value=''));
  });

  // recent count change (debounced fetch)
  if (recentCount) {
    recentCount.addEventListener('input', debounce(()=>{
      const n = parseInt(recentCount.value || '20', 10);
      fetch(`${window.location.pathname}?recent=${n}`, {headers:{'X-Requested-With':'XMLHttpRequest'}})
        .then(r=>r.text())
        .then(html=>{
          // server should return just the rows (tx_table_body.html)
          $('#recent-body').innerHTML = html;
        })
        .catch(()=>toast('خطا در بروزرسانی لیست', 'err'));
    }, 400));
  }

  // success message if ?ok=1 present (after POST redirect)
  const params = new URLSearchParams(window.location.search);
  if (params.get('ok') === '1') {
    toast('با موفقیت ثبت شد ✅','ok');
  }
})();
