// Manual meal form — dynamic multi-block, multi-item UI matching docs/dashboard-manually.png
// State and rendering are entirely JS-driven; templates/dashboard.html only provides mount points.

let manualBlocks = [];
let manualBlockIdSeq = 0;
let manualItemIdSeq = 0;

function createManualBlock() {
  return {
    id: manualBlockIdSeq++,
    items: [createManualItem()],
    remark: '',
    date: '',
    time: '',
    mealCategory: deriveMealCategoryFromTime(),
    userOverrodeCategory: false,
    status: null,
    errorMessage: ''
  };
}

function createManualItem() {
  return { id: manualItemIdSeq++, name: '', qty: '', unit: 'serving' };
}

function initManualForm() {
  manualBlocks = [createManualBlock()];
  renderManualBlocks();

  const container = document.getElementById('manual-meal-blocks');
  container.addEventListener('click', handleManualContainerClick);
  container.addEventListener('input', handleManualContainerInput);
  container.addEventListener('change', handleManualContainerChange);

  document.getElementById('manual-add-meal-btn').addEventListener('click', () => {
    manualBlocks.push(createManualBlock());
    renderManualBlocks();
  });

  document.getElementById('manual-submit-btn').addEventListener('click', handleManualSubmit);
}

function renderManualBlocks() {
  const container = document.getElementById('manual-meal-blocks');
  container.innerHTML = manualBlocks.map((block, i) => renderManualBlock(block, i)).join('');
}

function renderManualBlock(block, blockIndex) {
  const showDivider = blockIndex > 0;
  const itemRows = block.items.map((item, itemIndex) => renderManualItemRow(block, item, itemIndex)).join('');
  const pills = renderManualPills(block);
  const showRemoveBlock = manualBlocks.length > 1;

  const statusHtml = block.status === 'error' && block.errorMessage
    ? `<div class="text-sm text-error mt-2 mb-2">${escapeHtml(block.errorMessage)}</div>`
    : '';

  return `
    ${showDivider ? '<hr class="border-t border-dashed border-gray-300 my-5" />' : ''}
    <div data-block-id="${block.id}" class="manual-block">
      <div class="grid grid-cols-[2fr_1fr_1fr] gap-3 mb-4">
        ${itemRows}
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium text-heading mb-2">Remark (optional)</label>
        <input type="text" placeholder="e.g. grilled with olive oil" maxlength="255"
          class="manual-remark-input w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
          value="${escapeHtml(block.remark)}" data-block-id="${block.id}" />
      </div>

      <div class="grid grid-cols-[1fr_1fr] gap-3 mb-4">
        <div>
          <label class="block text-sm font-medium text-heading mb-2">Date</label>
          <input type="date" class="manual-date-input w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
            value="${block.date}" data-block-id="${block.id}" />
        </div>
        <div>
          <label class="block text-sm font-medium text-heading mb-2">Time</label>
          <input type="time" class="manual-time-input w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
            value="${block.time}" data-block-id="${block.id}" />
        </div>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium text-heading mb-2">Meal Type</label>
        ${pills}
      </div>

      <div class="flex items-center justify-between mb-2">
        <button type="button" class="manual-add-item-btn flex items-center gap-1 text-brand-orange font-medium text-sm hover:underline focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2 rounded"
          data-block-id="${block.id}">
          <span aria-hidden="true">➕</span> Add Item
        </button>
        ${showRemoveBlock ? `
          <button type="button" class="manual-remove-block-btn text-error font-medium text-sm hover:underline focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-2 rounded"
            data-block-id="${block.id}">
            ✕ Remove Meal
          </button>
        ` : ''}
      </div>

      ${statusHtml}
    </div>
  `;
}

