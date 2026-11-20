"""可复用视觉组件：把「画面零件」做成函数，场景只负责编排。

系列化时这些是 A 层资产（一次写好全系列共用）。
每个 builder 接收 (scene, cfg, **kw)，返回一个 VGroup，调用方决定何时入场/退场。
"""
import random

import numpy as np
from manim import (
    VGroup, Text, Dot, Rectangle, RoundedRectangle, Line,
    DashedLine, VMobject, UP, DOWN, LEFT, RIGHT,
    FadeIn, LaggedStart, ValueTracker, always_redraw,
)

from theme import FONT_STACK, SAFE_W, TOP_Y, BOTTOM_Y


def _color(style, key):
    return style.get(key, "#FFFFFF")


def _fs(style, key, default):
    """从配置读取字号，缺省时用默认值，便于统一调大/调小。"""
    return style.get(key, default)


# ---- 富文字特效（配置驱动，全局开关）----
# 由场景 construct 开始时调用 configure_rich() 注入。
# 默认关闭：保持清爽风格；打开后：高亮词自动染色 + 大标题描边立体。
_RICH = {
    "enabled": False,
    "words": [],
    "color": None,
    "outline": None,
    "outline_width": 1.2,
    "heading_boost": 1.0,
}


def configure_rich(style):
    """从 style 配置注入富文字特效开关。
    - rich_text:        总开关，默认 false
    - highlight_words:  出现即染色的关键词列表
    - highlight_color:  高亮颜色（缺省用 accent）
    - gold_outline:     标题描边色（缺省 None，不描边）
    - outline_width:    描边粗细（缺省 1.2；加强版可用 2.4~3.0）
    - heading_boost:    开启特效时大标题放大系数（如 1.15），制造字号层次
    """
    _RICH["enabled"] = bool(style.get("rich_text", False))
    _RICH["words"] = list(style.get("highlight_words", []))
    _RICH["color"] = style.get("highlight_color", style.get("accent", "#FFC857"))
    _RICH["outline"] = style.get("gold_outline")
    _RICH["outline_width"] = float(style.get("outline_width", 1.2))
    _RICH["heading_boost"] = float(style.get("heading_boost", 1.0))


def txt(text, size, color, bold=False, max_width=None, outline=False):
    """统一文字工厂：指定字体栈，避免不同系统缺字。

    max_width 为 None 时用安全宽度 SAFE_W；超宽自动等比缩小，
    从根本上杜绝长句被竖屏右边缘裁切。

    富文字特效（仅当 _RICH.enabled）：
    - 句内换色：高亮词表里的词自动染成 highlight_color（Text.t2c）
    - 描边立体：outline=True 的大标题加描边（stroke_color/width）
    两者都不改变动画逻辑，关掉开关即回到清爽版。
    """
    eff_size = size * _RICH["heading_boost"] if (outline and _RICH["enabled"]) else size
    kwargs = dict(
        font=FONT_STACK,
        font_size=eff_size,
        color=color,
        weight="BOLD" if bold else "NORMAL",
    )
    if _RICH["enabled"]:
        # 1) 句内换色：把命中的高亮词映射到强调色
        hits = {w: _RICH["color"] for w in _RICH["words"] if w and w in text}
        if hits:
            kwargs["t2c"] = hits
        # 2) 描边立体 + 3) 字号层次（放大）：仅大标题按需开启
        if outline and _RICH["outline"]:
            kwargs["stroke_color"] = _RICH["outline"]
            kwargs["stroke_width"] = _RICH["outline_width"]
    t = Text(text, **kwargs)
    limit = SAFE_W if max_width is None else max_width
    if hasattr(t, "width") and t.width > limit:
        t.scale_to_fit_width(limit)
    return t


# ---- 入场动态（配置驱动，全局开关）----
# motion: true 时画面逐层浮现、字幕逐字浮现；false 时整体淡入（旧行为）。
_MOTION = {"enabled": False}


def configure_motion(style):
    _MOTION["enabled"] = bool(style.get("motion", False))


