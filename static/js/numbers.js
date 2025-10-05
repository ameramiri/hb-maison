// تبدیل به انگلیسی برای محاسبه/ذخیره
function toEn(s){
  return String(s||'')
    .replace(/[\u200e\u200f]/g,'')          // حذف کاراکترهای کنترلی RTL/LTR
    .replace(/[,\u066C\u00A0\u202F]/g,'')   // حذف جداکننده هزارگان
    .replace(/[٫.]/g,'.')                   // نقطه اعشاری
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

// تبدیل به فارسی با جداکننده سه‌رقمی
function fa(n, decimals=0){
  try {
    const num = Number(n);
    const opts = { useGrouping: true };
    if (decimals > 0){
      opts.minimumFractionDigits = decimals;
      opts.maximumFractionDigits = decimals;
    }
    return new Intl.NumberFormat('fa-IR', opts).format(num);
  } catch(e) {
    return n;
  }
}

// فقط تبدیل رقم به فارسی
function toFaDigits(s){
  return String(s||'').replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
}

// فقط تبدیل رقم به انگلیسی
function toEnDigits(s){
  return String(s||'')
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

// خواندن مقدار عددی از یک input
function num(el){
  const v = toEn(el?.value||'');
  const n = parseFloat(v);
  return isNaN(n) ? NaN : n;
}

// کنترل ورودی عددی و اعشار
function allowNumericInput(el, decimals=0){
  if (!el) return;
  el.addEventListener('input', function(){
    let raw = toEn(el.value);

    // فقط ارقام و نقطه
    raw = raw.replace(/[^0-9.]/g, '');

    if (decimals === 0){
      raw = raw.replace(/\./g, ''); // اگر اعشار مجاز نیست نقطه حذف بشه
    } else {
      // فقط یک نقطه مجاز
      const firstDot = raw.indexOf('.');
      if (firstDot !== -1){
        raw = raw.slice(0, firstDot + 1) + raw.slice(firstDot + 1).replace(/\./g, '');
      }

      // محدود کردن رقم اعشار
      const parts = raw.split('.');
      if (parts[1]){
        parts[1] = parts[1].slice(0, decimals);
        raw = parts.join('.');
      }
    }
    el.value = raw;
  });
}

// فرمت‌دهی خودکار (سه‌رقمی + اعشار)
function formatOnInput(el, decimals=0, callback){
  if (!el) return;
  el.addEventListener('input', ()=>{
    let raw = toEn(el.value);

    if (raw === '.' && decimals > 0){
      el.value = '۰٫'; // اولین نقطه
    } else if (raw.endsWith('.') && decimals > 0){
      const intPart = raw.slice(0, -1);
      el.value = (intPart ? fa(intPart, 0) : '۰') + '٫';
    } else if (raw !== '' && !isNaN(raw)){
      const parts = raw.split('.');
      if (parts.length === 2 && decimals > 0){
        const persian = parts[1].replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
        el.value = fa(parts[0], 0) + '٫' + persian;
      } else {
        el.value = fa(raw, 0);
      }
    } else {
      el.value = '';
    }
    callback?.();
  });
  el.addEventListener('change', callback);

  // موقع blur → فرمت نهایی
  el.addEventListener('blur', ()=>{
    const val = toEn(el.value);
    if (val !== '' && !isNaN(val)){
      const numVal = parseFloat(val);
      el.value = fa(numVal, decimals);
    }
  });
}

// راه‌اندازی فیلد عددی
function setupNumericField(id, decimals=0, callback){
  const el = document.getElementById(id);
  if (!el) return null;
  allowNumericInput(el, decimals);
  formatOnInput(el, decimals, callback);
  return el;
}
