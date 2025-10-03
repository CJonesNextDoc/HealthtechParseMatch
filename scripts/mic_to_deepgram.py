# mic_to_deepgram.py
import asyncio
import json
import os
import queue
import sys

# import threading
import httpx
import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosed

load_dotenv()  # Load environment variables from .env

DG_API_KEY = os.getenv("DEEPGRAM_API_KEY")  # export before running
MODEL = "general"  # general                # good for general speech
ALT = 1  # N-best
NUMERALS = "true"  # turn numbers into digits
URL = f"wss://api.deepgram.com/v1/listen?model={MODEL}&alternatives={ALT}&interim_results=true&punctuate=true&encoding=linear16&sample_rate=16000&endpointing=1200"

# Your API endpoints (adjust if you use /asr/ingest instead)
PARSE_DOB_URL = "http://127.0.0.1:8000/parse/dob"
PARSE_ZIP_URL = "http://127.0.0.1:8000/parse/zip"

SAMPLE_RATE = 16000  # Deepgram handles 16k well (also fine with 8k); keep mono int16
CHANNELS = 1
CHUNK_MS = 200  # ~200ms chunks

audio_q: queue.Queue[bytes] = queue.Queue()


def audio_callback(indata, frames, time, status):
    if status:
        print("Audio status:", status)
    # Convert float32 [-1,1] -> int16 PCM
    pcm16 = (indata[:, 0] * 32767).astype(np.int16).tobytes()
    print("Audio block:", indata[:10, 0])  # Print first 10 samples
    print("Audio chunk size:", len(pcm16))  # Add this line
    audio_q.put(pcm16)


async def post_to_dob_api(transcripts: list[str]):
    # Merge N-best across finals (simple example: eliminate dupes and concatenate)
    unique_transcripts = list(set(transcripts))
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            print("unique transcripts:", unique_transcripts)
            dob = (await client.post(PARSE_DOB_URL, json={"transcripts": unique_transcripts})).json()
            print("DOB:", dob)
            # After: dob = (await client.post(PARSE_DOB_URL, json={"transcripts": unique_transcripts})).json()
            dob_cands = dob.get("dob_candidates", [])
            choose = (
                await client.post(
                    "http://127.0.0.1:8000/dob/choose",
                    json={"alternatives": unique_transcripts, "parsed_candidates": dob_cands},
                )
            ).json()
            print("DOB (chooser):", choose)

        except Exception as e:
            print("Error posting to API:", e)


async def post_to_zip_api(transcripts: list[str]):
    # Merge N-best across finals (simple example: eliminate dupes and concatenate)
    unique_transcripts = list(set(transcripts))
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            print("unique transcripts:", unique_transcripts)
            zip = (await client.post(PARSE_ZIP_URL, json={"transcripts": unique_transcripts})).json()
            print("ZIP:", zip)
        except Exception as e:
            print("Error posting to API:", e)


async def stream(answer_type: str = "dob"):
    # Clear any leftover audio chunks from previous runs
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except Exception:
            break
    headers = {"Authorization": f"Token {DG_API_KEY}"}
    sender_task = None
    receiver_task = None
    transcripts: list[str] = []
    done_event = asyncio.Event()
    try:
        print("Connecting to Deepgram websocket…")
        async with websockets.connect(
            URL,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            print("Websocket connected.")

            silence_count = 0
            loop = asyncio.get_running_loop()

            def audio_callback(indata, frames, time, status):
                nonlocal silence_count
                if status:
                    print("Audio status:", status)
                block = indata[:, 0] if CHANNELS > 1 else indata[:, 0] if indata.ndim > 1 else indata
                # Convert to int16
                pcm16 = (block * 32767).astype(np.int16).tobytes()
                print("Audio block:", block[:10])  # Print first 10 samples
                print("Audio chunk size:", len(pcm16))  # Add this line
                audio_q.put(pcm16)
                # Check for silence
                rms = np.sqrt(np.mean(block**2))
                if rms < 0.02:  # Increased threshold for less sensitivity
                    silence_count += 1
                    if silence_count > 10:  # Increased to ~2 seconds of silence
                        print("Local silence detected, stopping recording.")
                        loop.call_soon_threadsafe(done_event.set)
                else:
                    silence_count = 0

            # Start mic in a background thread
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * CHUNK_MS / 1000),
                callback=audio_callback,
                device=1,
            )
            stream.start()

            async def sender():
                try:
                    while True:
                        chunk = await asyncio.get_event_loop().run_in_executor(None, audio_q.get)
                        await ws.send(chunk)
                        print("Sent audio chunk")
                except (asyncio.CancelledError, ConnectionClosed):
                    pass

            async def receiver():
                async for msg in ws:
                    print("Received message:", msg)  # Debug: show all messages
                    data = json.loads(msg)
                    if data.get("type") == "Results":
                        alts = data["channel"]["alternatives"]
                        texts = [a.get("transcript", "").strip() for a in alts if a.get("transcript")]
                        if texts:
                            transcripts.extend(texts)  # Collect all transcripts
                            print("Transcript:", texts)  # Print each transcript as received
                        speech_final = data.get("speech_final", False)
                        print(f"Speech final: {speech_final}")
                        if speech_final:
                            print("Speech final detected, stopping recording.")
                            done_event.set()
                            break  # Stop listening for more messages

            # Run both tasks
            sender_task = asyncio.create_task(sender())
            receiver_task = asyncio.create_task(receiver())
            print("🎙️  Speak now. Recording until silence detected or 10 seconds...")
            # Wait for speech final or timeout
            try:
                await asyncio.wait_for(done_event.wait(), timeout=10.0)
                # After silence detected, wait 1 second for final transcript
                await asyncio.sleep(1)
            except asyncio.TimeoutError:
                print("Timeout reached, stopping recording.")
            # Cancel tasks
            sender_task.cancel()
            receiver_task.cancel()
            await asyncio.gather(*(t for t in [sender_task, receiver_task] if t), return_exceptions=True)
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting cleanly.")
        if sender_task:
            sender_task.cancel()
        if receiver_task:
            receiver_task.cancel()
        await asyncio.gather(*(t for t in [sender_task, receiver_task] if t), return_exceptions=True)
    finally:
        print("Stopping stream")
        try:
            stream.stop()
            stream.abort()  # Ensure stream is aborted
            print("Closing stream")
            stream.close()
        except Exception:
            pass
        if transcripts:
            print("Final N-best:", transcripts)
            if answer_type == "zip":
                await post_to_zip_api(transcripts)
            else:
                await post_to_dob_api(transcripts)
        else:
            print("No transcripts found.")
        print("Exiting script.")
        return


if __name__ == "__main__":
    try:
        # asyncio.run(stream(answer_type="dob"))
        asyncio.run(stream(answer_type="zip"))
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(0)
