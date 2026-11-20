"""可复用视觉组件：把「画面零件」做成函数，场景只负责编排。

系列化时这些是 A 层资产（一次写好全系列共用）。
每个 builder 接收 (scene, cfg, **kw)，返回一个 VGroup，调用方决定何时入场/退场。
"""
import random

import numpy as np
from manim import (
    VGroup, Text, Dot, Rectangle, RoundedRectangle, Line,
    DashedLine, VMobject, UP, DOWN, LEFT, RIGHT,
)

from theme import FONT_STACK, SAFE_W, TOP_Y, BOTTOM_Y


def _color(style, key):
    return style.get(key, "#FFFFFF")


def _fs(style, key, default):
    """从配置读取字号，缺省时用默认值，便于统一调大/调小。"""
    return style.get(key, default)


def txt(text, size, color, bold=False):
    """统一文字工厂：指定字体栈，避免不同系统缺字。"""
    t = Text(
        text,
        font=FONT_STACK,
        font_size=size,
        color=color,
        weight="BOLD" if bold else "NORMAL",
    )
    return t


def top_bar(cfg):
    """顶部：系列名 + 期号角标。无水印——这里不放任何作者名/账号。"""
    s = cfg["style"]
    m = cfg["meta"]
    group = VGroup()
    name = txt(f"{m['series']}  ·  第{m['episode_no']}期", _fs(s,"font_small",20), _color(s, "text_dim"))
    name.to_edge(UP, buff=0.18).to_edge(LEFT, buff=0.28)
    rule = Line(LEFT * 1.9, RIGHT * 1.9, stroke_width=1, color=_color(s, "panel_line"))
    rule.next_to(name, DOWN, buff=0.1).move_to([0, rule.get_y(), 0])
    group.add(name, rule)
    return group


def progress_track(cfg):
    """底部进度条：整条灰底，供场景按段填充。"""
    s = cfg["style"]
    track = Rectangle(
        width=SAFE_W, height=0.035,
        fill_color=_color(s, "panel_line"), fill_opacity=0.55,
        stroke_width=0,
    )
    track.move_to([0, BOTTOM_Y - 0.18, 0])
    return track


def progress_fill(cfg, fraction):
    """进度条已填充部分，fraction∈[0,1]。"""
    s = cfg["style"]
    w = max(0.001, SAFE_W * fraction)
    fill = Rectangle(
        width=w, height=0.035,
        fill_color=_color(s, "accent"), fill_opacity=0.95, stroke_width=0,
    )
    fill.move_to([-SAFE_W / 2 + w / 2, BOTTOM_Y - 0.18, 0])
    return fill


def caption(cfg, text):
    s = cfg["style"]
    t = txt(text, _fs(s,"font_caption",30), _color(s, "accent"))
    t.move_to([0, BOTTOM_Y + 0.12, 0])
    return t


def hook(cfg, seg):
    """段1：悬念钩子 + 注射器压缩示意。"""
    s = cfg["style"]
    g = VGroup()
    eyebrow = txt(seg["eyebrow"], _fs(s,"font_accent",30), _color(s, "accent"))
    l1 = txt(seg["line1"], _fs(s,"font_heading",38), _color(s, "text"), bold=True)
    l2 = txt(seg["line2"], _fs(s,"font_heading",38), _color(s, "text"), bold=True)
    g.add(eyebrow, l1, l2)
    g.arrange(DOWN, buff=0.18).move_to([0, 1.35, 0])

    # 注射器：筒身 + 活塞 + 内部气体
    barrel = Rectangle(
        width=2.0, height=0.66,
        stroke_color=_color(s, "panel_line"), stroke_width=2,
        fill_color=_color(s, "panel"), fill_opacity=0.6,
    )
    gas = Rectangle(width=1.3, height=0.5,
                    fill_color=_color(s, seg.get("gas_color", "no2")),
                    fill_opacity=0.75, stroke_width=0)
    gas.move_to(barrel.get_center() + RIGHT * 0.25)
    plunger = Line(UP * 0.42, DOWN * 0.42, stroke_width=5, color=_color(s, "text_dim"))
    plunger.move_to(barrel.get_left() + LEFT * 0.05)
    syringe = VGroup(barrel, gas, plunger).move_to([0, -1.5, 0])
    g.add(syringe)
    return g


