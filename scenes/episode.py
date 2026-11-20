"""通用场景：一期视频的编排逻辑，全系列共用。

读 config/ACTIVE 指定的配置（或环境变量 EPISODE）决定渲染哪一期。
以后新增期数只需：写一份 config/xxx.yaml + 把 ACTIVE 改成 xxx，
不用改这个文件、也不用改任何 Python 代码。

本地运行：
    EPISODE=haber_ammonia manim -r 720,1280 --fps 30 scenes/episode.py Episode

云端渲染见 .github/workflows/render.yml。本场景全程无水印。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from manim import Scene, FadeIn, FadeOut, Transform, UP, linear

from theme import load_config
from components import (
    BUILDERS, top_bar, progress_track, progress_fill, caption, caption_chars,
    particle_panel, equilibrium_anim, configure_rich, configure_motion, reveal,
)
from components import _MOTION


def _active_episode() -> str:
    """优先用环境变量，其次读 config/ACTIVE，最后回退第一期。"""
    env = os.environ.get("EPISODE")
    if env:
        return env.strip()
    active = ROOT / "config" / "ACTIVE"
    if active.exists():
        name = active.read_text(encoding="utf-8").strip()
        if name:
            return name
    return "no2_equilibrium"


class Episode(Scene):
    def construct(self):
        name = _active_episode()
        cfg = load_config(name)

        # ---- 视觉效果：读 style 开关（默认关闭，保持清爽风格）----
        configure_rich(cfg["style"])
        configure_motion(cfg["style"])

        # ---- 常驻元素：顶栏 + 进度条底轨（全程不清除）----
        header = top_bar(cfg)
        track = progress_track(cfg)
        self.add(header, track)

        # ---- BGM：默认关闭，输出无音轨纯画面；需要时在 YAML 里设 audio.enabled: true ----
        audio_cfg = cfg.get("audio", {})
        if audio_cfg.get("enabled", False):
            bgm = ROOT / audio_cfg.get("bgm", "assets/bgm.mp3")
            if bgm.exists():
                self.add_sound(str(bgm), gain=audio_cfg.get("volume", 0.18))

        segs = cfg["segments"]
        total = sum(x["dur"] for x in segs)
        elapsed = 0.0            # 已真实消耗的动画时间（秒）
        fill = None              # 当前进度条填充对象
        seg_objects = []         # 本段临时对象，切段时全部清除

        # 转场开销：入场上字幕 + 字幕 + 进度 + 退场（秒）
        T_IN, T_X, T_FADE = 0.5, 0.25, 0.3

        for i, seg in enumerate(segs):
            kind = seg["kind"]
            dur = seg["dur"]

            # ---- 1. 画面主体 ----
            if kind == "particle":
                visual = particle_panel(cfg, seg, compressed=False)
                reveal(self, visual, run_time=T_IN)
                seg_objects.append(visual)
                elapsed += T_IN

                # 前半段静止观察，后半段压缩变形
                hold = dur * 0.45
                self.wait(max(0.2, hold - T_IN))
                elapsed += max(0.2, hold - T_IN)

                compressed = particle_panel(cfg, seg, compressed=True)
                self.play(Transform(visual, compressed), run_time=1.0)
                elapsed += 1.0
                visual = compressed
                remain = dur - hold - 1.0
                self.wait(max(0.2, remain))
                elapsed += max(0.2, remain)

            elif kind == "equilibrium" and seg.get("curve_anim", False):
                # 动态 v-t 曲线：先淡入骨架，再让曲线随进度从左侧"长"出来，
                # 末端光点 + v正/v逆 标签 + 阶段文字全程跟随（参考启源化学）。
                static, alpha, dynamic = equilibrium_anim(cfg, seg)
                reveal(self, static, run_time=T_IN)
                seg_objects.append(static)
                elapsed += T_IN
                # always_redraw 对象用 add 常驻，由 alpha 驱动持续更新（不能用 FadeIn）
                for o in dynamic:
                    self.add(o)
                    seg_objects.append(o)

                grow = float(seg.get("curve_grow", 5.0))
                self.play(alpha.animate.set_value(1.0), run_time=grow, rate_func=linear)
                elapsed += grow
                stay = dur - T_IN - grow - T_X - T_FADE
                self.wait(max(0.2, stay))
                elapsed += max(0.2, stay)
            else:
                visual = BUILDERS[kind](cfg, seg)
                reveal(self, visual, run_time=T_IN)
                seg_objects.append(visual)
                elapsed += T_IN
                stay = dur - T_IN - T_X - T_FADE
                self.wait(max(0.2, stay))
                elapsed += max(0.2, stay)

            # ---- 2. 字幕：逐字浮现（motion 开）或整句淡入（关）----
            if seg.get("caption"):
                if _MOTION["enabled"]:
                    new_cap = caption_chars(cfg, seg["caption"])
                    reveal(self, new_cap, run_time=max(0.8, T_X * 3),
                           lag_ratio=0.06, shift=0.04)
                else:
                    new_cap = caption(cfg, seg["caption"])
                    self.play(FadeIn(new_cap), run_time=T_X)
                seg_objects.append(new_cap)
                elapsed += T_X

            # ---- 3. 进度条 ----
            fraction = min(1.0, elapsed / total)
            new_fill = progress_fill(cfg, fraction)
            if fill is None:
                fill = new_fill
                self.add(fill)
            else:
                self.play(Transform(fill, new_fill), run_time=T_X)
                elapsed += T_X

            # ---- 4. 退场：清空本段所有临时对象（关键修复：杜绝残留叠加）----
            if i < len(segs) - 1:
                to_remove = list(seg_objects)
                if to_remove:
                    # always_redraw 对象带 updater，先停更新再淡出，避免残留/淡出被重置
                    for o in to_remove:
                        if hasattr(o, "clear_updaters"):
                            o.clear_updaters()
                    self.play(*[FadeOut(o) for o in to_remove], run_time=T_FADE)
                    elapsed += T_FADE
                    self.remove(*to_remove)
                seg_objects = []

        self.wait(0.5)
