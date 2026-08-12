import base64
from pocketinfer.applications.base import BaseApplication
from pocketinfer.applications.registry import RegisterApplication

from pocketinfer.models.ollama import Ollama
from pocketinfer.models.piper import Piper
from pocketinfer.models.vosk import Vosk
from pocketinfer.models.bhashini import Bhashini

from pocketinfer.audio import AudioPlayer

from io import BytesIO
from subprocess import check_output

import time
import wave
import os
import json
import sys
import threading

from pocketinfer.models.base import ModelState


# Register this class as an application that can run on the Pocket Infer Device
# The argument here is a dictionary of metadata about the application
# Metadata will be used to instantiate the application and ensure dependencies are met
@RegisterApplication({
    "name": "Hear The World",
    "description": "An application that allows the user to ask questions about their surroundings.",
    "author": "PocketInfer",
    "version": "0.1.0",
    "models": {
        "ollama": {"model_name": "qwen3-vl:2b"},
        # "ollama": {"model_name": "moondream:1.8B"},
        # "ollama": {"model_name": "ministral-3:3B"},
        "piper": {"voice_name": "en_US-lessac-medium"},
        "vosk": {"model_name": "vosk-model-small-en-us-0.15"},
        "bhashini": {},
    },
    "default_settings": {
        "input_language": "en",
        "output_language": "en",
    },
    "service_dependencies": ["ollama", "bashini_models"],
})
class HearTheWorld(BaseApplication):
    def start(self):
        self.manager.subscribe_to_state_change(self.model_state_changed)
        # Load any models or resources needed for the application
        self.piper = Piper(voice_name=self.METADATA["models"]["piper"]["voice_name"],
                           audio_device=self.board.alsa_playback_device)
        self.vosk = Vosk(model_name=self.METADATA["models"]["vosk"]["model_name"])
        self.ollama = Ollama(model_name=self.METADATA["models"]["ollama"]["model_name"])
        self.bhashini = Bhashini()
        self.board.subscribe_to_ui(self.ui_cb)
        # Proceed with running the application in it's own thread
        if not os.path.exists("/tmp/hear_the_world_en_logs"):
            os.makedirs("/tmp/hear_the_world_en_logs")
        super().start()

    def model_state_changed(self, model_name, new_state, prev_state):
        self.logger.debug("Model state changed: %s from %s to %s", model_name, prev_state, new_state)
        if model_name == 'Ollama':
            model = self.ollama
        elif model_name == 'Bhashini':
            model = self.bhashini
        else:
            # Do not process any other events
            return

        # If Ollama or Bhashini service failed or was stopped:
        if new_state == ModelState.STOPPED or new_state == ModelState.ERROR:
            self.logger.warning(f"Model {model_name} stopped or encountered an error, forcing a restart")
            if model_name == 'Ollama':
                # Force unload the model, since we know the service is down
                self.ollama.model_name = None
            model.service_restart()
        # If Ollama or Bhashini service just came online:
        elif new_state == ModelState.RUNNING:
            if model_name == 'Ollama':
                model_name = self.METADATA['models']['ollama']['model_name']
                self.logger.info(f'Ollama service just started, loading model {model_name}')
                self.ollama.load_model(model_name)

    def ui_cb(self, msg):
        if msg == 'Reset':
            self.logger.info('Reset!')
            check_output('systemctl restart pocketinfer', shell=True)
        elif msg == 'Reboot':
            self.logger.info('REbooting!')
            # check_output('reboot', shell=True)
        elif msg == 'Shutdown':
            self.logger.info('Shutdown!')
            # check_output('halt', shell=True)
        elif msg.startswith('ASR'):
            self.settings['input_language'] = msg[4:].lower()
        elif msg.startswith('TTS'):
            self.settings['output_language'] = msg[4:].lower()

    def run(self):
        self.logger.debug('Starting with settings: %s', self.settings)
        while self.running:
            try:
                # Verifying services are running
                if not self.manager.check_state('Ollama') == ModelState.RUNNING:
                    self.board.statusbar("Waiting for Ollama service...")
                    self.ollama.service_restart()
                    self.manager.wait_for('Ollama')
                if not self.manager.check_state('Bhashini') == ModelState.RUNNING:
                    self.board.statusbar("Waiting for Bhashini service...")
                    self.bhashini.service_restart()
                    self.manager.wait_for('Bhashini')
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
                self.board.led_animation(1)
                asr_start = time.time()
                # Perform ASR on the recorded audio, convert it to text
                if self.settings["input_language"] != 'en':
                    wav_bytes = self.board.audio.to_audio_data().get_wav_data()
                    asr_result = self.bhashini.asr(wav_bytes, self.settings["input_language"])['text']
                else:
                    asr_result = self.vosk.recognize(self.board.audio.to_audio_data())['text']
                asr_stop = time.time()
                self.logger.info("Detected query is '{}'".format(asr_result))
                self.board.top_text(asr_result)
                # Perform NMT on the recognized text, convert it to the target language
                if self.settings['input_language'] != 'en':
                    self.board.statusbar(f"Running: NMT {self.settings['input_language']} -> en")
                    query = self.bhashini.nmt(asr_result, self.settings["input_language"], "EN")['translated_text']
                    self.logger.info("Translated query is '{}'".format(query))
                    self.board.top_text(query)
                else:
                    query = asr_result
                nmt_a_stop = time.time()
                # Perform LLM inference on the recognized text + image
                self.board.statusbar("Running: LLM")
                llm_start = time.time()
                resp = self.ollama.generate(images=[img], prompt=query+'. Limit response to one short sentence')
                llm_end = time.time()
                if resp.response is None:
                    self.board.bottom_text("No response")
                    continue
                result = resp.response.strip().rstrip()
                self.logger.info("Result is '{}'".format(result))
                self.board.bottom_text(result)
                # Perform NMT on the LLM response, convert it back to the original language
                if self.settings['output_language'] != 'en':
                    self.board.statusbar(f"Running: NMT en -> {self.settings['output_language']}")
                    nmt_result = self.bhashini.nmt(result, "EN", self.settings["output_language"])['translated_text']
                    self.logger.info("Translated result is '{}'".format(nmt_result))
                else:
                    nmt_result = result
                nmt_b_stop = time.time()
                self.board.top_text(asr_result)
                self.board.bottom_text(nmt_result)
                # Perform TTS on the LLM response, convert it to audio and play it back
                self.board.statusbar("Running: Playback")
                self.board.led_animation(0)
                tts_result = self.bhashini.tts(nmt_result, self.settings["output_language"])
                tts_result_bytes = base64.b64decode(tts_result['audio_base64'])
                # self.piper.start_playback(result)
                app_end = time.time()
                wave_obj = wave.open(BytesIO(tts_result_bytes), 'rb')
                with AudioPlayer(wave_obj.getframerate(), self.board.alsa_playback_device) as player:
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
            except KeyboardInterrupt:
                self.logger.info("Exit")
                self.board.clear_screen()
                self.running = False
            except Exception as e:
                self.logger.exception("Error in main application loop: %s", e)
                self.board.statusbar("Error: {}".format(str(e)))
                time.sleep(1)
