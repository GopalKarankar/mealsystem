import whisper
import sounddevice as sd
from scipy.io.wavfile import write

SAMPLE_RATE = 16000
DURATION = 5

print("Speak now...")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16"
)

sd.wait()

write("recording.wav", SAMPLE_RATE, audio)

print("Transcribing...")

model = whisper.load_model("base")

result = model.transcribe(
    "recording.wav",
    language="en"
)

print("You said:")
print(result["text"])