def reveal(scene, mobject, run_time=0.6, lag_ratio=0.12, shift=0.12):
    """把 mobject 拆成子件依次淡入，营造'一层层出现'的动态感。
    - 对 VGroup：逐个子对象入场（画面分层）
    - 对 Text：逐个字符入场（打字机效果）
    motion 关闭或只有一个子件时，退回整体淡入。
    """
    if not _MOTION["enabled"]:
        scene.play(FadeIn(mobject, shift=shift * UP), run_time=run_time)
        return run_time
    parts = list(mobject.submobjects)
    if len(parts) < 2:
        scene.play(FadeIn(mobject, shift=shift * UP), run_time=run_time)
        return run_time
    anims = [FadeIn(p, shift=shift * UP) for p in parts]
    scene.play(LaggedStart(*anims, lag_ratio=lag_ratio), run_time=run_time)
    return run_time


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
    # 白字正文 + 金黄高亮词（同色系深浅），关键词由 txt() 内的 t2c 自动染色。
    t = txt(text, _fs(s,"font_caption",30), _color(s, "text"))
    t.move_to([0, BOTTOM_Y + 0.12, 0])
    return t


def caption_chars(cfg, text):
    """字幕按字符拆成独立 Text，供 reveal() 做逐字浮现（打字机效果）。
    属于高亮词的字符用 highlight_color 染色，兼容富文字特效。
    """
    s = cfg["style"]
    size = _fs(s, "font_caption", 30)
    # 参考图逻辑：正文白字（浅），关键词金黄（深），靠同色系深浅区分。
    base_color = _color(s, "text")
    hi_color = s.get("highlight_color", _color(s, "accent")) if _RICH["enabled"] else base_color

    # 标出哪些位置属于高亮词
    hi_mask = [False] * len(text)
    if _RICH["enabled"]:
        for word in _RICH["words"]:
            if not word:
                continue
            start = 0
            while True:
                idx = text.find(word, start)
                if idx < 0:
                    break
                for k in range(idx, idx + len(word)):
                    if k < len(hi_mask):
                        hi_mask[k] = True
                start = idx + len(word)

    group = VGroup()
    for i, ch in enumerate(text):
        c = Text(ch, font=FONT_STACK, font_size=size,
                 color=hi_color if hi_mask[i] else base_color,
                 weight="BOLD")
        group.add(c)
    group.arrange(RIGHT, buff=0.0).move_to([0, BOTTOM_Y + 0.12, 0])
    return group


def hook(cfg, seg):
    """段1：悬念钩子 + 注射器压缩示意。"""
    s = cfg["style"]
    g = VGroup()
    eyebrow = txt(seg["eyebrow"], _fs(s,"font_accent",30), _color(s, "accent"))
    l1 = txt(seg["line1"], _fs(s,"font_heading",38), _color(s, "text"), bold=True, outline=True)
    l2 = txt(seg["line2"], _fs(s,"font_heading",38), _color(s, "text"), bold=True, outline=True)
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


# ---------- 动态 v-t 曲线（平衡段，配置开关 curve_anim）----------
def _vt_curve_points(kind, n=140):
    """正/逆反应速率曲线采样点（Manim 坐标）。
    v正 从高位指数衰减到平衡线；v逆 从低位指数上升到平衡线；末端汇合于 y_eq。
    """
    y_eq = -0.115
    x0, x1 = -1.5, 1.45
    if kind == "fwd":
        amp, k, sign = 1.115, 2.3, 1.0      # 从 y=1.0 降到 y_eq
    else:
        amp, k, sign = 0.985, 2.8, -1.0     # 从 y=-1.1 升到 y_eq
    pts = []
    for i in range(n):
        x = x0 + (x1 - x0) * i / (n - 1)
        y = y_eq + sign * amp * np.exp(-k * (x - x0))
        pts.append(np.array([x, y, 0.0]))
    return pts


def _vt_partial(pts, alpha):
    """按 alpha∈[0,1] 取曲线前缀，末端线性插值，让"生长"连续不跳。"""
    a = max(0.0, min(1.0, float(alpha)))
    total = len(pts) - 1
    f = a * total
    i = int(f)
    if i >= total:
        return list(pts)
    frac = f - i
    head = list(pts[:i + 1])
    if frac > 1e-6:
        head.append(pts[i] * (1 - frac) + pts[i + 1] * frac)
    return head


def _vt_curve(pts, color, width=3.2):
    """点列 -> VMobject 曲线。点数少用折线，多点用平滑，避免 set_points_smoothly 报错。"""
    m = VMobject(stroke_color=color, stroke_width=width)
    arr = [np.array(p) for p in pts]
    if len(arr) >= 4:
        m.set_points_smoothly(arr)
    elif len(arr) >= 2:
        m.set_points_as_corners(arr)
    return m


