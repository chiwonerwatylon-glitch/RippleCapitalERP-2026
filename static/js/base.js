// static/js/base.js

document.addEventListener("DOMContentLoaded", function () {
  // Sidebar toggle for mobile
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  // Auto-hide messages after a few seconds
  const messages = document.querySelectorAll(".messages .alert");
  if (messages.length) {
    setTimeout(() => {
      messages.forEach((el) => {
        el.style.transition = "opacity 0.3s ease";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 300);
      });
    }, 4000);
  }
});
