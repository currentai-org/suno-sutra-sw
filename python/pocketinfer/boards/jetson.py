from pocketinfer.serialcomms import IOInterface
from pocketinfer.boards.base import Board
from pocketinfer.ui.handheld import HandheldUI

import Jetson.GPIO as GPIO

import time
import displayio
import digitalio
import board
import fourwire
import adafruit_ili9341
import xpt2046_circuitpython as xpt2046


class PocketInferDevboard(Board):
    V4L_CAMERA_NAME = 'Arducam_8mp'
    ALSA_CAPTURE_NAME = 'Arducam_8mp'
    ALSA_PLAYBACK_NAME = 'USB Audio Device'
    TRIGGER_BOARD_IDX = 'GP167'  # Physical pin 7 on header

    def __init__(self, args):
        super().__init__(args)
        # Circuitpython modules may have already initialized in TEGRA_SOC mode.
        GPIO.setmode(GPIO.TEGRA_SOC)
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

class PocketInferDevboardUI(PocketInferDevboard):
    TOUCH_IRQ_BOARD_IDX = 'GP37_SPI3_MISO'  # Physical pin 22 on header
    ALSA_PLAYBACK_NAME = 'UACDemo'
    ALSA_PLAYBACK_CHANNEL_NAME = "PCM"

    def __init__(self, args):
        super().__init__(args)
        pwm_pin = digitalio.DigitalInOut(board.D18)
        reset_pin = digitalio.DigitalInOut(board.D13)
        tft_cs = board.D8
        tft_dc = board.D22
        touch_cs = board.D7
        touch_irq = board.D25

        GPIO.setmode(GPIO.TEGRA_SOC)
        GPIO.setup(self.TOUCH_IRQ_BOARD_IDX, GPIO.IN)
        GPIO.add_event_detect(self.TOUCH_IRQ_BOARD_IDX,
                              GPIO.BOTH,
                              callback=self.touch_cb,
                              bouncetime=100)

        # Setup SPI bus using hardware SPI:
        i2c = board.I2C()
        spi = board.SPI()
        # RESET pin for display
        reset_pin.direction = digitalio.Direction.OUTPUT
        reset_pin.value = False
        time.sleep(0.005)
        reset_pin.value = True
        time.sleep(0.005)
        # Turn on the display backlight
        pwm_pin.direction = digitalio.Direction.OUTPUT
        pwm_pin.value = True

        displayio.release_displays()
        display_bus = fourwire.FourWire(spi,
                                        command=tft_dc,
                                        chip_select=tft_cs,
                                        baudrate=30000000)
        display = adafruit_ili9341.ILI9341(display_bus,
                                           width=320,
                                           height=240,
                                           rotation=90)
        touch = xpt2046.Touch(spi,
                              cs=digitalio.DigitalInOut(touch_cs),
                              interrupt=digitalio.DigitalInOut(touch_irq),
                              force_baudrate=1000000)

        self.UI = HandheldUI(display, touch)

    def touch_cb(self, channel):
        self.logger.debug("Touch IRQ")
        self.UI.check_touch()

    def clear_screen(self):
        self.UI.clear_screen()

    def statusbar(self, text):
        self.UI.statusbar_text(text)
        return True

    def top_text(self, text):
        self.UI.top_text(text)
        return True

    def bottom_text(self, text):
        self.UI.bottom_text(text)
        return True

    def mode_text(self, text):
        self.UI.mode_text(text)
        return True

    def memory_text(self, text):
        self.UI.memory_text(text)
        return True

class RaspiAIHat2Board(Board):
    V4L_CAMERA_NAME = 'Arducam_8mp'
    ALSA_CAPTURE_NAME = 'Arducam_8mp'
    ALSA_PLAYBACK_NAME = 'USB Audio Device'
    TRIGGER_BOARD_IDX = 7

    def __init__(self, args):
        super().__init__(args)

class PocketInferDemo(Board):
    V4L_CAMERA_NAME = 'Arducam_8mp'
    ALSA_CAPTURE_NAME = 'USB PnP Sound Device'
    ALSA_CAPTURE_RATE = 44100
    ALSA_PLAYBACK_NAME = 'USB Audio Device'

    def __init__(self, args):
        super().__init__(args)
        self.ioexp = IOInterface()
        self.ioexp.subscribe(self.ioexp_cb)
        self.ioexp.open()
        self.clear_screen()
        self.statusbar("Loading...")

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

        return self.ioexp.transact(f'L{r},{g},{b}') == 'LOK'

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
        return self.ioexp.transact(f'a{int(val)}') == 'aOK'

    def statusbar(self, text):
        return self.ioexp.transact(f'TS{text}') == 'TSOK'

    def top_text(self, text):
        return self.ioexp.transact(f'TT{text}') == 'TTOK'
    
    def bottom_text(self, text):
        return self.ioexp.transact(f'TB{text}') == 'TBOK'

    def mode_text(self, text):
        return self.ioexp.transact(f'TM{text}') == 'TMOK'

    def memory_text(self, text):
        return self.ioexp.transact(f'Tm{text}') == 'TmOK'
