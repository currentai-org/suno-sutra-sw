import pyaudio
import wave
import os
import time
import threading
import numpy as np
import shutil
import subprocess
from typing import Optional
from speech_recognition import AudioData
from contextlib import contextmanager
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll


ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
    yield
    asound.snd_lib_error_set_handler(None)

class AudioRecorder:
    def __init__(self, device_idx=0, devname=None, rate=16000, channels=1, frames_per_buffer=1024):
        self.rate = rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        with noalsaerr():
            self.p = pyaudio.PyAudio()
        self.device_idx = device_idx,
        if devname is not None:
            for i in range(self.p.get_device_count()):
                devinfo = self.p.get_device_info_by_index(i)
                if devname in devinfo['name']:
                    self.device_idx = i
                    break
        self.stream = None
        self.frames = []
        self.thread = threading.Thread()
        self.recording = False

    def start(self):
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=self.channels,
                                  rate=self.rate,
                                  input=True,
                                  input_device_index=self.device_idx,
                                  frames_per_buffer=self.frames_per_buffer)
        self.frames = []
        self.thread = threading.Thread(target=self._record)
        self.thread.daemon = True
        self.recording = True
        self.thread.start()

    def _record(self):
        if self.stream is None:
            return
        try:
            while self.recording:
                data = self.stream.read(self.frames_per_buffer)
                self.frames.append(data)
        finally:
            self.recording = False


    def stop(self):
        self.recording = False
        time.sleep(0.15) # Experimentlaly determined to allow last buffer to be read
        self.thread.join()
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def save_to_file(self, filename):
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()

    def to_audio_data(self):
        byte_data = b''.join(self.frames)

        # Convert bytes to signed 16-bit samples
        arr = np.frombuffer(byte_data, dtype=np.int16)
        if len(arr) == 0:
            return AudioData(byte_data, self.rate, 2)
        ampl = max(abs(np.min(arr)), abs(np.max(arr)))
        gain = 32768.0 / ampl if ampl > 0 else 1.0
        arr = (arr*gain*1.2) # Intentionall hard-clip a little
        arr = np.clip(arr, -32768, 32767).astype(np.int16)

        return AudioData(arr.tobytes(), self.rate, 2)

    def terminate(self):
        self.p.terminate()

class DummyAudioRecorder(AudioRecorder):
    def __init__(self, filename):
        self.filename = filename
        self.channels = 1 
        self.frames_per_buffer = 1024
        self.frames = []

    def start(self):
        # open the file for reading.
        self.frames = []

    def stop(self):
        with wave.open(self.filename, 'rb') as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                raise ValueError("Audio file must be mono, 16-bit")
            self.rate = wf.getframerate() 
            self.frames = [wf.readframes(wf.getnframes())]


# The following was modified from piper's audio_playback.py to add device selection
class AudioPlayer:
    """Plays raw audio using ffplay."""

    def __init__(self, sample_rate: int, device: str = "default") -> None:
        """Initialzes audio player."""
        self.sample_rate = sample_rate
        self.device = device
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        """Starts ffplay subprocess and returns player."""
        my_env = os.environ.copy()
        my_env["SDL_AUDIODRIVER"] = "alsa"
        my_env["AUDIODEV"] = self.device
        self._proc = subprocess.Popen(
            [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-f",
                "s16le",
                "-ar",
                str(self.sample_rate),
                "-ac",
                "1",
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=my_env
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stops ffplay subprocess."""
        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass
            self._proc.wait(timeout=5)

    def play(self, audio_bytes: bytes) -> None:
        """Plays raw audio using ffplay."""
        assert self._proc is not None
        assert self._proc.stdin is not None

        self._proc.stdin.write(audio_bytes)
        self._proc.stdin.flush()

    @staticmethod
    def is_available() -> bool:
        """Returns true if ffplay is available."""
        return bool(shutil.which("ffplay"))
