// تبدیل به انگلیسی (برای ذخیره/محاسبه)
function toEn(s){
  return String(s||'')
    .replace(/[\u200e\u200f]/g,'')
    .replace(/[,\u066C\u00A0\u202F]/g,'')
    .replace(/[٫.]/g,'.')
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

// تبدیل به فارسی با جداکننده سه‌رقمی
function fa(n){
  try{
    const num = Number(n);
    if (Intl && Intl.NumberFormat){
      return new Intl.NumberFormat('fa-IR').format(num);
    }
    return String(Math.trunc(num))
      .replace(/\B(?=(\d{3})+(?!\d))/g,'٬')
      .replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
  }catch(e){
    return n;
  }
}

function num(el){
  const v = toEn(el?.value||'');
  const n = parseFloat(v);
  return isNaN(n) ? NaN : n;
}

// ⬅️ تابع عمومی: کنترل ورودی عددی با اعشار اختیاری
function allowNumericInput(el, decimals=0){
  if (!el) return;
  el.addEventListener('keydown', function(e){
    // اجازه به کلیدهای کنترلی
    const allowedKeys = ['Backspace','Delete','ArrowLeft','ArrowRight','Tab','Enter','Home','End'];
    if (allowedKeys.includes(e.key)) return;

    // کپی/پیست
    if ((e.ctrlKey || e.metaKey) && ['a','c','v','x'].includes(e.key.toLowerCase())) return;

    // اعداد
    if (/^[0-9۰-۹٠-٩]$/.test(e.key)) return;

    // اعشار (اگر مجاز باشه)
    if (decimals > 0 && (e.key === '.' || e.key === ',' || e.key === '٫' || e.key === '٬')) {
      // فقط یک بار
      if (/[.,٫٬]/.test(el.value)) {
        e.preventDefault();
      }
      return;
    }

    // غیر از این → بلاک
    e.preventDefault();
  });
}

// فرمت و تبدیل همزمان
function formatOnInput(el, decimals=0, callback){
  if (!el) return;
  el.addEventListener('input', ()=>{
    let raw = toEn(el.value);
    if (raw === '' || isNaN(raw)) return;

    // رند کردن اعشار (اگر نیاز بود)
    if (decimals === 0){
      raw = String(Math.trunc(parseFloat(raw)));
    } else {
      raw = parseFloat(raw).toFixed(decimals);
    }

    el.value = fa(raw);
    callback?.();
  });
  el.addEventListener('change', callback);
}

// تابع نهایی برای استفاده در فرم‌ها
function setupNumericField(id, decimals=0, callback){
  const el = document.getElementById(id);
  if (!el) return null;
  allowNumericInput(el, decimals);
  formatOnInput(el, decimals, callback);
  return el;
}
