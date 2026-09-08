// Dashboard state and logic

class Dashboard {
  constructor() {
    this.meals = [];
    this.dailyTotals = {
      calories: 0,
      protein_g: 0,
      carbs_g: 0,
      fats_g: 0,
      fiber_g: 0,
      confidence_distribution: { high: 0, medium: 0, low: 0 },
    };
    this.selectedDate = formatISO(new Date());
    this.macroChart = new MacroChart('macro-chart-canvas');
    this.isLoading = false;
  }

  async fetchDashboard() {
    if (this.isLoading) return;

    this.isLoading = true;
    try {
      const data = await apiGet(`/dashboard?date=${this.selectedDate}`);
      this.meals = data.meals || [];
      this.dailyTotals = data.daily_totals || {
        calories: 0,
        protein_g: 0,
        carbs_g: 0,
        fats_g: 0,
        fiber_g: 0,
        confidence_distribution: { high: 0, medium: 0, low: 0 },
      };
      this.render();
    } catch (error) {
      console.error('Error fetching dashboard:', error);
      this.showError('Failed to load dashboard');
    } finally {
      this.isLoading = false;
    }
  }

  async addMeal(audioBlob) {
    if (this.isLoading) return;

    this.isLoading = true;
    try {
      recorder.uploadAndProcess(
        (progress) => this.showProgress(progress),
        (meal) => {
          this.meals.unshift(meal);
          this.updateTotals();
          this.render();
          this.showSuccess('Meal added successfully');
        },
        (error) => {
          this.showError(error.message);
        }
      );
    } finally {
      this.isLoading = false;
    }
  }

  async updateMeal(mealId, mealItems) {
    if (this.isLoading) return;

    this.isLoading = true;
    try {
      const updatedMeal = await apiPatch(`/meals/${mealId}`, {
        meal_items: mealItems,
      });

      const index = this.meals.findIndex(m => m.meal_id === updatedMeal.meal_id);
      if (index !== -1) {
        this.meals[index] = updatedMeal;
      }

      this.updateTotals();
      this.render();
      this.showSuccess('Meal updated successfully');
    } catch (error) {
      console.error('Error updating meal:', error);
      this.showError('Failed to update meal');
    } finally {
      this.isLoading = false;
    }
  }

  async deleteMeal(mealId) {
    if (!confirm('Delete this meal?')) return;

    if (this.isLoading) return;

    this.isLoading = true;
    try {
      await apiDelete(`/meals/${mealId}`);
      this.meals = this.meals.filter(m => m.meal_id !== mealId);
      this.updateTotals();
      this.render();
      this.showSuccess('Meal deleted');
    } catch (error) {
      console.error('Error deleting meal:', error);
      this.showError('Failed to delete meal');
    } finally {
      this.isLoading = false;
    }
  }

  updateTotals() {
    this.dailyTotals = {
      calories: 0,
      protein_g: 0,
      carbs_g: 0,
      fats_g: 0,
      fiber_g: 0,
      confidence_distribution: { high: 0, medium: 0, low: 0 },
    };

    this.meals.forEach(meal => {
      this.dailyTotals.calories += meal.totals.calories;
      this.dailyTotals.protein_g += meal.totals.protein_g;
      this.dailyTotals.carbs_g += meal.totals.carbs_g;
      this.dailyTotals.fats_g += meal.totals.fats_g;
      this.dailyTotals.fiber_g += meal.totals.fiber_g;
    });
  }

  render() {
    this.renderSummary();
    this.renderMealList();
    this.renderMacroChart();
  }

  renderSummary() {
    const summary = document.getElementById('daily-summary');
    if (!summary) return;

    const { calories, protein_g, carbs_g, fats_g, fiber_g } = this.dailyTotals;

    summary.innerHTML = `
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <div class="bg-white rounded-lg p-4 shadow-sm">
          <p class="text-xs text-gray-600 mb-1">Calories</p>
          <p class="text-2xl font-bold text-gray-900">${formatNumber(calories)}</p>
          <p class="text-xs text-gray-500 mt-1">kcal</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm">
          <p class="text-xs text-gray-600 mb-1">Protein</p>
          <p class="text-2xl font-bold text-gray-900">${formatNumber(protein_g)}</p>
          <p class="text-xs text-gray-500 mt-1">g</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm">
          <p class="text-xs text-gray-600 mb-1">Carbs</p>
          <p class="text-2xl font-bold text-gray-900">${formatNumber(carbs_g)}</p>
          <p class="text-xs text-gray-500 mt-1">g</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm">
          <p class="text-xs text-gray-600 mb-1">Fats</p>
          <p class="text-2xl font-bold text-gray-900">${formatNumber(fats_g)}</p>
          <p class="text-xs text-gray-500 mt-1">g</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm">
          <p class="text-xs text-gray-600 mb-1">Fiber</p>
          <p class="text-2xl font-bold text-gray-900">${formatNumber(fiber_g)}</p>
          <p class="text-xs text-gray-500 mt-1">g</p>
        </div>
      </div>
    `;
  }

