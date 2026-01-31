# SPDX-FileCopyrightText: 2021 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""Example for Pico. Blinks the built-in LED."""
import time
import board
import digitalio
import supervisor
import usb_cdc
import neopixel
import busio
import adafruit_drv2605
import adafruit_ssd1306

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
# drv = adafruit_drv2605.DRV2605(i2c)
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
disp.fill(0)
disp.text("Reloading...", 20, 30, 1)
disp.show()

last_blink = time.monotonic()
last_press = time.monotonic()
last_button = False

def parse_msg(msg):
    try:
        if msg is None or len(msg) < 1:
            return
        if msg[0] == 'l':
            butled.value = int(msg[1:])
        elif msg[0] == 'L':
            rgb[0] = tuple(int(x) for x in msg[1:].split(','))
        elif msg[0] == 'b':
            rgb.brightness = float(msg[1:])
        elif msg[0] == 'd' and msg[0:4] == 'disp':
            eval(msg)
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
        if button_val != last_button and (time.monotonic() - last_press > 0.1):
            last_press = time.monotonic()
            # butled.value = not button_val
            print("B"+str(int(button_val)))
            last_button = button_val
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