function renderManualItemRow(block, item, itemIndex) {
  const isLastItem = block.items.length === 1;
  const isFirstColumn = itemIndex === 0;

  const label = isFirstColumn ? `
    <label class="block text-sm font-medium text-heading mb-2">Food</label>
  ` : '';

  return `
    ${isFirstColumn ? '<div class="col-span-3"><div class="flex items-start gap-3">' : ''}
      <div class="flex-1">
        ${label}
        <input type="text" placeholder="e.g. Chicken breast" maxlength="255"
          class="manual-item-name-input w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
          value="${escapeHtml(item.name)}" data-block-id="${block.id}" data-row-id="${item.id}" />
      </div>
      <div class="flex-0">
        ${isFirstColumn ? '<label class="block text-sm font-medium text-heading mb-2">Qty</label>' : ''}
        <input type="number" min="0.01" step="0.1" placeholder="1"
          class="manual-item-qty-input w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
          value="${item.qty}" data-block-id="${block.id}" data-row-id="${item.id}" />
      </div>
      <div class="flex-0">
        ${isFirstColumn ? '<label class="block text-sm font-medium text-heading mb-2">Unit</label>' : ''}
        <select class="manual-item-unit-select w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2"
          data-block-id="${block.id}" data-row-id="${item.id}">
          <option value="g" ${item.unit === 'g' ? 'selected' : ''}>g</option>
          <option value="kg" ${item.unit === 'kg' ? 'selected' : ''}>kg</option>
          <option value="ml" ${item.unit === 'ml' ? 'selected' : ''}>ml</option>
          <option value="l" ${item.unit === 'l' ? 'selected' : ''}>l</option>
          <option value="oz" ${item.unit === 'oz' ? 'selected' : ''}>oz</option>
          <option value="cup" ${item.unit === 'cup' ? 'selected' : ''}>cup</option>
          <option value="bowl" ${item.unit === 'bowl' ? 'selected' : ''}>bowl</option>
          <option value="plate" ${item.unit === 'plate' ? 'selected' : ''}>plate</option>
          <option value="piece" ${item.unit === 'piece' ? 'selected' : ''}>piece</option>
          <option value="serving" ${item.unit === 'serving' ? 'selected' : ''}>serving</option>
        </select>
      </div>
      ${!isLastItem ? `
        <button type="button" class="manual-remove-item-btn text-error font-medium text-sm hover:underline self-center"
          data-block-id="${block.id}" data-row-id="${item.id}">
          ✕
        </button>
      ` : '<div class="w-10"></div>'}
    ${isFirstColumn ? '</div></div>' : ''}
  `;
}

function renderManualPills(block) {
  const categories = [
    { value: 'early_morning', label: 'Early-Morning' },
    { value: 'breakfast', label: 'Breakfast' },
    { value: 'mid_morning', label: 'Mid-Morning Snack' },
    { value: 'lunch', label: 'Lunch' },
    { value: 'afternoon_snack', label: 'Afternoon Snack' },
    { value: 'dinner', label: 'Dinner' },
    { value: 'bedtime', label: 'Bedtime' }
  ];

  const pills = categories.map(cat => {
    const isActive = cat.value === block.mealCategory;
    const baseClass = 'px-3 py-1.5 text-xs font-medium rounded-full border cursor-pointer transition-colors';
    const activeClass = isActive ? 'bg-brand-orange text-white border-brand-orange' : 'bg-white border-gray-300 text-heading hover:border-brand-orange';
    return `
      <button type="button" class="manual-pill-btn ${baseClass} ${activeClass}"
        data-category="${cat.value}" data-block-id="${block.id}">
        ${cat.label}
      </button>
    `;
  }).join('');

  return `<div class="flex flex-wrap gap-2">${pills}</div>`;
}

function handleManualContainerClick(e) {
  const target = e.target;

  if (target.classList.contains('manual-add-item-btn')) {
    const blockId = parseInt(target.dataset.blockId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      block.items.push(createManualItem());
      renderManualBlocks();
    }
  } else if (target.classList.contains('manual-remove-item-btn')) {
    const blockId = parseInt(target.dataset.blockId);
    const rowId = parseInt(target.dataset.rowId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block && block.items.length > 1) {
      block.items = block.items.filter(item => item.id !== rowId);
      renderManualBlocks();
    }
  } else if (target.classList.contains('manual-remove-block-btn')) {
    const blockId = parseInt(target.dataset.blockId);
    if (manualBlocks.length > 1) {
      manualBlocks = manualBlocks.filter(b => b.id !== blockId);
      renderManualBlocks();
    }
  } else if (target.classList.contains('manual-pill-btn')) {
    const blockId = parseInt(target.dataset.blockId);
    const category = target.dataset.category;
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      block.mealCategory = category;
      block.userOverrodeCategory = true;
      renderManualBlocks();
    }
  }
}

function handleManualContainerInput(e) {
  const target = e.target;

  if (target.classList.contains('manual-item-name-input')) {
    const blockId = parseInt(target.dataset.blockId);
    const rowId = parseInt(target.dataset.rowId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      const item = block.items.find(i => i.id === rowId);
      if (item) item.name = target.value;
    }
  } else if (target.classList.contains('manual-item-qty-input')) {
    const blockId = parseInt(target.dataset.blockId);
    const rowId = parseInt(target.dataset.rowId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      const item = block.items.find(i => i.id === rowId);
      if (item) item.qty = target.value;
    }
  } else if (target.classList.contains('manual-remark-input')) {
    const blockId = parseInt(target.dataset.blockId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) block.remark = target.value;
  }
}

