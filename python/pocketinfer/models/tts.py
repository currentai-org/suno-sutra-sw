import requests

from pocketinfer.models.base import BaseSystemdModel, register_model


@register_model
class Tts(BaseSystemdModel):
    SYSTEMD_SERVICE = 'bhashini_model.service'
    BASE_URL = 'http://localhost:11400'

    def __init__(self):
        super().__init__()

    def infer(self, text: str, language: str):
        payload = {
            "text": text,
            "language": language
        }

        response = requests.post(f"{self.BASE_URL}/tts", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"TTS inference failed: {response.text}")

    @classmethod
    def update(cls, args):
        return True, "OK"
