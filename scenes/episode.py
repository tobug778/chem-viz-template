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

from manim import Scene, FadeIn, FadeOut, Transform, UP

from theme import load_config
from components import (
    BUILDERS, top_bar, progress_track, progress_fill, caption, particle_panel,
)


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
        s = cfg["style"]

        header = top_bar(cfg)
        track = progress_track(cfg)
        self.add(header, track)

        bgm = ROOT / cfg["audio"]["bgm"]
        if bgm.exists():
            self.add_sound(str(bgm), gain=cfg["audio"].get("volume", 0.18))

        segs = cfg["segments"]
        total = sum(x["dur"] for x in segs)
        elapsed = 0
        cap = None
        fill = None

        for i, seg in enumerate(segs):
            kind = seg["kind"]

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

            if seg.get("caption"):
                new_cap = caption(cfg, seg["caption"])
                if cap is None:
                    cap = new_cap
                    self.play(FadeIn(cap), run_time=0.3)
                else:
                    self.play(Transform(cap, new_cap), run_time=0.3)

            fraction = min(1.0, elapsed / total)
            new_fill = progress_fill(cfg, fraction)
            if fill is None:
                fill = new_fill
                self.add(fill)
            else:
                self.play(Transform(fill, new_fill), run_time=0.3)

            if i < len(segs) - 1:
                self.play(FadeOut(visual), run_time=0.4)

        self.wait(0.8)
