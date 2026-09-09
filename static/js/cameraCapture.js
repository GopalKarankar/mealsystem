class CameraCapture {
  constructor() {
    this.stream = null;
    this.state = 'idle'; // idle | streaming | captured
    this.videoElement = null;
  }

  async start(videoElement, onStreamEnded) {
    if (this.state === 'streaming') return;

    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Camera requires a secure connection (HTTPS or localhost)');
    }

    this.videoElement = videoElement;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      });

      videoElement.srcObject = this.stream;
      await videoElement.play();

      this.stream.getVideoTracks().forEach(track => {
        track.addEventListener('ended', () => onStreamEnded?.());
      });

      this.state = 'streaming';
    } catch (err) {
      let message = 'Unable to access camera';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        message = 'Camera permission denied. Please enable camera access in your browser settings.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        message = 'No camera found on this device';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        message = 'Camera is already in use by another application';
      }
      throw new Error(message);
    }
  }

  async capture() {
    return new Promise((resolve, reject) => {
      if (!this.videoElement) {
        reject(new Error('No video element available'));
        return;
      }

      const canvas = document.createElement('canvas');
      canvas.width = this.videoElement.videoWidth;
      canvas.height = this.videoElement.videoHeight;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Unable to create canvas context'));
        return;
      }

      ctx.drawImage(this.videoElement, 0, 0);

      canvas.toBlob(
        blob => {
          if (!blob) {
            reject(new Error('Failed to capture photo'));
            return;
          }
          resolve(blob);
        },
        'image/jpeg',
        0.9
      );
    });
  }

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
    this.stream = null;
    this.videoElement = null;
    this.state = 'idle';
  }

  toFile(blob) {
    return new File([blob], `camera-capture-${Date.now()}.jpg`, { type: 'image/jpeg' });
  }
}

const cameraCapture = new CameraCapture();
