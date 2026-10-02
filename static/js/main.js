// main/static/js/main.js

(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        initFlashAutoDismiss();
        initConfirmLinks();
        initPasswordStrengthMeter();
        initActiveNavLinks();
    });

    // ---------------------------------------------------------------------
    // Flash message auto-dismiss
    // ---------------------------------------------------------------------
    function initFlashAutoDismiss() {
        var alerts = document.querySelectorAll(".alert");
        if (!alerts.length) return;

        setTimeout(function () {
            alerts.forEach(function (alert) {
                // If it's Bootstrap 5 alert, trigger close
                var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            });
        }, 6000); // 6 seconds
    }

    // ---------------------------------------------------------------------
    // Confirmation dialogs on elements with data-confirm="..."
    // ---------------------------------------------------------------------
    function initConfirmLinks() {
        document.body.addEventListener("click", function (e) {
            var target = e.target;
            // Traverse up until we find a data-confirm
            while (target && target !== document.body) {
                if (target.dataset && target.dataset.confirm) {
                    var msg = target.dataset.confirm || "Are you sure?";
                    if (!window.confirm(msg)) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                    return;
                }
                target = target.parentElement;
            }
        });
    }

    // ---------------------------------------------------------------------
    // Password strength meter (used on profile & can be reused)
    // ---------------------------------------------------------------------
    function initPasswordStrengthMeter() {
        var passwordInput = document.querySelector("#new-password");
        if (!passwordInput) return;

        var strengthBar = document.getElementById("password-strength-bar");
        var strengthLabel = document.getElementById("password-strength-label");
        var strengthWarning = document.getElementById("password-strength-warning");

        passwordInput.addEventListener("input", function () {
            var val = passwordInput.value || "";
            var score = calculatePasswordScore(val);
            updateStrengthUI(score, strengthBar, strengthLabel, strengthWarning);
        });
    }

    function calculatePasswordScore(password) {
        if (!password) return 0;

        var score = 0;

        // Length
        if (password.length >= 8) score += 25;
        if (password.length >= 12) score += 15;

        // Contains uppercase
        if (/[A-Z]/.test(password)) score += 15;

        // Contains lowercase
        if (/[a-z]/.test(password)) score += 15;

        // Contains digits
        if (/\d/.test(password)) score += 15;

        // Contains special chars
        if (/[^A-Za-z0-9]/.test(password)) score += 15;

        if (score > 100) score = 100;
        return score;
    }

    function updateStrengthUI(score, bar, label, warning) {
        if (!bar || !label) return;

        var text;
        var colorClass;

        if (score === 0) {
            text = "Password strength: N/A";
            colorClass = "bg-secondary";
        } else if (score <= 30) {
            text = "Password strength: Very weak";
            colorClass = "bg-danger";
        } else if (score <= 50) {
            text = "Password strength: Weak";
            colorClass = "bg-warning";
        } else if (score <= 75) {
            text = "Password strength: Good";
            colorClass = "bg-info";
        } else {
            text = "Password strength: Strong";
            colorClass = "bg-success";
        }

        bar.style.width = score + "%";
        bar.className = "progress-bar " + colorClass;
        label.textContent = text;

        if (warning) {
            warning.classList.toggle("d-none", score >= 50);
        }
    }

    // ---------------------------------------------------------------------
    // Mark active navigation links (basic)
    // ---------------------------------------------------------------------
    function initActiveNavLinks() {
        var currentPath = window.location.pathname;
        var navLinks = document.querySelectorAll(".admin-sidebar .nav-link, .navbar .nav-link");

        navLinks.forEach(function (link) {
            var href = link.getAttribute("href");
            if (!href) return;

            try {
                var linkUrl = new URL(href, window.location.origin);
                if (currentPath === linkUrl.pathname) {
                    link.classList.add("active");
                }
            } catch (e) {
                // Ignore invalid URLs
            }
        });
    }

})();