function handleManualContainerChange(e) {
  const target = e.target;

  if (target.classList.contains('manual-item-unit-select')) {
    const blockId = parseInt(target.dataset.blockId);
    const rowId = parseInt(target.dataset.rowId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      const item = block.items.find(i => i.id === rowId);
      if (item) item.unit = target.value;
    }
  } else if (target.classList.contains('manual-date-input') || target.classList.contains('manual-time-input')) {
    const blockId = parseInt(target.dataset.blockId);
    const block = manualBlocks.find(b => b.id === blockId);
    if (block) {
      if (target.classList.contains('manual-date-input')) {
        block.date = target.value;
      } else {
        block.time = target.value;
      }

      if (!block.userOverrodeCategory) {
        block.mealCategory = deriveMealCategoryFromTime(buildDateFromPicked(block));
        renderManualBlocks();
      }
    }
  }
}

function buildDateFromPicked(block) {
  if (!block.date && !block.time) return new Date();
  const datePart = block.date || formatISO(new Date());
  const timePart = block.time || '00:00';
  return new Date(`${datePart}T${timePart}`);
}

function formatISO(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function validateManualBlock(block) {
  const validItems = block.items.filter(item => item.name.trim());
  if (validItems.length === 0) {
    return { valid: false, message: 'Add at least one food item with a name and quantity.' };
  }

  for (const item of validItems) {
    const qty = parseFloat(item.qty);
    if (!item.qty || isNaN(qty) || qty <= 0) {
      return { valid: false, message: 'All food items must have a quantity greater than 0.' };
    }
  }

  return { valid: true, message: '' };
}

function buildManualBlockText(block) {
  const itemStrings = block.items
    .filter(item => item.name.trim())
    .map(item => {
      const qty = item.qty && parseFloat(item.qty) > 0 ? item.qty : '';
      const unit = qty ? item.unit : '';
      return [qty, unit, item.name.trim()].filter(Boolean).join(' ');
    });
  let text = itemStrings.join(', ');
  if (block.remark.trim()) {
    text += `, ${block.remark.trim()}`;
  }
  return text;
}

async function handleManualSubmit() {
  const status = document.getElementById('manual-status');
  const submitBtn = document.getElementById('manual-submit-btn');

  const validations = manualBlocks.map(validateManualBlock);
  if (validations.every(v => !v.valid)) {
    renderManualBlocks();
    status.textContent = 'Please add at least one food item to a meal.';
    status.className = 'text-sm mb-3 text-error';
    return;
  }

  submitBtn.disabled = true;
  const results = { succeeded: 0, failed: 0, total: manualBlocks.length };

  for (const block of manualBlocks) {
    const validation = validateManualBlock(block);
    if (!validation.valid) {
      block.status = 'error';
      block.errorMessage = validation.message;
      results.failed++;
      continue;
    }

    block.status = 'pending';
    status.textContent = `Saving meal ${results.succeeded + results.failed + 1} of ${manualBlocks.length}...`;
    renderManualBlocks();

    const text = buildManualBlockText(block);
    try {
      const preview = await apiPost('/meals/text/preview', { text });
      const confirmPayload = {
        input_method: 'text',
        original_text: text,
        meal_category: block.mealCategory,
        meal_items: preview.items
      };
      const meal = await apiPost('/meals/confirm', confirmPayload);
      dashboard.handleMealResult(meal);
      block.status = 'success';
      results.succeeded++;
    } catch (error) {
      block.status = 'error';
      block.errorMessage = error.body?.detail || error.message || 'Failed to save this meal';
      results.failed++;
    }
  }

  manualBlocks = manualBlocks.filter(b => b.status !== 'success');
  if (manualBlocks.length === 0) {
    manualBlocks = [createManualBlock()];
  }
  renderManualBlocks();

  status.className = results.failed > 0 ? 'text-sm mb-3 text-error' : 'text-sm mb-3 text-success';
  status.textContent = results.failed === 0
    ? `Logged ${results.succeeded} meal(s) successfully.`
    : `${results.succeeded} of ${results.total} meal(s) saved. ${results.failed} failed — see details below and retry.`;

  submitBtn.disabled = false;
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}
