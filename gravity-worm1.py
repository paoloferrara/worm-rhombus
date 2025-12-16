from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from plyer import accelerometer

import colorsys
import math, os, wave, struct


# -------------------------------------------------
# Synth Arpeggios
# -------------------------------------------------

def generate_arpeggio(path, freqs, rate=44100, volume=0.35):
    if os.path.exists(path):
        return
    n = int(0.15 * rate)
    amp = int(32767 * volume)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for f in freqs:
            for i in range(n):
                t = i / rate
                s = math.sin(2 * math.pi * f * t)
                env = math.sin(math.pi * i / (n - 1))
                wf.writeframes(struct.pack("<h", int(amp * s * env)))

C_DUR  = [261.63, 329.63, 392.00, 523.25, 329.63, 392.00]
C_MOLL = [261.63, 311.13, 392.00, 523.25, 311.13, 392.00]
D_DUR  = [293.66, 369.99, 440.00, 587.33, 369.99, 440.00]
D_MOLL = [293.66, 349.23, 440.00, 587.33, 349.23, 440.00]

generate_arpeggio("up.wav", C_DUR)
generate_arpeggio("down.wav", C_MOLL)
generate_arpeggio("right.wav", D_DUR)
generate_arpeggio("left.wav", D_MOLL)


# -------------------------------------------------
# PlayField
# -------------------------------------------------

