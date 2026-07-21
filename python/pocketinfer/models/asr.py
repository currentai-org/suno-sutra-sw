import requests
import base64

from pocketinfer.models.base import BaseSystemdModel, register_model


@register_model
class Asr(BaseSystemdModel):
    SYSTEMD_SERVICE = 'bhashini_model.service'
    BASE_URL = 'http://localhost:11400/health'

    def __init__(self):
        super().__init__()

    def infer(self, wav_bytes: bytes, language: str):

        audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")

        payload = {
            "language": language,
            "audio_base64": audio_base64
        }

        response = requests.post("http://localhost:11400/asr", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"ASR inference failed: {response.text}")

    @classmethod
    def update(cls, args):
        return True, "OK"
