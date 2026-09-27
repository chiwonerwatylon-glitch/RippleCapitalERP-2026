// static/js/charts.js

// This file is prepared for when you want to add Chart.js dashboards.
// It checks if Chart.js is loaded and, if so, can render summary charts.

document.addEventListener("DOMContentLoaded", function () {
  if (typeof Chart === "undefined") {
    // Chart.js not loaded; nothing to do.
    return;
  }

  const ctxCommissionByInsurer = document.getElementById("chartCommissionByInsurer");
  if (ctxCommissionByInsurer) {
    const labels = JSON.parse(ctxCommissionByInsurer.dataset.labels || "[]");
    const data = JSON.parse(ctxCommissionByInsurer.dataset.values || "[]");

    new Chart(ctxCommissionByInsurer, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Commission (KES)",
            data: data,
            backgroundColor: "rgba(12, 19, 38, 0.8)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true },
        },
      },
    });
  }
});
