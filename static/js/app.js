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