def particle_panel(cfg, seg, compressed=False):
    """段2：分子尺度粒子系统。compressed=True 时体积减半、棕色变淡。"""
    s = cfg["style"]
    rng = random.Random(20261119)
    panel = Rectangle(
        width=3.5, height=2.1,
        stroke_color=_color(s, "panel_line"), stroke_width=1.5,
        fill_color=_color(s, "panel"), fill_opacity=0.5,
    )
    panel.move_to([0, 0.7, 0])

    dots = VGroup()
    # 粒子组成从配置读取：两种粒子的颜色键、半径、数量、压缩后数量
    p = seg.get("particles", {})
    a = p.get("a", {"color": "no2", "radius": 0.055, "opacity": 0.9,
                    "normal": 16, "compressed": 7})
    b = p.get("b", {"color": "n2o4", "radius": 0.04, "opacity": 0.55,
                    "normal": 14, "compressed": 22})
    for spec in (a, b):
        count = spec.get("compressed" if compressed else "normal", 0)
        for _ in range(count):
            d = Dot(radius=spec.get("radius", 0.05),
                    color=_color(s, spec.get("color", "text")),
                    fill_opacity=spec.get("opacity", 0.8))
            d.move_to(panel.get_center() + np.array([rng.uniform(-1.5, 1.5),
                                                     rng.uniform(-0.8, 0.8), 0]))
            dots.add(d)

    scale = 0.72 if compressed else 1.0
    dots.scale(scale).move_to(panel.get_center())

    formula = txt(seg["formula"], _fs(s,"font_formula",34), _color(s, "text"), bold=True)
    formula.move_to([0, 2.5, 0])
    sub = txt(seg["sub"], _fs(s,"font_accent",30), _color(s, "accent"))
    sub.move_to([0, -1.35, 0])
    return VGroup(formula, panel, dots, sub)


def equilibrium(cfg, seg):
    """段3：正逆反应速率曲线，收敛到 v正=v逆≠0。"""
    s = cfg["style"]
    g = VGroup()
    q = txt(seg["question"], _fs(s,"font_body",26), _color(s, "text"), bold=True)
    q.move_to([0, 2.4, 0])

    # 坐标轴
    ax = VGroup(
        Line([-1.6, -1.2, 0], [-1.6, 1.2, 0], stroke_width=1.5, color=_color(s, "text_dim")),
        Line([-1.6, -1.2, 0], [1.6, -1.2, 0], stroke_width=1.5, color=_color(s, "text_dim")),
    )

    # v正 下降曲线 / v逆 上升曲线，趋于同一水平线（≠0）
    pts_fwd = [(-1.5, 1.0, 0), (-0.9, 0.35, 0), (-0.3, 0.05, 0),
               (0.4, -0.1, 0), (1.4, -0.12, 0)]
    pts_rev = [(-1.5, -1.15, 0), (-0.9, -0.7, 0), (-0.3, -0.35, 0),
               (0.4, -0.12, 0), (1.4, -0.11, 0)]
    fwd = VMobjectCurve(pts_fwd, _color(s, "no2"))
    rev = VMobjectCurve(pts_rev, _color(s, "nitro"))
    eqline = DashedLineLike(-0.115, _color(s, "accent"))

    formula = txt(seg["formula"], _fs(s,"font_formula",34), _color(s, "accent"), bold=True)
    formula.move_to([0, -2.15, 0])
    g.add(q, ax, fwd, rev, eqline, formula)
    return g


