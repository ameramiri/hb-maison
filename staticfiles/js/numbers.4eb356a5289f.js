// تبدیل به انگلیسی (برای ذخیره/محاسبه)
function toEn(s){
  return String(s||'')
    .replace(/[\u200e\u200f]/g,'')
    .replace(/[,\u066C\u00A0\u202F]/g,'')
    .replace(/[٫.]/g,'.')
    .replace(/[۰-۹]/g, d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[٠-٩]/g, d=>'٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}

// تبدیل به فارسی با جداکننده سه‌رقمی و اعشار اختیاری
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

// گرفتن مقدار عددی از یک input
function num(el){
  const v = toEn(el?.value||'');
  const n = parseFloat(v);
  return isNaN(n) ? NaN : n;
}

// ⬅️ تابع نهایی برای کنترل و فرمت ورودی عددی
function setupNumericField(id, decimals=0, callback){
  const el = document.getElementById(id);
  if (!el) return null;

  el.addEventListener('input', ()=>{
    let raw = toEn(el.value);

    // فقط عدد و نقطه
    raw = raw.replace(/[^0-9.]/g, '');

    if (decimals === 0){
      // هیچ نقطه‌ای مجاز نیست
      raw = raw.replace(/\./g, '');
    } else {
      // فقط یک نقطه مجاز: همه نقطه‌ها رو پاک کن بجز اولین
      const firstDot = raw.indexOf('.');
      if (firstDot !== -1){
        raw = raw.slice(0, firstDot + 1) + raw.slice(firstDot + 1).replace(/\./g, '');
      }
      // محدود کردن تعداد رقم اعشار
      const parts = raw.split('.');
      if (parts[1]){
        parts[1] = parts[1].slice(0, decimals);
        raw = parts.join('.');
      }
    }

    // نمایش
    if (raw === '.' && decimals > 0){
      el.value = '۰٫';
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

  // موقع ترک فیلد: فرمت نهایی (toFixed)
  el.addEventListener('blur', ()=>{
    const val = toEn(el.value);
    if (val !== '' && !isNaN(val)){
      const numVal = parseFloat(val);
      el.value = fa(numVal, decimals);
    }
  });

  return el;
}