class PlayField(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.u = self.v = 0.0
        self.du = self.dv = 0.0
        self.step = 0.05

        self.max_len = 10
        self.points = [None]

        # Gravity-Vektor (Anzeige)
        self.gx = 0.0
        self.gy = 0.0
        self.gmag = 0.0

        self.sounds = {
            "UP": SoundLoader.load("up.wav"),
            "DOWN": SoundLoader.load("down.wav"),
            "LEFT": SoundLoader.load("left.wav"),
            "RIGHT": SoundLoader.load("right.wav"),
        }
        for s in self.sounds.values():
            if s:
                s.loop = True

        Clock.schedule_once(self.redraw, 0)

    def redraw(self, *a):
        self.canvas.clear()
        self.canvas.after.clear()

        self.cx, self.cy = self.center
        self.dx = self.width * 0.45
        self.dy = self.height * 0.4

        if len(self.points) == 1 and self.points[0] is None:
            self.points[0] = (self.cx, self.cy)

        with self.canvas:
            Color(0, 0.7, 1)
            self.draw_rhombus()
            self.draw_worm()

        with self.canvas.after:
            self.draw_axes()

    def draw_rhombus(self):
        Line(points=[
            self.cx, self.cy + self.dy,
            self.cx + self.dx, self.cy,
            self.cx, self.cy - self.dy,
            self.cx - self.dx, self.cy,
            self.cx, self.cy + self.dy
        ], width=18, dash_length=15, dash_offset=10)

    def uv_to_xy(self, u, v):
        return self.cx + u * self.dx, self.cy + v * self.dy

    def set_direction(self, du, dv):
        self.du, self.dv = du, dv

    def set_gravity_vector(self, gx, gy, mag):
        self.gx, self.gy, self.gmag = gx, gy, mag

    def move(self):
        if self.du == 0 and self.dv == 0:
            return

        self.u += self.du * self.step
        self.v += self.dv * self.step

        if abs(self.u) + abs(self.v) > 1:
            self.u, self.v = -self.u, -self.v
            self.points.append(None)

        self.points.append(self.uv_to_xy(self.u, self.v))
        self.points = self.points[-self.max_len * 3:]
        self.redraw()

    def draw_segments(self):
        segments, seg = [], []
        for p in self.points:
            if p is None:
                if seg:
                    segments.append(seg)
                    seg = []
            else:
                seg.append(p)
        if seg:
            segments.append(seg)

        total = len([p for p in self.points if p])
        drawn = 0

        for s in segments:
            for i in range(len(s) - 1):
                h = (drawn + i) / max(1, total - 1)
                Color(*colorsys.hsv_to_rgb(h, 1, 1))
                Line(points=[*s[i], *s[i+1]], width=6)
            drawn += len(s)
      
    def draw_worm(self):
        self.draw_segments()
        body = [p for p in self.points if p]
        if len(body) > 1:
            x, y = body[-1]
            Color(1, 1, 1)
            Rectangle(pos=(x - 8, y - 8), size=(16, 16))

    def draw_axes(self):
        ox = self.width * 0.85
        oy = self.height * 0.85
        scale = 70

        Color(1, 1, 1)
        Line(points=[ox - scale, oy, ox + scale, oy], width=2)
        Line(points=[ox, oy - scale, ox, oy + scale], width=2)

        # Gravity-Vektor: Länge ∝ Neigung
        Color(1, 0.2, 0.2)
        Line(points=[
            ox, oy,
            ox + self.gx * self.gmag * scale,
            oy + self.gy * self.gmag * scale
        ], width=3)


# -------------------------------------------------
# App
# -------------------------------------------------

class WormApp(App):
    DIRS = {
        "UP": (0, 1),
        "DOWN": (0, -1),
        "LEFT": (-1, 0),
        "RIGHT": (1, 0),
    }

    def build(self):
        root = FloatLayout()
        self.field = PlayField(size_hint=(1, 1))
        root.add_widget(self.field)

        self.active_keys = set()
        self.ev = None

        self.gravity_active = False
        self.gravity_ev = None
        self.ax0 = self.ay0 = None

        def btn(text, cx, cy):
            b = Button(text=text, size_hint=(0.18, 0.18),
                       pos_hint={"center_x": cx, "center_y": cy})
            b.bind(on_press=lambda *_: self.handle_press(text),
                   on_release=lambda *_: self.handle_release(text))
            root.add_widget(b)

        btn("UP", 0.5, 0.93)
        btn("RIGHT", 0.93, 0.5)
        btn("DOWN", 0.5, 0.07)
        btn("LEFT", 0.07, 0.5)

        self.gravity_btn = Button(
            text="GRAVITY",
            size_hint=(0.22, 0.12),
            pos_hint={"right": 0.98, "y": 0.02}
        )
        self.gravity_btn.bind(on_press=self.toggle_gravity)
        root.add_widget(self.gravity_btn)

        return root

    # ---------- Sound ----------

    def update_sound(self, du, dv):
        if du == 0 and dv == 0:
            for s in self.field.sounds.values():
                s.stop()
            return

        if abs(du) >= abs(dv):
            key = "RIGHT" if du > 0 else "LEFT"
        else:
            key = "UP" if dv > 0 else "DOWN"

        snd = self.field.sounds[key]
        if snd.state != "play":
            for s in self.field.sounds.values():
                s.stop()
            snd.play()

    # ---------- Gravity ----------

    def toggle_gravity(self, *_):
        if not self.gravity_active:
            accelerometer.enable()
            self.gravity_active = True
            self.gravity_btn.text = "GRAVITY ON"
            self.ax0 = self.ay0 = None
            self.gravity_ev = Clock.schedule_interval(self.poll_gravity, 1 / 25)
        else:
            self.gravity_active = False
            self.gravity_btn.text = "GRAVITY"
            Clock.unschedule(self.gravity_ev)
            accelerometer.disable()
            self.field.set_direction(0, 0)
            self.field.set_gravity_vector(0, 0, 0)
            self.stop_all()

    def poll_gravity(self, dt):
        val = accelerometer.acceleration
        if not val or any(v is None for v in val):
            return

        ax, ay, _ = val

        if self.ax0 is None:
            self.ax0, self.ay0 = ax, ay
            return

        dx = -(ax - self.ax0)
        dy = -(ay - self.ay0)

        mag = math.hypot(dx, dy)
        mag_norm = min(1.0, mag / 5.0)

        gx = dx / mag if mag else 0
        gy = dy / mag if mag else 0

        self.field.set_gravity_vector(gx, gy, mag_norm)

        dead = 0.8
        du = dv = 0

        if mag > dead:
            du = 1 if dx > dead else -1 if dx < -dead else 0
            dv = 1 if dy > dead else -1 if dy < -dead else 0

        self.field.set_direction(du, dv)
        self.update_sound(du, dv)

        if (du or dv) and not self.ev:
            self.ev = Clock.schedule_interval(lambda dt: self.field.move(), 0.15)
        if not (du or dv):
            self.stop_all()

    # ---------- Buttons ----------

    def handle_press(self, key):
        if self.gravity_active:
            return
        self.active_keys.add(key)
        self.update_movement()

    def handle_release(self, key):
        if self.gravity_active:
            return
        self.active_keys.discard(key)
        self.update_movement()

    def update_movement(self):
        du = sum(self.DIRS[k][0] for k in self.active_keys)
        dv = sum(self.DIRS[k][1] for k in self.active_keys)

        du = max(-1, min(1, du))
        dv = max(-1, min(1, dv))

        self.field.set_direction(du, dv)
        self.update_sound(du, dv)

        if (du or dv) and not self.ev:
            self.ev = Clock.schedule_interval(lambda dt: self.field.move(), 0.15)
        if not (du or dv):
            self.stop_all()

    def stop_all(self):
        if self.ev:
            Clock.unschedule(self.ev)
            self.ev = None
        for s in self.field.sounds.values():
            s.stop()


if __name__ == "__main__":
    WormApp().run()