  renderMealList() {
    const list = document.getElementById('meals-list');
    if (!list) return;

    if (this.meals.length === 0) {
      list.innerHTML = '<p class="text-center text-gray-500 py-8">No meals recorded yet</p>';
      return;
    }

    list.innerHTML = this.meals.map(meal => `
      <div class="bg-white rounded-lg shadow-sm p-4 mb-4">
        <div class="flex items-start justify-between mb-3">
          <div class="flex-1">
            <h3 class="font-medium text-gray-900">${meal.meal_items.map(i => i.item_name).join(', ')}</h3>
            <p class="text-sm text-gray-500 mt-1">${formatTime(meal.created_at)}</p>
          </div>
          <span class="inline-block px-3 py-1 text-sm font-medium rounded-full" style="background-color: ${getConfidenceColor(meal.confidence_score)}; color: white;">
            ${Math.round(meal.confidence_score * 100)}%
          </span>
        </div>
        <div class="grid grid-cols-3 gap-2 mb-3 text-sm">
          <div>
            <p class="text-gray-600">Calories</p>
            <p class="font-semibold text-gray-900">${formatNumber(meal.totals.calories)}</p>
          </div>
          <div>
            <p class="text-gray-600">Protein</p>
            <p class="font-semibold text-gray-900">${formatNumber(meal.totals.protein_g, 1)}g</p>
          </div>
          <div>
            <p class="text-gray-600">Carbs</p>
            <p class="font-semibold text-gray-900">${formatNumber(meal.totals.carbs_g, 1)}g</p>
          </div>
        </div>
        <button class="text-sm text-red-600 hover:text-red-800" onclick="dashboard.deleteMeal('${meal.meal_id}')">Delete</button>
      </div>
    `).join('');
  }

  renderMacroChart() {
    if (this.dailyTotals.calories === 0) {
      this.macroChart.renderEmpty();
    } else {
      this.macroChart.render(this.dailyTotals);
    }
  }

  showError(message) {
    const alert = document.createElement('div');
    alert.className = 'fixed top-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded';
    alert.textContent = message;
    document.body.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
  }

  showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'fixed top-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded';
    alert.textContent = message;
    document.body.appendChild(alert);
    setTimeout(() => alert.remove(), 3000);
  }

  showProgress(message) {
    // Could add a progress indicator here
    console.log(message);
  }
}

// Initialize on page load
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
  if (isTokenValid()) {
    dashboard = new Dashboard();
    dashboard.fetchDashboard();

    // Set up record button
    const recordBtn = document.getElementById('record-btn');
    if (recordBtn) {
      recordBtn.addEventListener('click', () => handleRecord());
    }
  }
});

async function handleRecord() {
  const recordBtn = document.getElementById('record-btn');
  const statusEl = document.getElementById('record-status');

  try {
    if (recorder.state === 'idle') {
      recordBtn.textContent = '⏹ Stop';
      recordBtn.classList.add('recording');
      statusEl.textContent = 'Recording...';
      await recorder.start();
    } else if (recorder.state === 'recording') {
      recordBtn.textContent = '🎤 Processing...';
      recordBtn.disabled = true;
      statusEl.textContent = 'Processing audio...';
      recorder.stop();
      await new Promise(r => setTimeout(r, 100)); // Let recorder finish
      await recorder.uploadAndProcess(
        () => {},
        (meal) => {
          dashboard.meals.unshift(meal);
          dashboard.updateTotals();
          dashboard.render();
          statusEl.textContent = 'Meal added!';
          recordBtn.textContent = '🎤 Record';
          recordBtn.disabled = false;
          setTimeout(() => { statusEl.textContent = ''; }, 3000);
        },
        (error) => {
          statusEl.textContent = `Error: ${error.message}`;
          recordBtn.textContent = '🎤 Record';
          recordBtn.disabled = false;
          setTimeout(() => { statusEl.textContent = ''; }, 5000);
        }
      );
    }
  } catch (error) {
    statusEl.textContent = `Error: ${error.message}`;
    recordBtn.textContent = '🎤 Record';
    recordBtn.disabled = false;
    setTimeout(() => { statusEl.textContent = ''; }, 5000);
  }
}
