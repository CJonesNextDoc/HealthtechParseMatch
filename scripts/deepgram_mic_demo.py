import asyncio
import json
import os
import queue
import sys

import sounddevice as sd
import websockets

# Version check for websockets
REQUIRED_WS_VERSION = (10, 0)


def check_websockets_version():
    version = tuple(map(int, websockets.__version__.split(".")))
    if version < REQUIRED_WS_VERSION:
        print(f"ERROR: websockets version {websockets.__version__} is too old. Please upgrade to >= 10.0.")
        sys.exit(1)


check_websockets_version()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_URL = os.getenv(
    "DEEPGRAM_URL",
    "wss://api.deepgram.com/v1/listen?model=general&language=en-US&punctuate=true&interim_results=true&encoding=linear16&sample_rate=16000",
)

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 200

audio_q: queue.Queue = queue.Queue()


def audio_callback(indata, frames, time, status):
    pcm16 = indata.copy()
    print("Audio block:", pcm16[:10])  # Print first 10 samples for debug
    audio_q.put_nowait(pcm16)


async def sender(ws):
    while True:
        # Use asyncio.to_thread to get audio from the queue
        pcm16 = await asyncio.to_thread(audio_q.get)
        await ws.send(pcm16.tobytes())


async def main():
    try:
        async with websockets.connect(
            DEEPGRAM_URL,
            additional_headers=[
                ("Authorization", f"Token {DEEPGRAM_API_KEY}"),
                ("Content-Type", "application/octet-stream"),
            ],
        ) as ws:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=int(SAMPLE_RATE * CHUNK_MS / 1000),
                callback=audio_callback,
                device=1,
            ) as stream:
                print("🎙️  Speak now. Ctrl+C to stop.")
                stream.start()  # Explicitly start the stream

                async def receiver():
                    async for msg in ws:
                        print("Raw Deepgram message:", msg)  # Debug: print every message
                        try:
                            data = json.loads(msg)
                        except Exception as e:
                            print("Error decoding JSON:", e)
                            continue
                        # Print transcript if present
                        if "channel" in data and "alternatives" in data["channel"]:
                            for alt in data["channel"]["alternatives"]:
                                transcript = alt.get("transcript")
                                if transcript:
                                    print("Transcript:", transcript)
                        else:
                            print("No transcript found in message.")

                await asyncio.gather(sender(ws), receiver())
    except TypeError as e:
        print("TypeError in websockets.connect:", e)
        print(
            """If you see 'unexpected keyword argument extra_headers', ensure you are using websockets >= 10.0
            and passing extra_headers as a list of tuples."""
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
