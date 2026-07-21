import requests

from pocketinfer.models.base import BaseSystemdModel, register_model


@register_model
class Nmt(BaseSystemdModel):
    SYSTEMD_SERVICE = 'bhashini_model.service'
    BASE_URL = 'http://localhost:11400/health'

    def __init__(self):
        super().__init__()

    def infer(self, text: str, source_lang: str, target_lang: str):
        payload = {
            "text": text,
            "src_lang": source_lang,
            "tgt_lang": target_lang
        }

        response = requests.post("http://localhost:11400/nmt", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"NMT inference failed: {response.text}")

    @classmethod
    def update(cls, args):
        return True, "OK"
