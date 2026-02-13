import requests


class Nmt:
    def __init__(self):
        pass

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
    def verify(cls, args):
        # For NMT, we can do a simple health check by sending a test translation request
        try:
            response = requests.get("http://localhost:11400/health")
            if response.status_code == 200:
                return True, "NMT service is available."
            else:
                return False, f"NMT service responded with status code {response.status_code}."
        except Exception as e:
            return False, str(e)
        
    @classmethod
    def update(cls, args):
        return True, "OK"