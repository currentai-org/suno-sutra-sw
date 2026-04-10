from os.path import exists
from os import system
from subprocess import run
from glob import glob
import threading
import logging
import cv2
import re
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

class CameraReader:
    def __init__(self, camera_name='', camera_interface='usb', width=1280, height=720):
        self.logger = logging.getLogger(__name__)
        self.camera_name = camera_name
        self.camera_interface = camera_interface
        self.camera_idx = None
        self.width = width
        self.height = height
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.frame = None
        self.running = False
        self.frame_available = threading.Event()

    def start(self):
        self.running = True
        self.thread.start()
    
    def _run(self):
        for filename in glob('/dev/v4l/by-id/*'):
            match = re.match(r'(\S+)\-(\S+)\-\S+\-index(\d+)', filename)
            if match is None:
                continue
            interface, name, idx = match.groups()
            if self.camera_interface in interface and self.camera_name in name:
                self.camera_idx = int(idx)
                break
        if self.camera_idx is None:
            self.logger.warning(f"Camera '{self.camera_name}' with interface '{self.camera_interface}' not found, defaulting to index 0")
            self.camera_idx = 0
        self.cap = cv2.VideoCapture(self.camera_idx)
        if not self.cap.isOpened():
            raise RuntimeError(f"Unable to open VideoCapture({self.camera_idx})")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
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
    V4L_CAMERA_NAME = ''
    V4L_CAMERA_INTERFACE = 'usb'
    ALSA_CAPTURE_NAME = ''
    ALSA_PLAYBACK_NAME = ''
    ALSA_CAPTURE_RATE = 16000

    def __init__(self, args):
        self.logger = logging.getLogger(__name__)
        self.args = args
        self.trigger_button = False
        self.trigger_button_down = threading.Event()
        self.trigger_button_up = threading.Event()
        self.camera = CameraReader(
            camera_name=self.V4L_CAMERA_NAME,
            camera_interface=self.V4L_CAMERA_INTERFACE
        )
        self.audio = audio.AudioRecorder(devname=self.ALSA_CAPTURE_NAME, rate=self.ALSA_CAPTURE_RATE, frames_per_buffer=4096)
        self.ALSA_CAPTURE_CARD = audio.find_card_by_name(self.ALSA_CAPTURE_NAME)
        self.ALSA_PLAYBACK_CARD = audio.find_card_by_name(self.ALSA_PLAYBACK_NAME)
        self.ALSA_PLAYBACK_DEVICE = f'hw:{self.ALSA_PLAYBACK_CARD},0'
        self.logger.debug('Detected ALSA capture card index: %s, Detected ALSA playback card index: %s', self.ALSA_CAPTURE_CARD, self.ALSA_PLAYBACK_CARD)
        system(f'amixer -c {self.ALSA_CAPTURE_CARD} sset Mic 100% > /dev/null')
        system(f'amixer -c {self.ALSA_PLAYBACK_CARD} sset Speaker 100% > /dev/null')
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
        args = {}
        if not exists('/proc/device-tree/model'):
            raise NotImplementedError('/proc/device-tree not found: Must be a linux system with modern kernel >4')
        with open('/proc/device-tree/model', 'r') as fil:
            devicetree_model = fil.read().replace('\x00', '').strip()
        if devicetree_model.startswith('NVIDIA'):
            # nv_tegra_release will only be present on NVIDIA platforms, possibly only JetPack
            if not exists('/etc/nv_tegra_release'):
                raise NotImplementedError("Only NVIDIA Tegra platforms supported "+devicetree_model)
            with open('/etc/nv_tegra_release', 'r') as fil:
                args['kernelinfo'] = fil.readline()
            # Read EEPROM data from the module and carrier board. These i2c EEPROMs should be available on all Jetson platforms
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
            # Load the correct board based on the carrier board
            if carrier_ver.startswith(b'699-13768-0000'):
                from pocketinfer.boards.jetson import PocketInferDevboard
                return PocketInferDevboard(args)
            if carrier_ver.startswith(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'):
                # The seeeedstudio carrier board has an eeprom present but zero-ed out memory
                from pocketinfer.boards.jetson import PocketInferDemo
                return PocketInferDemo(args)
            raise NotImplementedError('Unsupported Carrier Board: '+carrier_ver.decode('utf-8'))
        elif devicetree_model.startswith('Raspberry Pi'):
            # Raspberry Pi detection will be based on devicetree model:
            regex = re.compile(r"Raspberry Pi (\d+|Compute Module) (\d+)?.*")
            match = regex.match(devicetree_model)
            if match is None:
                raise NotImplementedError(f'Cannot detect Raspberry Pi model {devicetree_model}')
            a, b = match.groups()
            if a == 'Compute Module':
                # This is a Raspberry Pi Compute Module
                # CM3 and below do not expose PCIe, so couldn't possibly connect to Hailo accelerator
                if int(b) < 4:
                    raise NotImplementedError(f'Compute Module {b} has no support for PCIe')
            elif a.isdigit():
                # This is a base Raspberry PI (e.g: Raspberry Pi 5, Raspberry pi 4, etc)
                # Raspberry Pi 4 and below do not expose PCIe, so couldn't possibly connect to Hailo accelerator
                if int(a) < 5:
                    raise NotImplementedError(f'Raspberry Pi {b} has no support for PCIe')
            else:
                raise NotImplementedError(f'Unsupported Raspberry Pi model {devicetree_model}')
            ret_code = system('hailortcli scan | grep "Device:"')
            if ret_code:
                raise NotImplementedError(f'Hailo accelerator not installed or detected')
            hailo_ver_raw = run(['hailortcli', 'fw-control', 'identify'], capture_output=True, text=True)
            match = re.search(r'Control Protocol Version:\s+(\d+)', hailo_ver_raw.stdout)
            args["protocol_ver"] = match.group(1) if match else None
            match = re.search(r'Firmware Version:\s+(\S+)', hailo_ver_raw.stdout)
            args["fw_ver"] = match.group(1) if match else None
            match = re.search(r'Device Architecture:\s+(\S+)', hailo_ver_raw.stdout)
            args["arch"] = match.group(1) if match else None
            if hailo_ver_raw.stderr:
                raise NotImplementedError('Error detecting Hailo accelerator: '+hailo_ver_raw.stderr)
            from pocketinfer.boards.raspi import RaspiAIHat2Board
            return RaspiAIHat2Board(args)
        else:
            raise NotImplementedError('Unsupported linux platform: '+devicetree_model)

    # To be overridden, ideally
    def button_led(self, value) -> bool:
        return True
        
    def rgb_led(self, r, g=None, b=None) -> bool:
        return True

    def led_animation(self, val) -> bool:
        return True

    def clear_screen(self):
        return

    def statusbar(self, text) -> bool:
        self.logger.info("Statusbar: "+text)
        return True

    def top_text(self, text) -> bool:
        self.logger.info("Top text: "+text)
        return True
    
    def bottom_text(self, text) -> bool:
        self.logger.info("Bottom text: "+text)
        return True

    def mode_text(self, text) -> bool:
        self.logger.info("Mode text: "+text)
        return True

    def memory_text(self, text) -> bool:
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