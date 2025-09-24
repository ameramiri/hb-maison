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

function num(el){
  const v = toEn(el?.value||'');
  const n = parseFloat(v);
  return isNaN(n) ? NaN : n;
}

// ⬅️ تابع عمومی: کنترل ورودی عددی با اعشار اختیاری
function allowNumericInputs(el, decimals=0){
  if (!el) return;
  el.addEventListener('keydown', function(e){
    const allowedKeys = [
      'Backspace','Delete','ArrowLeft','ArrowRight','Tab','Enter','Home','End'
    ];
    if (allowedKeys.includes(e.key)) return;

    // Ctrl/Cmd + A/C/V/X
    if ((e.ctrlKey || e.metaKey) && ['a','c','v','x'].includes(e.key.toLowerCase())) return;

    // اعداد فارسی/عربی/انگلیسی
    if (/^[0-9۰-۹٠-٩]$/.test(e.key)) return;

    // اعشار

    if (decimals > 0 && (e.key === '.' || e.keyCode === 190)){
      console.log("🔑 key:", e.key, " | value before keydown:", el.value);
      if (el.value.includes('.')){
        console.log("❌ دومین نقطه بلاک شد");
        e.preventDefault(); // فقط یک بار نقطه مجاز
      } else {
        console.log("✅ اولین نقطه پذیرفته شد");
      }
      return;
    }


    // غیر از این → بلاک
    e.preventDefault();
  });
}


function allowNumericInput(el, decimals=0){
  if (!el) return;

  el.addEventListener('input', function(){
    let raw = toEn(el.value);

    // فقط اعداد و نقطه
    raw = raw.replace(/[^0-9.]/g, '');

    if (decimals === 0){
      // اگر اعشار مجاز نیست، نقطه‌ها حذف بشن
      raw = raw.replace(/\./g, '');
    } else {
      // فقط یک نقطه مجاز
      const parts = raw.split('.');
      if (parts.length > 2){
        raw = parts[0] + '.' + parts[1];
      }
      // محدود کردن رقم اعشار
      if (parts[1]){
        parts[1] = parts[1].slice(0, decimals);
        raw = parts.join('.');
      }
    }

    el.value = raw;
  });
}

// فرمت و تبدیل همزمان
function formatOnInput(el, decimals=0, callback){
  if (!el) return;
  el.addEventListener('input', ()=>{
    let raw = toEn(el.value);
    if (raw === '' || isNaN(raw)) return;

    if (raw === '.' && decimals > 0){
      // کاربر تازه ممیز زده؛ نمایشی "۰٫" بده
      el.value = '۰٫';
      return;
    }


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
