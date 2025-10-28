// static/js/app.js
document.addEventListener("DOMContentLoaded", () => {
  const hamburger = document.querySelector(".hamburger");
  const menu = document.querySelector(".navbar-menu");

  if (hamburger && menu) {
    hamburger.addEventListener("click", () => {
      menu.classList.toggle("active");
    });
  }
});

function initSelect2BySize() {
  $('.select2').each(function() {
    const $el = $(this);
    $el.select2({
      dir: 'rtl',
      placeholder: $el.attr('placeholder') || 'انتخاب کنید',
      width: 'resolve', // 👈 یعنی عرض را از CSS بخوان
      language: {
        noResults: function() { return "موردی یافت نشد"; }
      }
    });
  });
}

$(document).ready(initSelect2BySize);
