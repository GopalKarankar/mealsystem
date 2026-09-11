/**
 * MealItemsEditor: Shared UI for editing meal items (pre-save review or post-save edit).
 * Renders editable rows: name (text), quantity (number), unit (select).
 * Macros displayed as read-only.
 */

class MealItemsEditor {
  constructor(items = [], options = {}) {
    this.items = items;
    this.options = {
      showTranscription: options.showTranscription || false,
      transcription: options.transcription || "",
      ...options
    };
    this.unitOptions = ["g", "kg", "ml", "l", "oz", "cup", "bowl", "plate", "piece", "serving"];
  }

  render() {
    const html = `
      <div class="meal-editor" style="padding: 16px;">
        ${this.options.showTranscription ? `
          <div style="margin-bottom: 16px;">
            <label style="display: block; font-weight: 700; margin-bottom: 8px;">
              Transcription
            </label>
            <p style="margin: 0; color: #546E7A;">${escapeHtml(this.options.transcription)}</p>
          </div>
        ` : ""}

        <div style="margin-bottom: 16px;">
          <label style="display: block; font-weight: 700; margin-bottom: 8px;">
            Meal Items
          </label>
          <div id="items-list" style="display: flex; flex-direction: column; gap: 12px;">
            ${this.items.map((item, idx) => this.renderItemRow(item, idx)).join("")}
          </div>
          <button id="add-item-btn" type="button" style="margin-top: 12px; padding: 8px 16px; border: 1px dashed #FF7043; background-color: transparent; color: #FF7043; border-radius: 4px; cursor: pointer; font-family: inherit; font-size: inherit; font-weight: 500; width: 100%; transition: background-color 0.2s;">
            + Add Meal Item
          </button>
        </div>

        <div style="display: flex; gap: 8px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid #F3F4F6;">
          <button id="cancel-btn" class="btn btn-secondary" style="padding: 8px 16px;">Cancel</button>
          <button id="save-btn" class="btn btn-primary" style="padding: 8px 16px; background-color: #FF7043; color: white; border: none; border-radius: 4px; cursor: pointer;">Save Meal</button>
        </div>
      </div>
    `;
    return html;
  }

  createEmptyItem() {
    return {
      item_name: "",
      quantity: 1,
      unit: "serving",
      serving_size_grams: null,
      calories: 0,
      protein_g: 0,
      carbs_g: 0,
      fats_g: 0,
      fiber_g: 0,
      confidence: 0.85,
      source: "user_input"
    };
  }

  renderItemRow(item, idx) {
    return `
      <div class="item-row" data-idx="${idx}" style="display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr; gap: 8px; align-items: center; padding: 8px; background-color: #FFFDF9; border-radius: 8px; border: 1px solid #F3F4F6;">
        <input type="text" class="item-name-input" value="${escapeHtml(item.item_name)}" placeholder="Food name" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px; font-family: inherit; font-size: inherit;" />
        <input type="number" class="item-qty-input" value="${item.quantity}" min="0.01" step="0.1" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px; font-family: inherit; font-size: inherit;" />
        <select class="item-unit-select" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px; font-family: inherit; font-size: inherit;">
          ${this.unitOptions.map(u => `<option value="${u}" ${u === item.unit ? "selected" : ""}>${u}</option>`).join("")}
        </select>
        <div style="font-size: 12px; color: #546E7A;">
          ${Math.round(item.calories)} kcal | P: ${item.protein_g.toFixed(1)}g C: ${item.carbs_g.toFixed(1)}g F: ${item.fats_g.toFixed(1)}g
        </div>
      </div>
    `;
  }

  getEditedItems() {
    const rows = document.querySelectorAll(".item-row");
    const items = [];
    rows.forEach(row => {
      const idx = parseInt(row.dataset.idx);
      const oldItem = this.items[idx];
      items.push({
        ...oldItem,
        item_name: row.querySelector(".item-name-input").value,
        quantity: parseFloat(row.querySelector(".item-qty-input").value),
        unit: row.querySelector(".item-unit-select").value
      });
    });
    return items;
  }

  mount(selector) {
    const container = document.querySelector(selector);
    if (!container) return;
    container.innerHTML = this.render();
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}
