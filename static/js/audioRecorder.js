// Audio recorder for voice meal input
class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
    this.state = 'idle';  // idle, recording, processing
    this.startTime = null;
    this.mimeType = null;

    // Determine supported MIME type
    const mimeTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/mpeg',
    ];

    for (const type of mimeTypes) {
      if (MediaRecorder.isTypeSupported(type)) {
        this.mimeType = type;
        break;
      }
    }

    if (!this.mimeType) {
      this.mimeType = 'audio/webm';
    }
  }

  async start() {
    if (this.state !== 'idle') {
      throw new Error('Recorder not in idle state');
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (error.name === 'NotAllowedError') {
        throw new Error('Microphone permission denied');
      }
      throw error;
    }

    this.audioChunks = [];
    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: this.mimeType });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event.error);
      this.state = 'idle';
    };

    this.state = 'recording';
    this.startTime = Date.now();
    this.mediaRecorder.start();
  }

  stop() {
    if (this.state !== 'recording') {
      throw new Error('Recorder not recording');
    }

    const duration = (Date.now() - this.startTime) / 1000;

    // Check minimum duration (1.5 seconds)
    if (duration < 1.5) {
      this.state = 'idle';
      this.mediaRecorder.stop();
      this.stream.getTracks().forEach(track => track.stop());
      throw new Error('Recording too short. Minimum 1.5 seconds required.');
    }

    this.state = 'processing';
    this.mediaRecorder.stop();
  }

  getBlob() {
    return new Promise((resolve) => {
      const audioBlob = new Blob(this.audioChunks, { type: this.mimeType });
      this.state = 'idle';
      this.stream.getTracks().forEach(track => track.stop());
      resolve(audioBlob);
    });
  }

  async uploadAndProcess(onProgress, onSuccess, onError) {
    try {
      const audioBlob = await this.getBlob();

      // Determine file extension
      let extension = '.webm';
      if (this.mimeType.includes('mp4')) extension = '.m4a';
      else if (this.mimeType.includes('mpeg')) extension = '.mp3';

      const formData = new FormData();
      formData.append('file', audioBlob, `recording${extension}`);

      try {
        const result = await apiPostFile('/meals/voice', formData);
        onSuccess(result);
      } catch (error) {
        // apiPostFile already attaches the parsed backend response as error.status/error.body
        let errorMessage = error.body && error.body.detail;

        if (!errorMessage) {
          if (error.status === 413) {
            errorMessage = 'Recording too long. Maximum 25MB.';
          } else if (error.status === 422) {
            errorMessage = 'Could not understand the recording. Please try again with a clearer voice.';
          } else if (error.status === 400) {
            errorMessage = 'Unsupported audio format.';
          } else if (error.status === 503) {
            errorMessage = 'Speech recognition service unavailable.';
          } else {
            errorMessage = 'Failed to process audio';
          }
        }

        onError(new Error(errorMessage));
      }
    } catch (error) {
      onError(error);
    }
  }
}

// Export for use
const recorder = new AudioRecorder();
