from pocketinfer.applications.base import BaseApplication
from pocketinfer.applications.registry import RegisterApplication

from pocketinfer.models.ollama import Ollama
from pocketinfer.models.piper import Piper
from pocketinfer.models.vosk import Vosk


# Register this class as an application that can run on the Pocket Infer Device
# The argument here is a dictionary of metadata about the application
# Metadata will be used to instantiate the application and ensure dependencies are met
@RegisterApplication({
    "name": "Hear The World (English)",
    "description": "An application that allows the user to ask questions in english about their surroundings.",
    "author": "PocketInfer",
    "version": "0.1.0",
    "models": {
        "ollama": {"model_name": "ministral-3:3B"},
        "piper": {"voice_name": "en_US-lessac-medium"},
        "vosk": {"model_name": "vosk-model-small-en-us-0.15"},
    },
    "service_dependencies": ["ollama"],
})
class HearTheWorldEn(BaseApplication):
    def start(self):
        # Load any models or resources needed for the application
        self.piper = Piper(voice_name=self.METADATA["models"]["piper"]["voice_name"],
                           audio_device=self.board.ALSA_PLAYBACK_DEVICE)
        self.vosk = Vosk(model_name=self.METADATA["models"]["vosk"]["model_name"])
        self.ollama = Ollama(model_name=self.METADATA["models"]["ollama"]["model_name"])
        # Proceed with running the application in it's own thread
        super().start()

    def run(self):
        self.board.clear_screen()
        while self.running:
            self.board.statusbar("Ready - Press Button")
            self.board.wait_for_trigger_button_down()
            # When user presses button, start recording audio and snap a photo
            self.piper.stop_playback()  # If previous TTS is still playing, stop it
            self.board.audio.start()
            img = self.board.camera_frame_jpg()
            self.board.statusbar("Release Button")
            self.board.wraptext("")
            self.board.wait_for_trigger_button_up()
            # When user releases button, stop recording
            self.board.audio.stop()
            self.board.statusbar("Running: ASR")
            # Perform ASR on the recorded audio, convert it to text
            value = self.vosk.recognize(self.board.audio.to_audio_data())
            self.logger.info("Detected query is '{}'".format(value))
            self.board.wraptext(value)
            # Perform LLM inference on the recognized text + image
            self.board.statusbar("Running: LLM")
            resp = self.ollama.chat([
                {
                    'role': 'user',
                    'content': value+'. limit response to one short sentence',
                    'images':[img],
                }
            ])
            self.logger.info("Result is '{}'".format(resp.message.content))
            self.board.wraptext(resp.message.content)
            # Perform TTS on the LLM response, convert it to audio and play it back
            self.board.statusbar("Running: Playback")
            self.piper.start_playback(resp.message.content)
            # Loop back around and prepare for the next interaction