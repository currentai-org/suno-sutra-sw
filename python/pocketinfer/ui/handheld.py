import time
import displayio
import terminalio
from os.path import join
from adafruit_display_text import label, text_box
from adafruit_bitmap_font import bitmap_font
from adafruit_button.button import Button

from pocketinfer.ui import icons
from importlib.resources import files


class HandheldUI:
    def __init__(self, display, touch):
        self.display = display
        self.touch = touch

        # Make the display context
        self.layers = displayio.Group()
        self.topbar = displayio.Group()
        self.appui = displayio.Group()
        self.display.root_group = self.layers

        color_bitmap = displayio.Bitmap(320, 240, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0x000000

        # bg_sprite = displayio.TileGrid(color_bitmap,
        #                             pixel_shader=color_palette,
        #                             x=0, y=0)

        # Set text, font, and color
        font = terminalio.FONT
        color = 0xFFFFFF
        color_dim = 0x777777
        icon_font = bitmap_font.load_font(str(files('pocketinfer.ui').joinpath('forkawesome-16.pcf')))
        hindi_font = bitmap_font.load_font(str(files('pocketinfer.ui').joinpath('NotoSansDevanagari-Regular-12.pcf')))

        # Create the text label
        self.statusbar = label.Label(font, text=" "*52, color=color_dim)
        self.statusbar.anchor_point = (0.5, 1.0)
        self.statusbar.anchored_position = (160, 240)
        self.statusbar.text = "Initializing..."
        self.topbar.append(self.statusbar)


        self.modeval = label.Label(font, text=" "*52, color=color_dim)
        self.modeval.anchor_point = (0.0, 0.0)
        self.modeval.anchored_position = (0, 3)
        # modeval.text = "App: HearTheWorldEn"
        self.topbar.append(self.modeval)

        self.home_button = Button(
            x=320-28,
            y=0,
            width=28,
            height=28,
            label=icons.home,
            label_font=icon_font,
            label_color=color,
            fill_color=0x000000,
            outline_color=0x000000,
        )
        self.topbar.append(self.home_button)
        self.settings_button = Button(
            x=320-28*2,
            y=0,
            width=28,
            height=28,
            label=icons.book,
            label_font=icon_font,
            label_color=color,
            fill_color=0x000000,
            outline_color=0x000000,
        )
        self.topbar.append(self.settings_button)

        # Create the text label
        self.battval = label.Label(icon_font, text=f"{icons.microchip}     {icons.battery_full}", color=color)
        self.battval.anchor_point = (1.0, 0.0)
        self.battval.anchored_position = (320-28*2-4, 3)
        self.topbar.append(self.battval)

        self.memval = label.Label(hindi_font, text="    ", color=color)
        self.memval.anchor_point = (1.0, 0.0)
        self.memval.anchored_position = (240, 8)
        self.topbar.append(self.memval)

        self.toptext = text_box.TextBox(x=0, y=0, width=320, height=100, line_spacing=0.80, font=hindi_font, color=color)
        self.toptext.anchor_point = (0.0, 0.0)
        self.toptext.anchored_position = (0, 16)
        self.appui.append(self.toptext)


        self.bottomtext = text_box.TextBox(x=0, y=100, width=320, height=100, line_spacing=0.8, font=hindi_font, color=color)
        self.bottomtext.anchor_point = (0.0, 0.0)
        self.bottomtext.anchored_position = (0, 100)
        self.appui.append(self.bottomtext)

        self.setpage = displayio.Group()

        settingslabel = label.Label(font, text=" "*52, color=color)
        settingslabel.anchor_point = (0.5, 0.0)
        settingslabel.anchored_position = (160, 16)
        settingslabel.text = "Settings"
        self.setpage.append(settingslabel)

        self.settings_buttons = {}

        input_lang = label.Label(font, text="ASR Lang ", color=color)
        input_lang.anchor_point = (0.0, 0.5)
        input_lang.anchored_position = (0, 48)
        self.setpage.append(input_lang)

        self.settings_buttons['ASR En'] = Button(
            x=64,
            y=32,
            width=64,
            height=32,
            label="ASR En",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['ASR Hi'] = Button(
            x=64+64,
            y=32,
            width=64,
            height=32,
            label="ASR Hi",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['ASR Ta'] = Button(
            x=64+64*2,
            y=32,
            width=64,
            height=32,
            label="ASR Ta",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        output_lang = label.Label(font, text="TTS Lang ", color=color)
        output_lang.anchor_point = (0.0, 0.5)
        output_lang.anchored_position = (0, int(64+32/2))
        self.setpage.append(output_lang)

        self.settings_buttons['TTS En'] = Button(
            x=64,
            y=64,
            width=64,
            height=32,
            label="TTS En",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['TTS Hi'] = Button(
            x=64+64,
            y=64,
            width=64,
            height=32,
            label="TTS Hi",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['TTS Ta'] = Button(
            x=64+64*2,
            y=64,
            width=64,
            height=32,
            label="TTS Ta",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['Reset'] = Button(
            x=64,
            y=192,
            width=64,
            height=32,
            label="Reset",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['Shutdown'] = Button(
            x=64*2,
            y=192,
            width=64,
            height=32,
            label="Shutdown",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['Reboot'] = Button(
            x=64*3,
            y=192,
            width=64,
            height=32,
            label="Reboot",
            label_font=hindi_font,
            label_color=0xFF7E00,
            fill_color=0x5C5B5C,
            outline_color=0x767676,
            selected_fill=0x1A1A1A,
            selected_outline=0x2E2E2E,
        )

        self.settings_buttons['ASR En'].selected = True
        self.settings_buttons['TTS En'].selected = True

        for but in self.settings_buttons.values():
            self.setpage.append(but)

        self.setpage.hidden = True
        # self.layers.append(bg_sprite)
        self.layers.append(self.topbar)
        self.layers.append(self.appui)
        self.layers.append(self.setpage)

        self.last_blink = time.monotonic()
        self.last_press = time.monotonic()
        self.last_trigger_button = False
        self.last_touched = False
        self.last_buttons = [False, False, False, False]

    def top_text(self, text):
        self.toptext.text = text
    
    def bottom_text(self, text):
        self.bottomtext.text = text

    def statusbar_text(self, text):
        self.statusbar.text = text
    
    def mode_text(self, text):
        self.modeval.text = text

    def memory_text(self, text):
        self.memval.text = text
    
    def clear_screen(self):
        self.toptext.text = ""
        self.bottomtext.text = ""
        self.statusbar.text = ""
        self.modeval.text = ""
        self.memval.text = ""

    def force_refresh(self):
        self.display.root_group = None
        self.display.root_group = self.layers
        self.display.refresh()

    def check_buttons(self, x, y):
        for name in self.settings_buttons:
            butt = self.settings_buttons[name]
            if butt.selected:
                continue
            if butt.contains((x, y)):
                names = list(self.settings_buttons.keys())
                for other in filter(lambda x: x.startswith(name.split(' ')[0]), names):
                    self.settings_buttons[other].selected = False
                if name == 'Reset' or name == 'Reboot' or name == 'Shutdown':
                    self.setpage.hidden = True
                    self.appui.hidden = False
                    print('C'+name)
                    if name == 'Reboot':
                        time.sleep(0.1)
                        # microcontroller.reset()
                else:
                    butt.selected = True
                print('C'+name)
        if self.settings_button.contains((x, y)):
            if self.setpage.hidden:
                self.setpage.hidden = False
                self.appui.hidden = True
            else:
                self.setpage.hidden = True
                self.appui.hidden = False
            print('CSettings')

    def check_touch(self):
        if self.touch.is_pressed():
            try:
                args = self.touch.get_coordinates()
                if args is not None:
                    # NOTE, this implies 90 degree rotation on the display
                    # TODO - make this more robust to different rotations and touch coordinate mappings
                    y, x = args
                    y = 240 - y
                    print(f"Touch at ({x}, {y})")
                    self.check_buttons(x, y)
            except xpt2046.ReadFailedException as e:
                pass

if __name__ == "__main__":
    import digitalio
    import board
    import fourwire
    import adafruit_ili9341
    import xpt2046_circuitpython as xpt2046


    reset_pin = digitalio.DigitalInOut(board.pin.Pin("GP36_SPI3_CLK"))
    pwm_pin = digitalio.DigitalInOut(board.D18)
    cs_pin = digitalio.DigitalInOut(board.D8)
    dc_pin = digitalio.DigitalInOut(board.D22)
    #reset_pin = digitalio.DigitalInOut(board.D13)
    tft_cs = board.D8
    tft_dc = board.D22
    touch_cs = board.D7
    touch_irq = board.D25

    # Config for display baudrate (default max is 24mhz):
    BAUDRATE = 240000

    # Setup SPI bus using hardware SPI:
    i2c = board.I2C()
    spi = board.SPI()
    # Turn on the display backlight
    pwm_pin.direction = digitalio.Direction.OUTPUT
    pwm_pin.value = True

    # disp = ili9341.ILI9341(spi, rotation=180, width=320, height=240,                           # 2.2", 2.4", 2.8", 3.2" ILI9341
    #                        cs=cs_pin, dc=dc_pin, rst=reset_pin, baudrate=BAUDRATE)
    displayio.release_displays()
    display_bus = fourwire.FourWire(spi, command=tft_dc, chip_select=tft_cs, baudrate=50000000)
    display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240, rotation=90)
    touch = xpt2046.Touch(spi, cs=digitalio.DigitalInOut(touch_cs), interrupt=digitalio.DigitalInOut(touch_irq), force_baudrate=1000000)

    UI = HandheldUI(display, touch)

    while True:
        UI.check_touch()
        time.sleep(0.1)