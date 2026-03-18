from os.path import exists
from os import system
from subprocess import run
from pocketinfer.serialcomms import IOInterface
import threading
import logging
import cv2
import wave
import time
from pocketinfer import audio

import Jetson.GPIO as GPIO


class CameraIterable:
    def __init__(self, board):
        self.board = board
    def __iter__(self):
        return self
    def __next__(self):
        frame = self.board.camera_frame()
        if frame is None:
            raise StopIteration
        return frame

class CameraReader:
    def __init__(self, camera_index):
        self.camera_index = camera_index
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.frame = None
        self.running = False
        self.frame_available = threading.Event()

    def start(self):
        self.running = True
        self.thread.start()
    
    def _run(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Unable to open VideoCapture({self.camera_index})")
        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    continue
                self.frame = frame
                self.frame_available.set()
        finally:
            self.running = False
            self.cap.release()

    def stop(self):
        self.running = False
        self.thread.join()
        self.cap.release()

class Board:
    CV2_INDEX = None
    ALSA_PLAYBACK_DEVICE = "default"

    def __init__(self, args):
        self.logger = logging.getLogger(__name__)
        self.args = args
        self.trigger_button = False
        self.trigger_button_down = threading.Event()
        self.trigger_button_up = threading.Event()
        self.camera = CameraReader(self.CV2_INDEX)
        self.ui_cbs = []

    def subscribe_to_ui(self, func):
        if func not in self.ui_cbs:
            self.ui_cbs.append(func)

    def unsubscribe_to_ui(self, func):
        if func in self.ui_cbs:
            self.ui_cbs.remove(func)
    
    def wait_for_trigger_button_down(self, timeout=None):
        self.trigger_button_down.clear()
        self.trigger_button_down.wait(timeout=timeout)
    
    def wait_for_trigger_button_up(self, timeout=None):
        self.trigger_button_up.clear()
        self.trigger_button_up.wait(timeout=timeout)

    def camera_frame(self):
        if not self.camera.running:
            self.camera.frame_available.clear()
            self.camera.start()
            self.camera.frame_available.wait(timeout=5.0)
        return self.camera.frame

    def camera_frames(self):
        return CameraIterable(self)

    def camera_frame_jpg(self):
        frame = self.camera_frame()
        if frame is None:
            return None
        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            return None
        return bytearray(buffer)

    @classmethod
    def get_board(cls):
        if not exists('/etc/nv_tegra_release'):
            raise NotImplementedError('Cannot detect nvidia platform - /etc/nv_tegra_release missing')
        args = {}
        with open('/etc/nv_tegra_release', 'r') as fil:
            args['kernelinfo'] = fil.readline()
        module_ver_raw = run(['i2ctransfer', '-f', '-y', '0', 'w1@0x50', '0x14', 'r22@0x50'], capture_output=True, text=True)
        if module_ver_raw.stderr:
            raise NotImplementedError('Cannot detect nvidia platform - Error reading module eeprom: '+module_ver_raw.stderr)
        module_ver = bytearray([int(x,16) for x in module_ver_raw.stdout.split(' ')])
        carrier_ver_raw = run(['i2ctransfer', '-f', '-y', '0', 'w1@0x57', '0x14', 'r22@0x57'], capture_output=True, text=True)
        if carrier_ver_raw.stderr:
            raise NotImplementedError('Cannot detect nvidia platform - Error reading module eeprom: '+carrier_ver_raw.stderr)
        carrier_ver = bytearray([int(x,16) for x in carrier_ver_raw.stdout.split(' ')])
        if not module_ver.startswith(b'699-13767-0005'):
            raise NotImplementedError('Unsupported Jetson module: '+module_ver.decode('utf-8'))
        args['module_ver'] = module_ver
        args['carrier_ver'] = carrier_ver 
        if carrier_ver.startswith(b'699-13768-0000'):
            return PocketInferDevboard(args)
        if carrier_ver.startswith(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'):
            return PocketInferDemo(args)
        raise NotImplementedError('Unsupported Carrier Board: '+carrier_ver.decode('utf-8'))

    # To be overridden, ideally
    def button_led(self, value):
        return True
        
    def rgb_led(self, r, g=None, b=None):
        return True

    def led_animation(self, val):
        return True

    def clear_screen(self):
        return

    def statusbar(self, text):
        self.logger.info("Statusbar: "+text)
        return True

    def top_text(self, text):
        self.logger.info("Top text: "+text)
        return True
    
    def bottom_text(self, text):
        self.logger.info("Bottom text: "+text)
        return True

    def mode_text(self, text):
        self.logger.info("Mode text: "+text)
        return True

    def memory_text(self, text):
        return True

class DummyBoard(Board):
    def __init__(self, args):
        super().__init__(args)
        self.logger.info("Using DummyBoard - no hardware features will work")
        self.audio = audio.DummyAudioRecorder(args['audio_file'])

    def wait_for_trigger_button_down(self, timeout=None):
        self.trigger_button_down.clear()
        return
    
    def wait_for_trigger_button_up(self, timeout=None):
        self.trigger_button_up.clear()
        return
    
    def camera_frame(self):
        if 'image_file' not in self.args:
            return None
        img = self.args.get('image_file')
        if isinstance(img, str):
            if not exists(img):
                raise FileNotFoundError(f"DummyBoard image file '{img}' not found")
            return cv2.imread(img)
        if isinstance(img, bytes):
            return cv2.imdecode(img, cv2.IMREAD_COLOR)
        return img
    

class PocketInferDevboard(Board):
    ALSA_PLAYBACK_DEVICE = "hw:2,0"
    ALSA_PLAYBACK_CARD = 2
    ALSA_CAPTURE_CARD = 1
    CV2_INDEX = 0
    TRIGGER_BOARD_IDX = 7

    def __init__(self, args):
        super().__init__(args)
        self.audio = audio.AudioRecorder(devname='USB PnP Sound Device', rate=44100, frames_per_buffer=4096)
        system(f'amixer -c {self.ALSA_CAPTURE_CARD} sset Mic 100% > /dev/null')
        system(f'amixer -c {self.ALSA_PLAYBACK_CARD} sset Speaker 100% > /dev/null')
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.TRIGGER_BOARD_IDX, GPIO.IN)
        GPIO.add_event_detect(self.TRIGGER_BOARD_IDX, GPIO.BOTH, callback=self.trig_cb, bouncetime=100)

    def trig_cb(self, channel):
        if GPIO.input(self.TRIGGER_BOARD_IDX):
            self.trigger_button = True
            self.trigger_button_down.set()
            self.logger.debug("Trigger button down")
        else:
            self.trigger_button = False
            self.trigger_button_up.set()
            self.logger.debug("Trigger button up")



class PocketInferDemo(Board):
    ALSA_PLAYBACK_DEVICE = "hw:2,0"
    ALSA_PLAYBACK_CARD = 2
    ALSA_CAPTURE_CARD = 1
    CV2_INDEX = 0

    def __init__(self, args):
        super().__init__(args)
        self.ioexp = IOInterface()
        self.ioexp.subscribe(self.ioexp_cb)
        self.ioexp.open()
        self.clear_screen()
        self.statusbar("Loading...")
        self.audio = audio.AudioRecorder(devname='USB PnP Sound Device', rate=44100, frames_per_buffer=4096)
        system(f'amixer -c {self.ALSA_CAPTURE_CARD} sset Mic 100% > /dev/null')
        system(f'amixer -c {self.ALSA_PLAYBACK_CARD} sset Speaker 100% > /dev/null')

    def ioexp_cb(self, msg):
        if msg == 'BT0':
            self.trigger_button = True
            self.trigger_button_down.set()
            self.logger.debug("Trigger button down")
        elif msg == 'BT1':
            self.trigger_button = False
            self.trigger_button_up.set()
            self.logger.debug("Trigger button up")
        elif msg == 'dOK':
            pass
        elif msg.startswith('C'):
            for cb in self.ui_cbs:
                try:
                    cb(msg[1:])
                except:
                    pass
        else:
            self.logger.debug("RX: "+msg)

    def button_led(self, value):
        if value:
            return self.ioexp.transact('l1') == 'lOK'
        else:
            return self.ioexp.transact('l0') == 'lOK'
        
    def rgb_led(self, r, g=None, b=None):
        if isinstance(r, str):
            if r == 'off' or r == 'black':
                r,g,b = (0,0,0)
            elif r == 'on' or r == 'white':
                r,g,b = (255,255,255)
            elif r == 'red':
                r,g,b = (255,0,0)
            elif r == 'green':
                r,g,b = (0,255,0)
            elif r == 'blue':
                r,g,b = (0,0,255)
            elif r == 'yellow':
                r,g,b = (255,200,0)
            elif r == 'purple':
                r,g,b = (100,0,255)
            elif r == 'cyan':
                r,g,b = (0,255,255)
            elif r== 'orange':
                r,g,b = (255,75,0)
        elif g is None or b is None:
            raise SyntaxError("If color is not specified, all three r,g,b values must be specified")

        if isinstance(r,float):
            r = int(r*255.0)
        if isinstance(g,float):
            g = int(g*255.0)
        if isinstance(b,float):
            b = int(b*255.0)

        if isinstance(r,bool):
            r = r*255
        if isinstance(g,bool):
            g = g*255
        if isinstance(b,bool):
            b = b*255

        return self.ioexp.transact(f'L{r},{g},{b}')

    def clear_screen(self):
        self.ioexp.ser.write('''
        a0
        TT
        TB
        TS 
        TM
        tm
        '''.encode('utf-8'))

    def led_animation(self, val):
        return self.ioexp.transact(f'a{int(val)}')

    def statusbar(self, text):
        return self.ioexp.transact(f'TS{text}')

    def top_text(self, text):
        return self.ioexp.transact(f'TT{text}')
    
    def bottom_text(self, text):
        return self.ioexp.transact(f'TB{text}')

    def mode_text(self, text):
        return self.ioexp.transact(f'TM{text}')

    def memory_text(self, text):
        return self.ioexp.transact(f'Tm{text}')
