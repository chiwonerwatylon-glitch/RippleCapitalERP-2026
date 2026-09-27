document.addEventListener("DOMContentLoaded", function () {

    // ---- Password show/hide toggle (supports multiple fields via data-target) ----
    const toggleButtons = document.querySelectorAll(".toggle-password");

    toggleButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            const targetId = btn.getAttribute("data-target") || "id_password";
            const input = document.getElementById(targetId);
            if (!input) return;

            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
            btn.classList.toggle("active", isHidden);
        });
    });

    // ---- Submit button loading state ----
    const form = document.getElementById("loginForm") || document.querySelector("form");
    const submitBtn = document.getElementById("submitBtn");

    if (form && submitBtn) {
        form.addEventListener("submit", function () {
            const btnText = submitBtn.querySelector(".btn-text");
            const spinner = submitBtn.querySelector(".btn-spinner");
            if (!btnText || !spinner) return;

            submitBtn.disabled = true;
            btnText.textContent = "Please wait...";
            spinner.hidden = false;
        });
    }

});
