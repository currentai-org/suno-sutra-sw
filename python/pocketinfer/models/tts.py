import requests


class Tts:
    def __init__(self):
        pass

    def infer(self, text: str, language: str):
        payload = {
            "text": text,
            "language": language
        }

        response = requests.post("http://localhost:11400/tts", json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"TTS inference failed: {response.text}")

    @classmethod
    def verify(cls, args):
        # For TTS, we can do a simple health check by sending a test synthesis request
        try:
            response = requests.get("http://localhost:11400/health")
            if response.status_code == 200:
                return True, "TTS service is available."
            else:
                return False, f"TTS service responded with status code {response.status_code}."
        except Exception as e:
            return False, str(e)
        
    @classmethod
    def update(cls, args):
        return True, "OK"