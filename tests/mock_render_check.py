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
    def play(self, *a, **k):
        name = type(a[0]).__name__ if a else "empty"
        self.events.append(("play", name, float(k.get("run_time", 0))))
    def add(self, *a, **k): self.events.append(("add",))
    def remove(self, *a, **k): pass
    def wait(self, *a, **k):
        secs = float(a[0]) if a else 0.0
        self.events.append(("wait", secs))
    def add_sound(self, *a, **k): pass


m.Scene = Scene
sys.modules["manim"] = m

import episode as ep

results = {}
scenes = {}
for name in ["haber_ammonia", "no2_equilibrium"]:
    os.environ["EPISODE"] = name
    sc = ep.Episode(); sc.construct()
    scenes[name] = sc
    anims = [e[1] for e in sc.events if e[0] == "play"]
    results[name] = dict(Counter(anims))
    waits = [e[1] for e in sc.events if e[0] == "wait"]
    print("%s ✅ play=%d wait=%d add=%d" % (
        name, len(anims), len(waits),
        sum(1 for e in sc.events if e[0] == "add")))
    print("   ", results[name])

for need in ["GrowFromEdge", "Create", "Rotate"]:
    assert need in results["haber_ammonia"], "合成氨版缺动画 " + need
    assert need not in results["no2_equilibrium"], "第一期不该有 " + need

# --- 本次回归：时长 bug 修复 + 6 段编号转场环 ---
# 1) 圆环描边 Create 恰好 6 次 = 6 个章节环
n_create = results["haber_ammonia"].get("Create", 0)
assert n_create == 6, "章节环数量应为 6，实际 %d" % n_create
print("\n章节环 Create 次数: %d ✅" % n_create)

# 2) 第一段 no2 无转场环
assert results["no2_equilibrium"].get("Create", 0) == 0, "第一期不应有转场环"
print("第一期无转场环 ✅")

# 3) 统计实际成片时长 = 所有 play run_time + wait 时长
def total_time(sc):
    return sum(e[2] for e in sc.events if e[0] == "play") + \
           sum(e[1] for e in sc.events if e[0] == "wait")

t_haber = total_time(scenes["haber_ammonia"])
print("成片估算时长: %.1f 秒（配置预算 58s）" % t_haber)
assert 50 <= t_haber <= 70, "时长被腰斩或异常: %.1f" % t_haber

# 4) 每段的 wait 都应该是显式正数（bug 修复的核心标志：不再有大量 0 秒 wait 被跳过）
waits = [e[1] for e in scenes["haber_ammonia"].events if e[0] == "wait"]
print("所有 wait 时长:", [round(w, 2) for w in waits])
assert all(w > 0 for w in waits), "存在 0/负 wait，stay 又被跳过了"

print("\n✅ 6 环就位 / 时长恢复 ~58s / stay 不再被跳过 / 第一期不受影响")

# --- 回归：字幕叠字修复 ---
# caption_chars 必须与 caption 共用同一个整句 Text（原生 t2c 高亮）。
# 一旦退回"每字独立 Text + arrange 重排"，中文字符 bearing 会让金/白字错位叠字。
import components as comp
os.environ["EPISODE"] = "salt_hydrolysis"
cfg_salt = ep.load_config("salt_hydrolysis")
comp.configure_rich(cfg_salt["style"])
SAMPLE = "弱酸根抢水电离的 H⁺，剩下 OH⁻"
cap_plain = comp.caption(cfg_salt, SAMPLE)
cap_chars = comp.caption_chars(cfg_salt, SAMPLE)
assert type(cap_chars) is type(cap_plain), \
    "caption_chars 必须与 caption 同为整句 Text，不能是逐字 VGroup（叠字根因）"
assert getattr(cap_chars, "t", None) == SAMPLE, "字幕文本应保持完整整句"
print("字幕整句 Text（无逐字重排/叠字）✅")

# --- 回归：盐的水解球棍微观过程 + 柱顶化学式（本期新需求）---
# 1) micro 段应构建出球棍分子骨架，并带可动部件属性
os.environ["EPISODE"] = "salt_hydrolysis"
cfg_s = ep.load_config("salt_hydrolysis")
seg_micro = next(x for x in cfg_s["segments"] if x.get("micro"))
assert seg_micro["kind"] == "particle", "micro 开关应挂在 particle 段"
comp.configure_rich(cfg_s["style"])
mg = comp.micro_process(cfg_s, seg_micro)
for attr in ("h_flash", "acetate_o", "col_accent"):
    assert hasattr(mg, attr), "球棍骨架缺可动属性 " + attr
steps, created = comp.micro_process_anim(cfg_s, seg_micro, mg)
assert len(steps) >= 5, "夺 H⁺ 动态步骤过少"
assert len(created) >= 6, "微观过程产物对象过少"
anims_used = [type(a).__name__ for st, _ in steps for a in st]
assert "Transform" in anims_used, "缺 H⁺ 飞向醋酸根的 Transform 动画"
assert "Create" in anims_used, "缺高亮圈 Create 动画"
print("球棍微观过程（动态夺H⁺ + 高亮圈）✅ steps=%d" % len(steps))

# 2) 跑通盐的水水解整条 construct，确保 micro 分支在场景里被触发且时长正常
sc_s = ep.Episode(); sc_s.construct()
anims_s = [e[1] for e in sc_s.events if e[0] == "play"]
assert "Transform" in anims_s and "Create" in anims_s, "场景未播放微观过程动画"
t_s = total_time(sc_s)
assert 50 <= t_s <= 70, "盐的水解时长异常: %.1f" % t_s
print("盐的水水解 construct ✅ 时长 %.1fs / Transform=%d" % (
    t_s, anims_s.count("Transform")))

# 3) 柱顶标注：配置驱动。本期 H⁺/OH⁻；其它主题不写该字段 -> 仍用数字
assert seg_micro is not None
seg_bars = next(x for x in cfg_s["segments"] if x["kind"] == "bars")
assert seg_bars.get("bar_top_labels") == ["H⁺", "OH⁻"], "本期柱顶应为化学式"
for other in ["haber_ammonia", "galvanic_cell", "no2_equilibrium"]:
    cfg_o = ep.load_config(other)
    for seg in cfg_o["segments"]:
        if seg["kind"] == "bars":
            assert not seg.get("bar_top_labels"), \
                "%s 不应有 bar_top_labels（避免串味）" % other
print("柱顶标注配置驱动（仅盐的水解用化学式，其它主题不串味）✅")
