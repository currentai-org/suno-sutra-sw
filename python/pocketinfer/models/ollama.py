from collections.abc import Mapping, Sequence
from typing import Any, Optional, Union

import ollama
import logging
from subprocess import check_output
import requests

from pocketinfer.models.base import BaseSystemdModel, register_model, ModelNotFoundError


@register_model
class Ollama(BaseSystemdModel):
    SYSTEMD_SERVICE = 'ollama.service'
    BASE_URL = 'http://localhost:11434'

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name

    def chat(self, messages: Sequence[Mapping[str, Any] | ollama.Message]) -> ollama.ChatResponse:
        if self.model_name is None:
            raise ValueError("No model loaded")
        return ollama.chat(model=self.model_name, messages=messages)

    def generate(self, prompt: str, images: Optional[Sequence[Union[str, bytes, ollama.Image]]] = None) -> ollama.GenerateResponse:
        if self.model_name is None:
            raise ValueError("No model loaded")
        return ollama.generate(model=self.model_name, images=images, prompt=prompt)

    def load_model(self, model_name: str):
        ret = ollama.list()
        models = []
        for model in ret.models:
            if model.model is not None:
                models.append(model.model)
            if model.model == model_name:
                requests.post(f'{self.BASE_URL}/api/generate', json={'model': model_name, 'keep_alive': -1})
                self.model_name = model_name
                return
        raise ModelNotFoundError(f"Model '{model_name}' not found.", models)
    
    def unload_model(self):
        requests.post(f'{self.BASE_URL}/api/generate', json={'model': self.model_name, 'keep_alive': 0})
        self.model_name = None
    
    @classmethod
    def verify(cls, args):
        if not super().verify(args):
            return False
        try:
            ret = ollama.list()
            for model in ret.models:
                if model.model == args["model_name"]:
                    requests.post(f'{cls.BASE_URL}/api/generate', json={'model': args['model_name'], 'keep_alive': -1})
                    return True
            return False
        except Exception as e:
            return False

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
