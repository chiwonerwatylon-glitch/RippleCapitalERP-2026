// Ripple Capital - light/dark mode toggle for pages that do not extend base.html.
// The initial theme is set inline in <head> (partials/theme_head.html) before paint.
(function () {
    "use strict";

    var root = document.documentElement;

    function currentTheme() {
        return root.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
    }

    function syncButtons() {
        var dark = currentTheme() === "dark";
        var label = dark ? "Switch to light mode" : "Switch to dark mode";
        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
            var icon = btn.querySelector("i");
            if (icon) icon.className = dark ? "fas fa-sun" : "fas fa-moon";
            btn.setAttribute("aria-label", label);
            btn.setAttribute("title", label);
        });
    }

    function setTheme(theme, persist) {
        root.setAttribute("data-bs-theme", theme);
        if (persist) {
            try { localStorage.setItem("ripple-theme", theme); } catch (e) {}
        }
        syncButtons();
    }

    document.addEventListener("DOMContentLoaded", function () {
        syncButtons();

        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                setTheme(currentTheme() === "dark" ? "light" : "dark", true);
            });
        });

        // Enable colour transitions only after first paint.
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                root.classList.add("theme-ready");
            });
        });
    });

    // Follow OS changes only when the user has not picked a theme.
    if (window.matchMedia) {
        var mq = window.matchMedia("(prefers-color-scheme: dark)");
        var onChange = function (e) {
            var saved = null;
            try { saved = localStorage.getItem("ripple-theme"); } catch (err) {}
            if (saved !== "light" && saved !== "dark") setTheme(e.matches ? "dark" : "light", false);
        };
        if (mq.addEventListener) mq.addEventListener("change", onChange);
        else if (mq.addListener) mq.addListener(onChange);
    }
})();

