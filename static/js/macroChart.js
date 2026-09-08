// Macro pie chart using Chart.js

class MacroChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chart = null;
  }

  render(totals) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) {
      console.error(`Canvas element #${this.canvasId} not found`);
      return;
    }

    // Calculate calories from macros
    const proteinCals = (totals.protein_g || 0) * 4;
    const carbsCals = (totals.carbs_g || 0) * 4;
    const fatsCals = (totals.fats_g || 0) * 9;

    const data = {
      labels: ['Protein', 'Carbs', 'Fats'],
      datasets: [{
        data: [proteinCals, carbsCals, fatsCals],
        backgroundColor: ['#FF7043', '#0369A1', '#D97706'],
        borderColor: ['#E64A19', '#075985', '#B45309'],
        borderWidth: 2,
      }],
    };

    const options = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            font: { size: 12 },
            padding: 15,
            usePointStyle: true,
          },
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = Math.round(context.parsed);
              const percent = Math.round((context.parsed / context.dataset.data.reduce((a, b) => a + b, 0)) * 100);
              return `${label}: ${value} kcal (${percent}%)`;
            },
          },
        },
      },
    };

    // Destroy existing chart if it exists
    if (this.chart) {
      this.chart.destroy();
    }

    const ctx = canvas.getContext('2d');
    this.chart = new Chart(ctx, {
      type: 'doughnut',
      data: data,
      options: options,
    });
  }

  renderEmpty() {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw "No data" message
    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#9CA3AF';
    ctx.textAlign = 'center';
    ctx.fillText('No data to display', canvas.width / 2, canvas.height / 2);

    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }

  clear() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}
