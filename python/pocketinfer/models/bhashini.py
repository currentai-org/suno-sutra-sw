import requests
import base64
from typing import TypedDict

from pocketinfer.models.base import BaseSystemdModel, register_model

class ASRResult(TypedDict):
    language: str
    processing_time_sec: float
    text: str

class NMTResult(TypedDict):
    processing_time_sec: float
    src_lang: str
    tgt_lang: str
    translated_text: str

class TTSResult(TypedDict):
    processing_time_sec: float
    language: str
    audio_base64: str

@register_model
class Bhashini(BaseSystemdModel):
    SYSTEMD_SERVICE = 'bhashini_models.service'
    BASE_URL = 'http://localhost:11400'

    def __init__(self):
        super().__init__()

    def asr(self, wav_bytes: bytes, language: str) -> ASRResult:

        audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")

        payload = {
            "language": language,
            "audio_base64": audio_base64
        }

        response = requests.post(f"{self.BASE_URL}/asr", json=payload)

        if response.status_code == 200:
            return ASRResult(response.json())
        else:
            raise RuntimeError(f"ASR inference failed: {response.text}")

    def nmt(self, text: str, source_lang: str, target_lang: str) -> NMTResult:
        payload = {
            "text": text,
            "src_lang": source_lang,
            "tgt_lang": target_lang
        }

        response = requests.post(f"{self.BASE_URL}/nmt", json=payload)

        if response.status_code == 200:
            return NMTResult(response.json())
        else:
            raise RuntimeError(f"NMT inference failed: {response.text}")

    def tts(self, text: str, language: str) -> TTSResult:
        payload = {
            "text": text,
            "language": language
        }

        response = requests.post(f"{self.BASE_URL}/tts", json=payload)

        if response.status_code == 200:
            return TTSResult(response.json())
        else:
            raise RuntimeError(f"TTS inference failed: {response.text}")

    def load_model(self, model_name: str):
        # Model loaded automatically on service startup, cannot be changed.
        pass
    
    def unload_model(self):
        # Model cannot be changed.
        pass

    def model_loaded(self) -> bool:
        # Bhashini models are always considered loaded if the service is running
        return True

    def update(self, args):
        return True, "OK"
