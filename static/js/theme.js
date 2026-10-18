// Ripple Capital - follows the OS light/dark setting for pages that do not extend base.html.
// The initial theme is set inline in <head> (partials/theme_head.html) before paint.
(function () {
    "use strict";

    var root = document.documentElement;

    function setTheme(theme) {
        root.setAttribute("data-bs-theme", theme);
    }

    document.addEventListener("DOMContentLoaded", function () {
        // Enable colour transitions only after first paint.
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                root.classList.add("theme-ready");
            });
        });
    });

    if (window.matchMedia) {
        var mq = window.matchMedia("(prefers-color-scheme: dark)");
        var onChange = function (e) { setTheme(e.matches ? "dark" : "light"); };
        if (mq.addEventListener) mq.addEventListener("change", onChange);
        else if (mq.addListener) mq.addListener(onChange);
    }
})();

