import ollama
import logging
from subprocess import check_output
import requests


class Ollama:
    def __init__(self, model_name: str):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        #TODO execute curl http://localhost:11434/api/generate -d '{"model": model_name, "keep_alive": -1}'

    def chat(self, messages: list) -> ollama.ChatResponse:
        return ollama.chat(model=self.model_name, messages=messages)

    def generate(self, images, prompt):
        return ollama.generate(model=self.model_name, images=images, prompt=prompt)

    def restart(self):
        print(check_output('systemctl restart ollama', shell=True))
        requests.post('http://localhost:11434/api/generate', json={'model': self.model_name, 'keep_alive': -1})
    
    @classmethod
    def verify(cls, args):
        try:
            ret = ollama.list()
            for model in ret.models:
                if model.model == args["model_name"]:
                    requests.post('http://localhost:11434/api/generate', json={'model': args['model_name'], 'keep_alive': -1})
                    return True, "Ollama service is available."
            return False, f"Model '{args['model_name']}' not found."
        except Exception as e:
            return False, str(e)

    @classmethod
    def update(cls, args):
        # Ollama models are managed by the Ollama service itself.
        # This method can be used to pull the latest model if needed.
        # TODO - ensure ollama service is running
        try:
            logging.info(f"Pulling Ollama model '{args['model_name']}'")
            ollama.pull(model=args["model_name"])
        except Exception as e:
            raise RuntimeError(f"Failed to update Ollama model '{args['model_name']}': {str(e)}")
