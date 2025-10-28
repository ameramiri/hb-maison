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
function fa(n, decimals=0, useGrouping=true){
  try {
    const num = Number(n);
    const opts = { useGrouping };
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
function attachNumericBehavior(el, {decimals, maxIntLen, useGrouping, callback}) {

  // این فانکشن خام رو normalize می‌کنه: فقط ارقام و یک نقطه، و بعد محدودیت‌ها رو اعمال می‌کنه
  function normalizeRawInput(raw){
    // به انگلیسی تمیز
    raw = toEn(raw);

    // فقط ارقام و یک نقطه
    raw = raw.replace(/[^0-9.]/g, '');
    const firstDot = raw.indexOf('.');
    if (firstDot !== -1){
      raw = raw.slice(0, firstDot + 1) + raw.slice(firstDot + 1).replace(/\./g, '');
    }

    // جدا کن بخش صحیح و اعشار
    let [intPart = '', fracPart = undefined] = raw.split('.');

    // محدودیت طول فقط روی بخش صحیح
    if (maxIntLen && intPart.length > maxIntLen){
        intPart = intPart.slice(0, maxIntLen);
    }

    // اگر اعشار نداریم یا decimals=0، اصلا بخش اعشار رو حذف کن
    if (decimals === 0){
      return intPart;
    }

    // در غیر این صورت، اعشار مجاز است:
    if (fracPart === undefined){
      // یعنی هنوز نقطه نزده یا پاک شده
      return intPart;
    }

    // اگر کاربر فقط "12." زده و هنوز چیزی بعدش نیست
    if (fracPart === '' && raw.endsWith('.')){
      return intPart + '.';
    }

    // بریدن تعداد ارقام اعشاری
    fracPart = fracPart.slice(0, decimals);

    return fracPart === ''
      ? (intPart + '.')        // 12.
      : (intPart + '.' + fracPart); // 12.34
  }

  // این فانکشن مقدار نرمال‌شده رو به حالت نمایش (فارسی+گروه‌بندی) درمیاره
  function formatForDisplay(rawNormalized){
    if (rawNormalized === ''){
      return '';
    }

    const hasDot = rawNormalized.includes('.');
    let [intPart, fracPart] = rawNormalized.split('.');

    // عدد صحیح رو به فارسی با یا بدون جداکننده نمایش بده
    const intFa = fa(intPart === '' ? 0 : intPart, 0, useGrouping);

    if (decimals === 0){
      return intFa;
    }

    // اگر هنوز فقط "12." هست
    if (hasDot && (fracPart === undefined || fracPart === '')){
      return intFa + '٫';
    }

    // اگر اعشار داریم
    if (fracPart !== undefined){
      // رقم‌های اعشار رو به فارسی تبدیل کن
      const fracFa = fracPart.replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
      return intFa + '٫' + fracFa;
    }

    return intFa;
  }

  // وقتی کاربر تایپ می‌کند
  el.addEventListener('input', () => {
    const normalized = normalizeRawInput(el.value);
    el.value = formatForDisplay(normalized);
    callback?.();
  });

  // وقتی فوکوس از فیلد بیرون می‌رود → خروجی نهایی تمیز
  el.addEventListener('blur', () => {
    const normalized = normalizeRawInput(el.value);
    if (normalized === '') {
      el.value = '';
      return;
    }

    // اینجا می‌تونیم عدد نهایی رو با تعداد اعشار ثابت کنیم
    let numVal = parseFloat(normalized); // مثلا "123.4" → 123.4

    if (!isNaN(numVal)){
      el.value = fa(numVal, decimals, useGrouping);
    }

    callback?.();
  });

  // اگر به هر دلیلی بخوایم روی change هم تریگر داشته باشیم:
  el.addEventListener('change', () => {
    callback?.();
  });
}

// راه‌اندازی فیلد عددی
function setupNumericField(id, decimals = 0, callback){
  const el = document.getElementById(id);
  if (!el) return null;

  const maxIntLen = Number(el.dataset.maxint || '') || null;
  const decs = decimals !== null ? decimals : (Number(el.dataset.decimals || '') || 0);

  // اگر طول بخش صحیح کوتاهه (مثلاً سال، درصد، تعداد کم)، جداکننده هزارگان نذار
  const useGrouping = !maxIntLen || maxIntLen > 4;

  attachNumericBehavior(el, {
    decimals: decs,
    maxIntLen,
    useGrouping,
    callback
  });

  return el;
}
