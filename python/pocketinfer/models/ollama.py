from collections.abc import Mapping, Sequence
from typing import Any, Optional, Union

import httpx
import ollama
import logging
import threading
from subprocess import check_output
import requests

from pocketinfer.models.base import BaseSystemdModel, register_model, ModelNotFoundError


@register_model
class Ollama(BaseSystemdModel):
    SYSTEMD_SERVICE = 'ollama.service'
    BASE_URL = 'http://localhost:11434'

    def __init__(self, model_name: Optional[str] = None):
        super().__init__()
        self.model_name = None
        if model_name is not None:
            # Do not block waiting for model to be loaded
            th = threading.Thread(target=self.load_model, args=(model_name,), daemon=True)
            th.start()

    def chat(self, messages: Sequence[Mapping[str, Any] | ollama.Message]) -> ollama.ChatResponse:
        if self.model_name is None:
            raise ValueError("No model loaded")
        return ollama.chat(model=self.model_name, messages=messages)

    def generate(self, prompt: str, images: Optional[Sequence[Union[str, bytes, ollama.Image]]] = None) -> ollama.GenerateResponse:
        if self.model_name is None:
            raise ValueError("No model loaded")
        return ollama.generate(model=self.model_name, images=images, prompt=prompt)
    
    def available_models(self):
        ret = ollama.list()
        models = []
        for model in ret.models:
            if model.model is not None:
                models.append(model.model)
        return models

    def model_loaded(self) -> bool:
        return self.model_name is not None

    def load_model(self, model_name: str, timeout: Optional[float] = None):
        ret = ollama.list()
        models = []
        for model in ret.models:
            if model.model is not None:
                models.append(model.model)
            if model.model == model_name:
                if timeout is not None:
                    requests.post(f'{self.BASE_URL}/api/generate', json={'model': model_name, 'keep_alive': -1}, timeout=timeout)
                else:
                    requests.post(f'{self.BASE_URL}/api/generate', json={'model': model_name, 'keep_alive': -1})
                self.model_name = model_name
                return
        raise ModelNotFoundError(model_name, models)
    
    def unload_model(self):
        requests.post(f'{self.BASE_URL}/api/generate', json={'model': self.model_name, 'keep_alive': 0})
        self.model_name = None

    def service_stop(self):
        ret = super().service_stop()
        if ret:
            self.model_name = None
        return ret

    def verify(self) -> bool:
        if not super().verify():
            return False
        try:
            # Hit the ollama API, this would double-confirm that it's running
            ret = ollama.list()
            # If we don't yet know the model being used, it's OK to assume we're ready
            if self.model_name is None:
                return True
            # Otherwise, actually verify the specified model is available
            for model in ret.models:
                if model.model == self.model_name:
                    requests.post(f'{self.BASE_URL}/api/generate', json={'model': self.model_name, 'keep_alive': -1})
                    return True
            return False
        except Exception as e:
            self.logger.exception(f'Failed to verify Ollama model: {str(e)}')
            return False

    def update(self, args):
        # Ollama models are managed by the Ollama service itself.
        # This method can be used to pull the latest model if needed.
        # TODO - ensure ollama service is running
        try:
            logging.info(f"Pulling Ollama model '{args['model_name']}'")
            ollama.pull(model=args["model_name"])
        except Exception as e:
            raise RuntimeError(f"Failed to update Ollama model '{args['model_name']}': {str(e)}")
