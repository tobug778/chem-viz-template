"""无 Manim 环境下的回归检查：用 mock 跑通两期 Episode.construct，验证关键动画就位。

本机无 cairo/manim，无法真渲染；此脚本只验证编排逻辑、参数读取、动画调用不出错。
运行：PYTHONPATH=src python3 tests/mock_render_check.py
"""
import os
import sys
import types
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scenes"))

m = types.ModuleType("manim")


class Mobject:
    def __init__(self, *a, **k):
        self.kw = k; self.width = 1.0; self.height = 1.0
        self.submobjects = []; self._up = []
    def move_to(self, *a, **k): return self
    def to_edge(self, *a, **k): return self
    def next_to(self, *a, **k): return self
    def shift(self, *a, **k): return self
    def scale_to_fit_width(self, w): return self
    def get_center(self): return np.array([0., 0., 0.])
    def get_left(self): return np.array([0., 0., 0.])
    def get_y(self): return 0.0
    def arrange(self, *a, **k): return self
    def scale(self, *a, **k): return self
    def add_updater(self, *a, **k): return self
    def clear_updaters(self): self._up = []; return self
    def set_points_smoothly(self, pts): return self
    def set_points_as_corners(self, pts): return self


class Text(Mobject):
    def __init__(self, text, **kw):
        super().__init__(**kw); self.t = text


class VGroup(Mobject):
    def __init__(self, *a, **k):
        super().__init__(**k); self.items = list(a); self.submobjects = list(a)
    def add(self, *xs): self.items.extend(xs); self.submobjects.extend(xs)
    def __getitem__(self, i): return self.submobjects[i]
    def __len__(self): return len(self.submobjects)


class ValueTracker(Mobject):
    def __init__(self, v=0., *a, **k): super().__init__(*a, **k); self.v = v
    def set_value(self, v): self.v = v; return self
    def get_value(self): return self.v
    @property
    def animate(self): return _Anim(self)


class _Anim:
    def __init__(self, vt): self.vt = vt
    def set_value(self, v): return ("anim", self.vt, v)


def always_redraw(fn):
    o = fn(); o._redraw = True; return o


class Dot(Mobject): pass
class VMobject(Mobject): pass
class Circle(Mobject): pass


def linear(t): return t


for n in ["Rectangle", "RoundedRectangle", "Line", "DashedLine"]:
    setattr(m, n, type(n, (Mobject,), {}))


class Anim:
    def __init__(self, *a, **k): self.kw = k; self.args = a


for n in ["FadeIn", "LaggedStart", "FadeOut", "Transform", "GrowFromEdge", "Rotate", "Create"]:
    setattr(m, n, type(n, (Anim,), {}))

for n, v in [("UP", np.array([0, 1., 0])), ("DOWN", np.array([0, -1., 0])),
             ("LEFT", np.array([-1., 0, 0])), ("RIGHT", np.array([1., 0, 0]))]:
    setattr(m, n, v)

for n, v in [("VGroup", VGroup), ("Text", Text), ("Dot", Dot), ("VMobject", VMobject),
             ("Circle", Circle), ("ValueTracker", ValueTracker),
             ("always_redraw", always_redraw), ("linear", linear)]:
    setattr(m, n, v)


class Scene:
    def __init__(self): self.events = []
    def play(self, *a, **k): self.events.append(("play", type(a[0]).__name__ if a else "empty"))
    def add(self, *a, **k): self.events.append(("add",))
    def remove(self, *a, **k): pass
    def wait(self, *a, **k): self.events.append(("wait",))
    def add_sound(self, *a, **k): pass


m.Scene = Scene
sys.modules["manim"] = m

import episode as ep

results = {}
for name in ["haber_ammonia", "no2_equilibrium"]:
    os.environ["EPISODE"] = name
    sc = ep.Episode(); sc.construct()
    anims = [e[1] for e in sc.events if e[0] == "play"]
    results[name] = dict(Counter(anims))
    print("%s ✅ play=%d wait=%d add=%d" % (
        name, len(anims), sum(1 for e in sc.events if e[0] == "wait"),
        sum(1 for e in sc.events if e[0] == "add")))
    print("   ", results[name])

for need in ["GrowFromEdge", "Create", "Rotate"]:
    assert need in results["haber_ammonia"], "合成氨版缺动画 " + need
    assert need not in results["no2_equilibrium"], "第一期不该有 " + need
print("\n✅ 三项新动画仅出现在合成氨版，第一期不受影响；两期 construct 均跑通")
