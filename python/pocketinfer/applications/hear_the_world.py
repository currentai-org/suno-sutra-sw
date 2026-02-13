import base64
from pocketinfer.applications.base import BaseApplication
from pocketinfer.applications.registry import RegisterApplication

from pocketinfer.models.ollama import Ollama
from pocketinfer.models.piper import Piper
from pocketinfer.models.vosk import Vosk
from pocketinfer.models.asr import Asr
from pocketinfer.models.nmt import Nmt
from pocketinfer.models.tts import Tts

from pocketinfer.audio import AudioPlayer

from io import BytesIO

import time
import wave
import os
import json


# Register this class as an application that can run on the Pocket Infer Device
# The argument here is a dictionary of metadata about the application
# Metadata will be used to instantiate the application and ensure dependencies are met
@RegisterApplication({
    "name": "Hear The World",
    "description": "An application that allows the user to ask questions about their surroundings.",
    "author": "PocketInfer",
    "version": "0.1.0",
    "models": {
        # "ollama": {"model_name": "qwen3-vl:2b"},
        # "ollama": {"model_name": "moondream:1.8B"},
        "ollama": {"model_name": "ministral-3:3B"},
        "piper": {"voice_name": "en_US-lessac-medium"},
        "vosk": {"model_name": "vosk-model-small-en-us-0.15"},
        "asr": {},
        "nmt": {},
        "tts": {},
    },
    "default_settings": {
        "input_language": "hi",
        "output_language": "hi",
    },
    "service_dependencies": ["ollama", "bashini_models"],
})
class HearTheWorld(BaseApplication):
    def start(self):
        # Load any models or resources needed for the application
        self.piper = Piper(voice_name=self.METADATA["models"]["piper"]["voice_name"],
                           audio_device=self.board.ALSA_PLAYBACK_DEVICE)
        self.vosk = Vosk(model_name=self.METADATA["models"]["vosk"]["model_name"])
        self.ollama = Ollama(model_name=self.METADATA["models"]["ollama"]["model_name"])
        self.asr = Asr()
        self.nmt = Nmt()
        self.tts = Tts()
        # Proceed with running the application in it's own thread
        if not os.path.exists("/tmp/hear_the_world_en_logs"):
            os.makedirs("/tmp/hear_the_world_en_logs")
        super().start()

    def run(self):
        self.board.clear_screen()
        while self.running:
            self.board.statusbar("Ready - Press Button")
            self.board.wait_for_trigger_button_down()
            self.board.statusbar("Release Button")
            self.board.top_text("")
            self.board.bottom_text("")
            audio_start = time.time()
            # When user presses button, start recording audio and snap a photo
            self.piper.stop_playback()  # If previous TTS is still playing, stop it
            self.board.audio.start()
            img = self.board.camera_frame_jpg()
            self.board.wait_for_trigger_button_up()
            audio_stop = time.time()
            # When user releases button, stop recording
            self.board.audio.stop()
            self.board.statusbar("Running: ASR")
            asr_start = time.time()
            # Perform ASR on the recorded audio, convert it to text
            wav_bytes = self.board.audio.to_audio_data().get_wav_data()
            asr_result = self.asr.infer(wav_bytes, self.settings["input_language"])
            raw_query = asr_result['text']
            asr_stop = time.time()
            self.logger.info("Detected query is '{}'".format(raw_query))
            # self.board.top_text(query)
            # Perform NMT on the recognized text, convert it to the target language
            self.board.statusbar(f"Running: NMT {self.settings['input_language']} -> en")
            query = self.nmt.infer(raw_query, self.settings["input_language"], "EN")['translated_text']
            self.logger.info("Translated query is '{}'".format(query))
            self.board.top_text(query)
            nmt_a_stop = time.time()
            # Perform LLM inference on the recognized text + image
            self.board.statusbar("Running: LLM")
            llm_start = time.time()
            resp = self.ollama.generate(images=[img], prompt=query+'. Limit response to one short sentence')
            llm_end = time.time()
            result = resp.response.strip().rstrip()
            self.logger.info("Result is '{}'".format(result))
            self.board.bottom_text(result)
            # Perform NMT on the LLM response, convert it back to the original language
            self.board.statusbar(f"Running: NMT en -> {self.settings['output_language']}")
            nmt_result = self.nmt.infer(result, "EN", self.settings["output_language"])['translated_text']
            self.logger.info("Translated result is '{}'".format(nmt_result))
            nmt_b_stop = time.time()
            # self.board.bottom_text(nmt_result)
            # Perform TTS on the LLM response, convert it to audio and play it back
            self.board.statusbar("Running: Playback")
            tts_result = self.tts.infer(nmt_result, self.settings["output_language"])
            tts_result_bytes = base64.b64decode(tts_result['audio_base64'])
            # self.piper.start_playback(result)
            app_end = time.time()
            wave_obj = wave.open(BytesIO(tts_result_bytes), 'rb')
            with AudioPlayer(wave_obj.getframerate(), self.board.ALSA_PLAYBACK_DEVICE) as player:
                player.play(wave_obj.readframes(wave_obj.getnframes()))
            self.logger.debug(f"Total Run time {app_end-audio_start}s, audio {audio_stop-audio_start}s, ASR {asr_stop-asr_start}, NMT A {nmt_a_stop-asr_stop}, LLM {llm_end-llm_start}, NMT B {nmt_b_stop-llm_end}, TTS {app_end-nmt_b_stop}")
            # Log
            log_id = int(audio_start*1000)
            log_data = {
                'id': log_id,
                "query": asr_result,
                "response": resp.model_dump(),
                "timestamps": {
                    "audio_start": audio_start,
                    "audio_stop": audio_stop,
                    "asr_start": asr_start,
                    "asr_stop": asr_stop,
                    "nmt_a_stop": nmt_a_stop,
                    "llm_start": llm_start,
                    "llm_end": llm_end,
                    "nmt_b_stop": nmt_b_stop,
                    "app_end": app_end
                }
            }
            with open("/tmp/hear_the_world_en_logs/log.jsonl", "a") as f:
                f.write(json.dumps(log_data)+"\n")
            with open("/tmp/hear_the_world_en_logs/img_{}.jpg".format(log_id), "wb") as f:
                f.write(img)
            with open("/tmp/hear_the_world_en_logs/audio_{}.wav".format(log_id), "wb") as f:
                f.write(tts_result_bytes)
            # Loop back around and prepare for the next interactionw
