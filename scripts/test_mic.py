import sounddevice as sd

# Record for 5 seconds
duration = 5  # seconds
fs = 16000  # sample rate

print("Recording...")
recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="float32")
sd.wait()  # Wait until recording is finished
print("Recording finished.")

# Play back the recording
print("Playing back...")
sd.play(recording, samplerate=fs)
sd.wait()  # Wait until playback is finished
print("Playback finished.")
