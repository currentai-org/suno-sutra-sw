import base64
import subprocess
import os
import tempfile
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# =========================================================
# CONFIG
# =========================================================
FLITE_BIN = "/home/ubuntu/s2s_service/flite/bin/flite"
VOICES_DIR = "/home/ubuntu/s2s_service/flite/voices"

app = FastAPI(title="TTS API")


# =========================================================
# LANGUAGE → VOICE MAP
# =========================================================
LANG_VOICE_MAP = {
    "bn": ["cmu_indic_ben_rm.flitevox"],
    "gu": [
        "cmu_indic_guj_ad.flitevox",
        "cmu_indic_guj_dp.flitevox",
        "cmu_indic_guj_kt.flitevox",
    ],
    "hi": ["cmu_indic_hin_ab.flitevox"],
    "ka": ["cmu_indic_kan_plv.flitevox"],
    "mr": [
        "cmu_indic_mar_aup.flitevox",
        "cmu_indic_mar_slp.flitevox",
    ],
    "pa": ["cmu_indic_pan_amp.flitevox"],
    "ta": ["cmu_indic_tam_sdr.flitevox"],
    "te": [
        "cmu_indic_tel_kpn.flitevox",
        "cmu_indic_tel_sk.flitevox",
        "cmu_indic_tel_ss.flitevox",
    ],
    "en": [
        "cmu_us_aew.flitevox",
        "cmu_us_ahw.flitevox",
        "cmu_us_awb.flitevox",
        "cmu_us_axb.flitevox",
        "cmu_us_bdl.flitevox",
        "cmu_us_clb.flitevox",
    ],
}


# =========================================================
# REQUEST SCHEMA
# =========================================================
class TTSRequest(BaseModel):
    text: str
    language: str
    voice_name: str | None = None
    duration_stretch: float = 1.0
    f0_mean: int = 110


# =========================================================
# SYNTHESIS FUNCTION
# =========================================================
def synthesize_to_bytes(
    text: str,
    lang: str,
    voice_name: str | None,
    duration_stretch: float,
    f0_mean: int,
) -> bytes:

    if lang not in LANG_VOICE_MAP:
        raise HTTPException(400, f"Language '{lang}' not supported")

    voices = LANG_VOICE_MAP[lang]

    # Default voice
    if voice_name is None:
        voice_name = voices[0]

    if voice_name not in voices:
        raise HTTPException(
            400,
            f"Voice '{voice_name}' not valid. Available: {voices}"
        )

    voice_path = os.path.join(VOICES_DIR, voice_name)

    # Temp wav
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    ) as tmp_file:

        tmp_wav_path = tmp_file.name

    # -----------------------------------------------------
    # Flite call (aligned with your S2S reference)
    # -----------------------------------------------------
    cmd = [
        FLITE_BIN,
        "-voice", voice_path,
        "--setf", f"duration_stretch={duration_stretch}",
        "--setf", f"int_f0_target_mean={f0_mean}",
        "-t", text,
        tmp_wav_path,
    ]

    subprocess.run(cmd, check=True)

    # Read bytes
    with open(tmp_wav_path, "rb") as f:
        audio_bytes = f.read()

    os.remove(tmp_wav_path)

    return audio_bytes


# =========================================================
# ENDPOINT
# =========================================================
@app.post("/tts")
def run_tts(req: TTSRequest):

    start_time = time.time()

    if not req.text.strip():
        raise HTTPException(400, "Text cannot be empty")

    audio_bytes = synthesize_to_bytes(
        text=req.text,
        lang=req.language,
        voice_name=req.voice_name,
        duration_stretch=req.duration_stretch,
        f0_mean=req.f0_mean,
    )

    audio_b64 = base64.b64encode(audio_bytes).decode()

    return {
        "audio_base64": audio_b64,
        "language": req.language,
        "processing_time_sec": round(time.time() - start_time, 3)
    }
