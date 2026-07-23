import requests

from pocketinfer.models.base import BaseSystemdModel, register_model


@register_model
class Nmt(BaseSystemdModel):
    SYSTEMD_SERVICE = 'bhashini_model.service'
    BASE_URL = 'http://localhost:11400'

    def __init__(self):
        super().__init__()

    def infer(self, text: str, source_lang: str, target_lang: str):
        payload = {
            "text": text,
            "src_lang": source_lang,
            "tgt_lang": target_lang
        }

        response = requests.post(f"{self.BASE_URL}/nmt", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"NMT inference failed: {response.text}")

    def load_model(self, model_name: str):
        # Model loaded automatically on service startup, cannot be changed.
        pass
    
    def unload_model(self):
        # Model cannot be changed.
        pass

    @classmethod
    def update(cls, args):
        return True, "OK"
