"""可复用视觉组件：把「画面零件」做成函数，场景只负责编排。

系列化时这些是 A 层资产（一次写好全系列共用）。
每个 builder 接收 (scene, cfg, **kw)，返回一个 VGroup，调用方决定何时入场/退场。
"""
import random

import numpy as np
from manim import (
    VGroup, Text, Dot, Rectangle, RoundedRectangle, Line, Circle,
    DashedLine, VMobject, UP, DOWN, LEFT, RIGHT,
    FadeIn, FadeOut, LaggedStart, Transform, ValueTracker, always_redraw,
    GrowFromEdge, Rotate, Create,
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
    """字幕：整句一次排版 + Manim 原生 t2c 高亮（白字正文 + 金黄高亮词）。

    关键修复：字幕必须是一个整句 Text，不能手工按字拆开再 arrange ——
    单个中文字符 Text 的宽度含字体 bearing，逐字重排后高亮字与正文字会
    水平错位、叠成金/白两行。整句排版从根上杜绝叠字。
    """
    s = cfg["style"]
    t = txt(text, _fs(s, "font_caption", 30), _color(s, "text"))
    t.move_to([0, BOTTOM_Y + 0.12, 0])
    return t


def caption_chars(cfg, text):
    """逐字浮现用的字幕，与 caption() 共用同一个整句 Text。

    Manim 的 Text.submobjects 本身就是逐字符的，reveal() 直接对这层原生
    子件做 LaggedStart(FadeIn) 即可打字机效果；t2c 高亮由 Manim 原生处理。
    不再手工 Text(ch)+arrange —— 那是金/白两层错位的根因。
    """
    return caption(cfg, text)


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


# ---------- 球棍分子微观过程（盐的水解：醋酸根夺 H⁺）----------
# 参考启源化学"放大到分子"：画能认出来的球棍分子 + 用圆圈高亮标出
# 正在反应的原子，动态演示"夺走 H⁺ → 断键 → 生成新分子"，而不是一团散点。
def _atom(pos, radius, color, opacity=1.0):
    """单个原子球：pos 为 (x,y)，用 Dot 近似球棍模型的球。"""
    d = Dot(point=[pos[0], pos[1], 0.0], radius=radius, color=color)
    return d


def _bond(p1, p2, color, width=3.0):
    """一根化学键：两点之间连线。"""
    return Line([p1[0], p1[1], 0.0], [p2[0], p2[1], 0.0],
                stroke_width=width, color=color)


def _water_molecule(center, size, col_o, col_h):
    """水分子 H₂O 球棍：中心 O（大）+ 两个 H（小）呈 V 形。
    返回 (VGroup, O位置, [H位置...], [H球对象...])，H 球对象供动画里"夺走"后淡出。"""
    cx, cy = center
    r = size
    pos_o = (cx, cy)
    pos_h1 = (cx - 0.9 * r, cy + 0.8 * r)
    pos_h2 = (cx + 0.9 * r, cy + 0.8 * r)
    dot_h1 = _atom(pos_h1, r * 0.52, col_h)
    dot_h2 = _atom(pos_h2, r * 0.52, col_h)
    g = VGroup()
    g.add(_bond(pos_o, pos_h1, col_o, 2.6), _bond(pos_o, pos_h2, col_o, 2.6))
    g.add(_atom(pos_o, r, col_o), dot_h1, dot_h2)
    return g, pos_o, [pos_h1, pos_h2], [dot_h1, dot_h2]


def _acetate_molecule(center, size, col_c, col_o, col_h):
    """醋酸根 CH₃COO⁻ 简化球棍：甲基碳 + 羧基两氧，末端带负电。返回 VGroup。"""
    cx, cy = center
    r = size
    c_methyl = (cx - 0.75 * r, cy)             # 甲基碳
    c_carboxyl = (cx + 0.55 * r, cy)           # 羧基碳
    o_top = (cx + 1.35 * r, cy + 0.75 * r)     # 羧基氧 1（将被 H⁺ 结合）
    o_bot = (cx + 1.35 * r, cy - 0.75 * r)     # 羧基氧 2（带负电）
    g = VGroup()
    # 碳骨架键
    g.add(_bond(c_methyl, c_carboxyl, col_c, 3.2))
    g.add(_bond(c_carboxyl, o_top, col_c, 3.0), _bond(c_carboxyl, o_bot, col_c, 3.0))
    # 甲基上的三个氢（V 形三点）
    for hpos in [(c_methyl[0] - 0.6 * r, cy + 0.85 * r),
                 (c_methyl[0] - 1.0 * r, cy),
                 (c_methyl[0] - 0.6 * r, cy - 0.85 * r)]:
        g.add(_bond(c_methyl, hpos, col_c, 2.2), _atom(hpos, r * 0.42, col_h))
    g.add(_atom(c_methyl, r * 0.9, col_c), _atom(c_carboxyl, r * 0.9, col_c))
    g.add(_atom(o_top, r * 0.85, col_o), _atom(o_bot, r * 0.85, col_o))
    return g, o_top


def micro_process(cfg, seg):
    """段2 微观过程静态骨架：面板 + 一对球棍分子（水、醋酸根）+ 公式 + 图注 + 负电荷标记。

    真正的"夺 H⁺ 动态"在 micro_process_anim() 里做。这里只返回入场后的静态对象，
    并把可动部件（水的某个 H、高亮圈、产物标签）挂到 group 属性上供动画引用。
    """
    s = cfg["style"]
    col_o = _color(s, "ox")       # 氧：橙红
    col_c = _color(s, "n2o4")     # 碳：灰蓝
    col_h = _color(s, "text")     # 氢：白
    col_neg = _color(s, "nitro")  # 负电荷：蓝
    small = _fs(s, "font_small", 18)

    panel = Rectangle(
        width=3.7, height=2.35,
        stroke_color=_color(s, "panel_line"), stroke_width=1.5,
        fill_color=_color(s, "panel"), fill_opacity=0.5,
    )
    panel.move_to([0, 0.55, 0])

    # 反应物摆在面板内：醋酸根偏左，水分子偏右
    water, o_pos, h_positions, h_dots = _water_molecule((1.05, 0.85), 0.20, col_o, col_h)
    acetate, o_top = _acetate_molecule((-1.05, 0.75), 0.20, col_c, col_o, col_h)

    formula = txt(seg["formula"], _fs(s, "font_formula_long", 24), _color(s, "text"), bold=True)
    formula.move_to([0, 2.45, 0])
    sub = txt(seg["sub"], _fs(s, "font_accent", 26), _color(s, "accent"))
    sub.move_to([0, -1.35, 0])

    # 图例：球棍颜色说明（参照参考图底部 NO₂/N₂O₄ 图例）
    legend_w = txt("H₂O  水分子", small, _color(s, "text_dim"))
    legend_a = txt("CH₃COO⁻  醋酸根", small, _color(s, "text_dim"))
    legend_w.move_to([-1.05, -0.55, 0])
    legend_a.move_to([1.05, -0.55, 0])

    # 醋酸根负电荷标记（放在带负电的羧基氧 o_bot 旁）
    neg_pos = (-1.05 + 1.35 * 0.20, 0.75 - 0.75 * 0.20)
    neg = txt("⁻", small * 1.2, col_neg).next_to(
        Dot(point=[neg_pos[0], neg_pos[1], 0.0]), RIGHT, buff=0.04)

    g = VGroup(formula, panel, water, acetate, sub, legend_w, legend_a, neg)
    # 挂可动部件供动画引用：被夺的 H（水左侧那个）、受体氧（醋酸根羧基氧）
    g.h_flash = h_positions[0]
    g.h_donor = h_dots[0]        # 被夺走的那个白色 H 球，动画里淡出（水→OH⁻）
    g.neg_mark = neg             # 醋酸根负电荷，结合 H⁺ 后淡出
    g.acetate_o = o_top
    g.col_accent = _color(s, "accent")
    g.col_o = col_o
    g.col_h = col_h
    return g


def micro_process_anim(cfg, seg, group):
    """动态过程（球棍图示化，非散点）：
    ① 金黄高亮圈圈住水的 H → ② H⁺ 从水分子飞出 → ③ 飞向醋酸根羧基氧 →
    ④ 高亮圈转移到结合位点 → ⑤ 标注产物 CH₃COOH / OH⁻ → ⑥ 结论点题显碱性。

    返回 (steps, created)：
      steps   = [(anims, run_time), ...]，场景逐条 play；只用 Create/FadeIn/FadeOut/
                Transform，均为 mock 与真实 Manim 都支持的动画。
      created = 动画中新建的全部对象，供退场时统一 FadeOut 清理。
    """
    s = cfg["style"]
    small = _fs(s, "font_small", 18)
    accent = group.col_accent
    col_o, col_h = group.col_o, group.col_h

    hf = group.h_flash          # 起点：水的左侧 H
    ao = group.acetate_o        # 终点：醋酸根羧基氧

    # ① 圈住即将被夺走的 H
    halo_h = Circle(radius=0.17, stroke_color=accent, stroke_width=2)
    halo_h.move_to([hf[0], hf[1], 0.0])

    # ② 飞行的 H⁺（金黄，区别于普通白 H）+ 标签
    flying = Dot(point=[hf[0], hf[1], 0.0], radius=0.12, color=accent)
    hlabel = txt("H⁺", small, accent, bold=True).next_to(flying, UP, buff=0.06)
    # 终态：飞到受体氧处
    flying_target = Dot(point=[ao[0], ao[1], 0.0], radius=0.12, color=accent)
    hlabel_target = txt("H⁺", small, accent, bold=True).next_to(flying_target, UP, buff=0.06)

    # ④ 结合位点高亮圈
    halo_accept = Circle(radius=0.19, stroke_color=accent, stroke_width=2)
    halo_accept.move_to([ao[0], ao[1], 0.0])

    # ⑤ 产物图示化标注
    lbl_acid = txt("→ CH₃COOH  醋酸分子", small, accent, bold=True)
    lbl_acid.move_to([-1.15, -0.98, 0])
    lbl_oh = txt("→ OH⁻  氢氧根", small, _color(s, "nitro"), bold=True)
    lbl_oh.move_to([1.15, -0.98, 0])

    # ⑥ 结论
    conclusion = txt(seg.get("conclusion", "c(OH⁻) > c(H⁺) → 显碱性"),
                     _fs(s, "font_accent", 26), accent, bold=True)
    conclusion.move_to([0, -2.15, 0])

    steps = [
        ([Create(halo_h)], 0.5),                                   # ① 圈出被夺的 H
        ([FadeIn(flying), FadeIn(hlabel)], 0.4),                    # ② H⁺ 现身
        ([Transform(flying, flying_target),                         # ③ 飞向醋酸根：
          Transform(hlabel, hlabel_target),                         #    原白 H 消失(水→OH⁻)，
          FadeOut(group.h_donor), FadeOut(group.neg_mark)], 1.4),   #    负电荷消失(已成醋酸)
        ([FadeOut(halo_h), Create(halo_accept)], 0.5),              # ④ 高亮转移=成键
        ([FadeIn(lbl_acid), FadeIn(lbl_oh)], 0.6),                  # ⑤ 产物标注
        ([FadeIn(conclusion)], 0.6),                                # ⑥ 结论点题
    ]
    created = [halo_h, flying, hlabel, halo_accept, lbl_acid, lbl_oh, conclusion]
    return steps, created


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


# ---------- 动态柱状图（配置开关 bar_anim）----------
def bars_anim_parts(cfg, seg):
    """动态柱状图：骨架一次淡入，三阶段依次出现。
    每个阶段 = (阶段组, 该阶段柱子列表, 该阶段数值列表)，供场景按顺序 GrowFromEdge 长出柱子、
    数值紧跟标注。参考启源化学：上方色块 + 阶段标签 + 两根柱 + 柱顶数值，逐阶段构建。
    返回 (static, stages, base_y)
    """
    s = cfg["style"]
    moment = txt(seg["moment"], _fs(s, "font_body", 26), _color(s, "text"), bold=True)
    moment.move_to([0, 2.5, 0])
    formula = txt(seg["formula"], _fs(s, "font_formula_long", 26), _color(s, "text"))
    formula.move_to([0, -2.2, 0])
    base_y = -1.0
    baseline = Line([-1.8, base_y, 0], [1.8, base_y, 0],
                    stroke_width=1, color=_color(s, "panel_line"))
    static = VGroup(moment, formula, baseline)

    stages = seg.get("bar_stages", [
        ("压缩前", 1.0, 0.6), ("刚压完", 1.9, 1.15), ("新平衡", 1.35, 1.0),
    ])
    col_a = _color(s, seg.get("bar_color_a", "no2"))
    col_b = _color(s, seg.get("bar_color_b", "n2o4"))
    # 阶段顶部色块：反应物柱色 / 生成物柱色的深色调，参考图的三个色卡
    swatches = seg.get("bar_swatches", [])
    sm = _fs(s, "font_small", 18)

    out = []
    for i, stage in enumerate(stages):
        label, h_a, h_b = stage[0], stage[1], stage[2]
        cx = -1.25 + i * 1.25
        grp = VGroup()

        # 顶部色块（若有）：参考图的深/中/深色卡
        if i < len(swatches):
            sw = RoundedRectangle(
                width=0.78, height=0.34, corner_radius=0.05,
                stroke_color=_color(s, "panel_line"), stroke_width=1,
                fill_color=_color(s, swatches[i]), fill_opacity=0.85)
            sw.move_to([cx, 2.0, 0])
            grp.add(sw)

        b1 = Rectangle(width=0.34, height=h_a, fill_color=col_a,
                       fill_opacity=0.9, stroke_width=0)
        b1.move_to([cx - 0.2, base_y + h_a / 2, 0])
        b2 = Rectangle(width=0.34, height=h_b, fill_color=col_b,
                       fill_opacity=0.8, stroke_width=0)
        b2.move_to([cx + 0.2, base_y + h_b / 2, 0])
        lab = txt(label, sm, _color(s, "text_dim"))
        lab.move_to([cx, base_y - 0.22, 0])

        # 柱顶标注（配置驱动，仅本主题生效，不跨主题复用）：
        #   bar_top_labels: ["H⁺", "OH⁻"]  → 柱顶显示化学式（盐的水解：橙=H⁺，蓝=OH⁻）
        #   未配置 → 回退到 stage 可选数值 / 柱高数字（合成氨、原电池、第一期照旧）
        top_labels = seg.get("bar_top_labels") or []
        if top_labels:
            va = str(top_labels[0]) if len(top_labels) > 0 else ""
            vb = str(top_labels[1]) if len(top_labels) > 1 else ""
        else:
            va = _fmt_num(stage[3]) if len(stage) > 3 else _fmt_num(h_a)
            vb = _fmt_num(stage[4]) if len(stage) > 4 else _fmt_num(h_b)
        na = txt(va, sm, col_a, bold=True)
        na.next_to(b1, UP, buff=0.08)
        nb = txt(vb, sm, _color(s, "text"), bold=True)
        nb.next_to(b2, UP, buff=0.08)

        # 注意：柱子不放进 grp（grp 只淡入色块+标签）。柱子交给 GrowFromEdge
        # 从底部长出，否则 FadeIn(grp) 时柱子已完整显示，"生长"效果就没了。
        grp.add(lab)
        out.append((grp, [b1, b2], [na, nb]))
    return static, out, base_y


def _fmt_num(v):
    """数值标注格式化：去掉多余的 .0。"""
    try:
        f = float(v)
        return str(int(f)) if abs(f - int(f)) < 1e-6 else ("%.2f" % f).rstrip("0")
    except (ValueError, TypeError):
        return str(v)


def chapter_transition(cfg, seg, number, title, en_title):
    """圆环过场（参考启源化学"04 减弱，不是抵消"）：
    外圈细金圆环 + 内圈黄蓝交替光点绕圈 + 中心大页码/标题/英文。
    返回 (group, ring, dots)，场景负责让 ring 描边绘制、dots 旋转、文字淡入，一闪而过。
    """
    s = cfg["style"]
    g = VGroup()
    ring = Circle(
        radius=1.9,
        stroke_color=_color(s, "accent"), stroke_width=1.6,
    )
    # 内圈光点：黄蓝交替，绕成一圈
    dots = VGroup()
    n = 24
    radius = 1.42
    for k in range(n):
        ang = 2 * np.pi * k / n
        col = _color(s, "accent") if k % 2 == 0 else _color(s, "nitro")
        d = Dot(point=np.array([radius * np.cos(ang), radius * np.sin(ang), 0.0]),
                radius=0.045, color=col)
        dots.add(d)

    num = txt(str(number), _fs(s, "font_heading", 34) * 2.0,
              _color(s, "accent"), bold=True)
    ttl = txt(title, _fs(s, "font_heading", 34), _color(s, "text"), bold=True)
    en = txt(en_title, _fs(s, "font_small", 18), _color(s, "text_dim"))
    center = VGroup(num, ttl, en).arrange(DOWN, buff=0.22)

    g.add(ring, dots, center)
    return g, ring, dots, center


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
