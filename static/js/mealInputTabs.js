// Tab switching and Type/Photo meal input flows

function initMealInputTabs() {
  const tabButtons = document.querySelectorAll('[role="tab"]');
  const tabPanels = document.querySelectorAll('[role="tabpanel"]');

  // Tab switching via click and keyboard
  tabButtons.forEach((button, index) => {
    button.addEventListener('click', () => switchTab(button));
    button.addEventListener('keydown', (e) => {
      const isLeft = e.key === 'ArrowLeft';
      const isRight = e.key === 'ArrowRight';
      if (isLeft || isRight) {
        e.preventDefault();
        const newIndex = isLeft ?
          (index - 1 + tabButtons.length) % tabButtons.length :
          (index + 1) % tabButtons.length;
        tabButtons[newIndex].focus();
        switchTab(tabButtons[newIndex]);
      }
    });
  });

  // Type flow
  const typeSubmitBtn = document.getElementById('type-submit-btn');
  if (typeSubmitBtn) {
    typeSubmitBtn.addEventListener('click', handleTypeSubmit);
  }

  // Photo flow
  const photoInput = document.getElementById('photo-file-input');
  const photoDropzone = document.getElementById('photo-dropzone');
  const photoSubmitBtn = document.getElementById('photo-submit-btn');
  const photoRemoveBtn = document.getElementById('photo-remove-btn');

  if (photoDropzone) {
    photoDropzone.addEventListener('click', () => photoInput.click());
    photoDropzone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        photoInput.click();
      }
    });
    photoDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      photoDropzone.classList.add('border-brand-orange');
    });
    photoDropzone.addEventListener('dragleave', () => {
      photoDropzone.classList.remove('border-brand-orange');
    });
    photoDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      photoDropzone.classList.remove('border-brand-orange');
      if (e.dataTransfer.files.length > 0) {
        handlePhotoSelect(e.dataTransfer.files[0]);
      }
    });
  }

  if (photoInput) {
    photoInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handlePhotoSelect(e.target.files[0]);
      }
    });
  }

  if (photoRemoveBtn) {
    photoRemoveBtn.addEventListener('click', () => clearPhotoSelection());
  }

  if (photoSubmitBtn) {
    photoSubmitBtn.addEventListener('click', handlePhotoSubmit);
  }
}

function switchTab(button) {
  const panelId = button.getAttribute('aria-controls');
  const panel = document.getElementById(panelId);

  if (!panel) return;

  // Deactivate all tabs and hide all panels
  document.querySelectorAll('[role="tab"]').forEach(tab => {
    tab.setAttribute('aria-selected', 'false');
    tab.setAttribute('tabindex', '-1');
    // Remove active styling (orange underline and text)
    tab.classList.remove('border-brand-orange', 'text-brand-orange');
    // Add inactive styling (transparent border and body gray text)
    tab.classList.add('border-transparent', 'text-body');
  });
  document.querySelectorAll('[role="tabpanel"]').forEach(p => {
    p.classList.add('hidden');
  });

  // Activate clicked tab and show its panel
  button.setAttribute('aria-selected', 'true');
  button.setAttribute('tabindex', '0');
  // Add active styling (orange underline and text)
  button.classList.remove('border-transparent', 'text-body');
  button.classList.add('border-brand-orange', 'text-brand-orange');
  panel.classList.remove('hidden');
}

let selectedPhotoFile = null;

function handlePhotoSelect(file) {
  const photoInput = document.getElementById('photo-file-input');
  const photoPreviewImg = document.getElementById('photo-preview-img');
  const photoFilename = document.getElementById('photo-filename');
  const photoPreviewWrap = document.getElementById('photo-preview-wrap');
  const photoSubmitBtn = document.getElementById('photo-submit-btn');

  // Client-side format check (UX only; server does real validation)
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    dashboard.showError('Please select a JPEG, PNG, or WEBP image');
    return;
  }

  selectedPhotoFile = file;

  // Render preview
  const reader = new FileReader();
  reader.onload = (e) => {
    photoPreviewImg.src = e.target.result;
  };
  reader.readAsDataURL(file);

  photoFilename.textContent = file.name;
  photoPreviewWrap.classList.remove('hidden');
  photoSubmitBtn.disabled = false;
}

function clearPhotoSelection() {
  selectedPhotoFile = null;
  const photoInput = document.getElementById('photo-file-input');
  const photoPreviewWrap = document.getElementById('photo-preview-wrap');
  const photoSubmitBtn = document.getElementById('photo-submit-btn');

  if (photoInput) {
    photoInput.value = '';
  }
  photoPreviewWrap.classList.add('hidden');
  photoSubmitBtn.disabled = true;
}

async function handleTypeSubmit() {
  const typeTextarea = document.getElementById('type-textarea');
  const typeStatus = document.getElementById('type-status');
  const typeSubmitBtn = document.getElementById('type-submit-btn');
  const text = typeTextarea.value.trim();

  if (!text) {
    typeStatus.textContent = 'Please enter a description';
    return;
  }

  typeSubmitBtn.disabled = true;
  typeStatus.textContent = 'Adding meal...';

  try {
    const response = await apiPost('/meals/text', { text });
    typeTextarea.value = '';
    typeStatus.textContent = '';
    typeSubmitBtn.disabled = false;
    dashboard.handleMealResult(response);
  } catch (error) {
    typeStatus.textContent = error.body?.detail || error.message || 'Failed to add meal';
    typeSubmitBtn.disabled = false;
  }
}

async function handlePhotoSubmit() {
  const photoStatus = document.getElementById('photo-status');
  const photoSubmitBtn = document.getElementById('photo-submit-btn');

  if (!selectedPhotoFile) {
    photoStatus.textContent = 'Please select a photo';
    return;
  }

  const formData = new FormData();
  formData.append('file', selectedPhotoFile);

  photoSubmitBtn.disabled = true;
  photoStatus.textContent = 'Scanning photo...';

  try {
    const response = await apiPostFile('/meals/image', formData);
    clearPhotoSelection();
    photoStatus.textContent = '';
    photoSubmitBtn.disabled = false;
    dashboard.handleMealResult(response);
  } catch (error) {
    let message = error.body?.detail || error.message || 'Failed to scan photo';

    // Map HTTP status codes to friendly messages
    if (error.status === 413) {
      message = 'Photo is too large. Maximum 10MB.';
    } else if (error.status === 422) {
      message = 'Could not identify food in the photo. Please try a clearer photo.';
    } else if (error.status === 400) {
      message = 'Unsupported image format. Please use JPG, PNG, or WEBP.';
    } else if (error.status === 503) {
      message = 'Vision service is unavailable. Please try again later.';
    }

    photoStatus.textContent = message;
    photoSubmitBtn.disabled = false;
  }
}
