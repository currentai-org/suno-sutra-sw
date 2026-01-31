from os.path import exists
from subprocess import run
from pocketinfer.serialcomms import IOInterface
import threading
import logging
import cv2
from pocketinfer import audio


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

class Board:
    CV2_INDEX = 0
    ALSA_PLAYBACK_DEVICE = "default"

    def __init__(self, args):
        self.logger = logging.getLogger(__name__)
        self.args = args
        self.trigger_button = False
        self.trigger_button_down = threading.Event()
        self.trigger_button_up = threading.Event()
        self.cap = cv2.VideoCapture(self.CV2_INDEX)
    
    def wait_for_trigger_button_down(self, timeout=None):
        self.trigger_button_down.clear()
        self.trigger_button_down.wait(timeout=timeout)
    
    def wait_for_trigger_button_up(self, timeout=None):
        self.trigger_button_up.clear()
        self.trigger_button_up.wait(timeout=timeout)

    def camera_frame(self):
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.CV2_INDEX)
            if not self.cap.isOpened():
                raise RuntimeError(f"Unable to re-open VideoCapture({self.CV2_INDEX})")
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

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


class PocketInferDevboard(Board):
    pass

class PocketInferDemo(Board):
    ALSA_PLAYBACK_DEVICE = "hw:2,0"

    def __init__(self, args):
        super().__init__(args)
        self.ioexp = IOInterface()
        self.ioexp.subscribe(self.ioexp_cb)
        self.ioexp.open()
        self.audio = audio.AudioRecorder(devname='USB Audio Device', rate=44100, frames_per_buffer=4096)

    def ioexp_cb(self, msg):
        if msg == 'B0':
            self.trigger_button_down.set()
            self.trigger_button = True
            self.logger.debug("Trigger button down")
        elif msg == 'B1':
            self.trigger_button_up.set()
            self.trigger_button = False
            self.logger.debug("Trigger button up")
        elif msg == 'dOK':
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
        disp.fill(0)
        disp.show()
        '''.encode('utf-8'))

    def statusbar(self, text):
        self.ioexp.ser.write(f'''
        disp.fill_rect(0,57,128,9,0)
        disp.text("{text}", 0,57,1)
        disp.show()
        '''.encode('utf-8'))

    def wraptext(self, text):
        lines = [text[idx:idx+20] for idx in range(0, len(text), 20)]
        xidx = 0
        self.ioexp.ser.write(b'disp.fill_rect(0,0,128,56,0)\n')
        for line in lines[:7]:
            self.ioexp.ser.write(f'disp.text("{line}",0, {xidx},1)\n'.encode('utf-8'))
            xidx += 8
        self.ioexp.ser.write(b'disp.show()\n')