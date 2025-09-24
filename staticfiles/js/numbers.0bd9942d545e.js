// numbers.js
// توابع کمکی برای ورود و فرمت‌دهی اعداد فارسی با جداکننده سه‌رقمی

function toEn(s){
  return String(s||'')
    .replace(/[\u200e\u200f]/g,'')
    .replace(/[,\u066C\u00A0\u202F]/g,'')
    .replace(/[٫.]/g,'.')
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

function fa(n){
  try{
    var num = Number(n);
    if (Intl && Intl.NumberFormat){ return new Intl.NumberFormat('fa-IR').format(num); }
    return String(Math.trunc(num))
      .replace(/\B(?=(\d{3})+(?!\d))/g,'٬')
      .replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
  }catch(e){ return n; }
}

function num(el){
  const v = toEn(el?.value||'');
  const n = parseFloat(v);
  return isNaN(n)?NaN:n;
}

function allowOnlyIntegerInput(el){
  if (!el) return;
  el.addEventListener('keydown', function(e){
    const allowedKeys = ['Backspace','Delete','ArrowLeft','ArrowRight','Tab','Enter','Home','End'];
    if (allowedKeys.includes(e.key)) return;
    if ((e.ctrlKey || e.metaKey) && ['a','c','v','x'].includes(e.key.toLowerCase())) return;
    if (/[\d۰-۹٠-٩]/.test(e.key)) return;
    e.preventDefault();
  });
}

function formatOnInput(el, callback){
  if(!el) return;
  el.addEventListener('input', ()=>{
    const raw = toEn(el.value);
    if (raw==='' || isNaN(raw)) return;
    el.value = fa(raw);
    callback?.();
  });
  el.addEventListener('change', callback);
}

// -----------------
// ابزارک آماده: اعمال فرمت روی چند فیلد با یک خط
// -----------------
function setupNumericField(id, callback){
  const el = document.getElementById(id);
  if (!el) return;
  allowOnlyIntegerInput(el);
  formatOnInput(el, callback);
  return el;
}

function toFaDigits(s){
  return String(s||'')
    .replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d])
    .replace(/[٠-٩]/g, d=>'۰۱۲۳۴۵۶۷۸۹'['٠١٢٣٤٥٦٧٨٩'.indexOf(d)]);
}

function toEnDigits(s){
  return String(s||'')
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}