def equilibrium_anim(cfg, seg):
    """平衡段动态版：曲线随时间从左侧"长"出来，末端光点与 v正/v逆 文字跟随，
    阶段文字随进度切换。参考启源化学的 v-t 图。

    返回 (static, alpha, dynamic)：
      - static:   坐标轴 / 平衡虚线 / 问题 / 公式（一次淡入）
      - alpha:    ValueTracker(0→1) 驱动生长
      - dynamic:  always_redraw 对象列表，加入场景后随 alpha 自动更新
    配置：curve_anim: true, curve_grow: 秒数, curve_stages: [{at, text}, ...]
    """
    s = cfg["style"]
    q = txt(seg["question"], _fs(s, "font_body", 26), _color(s, "text"), bold=True)
    q.move_to([0, 2.4, 0])
    ax = VGroup(
        Line([-1.6, -1.2, 0], [-1.6, 1.2, 0], stroke_width=1.5, color=_color(s, "text_dim")),
        Line([-1.6, -1.2, 0], [1.6, -1.2, 0], stroke_width=1.5, color=_color(s, "text_dim")),
    )
    eqline = DashedLineLike(-0.115, _color(s, "accent"))
    formula = txt(seg["formula"], _fs(s, "font_formula", 34), _color(s, "accent"), bold=True)
    formula.move_to([0, -2.15, 0])
    static = VGroup(q, ax, eqline, formula)

    fwd_pts = _vt_curve_points("fwd")
    rev_pts = _vt_curve_points("rev")
    col_f = _color(s, "accent")    # v正 金黄
    col_r = _color(s, "nitro")     # v逆 蓝（图表编码，与参考片一致）
    small = _fs(s, "font_small", 20)

    alpha = ValueTracker(0.0)

    fwd_curve = always_redraw(lambda: _vt_curve(_vt_partial(fwd_pts, alpha.get_value()), col_f))
    rev_curve = always_redraw(lambda: _vt_curve(_vt_partial(rev_pts, alpha.get_value()), col_r))

    fwd_dot = always_redraw(lambda: Dot(
        point=_vt_partial(fwd_pts, alpha.get_value())[-1],
        radius=0.055, color=col_f))
    rev_dot = always_redraw(lambda: Dot(
        point=_vt_partial(rev_pts, alpha.get_value())[-1],
        radius=0.055, color=col_r))

    # v正 / v逆 标签跟随各自曲线末端；汇合点上下错开，避免叠字
    fwd_lab = always_redraw(lambda: txt("v正", small, col_f, bold=True).move_to(
        _vt_partial(fwd_pts, alpha.get_value())[-1] + np.array([0.34, 0.17, 0.0])))
    rev_lab = always_redraw(lambda: txt("v逆", small, col_r, bold=True).move_to(
        _vt_partial(rev_pts, alpha.get_value())[-1] + np.array([0.34, -0.30, 0.0])))

    dynamic = [fwd_curve, rev_curve, fwd_dot, rev_dot, fwd_lab, rev_lab]

    # 可选：阶段文字，随进度切换（"反应刚开始 → 趋向平衡 → 达到平衡"）
    stages = seg.get("curve_stages", [])
    if stages:
        def _stage_now():
            a = alpha.get_value()
            cur = stages[0].get("text", "")
            for st in stages:
                if a >= float(st.get("at", 0.0)):
                    cur = st.get("text", "")
            return txt(cur, small, _color(s, "text_dim")).move_to([0, -1.62, 0])
        dynamic.append(always_redraw(_stage_now))

    return static, alpha, dynamic


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
    l1 = txt(seg["line1"], _fs(s,"font_heading",38), _color(s, "accent"), bold=True, outline=True)
    l2 = txt(seg["line2"], _fs(s,"font_body",26), _color(s, "text"))
    formula = txt(seg["formula"], _fs(s,"font_formula_long",26), _color(s, "n2o4"))
    g.add(lab, l1, l2, formula)
    g.arrange(DOWN, buff=0.22).move_to([0, 0.7, 0])
    return g


def outro(cfg, seg):
    """段6：互动收尾。"""
    s = cfg["style"]
    g = VGroup()
    q = txt(seg["question"], _fs(s,"font_heading",38), _color(s, "text"), bold=True, outline=True)
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
