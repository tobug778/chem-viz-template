"""第一期：NO₂ 平衡（复刻参考视频的六段式结构）。

运行（本地需装好 manim + cairo/pango）：
    manim -qh scenes/no2_equilibrium.py NO2Equilibrium

云端渲染见 .github/workflows/render.yml —— 推代码自动生成 mp4。
本场景全程无水印：不添加任何作者名、账号名、角标。
"""
import sys
from pathlib import Path

# 让 src/ 在任意工作目录下都可导入
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from manim import Scene, FadeIn, FadeOut, Transform, UP

from theme import load_config
from components import (
    BUILDERS, top_bar, progress_track, progress_fill, caption, particle_panel,
)


class NO2Equilibrium(Scene):
    def construct(self):
        cfg = load_config("no2_equilibrium")
        s = cfg["style"]

        header = top_bar(cfg)
        track = progress_track(cfg)
        self.add(header, track)

        bgm = ROOT / cfg["audio"]["bgm"]
        if bgm.exists():
            # 不传 loop：底层是否支持不确定，保持参数最小可用集
            self.add_sound(str(bgm), gain=cfg["audio"].get("volume", 0.18))

        segs = cfg["segments"]
        total = sum(x["dur"] for x in segs)
        elapsed = 0
        cap = None
        fill = None

        for i, seg in enumerate(segs):
            kind = seg["kind"]

            # ---- 画面主体 ----
            if kind == "particle":
                visual = particle_panel(cfg, seg, compressed=False)
                self.play(FadeIn(visual, shift=0.15 * UP), run_time=0.6)
                self.wait(seg["dur"] * 0.45)
                compressed = particle_panel(cfg, seg, compressed=True)
                self.play(Transform(visual, compressed), run_time=1.2)
                elapsed += seg["dur"] * 0.45 + 1.2
                remain = seg["dur"] - (seg["dur"] * 0.45 + 1.2)
                self.wait(max(0.2, remain))
                visual = compressed
            else:
                visual = BUILDERS[kind](cfg, seg)
                self.play(FadeIn(visual, shift=0.12 * UP), run_time=0.6)
                self.wait(max(0.2, seg["dur"] - 0.6))
                elapsed += seg["dur"]

            # ---- 字幕 ----
            if seg.get("caption"):
                new_cap = caption(cfg, seg["caption"])
                if cap is None:
                    cap = new_cap
                    self.play(FadeIn(cap), run_time=0.3)
                else:
                    self.play(Transform(cap, new_cap), run_time=0.3)

            # ---- 进度 ----
            fraction = min(1.0, elapsed / total)
            new_fill = progress_fill(cfg, fraction)
            if fill is None:
                fill = new_fill
                self.add(fill)
            else:
                self.play(Transform(fill, new_fill), run_time=0.3)

            # ---- 退场（最后一段留白收尾）----
            if i < len(segs) - 1:
                self.play(FadeOut(visual), run_time=0.4)

        self.wait(0.8)
