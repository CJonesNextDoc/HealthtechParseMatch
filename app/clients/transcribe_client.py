# app/clients/transcribe_client.py
import io
import os
import time
import uuid

import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("TRANSCRIBE_INPUT_BUCKET")
S3_OUT_BUCKET = os.getenv("TRANSCRIBE_OUTPUT_BUCKET")

# Initialize clients only if environment variables are set
s3_client = None
transcribe_client = None

if S3_BUCKET and S3_OUT_BUCKET:
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    transcribe_client = boto3.client("transcribe", region_name=AWS_REGION)


def _upload_bytes_to_s3(audio_bytes: bytes, key_prefix="asr/") -> str:
    if not s3_client or not S3_BUCKET:
        raise ValueError("AWS S3 client not initialized. Check TRANSCRIBE_INPUT_BUCKET environment variable.")
    key = f"{key_prefix}{uuid.uuid4()}.wav"
    s3_client.upload_fileobj(io.BytesIO(audio_bytes), S3_BUCKET, key, ExtraArgs={"ContentType": "audio/wav"})
    return f"s3://{S3_BUCKET}/{key}"


def start_job_with_alternatives(job_name: str, media_uri: str, lang="en-US", max_alts=5):
    if not transcribe_client or not S3_OUT_BUCKET:
        raise ValueError("AWS Transcribe client not initialized. Check TRANSCRIBE_OUTPUT_BUCKET environment variable.")
    return transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        LanguageCode=lang,
        Media={"MediaFileUri": media_uri},
        OutputBucketName=S3_OUT_BUCKET,
        Settings={"ShowAlternatives": True, "MaxAlternatives": max(2, min(10, max_alts))},
    )


def wait_for_job_and_fetch_alternatives(start_fn, audio_bytes: bytes, max_alts=5, timeout_s=120) -> list[str]:
    media_uri = _upload_bytes_to_s3(audio_bytes)
    job_name = f"asr-{uuid.uuid4()}"
    start_fn(job_name=job_name, media_uri=media_uri, max_alts=max_alts)

    # Wait
    t0 = time.time()
    while True:
        if not transcribe_client:
            raise ValueError("AWS Transcribe client not initialized.")
        job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]
        if status in ("COMPLETED", "FAILED"):
            break
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Transcription job timed out")
        time.sleep(2)

    if status == "FAILED":
        raise RuntimeError(job.get("FailureReason", "Transcribe failed"))

    # Fetch result from S3 output
    uri = job["Transcript"]["TranscriptFileUri"]  # pre-signed URL OR s3 object
    # Prefer S3 since we set OutputBucketName
    # out_key = f"transcribe/{job_name}.json"  # AWS picks its own; safer: parse from uri
    # Simpler: get via presigned URL using requests/httpx:
    import httpx

    with httpx.Client(timeout=30) as client:
        resp = client.get(uri)
        resp.raise_for_status()
        data = resp.json()

    # Alternatives (batch JSON has `results.alternatives`)
    nbest = []
    for alt in data.get("results", {}).get("alternatives", []):
        txt = (alt.get("transcript") or "").strip()
        if txt:
            nbest.append(txt)
    # Fallback if structure differs
    if not nbest and "results" in data and "transcripts" in data["results"]:
        nbest = [t["transcript"] for t in data["results"]["transcripts"] if t.get("transcript")]
    return nbest[:max_alts]
