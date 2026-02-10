# SPDX-FileCopyrightText: 2021 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""Example for Pico. Blinks the built-in LED."""
import time
import board
import digitalio
import microcontroller
import supervisor
import usb_cdc
import neopixel
import busio
import adafruit_drv2605
import displayio
import terminalio
from adafruit_display_text import label, text_box
import fourwire
import adafruit_ili9341
from adafruit_neokey.neokey1x4 import NeoKey1x4

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
butled = digitalio.DigitalInOut(board.D7)
butled.direction = digitalio.Direction.OUTPUT
button = digitalio.DigitalInOut(board.D6)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

ser = usb_cdc.console

rgb = neopixel.NeoPixel(board.NEOPIXEL, 1)
rgb.brightness = 0.25

i2c = board.I2C()
spi = board.SPI()
tft_cs = board.D3
tft_dc = board.D2
# Create a NeoKey object
neokey = NeoKey1x4(i2c, addr=0x30)
# drv = adafruit_drv2605.DRV2605(i2c)

# If you use explicit pins with busio.SPI(...), calling release_displays() first
# prevents "pin in use" errors on subsequent reloads.
displayio.release_displays()
display_bus = fourwire.FourWire(spi, command=tft_dc, chip_select=tft_cs, baudrate=35000000)
display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240, rotation=180)

# Make the display context
splash = displayio.Group()
display.root_group = splash

color_bitmap = displayio.Bitmap(320, 240, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x000000

bg_sprite = displayio.TileGrid(color_bitmap,
                            pixel_shader=color_palette,
                            x=0, y=0)
splash.append(bg_sprite)

# Set text, font, and color
font = terminalio.FONT
color = 0xFFFFFF

# Create the text label
statusbar = label.Label(font, text=" "*52, color=color)
statusbar.anchor_point = (0.5, 1.0)
statusbar.anchored_position = (160, 240)
statusbar.text = "Initializing..."
splash.append(statusbar)

toptext = text_box.TextBox(x=0, y=0, width=320, height=100, font=font, color=color)
toptext.anchor_point = (0.0, 0.0)
toptext.anchored_position = (0, 0)
splash.append(toptext)

bottomtext = text_box.TextBox(x=0, y=100, width=320, height=100, font=font, color=color)
bottomtext.anchor_point = (0.0, 0.0)
bottomtext.anchored_position = (0, 100)
splash.append(bottomtext)

last_blink = time.monotonic()
last_press = time.monotonic()
last_trigger_button = False
last_buttons = [False, False, False, False]


def parse_msg(msg):
    try:
        if msg is None or len(msg) < 1:
            return
        if msg[0] == 'l':
            butled.value = int(msg[1:])
        elif msg[0] == 'L':
            idx = int(msg[1])
            if idx < 0 or idx > 4:
                raise ValueError("NeoKey index must be 0-4")
            if idx < 4:
                vals = tuple(int(x) for x in msg[2:].split(','))
                val = vals[2] & 0xFF | ((vals[1] & 0xFF) << 8) | ((vals[0] & 0xFF) << 16)
                neokey.pixels[idx] = val
            if idx == 4:
                rgb[0] = tuple(int(x) for x in msg[2:].split(','))
        elif msg[0] == 'b':
            rgb.brightness = float(msg[1:])
        elif msg[0] == 'd' and msg[0:4] == 'disp':
            eval(msg)
        elif msg[0] == 'T':
            if msg[1] == 'S':
                statusbar.text = msg[2:].strip()
            elif msg[1] == 'T':
                toptext.text = msg[2:].strip()
            elif msg[1] == 'B':
                bottomtext.text = msg[2:].strip()
            else:
                print(msg[0]+'Unk')
                return
        elif msg == 'reboot':
            microcontroller.reset()
        else:
            print(msg[0]+'Unk')
            return
        print(msg[0]+'OK')
    except Exception as e:
        print(msg[0]+'ERR: '+str(e))

try:
    msg_buf = b''
    while True:
        if (time.monotonic() - last_blink) > 0.5:
            led.value = not led.value
            last_blink = time.monotonic()
        button_val = button.value
        if button_val != last_trigger_button and (time.monotonic() - last_press > 0.1):
            last_press = time.monotonic()
            # butled.value = not button_val
            print("BT"+str(int(button_val)))
            last_trigger_button = button_val
        buttons = neokey.get_keys()
        if buttons[0] != last_buttons[0]:
            print("BA"+str(int(buttons[0])))
        if buttons[1] != last_buttons[1]:
            print("BB"+str(int(buttons[1])))
        if buttons[2] != last_buttons[2]:
            print("BC"+str(int(buttons[2])))
        if buttons[3] != last_buttons[3]:
            print("BD"+str(int(buttons[3])))
        last_buttons = buttons
        if ser.in_waiting:
            # Read all available bytes from serial port
            msg_buf += ser.read(ser.in_waiting)
            # Extract any messages delimited by '\n' or '\r'
            while '\r' in msg_buf or '\n' in msg_buf:
                if '\r' in msg_buf:
                    msg = msg_buf[:msg_buf.find(b'\r')].strip().rstrip()
                    parse_msg(msg.decode('utf-8'))
                    msg_buf = msg_buf[msg_buf.find(b'\r')+1:]
                elif '\n' in msg_buf:
                    msg = msg_buf[:msg_buf.find(b'\n')].strip().rstrip()
                    parse_msg(msg.decode('utf-8'))
                    msg_buf = msg_buf[msg_buf.find(b'\n')+1:]
except Exception as e:
    print(f"Caught Exception: {e}")
    print("Reloading in 1 second")
    time.sleep(1)
    supervisor.reload()
