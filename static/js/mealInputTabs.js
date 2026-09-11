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

  // Manual flow
  const manualSubmitBtn = document.getElementById('manual-submit-btn');
  if (manualSubmitBtn) {
    manualSubmitBtn.addEventListener('click', handleManualSubmit);
  }

  // Camera flow
  const photoCameraTriggerBtn = document.getElementById('photo-camera-trigger-btn');
  const photoCameraCloseBtn = document.getElementById('photo-camera-close-btn');
  const photoCameraCaptureBtn = document.getElementById('photo-camera-capture-btn');
  const photoCameraRetakeBtn = document.getElementById('photo-camera-retake-btn');
  const photoCameraUseBtn = document.getElementById('photo-camera-use-btn');

  if (photoCameraTriggerBtn) {
    photoCameraTriggerBtn.addEventListener('click', openCameraView);
  }

  if (photoCameraCloseBtn) {
    photoCameraCloseBtn.addEventListener('click', closeCameraView);
  }

  if (photoCameraCaptureBtn) {
    photoCameraCaptureBtn.addEventListener('click', handleCameraCapture);
  }

  if (photoCameraRetakeBtn) {
    photoCameraRetakeBtn.addEventListener('click', retakeCamera);
  }

  if (photoCameraUseBtn) {
    photoCameraUseBtn.addEventListener('click', useCameraPhoto);
  }

  // Page unload cleanup
  window.addEventListener('beforeunload', () => cameraCapture.stop());
}

function switchTab(button) {
  // Close camera if open when switching tabs
  const photoCameraView = document.getElementById('photo-camera-view');
  if (photoCameraView && !photoCameraView.classList.contains('hidden')) {
    closeCameraViewIfOpen();
  }

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
  photoStatus.textContent = 'Scanning photo… this can take up to 75 seconds if the vision service is busy';

  try {
    const response = await apiPostFile('/meals/image', formData, 75000);
    clearPhotoSelection();
    photoStatus.textContent = '';
    photoSubmitBtn.disabled = false;
    dashboard.handleMealResult(response);
  } catch (error) {
    let message = error.body?.detail || error.message || 'Failed to scan photo';

    // Handle timeout/abort errors
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      message = 'Request timed out. Please try again.';
    }
    // Map HTTP status codes to friendly messages
    else if (error.status === 413) {
      message = 'Photo is too large. Maximum 10MB.';
    } else if (error.status === 422 && !error.body?.detail) {
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

// Camera capture functions
async function openCameraView() {
  const photoCameraTriggerBtn = document.getElementById('photo-camera-trigger-btn');
  const photoCameraView = document.getElementById('photo-camera-view');
  const photoCameraVideo = document.getElementById('photo-camera-video');
  const photoCameraErrorEl = document.getElementById('photo-camera-error');
  const photoCameraCaptureBtn = document.getElementById('photo-camera-capture-btn');

  photoCameraTriggerBtn.setAttribute('aria-expanded', 'true');
  photoCameraErrorEl.classList.add('hidden');
  photoCameraView.classList.remove('hidden');

  try {
    await cameraCapture.start(photoCameraVideo, handleStreamEnded);
    photoCameraCaptureBtn.focus();
  } catch (err) {
    photoCameraErrorEl.textContent = err.message;
    photoCameraErrorEl.classList.remove('hidden');
  }
}

function closeCameraView() {
  const photoCameraTriggerBtn = document.getElementById('photo-camera-trigger-btn');
  const photoCameraView = document.getElementById('photo-camera-view');

  cameraCapture.stop();
  photoCameraView.classList.add('hidden');
  photoCameraTriggerBtn.setAttribute('aria-expanded', 'false');
  photoCameraTriggerBtn.focus();
}

function closeCameraViewIfOpen() {
  const photoCameraView = document.getElementById('photo-camera-view');
  if (photoCameraView && !photoCameraView.classList.contains('hidden')) {
    closeCameraView();
  }
}

function handleStreamEnded() {
  const photoCameraErrorEl = document.getElementById('photo-camera-error');
  const photoCameraVideo = document.getElementById('photo-camera-video');

  photoCameraErrorEl.textContent = 'Camera access was lost. Please click Cancel and try again.';
  photoCameraErrorEl.classList.remove('hidden');
  // Pause video to show last frame
  if (photoCameraVideo) {
    photoCameraVideo.pause();
  }
}

async function handleCameraCapture() {
  const photoCameraVideo = document.getElementById('photo-camera-video');
  const photoCameraErrorEl = document.getElementById('photo-camera-error');
  const photoCameraCaptureBtn = document.getElementById('photo-camera-capture-btn');
  const photoCameraRetakeBtn = document.getElementById('photo-camera-retake-btn');
  const photoCameraUseBtn = document.getElementById('photo-camera-use-btn');

  photoCameraErrorEl.classList.add('hidden');

  try {
    const blob = await cameraCapture.capture();
    // Pause video to show frozen frame as preview
    photoCameraVideo.pause();
    // Store the captured blob for later use
    window.capturedPhotoBlob = blob;
    // Swap button visibility
    photoCameraCaptureBtn.classList.add('hidden');
    photoCameraRetakeBtn.classList.remove('hidden');
    photoCameraUseBtn.classList.remove('hidden');
  } catch (err) {
    photoCameraErrorEl.textContent = err.message || 'Failed to capture photo';
    photoCameraErrorEl.classList.remove('hidden');
  }
}

function retakeCamera() {
  const photoCameraVideo = document.getElementById('photo-camera-video');
  const photoCameraCaptureBtn = document.getElementById('photo-camera-capture-btn');
  const photoCameraRetakeBtn = document.getElementById('photo-camera-retake-btn');
  const photoCameraUseBtn = document.getElementById('photo-camera-use-btn');
  const photoCameraErrorEl = document.getElementById('photo-camera-error');

  // Resume video stream
  photoCameraVideo.play();
  // Swap button visibility back
  photoCameraCaptureBtn.classList.remove('hidden');
  photoCameraRetakeBtn.classList.add('hidden');
  photoCameraUseBtn.classList.add('hidden');
  photoCameraErrorEl.classList.add('hidden');
  window.capturedPhotoBlob = null;
}

async function useCameraPhoto() {
  const blob = window.capturedPhotoBlob;
  if (!blob) {
    alert('No photo captured');
    return;
  }

  const file = cameraCapture.toFile(blob);
  cameraCapture.stop();
  handlePhotoSelect(file);
  closeCameraView();
  // Focus on submit button
  const photoSubmitBtn = document.getElementById('photo-submit-btn');
  photoSubmitBtn.focus();
}

async function handleManualSubmit() {
  const foodName = document.getElementById('manual-food-name');
  const remark = document.getElementById('manual-remark');
  const category = document.getElementById('manual-category');
  const status = document.getElementById('manual-status');
  const submitBtn = document.getElementById('manual-submit-btn');

  const name = foodName.value.trim();
  if (!name) {
    status.textContent = 'Please enter a food name';
    return;
  }

  const text = remark.value.trim() ? `${name}, ${remark.value.trim()}` : name;

  submitBtn.disabled = true;
  status.textContent = 'Adding meal...';

  try {
    const response = await apiPost('/meals/text', { text, category: category.value });
    foodName.value = '';
    remark.value = '';
    status.textContent = '';
    submitBtn.disabled = false;
    dashboard.handleMealResult(response);
  } catch (error) {
    status.textContent = error.body?.detail || error.message || 'Failed to add meal';
    submitBtn.disabled = false;
  }
}
