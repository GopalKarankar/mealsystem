class WaterTracker {
  constructor() {
    this.date = formatISO(new Date());
    this.glassCount = 0;
    this.target = 10;
  }

  async fetchWaterLog(date) {
    this.date = date;
    try {
      const data = await apiGet(`/health/water?date=${date}`);
      this.glassCount = data.glass_count || 0;
    } catch (err) {
      console.error('Failed to fetch water log:', err);
      this.glassCount = 0;
    }
    this.render();
  }

  async addGlass() {
    const next = this.glassCount + 1;
    try {
      const data = await apiPost('/health/water', { date: this.date, glass_count: next });
      this.glassCount = data.glass_count;
    } catch (err) {
      console.error('Failed to add glass:', err);
    }
    this.render();
  }

  render() {
    const visual = document.getElementById('water-glasses-visual');
    const status = document.getElementById('water-status');
    if (visual) {
      visual.innerHTML = Array.from({ length: this.target }, (_, i) =>
        `<div class="w-6 h-8 rounded ${i < this.glassCount ? 'bg-brand-orange' : 'bg-gray-200'}"></div>`
      ).join('');
    }
    if (status) {
      status.textContent = `${this.glassCount} of ${this.target} glasses completed`;
    }
    if (window.dashboard && document.getElementById('hero-water')) {
      document.getElementById('hero-water').textContent = this.glassCount;
    }
  }
}

let waterTracker;
document.addEventListener('DOMContentLoaded', () => {
  if (!isTokenValid()) return;
  waterTracker = new WaterTracker();
  const datePicker = document.getElementById('water-date-picker');
  const initialDate = formatISO(new Date());
  if (datePicker) datePicker.value = initialDate;
  waterTracker.fetchWaterLog(initialDate);

  if (datePicker) {
    datePicker.addEventListener('change', (e) => waterTracker.fetchWaterLog(e.target.value));
  }
  const addBtn = document.getElementById('water-add-btn');
  if (addBtn) addBtn.addEventListener('click', () => waterTracker.addGlass());
});