def bars(cfg, seg):
    """段4：压缩瞬间——三种状态浓度柱状图（压缩前/刚压完/新平衡）。"""
    s = cfg["style"]
    g = VGroup()
    moment = txt(seg["moment"], _fs(s,"font_body",26), _color(s, "text"), bold=True)
    moment.move_to([0, 2.5, 0])

    base_y = -1.0
    # 三阶段柱状图从配置读取：每阶段标签 + 两种物质的柱高
    stages = seg.get("bar_stages", [
        ("压缩前", 1.0, 0.6), ("刚压完", 1.9, 1.15), ("新平衡", 1.35, 1.0),
    ])
    colors = [
        _color(s, seg.get("bar_color_a", "no2")),
        _color(s, seg.get("bar_color_b", "n2o4")),
    ]
    for i, stage in enumerate(stages):
        label, h_a, h_b = stage[0], stage[1], stage[2]
        cx = -1.25 + i * 1.25
        b1 = Rectangle(width=0.34, height=h_a, fill_color=colors[0],
                       fill_opacity=0.85, stroke_width=0)
        b1.move_to([cx - 0.2, base_y + h_a / 2, 0])
        b2 = Rectangle(width=0.34, height=h_b, fill_color=colors[1],
                       fill_opacity=0.7, stroke_width=0)
        b2.move_to([cx + 0.2, base_y + h_b / 2, 0])
        lab = txt(label, _fs(s,"font_small",20), _color(s, "text_dim"))
        lab.move_to([cx, base_y - 0.2, 0])
        g.add(b1, b2, lab)

    baseline = Line([-1.8, base_y, 0], [1.8, base_y, 0],
                    stroke_width=1, color=_color(s, "panel_line"))
    formula = txt(seg["formula"], _fs(s,"font_formula_long",26), _color(s, "accent"))
    formula.move_to([0, -2.2, 0])
    g.add(baseline, formula)
    return g


def lechatelier(cfg, seg):
    """段5：勒夏特列原理 + 平衡常数。"""
    s = cfg["style"]
    g = VGroup()
    lab = txt(seg["label"], _fs(s,"font_small",20), _color(s, "text_dim"))
    l1 = txt(seg["line1"], _fs(s,"font_heading",38), _color(s, "accent"), bold=True)
    l2 = txt(seg["line2"], _fs(s,"font_body",26), _color(s, "text"))
    formula = txt(seg["formula"], _fs(s,"font_formula_long",26), _color(s, "n2o4"))
    g.add(lab, l1, l2, formula)
    g.arrange(DOWN, buff=0.22).move_to([0, 0.7, 0])
    return g


def outro(cfg, seg):
    """段6：互动收尾。"""
    s = cfg["style"]
    g = VGroup()
    q = txt(seg["question"], _fs(s,"font_heading",38), _color(s, "text"), bold=True)
    opts = VGroup(
        RoundedRectangle(width=1.7, height=0.55, corner_radius=0.08,
                         stroke_color=_color(s, "panel_line"), stroke_width=1.5,
                         fill_color=_color(s, "panel"), fill_opacity=0.6),
        RoundedRectangle(width=1.7, height=0.55, corner_radius=0.08,
                         stroke_color=_color(s, "panel_line"), stroke_width=1.5,
                         fill_color=_color(s, "panel"), fill_opacity=0.6),
    ).arrange(RIGHT, buff=0.35)
    oa = txt(seg.get("opt_a", "A  变深"), _fs(s,"font_small",20), _color(s, "text_dim")).move_to(opts[0].get_center())
    ob = txt(seg.get("opt_b", "B  变浅"), _fs(s,"font_small",20), _color(s, "text_dim")).move_to(opts[1].get_center())
    cta = txt(seg["cta"], _fs(s,"font_accent",30), _color(s, "accent"))
    g.add(q, opts, oa, ob, cta)
    q.move_to([0, 1.5, 0])
    opts.move_to([0, 0.1, 0])
    cta.move_to([0, -1.5, 0])
    return g


# ---------- 内部小工具 ----------
def VMobjectCurve(points, color):
    m = VMobject(stroke_color=color, stroke_width=3)
    m.set_points_smoothly([np.array(p) for p in points])
    return m


def DashedLineLike(y, color):
    return DashedLine([-1.6, y, 0], [1.6, y, 0],
                      stroke_width=1.5, color=color, dash_length=0.08)


BUILDERS = {
    "hook": hook,
    "particle": particle_panel,
    "equilibrium": equilibrium,
    "bars": bars,
    "lechatelier": lechatelier,
    "outro": outro,
}
