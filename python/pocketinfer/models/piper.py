from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice
from pocketinfer.audio import AudioPlayer
import threading
import os
import logging
from pathlib import Path
from appdirs import user_cache_dir

from pocketinfer.models.base import BaseModel, register_model


@register_model
class Piper(BaseModel):
    MODEL_DIR = Path(user_cache_dir("pocketinfer")) / "piper_voice"

    def __init__(self, voice_name, audio_device):
        super().__init__()
        self.voice_name = voice_name
        self.audio_device = audio_device
        self.voice = PiperVoice.load(model_path=Path(self.MODEL_DIR, voice_name + ".onnx"),
                                     config_path=Path(self.MODEL_DIR, voice_name + ".onnx.json"))
        self.syn_config = SynthesisConfig(
            speaker_id=0,
            length_scale=None,
            noise_scale=None,
            noise_w_scale=None,
            normalize_audio=True,
            volume=1.0,
        )
        self.thread = threading.Thread()
        self.playing = False
    
    def _synthesize_and_play(self, text):
        self.logger.debug(f"Starting synthesis and playback on {self.audio_device}")
        with AudioPlayer(self.voice.config.sample_rate, device=self.audio_device) as player:
            for i, audio_chunk in enumerate(self.voice.synthesize(text, self.syn_config)):
                if not self.playing:
                    break
                player.play(audio_chunk.audio_int16_bytes)
        self.logger.debug("Playback complete")

    def start_playback(self, text):
        self.thread = threading.Thread(target=self._synthesize_and_play, args=(text,))
        self.thread.daemon = True
        self.playing = True
        self.thread.start()

    def stop_playback(self):
        if self.playing:
            self.playing = False
            self.thread.join()
    
    def verify(self):
        if not os.path.exists(self.MODEL_DIR):
            return False
        try:
            PiperVoice.load(model_path=Path(self.MODEL_DIR, self.voice_name + ".onnx"),
                            config_path=Path(self.MODEL_DIR, self.voice_name + ".onnx.json"))
            return True
        except Exception as e:
            return False
        
    def update(self, args):
        if not os.path.exists(self.MODEL_DIR):
            os.makedirs(self.MODEL_DIR)
        # For Piper, we might download or update the voice model here
        logging.info(f"Downloading Piper voice '{self.voice_name}'")
        download_voice(self.voice_name, self.MODEL_DIR)