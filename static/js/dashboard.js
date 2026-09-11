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
    this.selectedCategory = null;
    this.categoryCounts = {};
    this.latestWeightKg = null;
    this.macroChart = new MacroChart('macro-chart-canvas');
    this.isLoading = false;
  }

  async fetchDashboard() {
    if (this.isLoading) return;

    this.isLoading = true;
    try {
      const categoryParam = this.selectedCategory ? `&category=${this.selectedCategory}` : '';
      const data = await apiGet(`/meals/dashboard?date=${this.selectedDate}${categoryParam}`);
      this.meals = data.meals || [];
      this.dailyTotals = data.daily_totals || {
        calories: 0,
        protein_g: 0,
        carbs_g: 0,
        fats_g: 0,
        fiber_g: 0,
        confidence_distribution: { high: 0, medium: 0, low: 0 },
      };
      this.categoryCounts = data.category_counts || {};
      this.render();
    } catch (error) {
      console.error('Error fetching dashboard:', error);
      this.showError('Failed to load dashboard');
    } finally {
      this.isLoading = false;
    }
  }

  async fetchLatestWeight() {
    try {
      const data = await apiGet('/health/weight?limit=1');
      this.latestWeightKg = data.entries && data.entries.length ? data.entries[0].weight_kg : null;
    } catch (err) {
      console.error('Error fetching latest weight:', err);
      this.latestWeightKg = null;
    }
  }

  handleMealResult(meal) {
    this.meals.unshift(meal);
    this.updateTotals();
    this.render();
    this.showSuccess('Meal added successfully');
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

  editMeal(mealId) {
    const meal = this.meals.find(m => m.meal_id === parseInt(mealId));
    if (!meal) return;
    this.openMealEditorModal(meal.meal_items, {mode: 'patch', mealId});
  }

  openMealEditorModal(items, options) {
    const modal = document.createElement("div");
    modal.style.cssText = "position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;";

    const editor = new MealItemsEditor(items, {
      showTranscription: options.showTranscription,
      transcription: options.transcription || ""
    });

    modal.innerHTML = `<div style="background: white; border-radius: 12px; padding: 0; max-width: 600px; max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 24px rgba(0,0,0,0.15);">${editor.render()}</div>`;
    document.body.appendChild(modal);

    const cancelBtn = modal.querySelector("#cancel-btn");
    const saveBtn = modal.querySelector("#save-btn");

    cancelBtn.onclick = () => {
      modal.remove();
    };

    saveBtn.onclick = async () => {
      editor.mount(".meal-editor");
      const editedItems = editor.getEditedItems();

      if (options.mode === 'patch') {
        await this.updateMeal(options.mealId, editedItems);
      } else if (options.mode === 'confirm') {
        const confirmPayload = {
          input_method: options.inputMethod,
          original_text: options.originalText || "",
          transcription_text: options.transcriptionText,
          meal_category: options.mealCategory,
          meal_items: editedItems
        };
        if (this.isLoading) return;
        this.isLoading = true;
        try {
          const response = await apiPost('/meals/confirm', confirmPayload);
          this.handleMealResult(response);
          modal.remove();
        } catch (error) {
          console.error('Error confirming meal:', error);
          this.showError('Failed to save meal');
        } finally {
          this.isLoading = false;
        }
      }
      modal.remove();
    };
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
    this.renderCategoryPills();
  }

  renderSummary() {
    const summary = document.getElementById('daily-summary');
    if (!summary) return;

    const { calories, protein_g, carbs_g, fats_g, fiber_g } = this.dailyTotals;

    const cards = [
      { label: 'Calories', value: formatNumber(calories), unit: 'kcal', icon: '🔥' },
      { label: 'Protein', value: formatNumber(protein_g), unit: 'g', icon: '🍗' },
      { label: 'Carbs', value: formatNumber(carbs_g), unit: 'g', icon: '🌾' },
      { label: 'Fats', value: formatNumber(fats_g), unit: 'g', icon: '🧈' },
      { label: 'Fiber', value: formatNumber(fiber_g), unit: 'g', icon: '🌿' },
    ];

    summary.innerHTML = cards.map(card => `
      <div class="bg-white rounded-2xl shadow-card hover:shadow-hover transition-shadow p-4 relative">
        <div class="absolute top-3 right-3 h-10 w-10 rounded-full bg-orange-100 flex items-center justify-center text-orange-700 text-sm">
          ${card.icon}
        </div>
        <p class="text-xs text-body mb-2">${card.label}</p>
        <p class="text-2xl font-bold text-brand-orange">${card.value}</p>
        <p class="text-xs text-body mt-1">${card.unit}</p>
      </div>
    `).join('');

    const heroCalories = document.getElementById('hero-calories');
    if (heroCalories) heroCalories.textContent = formatNumber(calories);
    const heroWeight = document.getElementById('hero-weight');
    if (heroWeight && this.latestWeightKg != null) heroWeight.textContent = formatNumber(this.latestWeightKg, 1);
  }

  renderCategoryPills() {
    const container = document.getElementById('category-pills');
    if (!container) return;

    const pills = [
      { key: null, label: 'All', count: Object.values(this.categoryCounts).reduce((a, b) => a + b, 0) },
      { key: 'early_morning', label: 'Early Morning', count: this.categoryCounts.early_morning || 0 },
      { key: 'breakfast', label: 'Breakfast', count: this.categoryCounts.breakfast || 0 },
      { key: 'mid_morning', label: 'Mid-Morning', count: this.categoryCounts.mid_morning || 0 },
      { key: 'lunch', label: 'Lunch', count: this.categoryCounts.lunch || 0 },
      { key: 'afternoon_snack', label: 'Afternoon Snack', count: this.categoryCounts.afternoon_snack || 0 },
      { key: 'dinner', label: 'Dinner', count: this.categoryCounts.dinner || 0 },
      { key: 'bedtime', label: 'Bedtime', count: this.categoryCounts.bedtime || 0 },
    ];

    container.innerHTML = pills.map(pill => `
      <button
        data-category="${pill.key || ''}"
        class="px-3 py-1 text-xs font-medium rounded-full ${
          this.selectedCategory === pill.key
            ? 'bg-brand-orange text-white'
            : 'bg-gray-200 text-body hover:bg-gray-300'
        } cursor-pointer transition-colors"
      >
        ${pill.label} (${pill.count})
      </button>
    `).join('');

    container.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        this.selectedCategory = btn.dataset.category === '' ? null : btn.dataset.category;
        this.fetchDashboard();
      });
    });
  }

  renderMealList() {
    const list = document.getElementById('meals-list');
    if (!list) return;

    if (this.meals.length === 0) {
      list.innerHTML = '<p class="text-center text-body py-8">No meals recorded yet</p>';
      return;
    }

    const methodIcon = { voice: '🎤', text: '⌨️', image: '📷' };

    list.innerHTML = this.meals.map(meal => `
      <div class="bg-white rounded-2xl shadow-card hover:shadow-hover transition-shadow p-4 mb-4">
        <div class="flex items-start justify-between mb-3">
          <div class="flex-1">
            <h3 class="font-medium text-heading">${meal.meal_items.map(i => i.item_name).join(', ')}</h3>
            <p class="text-sm text-body mt-1">${formatTime(meal.created_at)}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-body mr-1" title="Logged via ${meal.input_method}">${methodIcon[meal.input_method] || ''}</span>
            <span class="inline-block px-3 py-1 text-sm font-bold rounded-full ${getConfidenceTintClass(meal.confidence_score)}">
              ${Math.round(meal.confidence_score * 100)}%
            </span>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-2 mb-3 text-sm">
          <div>
            <p class="text-body">Calories</p>
            <p class="font-semibold text-heading">${formatNumber(meal.totals.calories)}</p>
          </div>
          <div>
            <p class="text-body">Protein</p>
            <p class="font-semibold text-heading">${formatNumber(meal.totals.protein_g, 1)}g</p>
          </div>
          <div>
            <p class="text-body">Carbs</p>
            <p class="font-semibold text-heading">${formatNumber(meal.totals.carbs_g, 1)}g</p>
          </div>
        </div>
        <div style="display: flex; gap: 12px;">
          <button class="text-sm text-brand-orange hover:opacity-80 transition" onclick="dashboard.editMeal('${meal.meal_id}')" style="color: #FF7043; cursor: pointer; border: none; background: none; font-size: inherit; font-family: inherit;">Edit</button>
          <button class="text-sm text-error hover:opacity-80 transition" onclick="dashboard.deleteMeal('${meal.meal_id}')" style="color: #D64444; cursor: pointer; border: none; background: none; font-size: inherit; font-family: inherit;">Delete</button>
        </div>
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
    alert.className = 'fixed top-4 right-4 z-50 bg-error text-white px-4 py-3 rounded-lg shadow-modal flex items-center gap-2';
    alert.textContent = '⚠️ ' + message;
    document.body.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
  }

  showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'fixed top-4 right-4 z-50 bg-success text-white px-4 py-3 rounded-lg shadow-modal flex items-center gap-2';
    alert.textContent = '✓ ' + message;
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
    dashboard.fetchLatestWeight();

    // Set up record button
    const recordBtn = document.getElementById('record-btn');
    if (recordBtn) {
      recordBtn.addEventListener('click', () => handleRecord());
    }

    // Initialize tabbed input UI
    initMealInputTabs();
  }
});

async function handleRecord() {
  const recordBtn = document.getElementById('record-btn');
  const statusEl = document.getElementById('record-status');

  try {
    if (recorder.state === 'idle') {
      recordBtn.textContent = '⏹ Stop';
      recordBtn.classList.add('bg-error', 'animate-pulse');
      recordBtn.classList.remove('bg-brand-orange');
      statusEl.textContent = 'Recording...';
      await recorder.start();
    } else if (recorder.state === 'recording') {
      recordBtn.textContent = '🎤 Processing...';
      recordBtn.disabled = true;
      recordBtn.classList.remove('bg-error', 'animate-pulse');
      recordBtn.classList.add('bg-brand-orange');
      statusEl.textContent = 'Processing audio...';
      recorder.stop();
      await new Promise(r => setTimeout(r, 100)); // Let recorder finish
      await recorder.uploadAndProcess(
        () => {},
        (previewData) => {
          dashboard.openMealEditorModal(previewData.items, {
            mode: 'confirm',
            inputMethod: 'voice',
            originalText: previewData.original_text,
            transcriptionText: previewData.transcription_text,
            showTranscription: true,
            transcription: previewData.transcription_text
          });
          recordBtn.textContent = '🎤 Record';
          recordBtn.disabled = false;
          statusEl.textContent = '';
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
    recordBtn.classList.remove('bg-error', 'animate-pulse');
    recordBtn.classList.add('bg-brand-orange');
    setTimeout(() => { statusEl.textContent = ''; }, 5000);
  }
}
