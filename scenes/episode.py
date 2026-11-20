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

from manim import (Scene, FadeIn, FadeOut, Transform, LaggedStart, UP, DOWN, linear,
                   GrowFromEdge, Rotate, Create)

from theme import load_config
from components import (
    BUILDERS, top_bar, progress_track, progress_fill, caption, caption_chars,
    particle_panel, equilibrium_anim, bars_anim_parts, chapter_transition,
    configure_rich, configure_motion, reveal,
    micro_process, micro_process_anim,
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
        elapsed = 0.0            # 全局已消耗时间（只给进度条用）
        fill = None              # 当前进度条填充对象
        seg_objects = []         # 本段临时对象，切段时全部清除

        # 转场开销：入场上字幕 + 字幕 + 进度 + 退场（秒）
        T_IN, T_X, T_FADE = 0.5, 0.25, 0.3

        for i, seg in enumerate(segs):
            kind = seg["kind"]
            dur = seg["dur"]
            seg_used = 0.0       # 本段已用时间（每段重置）
                                 # 关键修复：stay 必须减"本段已用"，不能用全局 elapsed，
                                 # 否则到后几段 stay 变负数被跳过 → 成片时长被腰斩。

            # ---- 0. 章节转场环（所有段通用，配置驱动）----
            # 每段可选配 transition：编号 01/02/03... 依次递增 + 中文标题 + 英文副标题。
            # 金环描边绘制 → 光点绕圈 → 中心文字淡入 → 停留 → 整页一闪淡出。
            if seg.get("transition"):
                tr = seg["transition"]
                page, ring, dots, center = chapter_transition(
                    cfg, seg, tr.get("number", "01"),
                    tr.get("title", ""), tr.get("en", ""))
                self.play(Create(ring), run_time=0.4)
                self.add(dots)
                self.play(FadeIn(center), run_time=0.25)
                tr_dur = float(tr.get("dur", 1.6))
                rot = min(0.7, tr_dur * 0.4)
                self.play(Rotate(dots, angle=2 * 3.14159265 * 0.75), run_time=rot)
                self.wait(max(0.15, tr_dur - 0.4 - 0.25 - rot))
                self.play(FadeOut(page), run_time=T_FADE)
                self.remove(page)
                seg_used += tr_dur + T_FADE
                elapsed += tr_dur + T_FADE

            # ---- 1. 画面主体（只做入场与"变化"动画，不在此处 wait）----
            # 关键节奏修复：字幕要紧跟画面立即出现，等待统一放到字幕之后，
            # 否则会出现"画面出来了，文字要等好几秒才冒出来"的拖沓感。
            pending = None
            if kind == "particle" and seg.get("micro"):
                # 微观过程（盐的水解）：球棍分子 + 夺 H⁺ 动态 + 高亮圈 + 结论。
                # 由 seg.micro 开关控制，其它主题 particle 段仍走下面的散点压缩，
                # 互不影响。动画步骤在字幕之后统一播放（见 2b）。
                visual = micro_process(cfg, seg)
                reveal(self, visual, run_time=T_IN)
                seg_objects.append(visual)
                seg_used += T_IN
                elapsed += T_IN
                pending = "micro"
            elif kind == "particle":
                visual = particle_panel(cfg, seg, compressed=False)
                reveal(self, visual, run_time=T_IN)
                seg_objects.append(visual)
                seg_used += T_IN
                elapsed += T_IN
                # 压缩变形放在字幕之后执行（见下方 particle 延后动作）
                pending = "particle"

            elif kind == "equilibrium" and seg.get("curve_anim", False):
                # 动态 v-t 曲线：骨架淡入 → 曲线随进度"长"出来 →
                # 末端光点 + v正/v逆 标签 + 阶段文字全程跟随。
                static, alpha, dynamic = equilibrium_anim(cfg, seg)
                reveal(self, static, run_time=T_IN)
                seg_objects.append(static)
                seg_used += T_IN
                elapsed += T_IN
                for o in dynamic:
                    self.add(o)
                    seg_objects.append(o)
                grow = float(seg.get("curve_grow", 5.0))
                self.play(alpha.animate.set_value(1.0), run_time=grow, rate_func=linear)
                seg_used += grow
                elapsed += grow

            elif kind == "bars" and seg.get("bar_anim", False):
                # 动态柱状图：骨架淡入 → 三阶段依次长出柱子，每阶段数值立刻跟随。
                static, stages, base_y = bars_anim_parts(cfg, seg)
                reveal(self, static, run_time=T_IN)
                seg_objects.append(static)
                seg_used += T_IN
                elapsed += T_IN
                bar_grow = float(seg.get("bar_grow", 0.9))
                for grp, bars, nums in stages:
                    # 阶段静态部分淡入（阶段标签 + 顶部色块），柱子先不显示
                    self.play(FadeIn(grp), run_time=0.25)
                    seg_objects.append(grp)
                    seg_used += 0.25
                    elapsed += 0.25
                    # 两根柱子从底部长出（GrowFromEdge 会把柱子加入场景）
                    self.play(*[GrowFromEdge(b, DOWN) for b in bars], run_time=bar_grow)
                    for b in bars:
                        seg_objects.append(b)
                    seg_used += bar_grow
                    elapsed += bar_grow
                    # 数值紧跟标注（不等，柱子长完立刻出）
                    self.play(LaggedStart(*[FadeIn(n) for n in nums],
                                          lag_ratio=0.3), run_time=0.3)
                    for n in nums:
                        self.add(n)
                        seg_objects.append(n)
                    seg_used += 0.3
                    elapsed += 0.3
            else:
                visual = BUILDERS[kind](cfg, seg)
                reveal(self, visual, run_time=T_IN)
                seg_objects.append(visual)
                seg_used += T_IN
                elapsed += T_IN

            # ---- 2. 字幕：紧跟画面立即出现（逐字浮现 / 整句淡入）----
            if seg.get("caption"):
                if _MOTION["enabled"]:
                    new_cap = caption_chars(cfg, seg["caption"])
                    reveal(self, new_cap, run_time=max(0.8, T_X * 3),
                           lag_ratio=0.06, shift=0.04)
                else:
                    new_cap = caption(cfg, seg["caption"])
                    self.play(FadeIn(new_cap), run_time=T_X)
                seg_objects.append(new_cap)
                seg_used += T_X
                elapsed += T_X

            # ---- 2b. particle 延后动作：字幕出现后再做压缩变形 ----
            if pending == "particle":
                hold = dur * 0.35
                w = max(0.2, hold - seg_used)
                self.wait(w)
                seg_used += w
                elapsed += w
                compressed = particle_panel(cfg, seg, compressed=True)
                self.play(Transform(visual, compressed), run_time=1.0)
                elapsed += 1.0
                seg_used += 1.0
                visual = compressed
                seg_objects.append(visual)

            # ---- 2b-2. micro 延后动作：字幕出现后再播放夺 H⁺ 动态过程 ----
            if pending == "micro":
                steps, created = micro_process_anim(cfg, seg, visual)
                for anims, rt in steps:
                    self.play(*anims, run_time=rt)
                    seg_used += rt
                    elapsed += rt
                seg_objects.extend(created)

            # ---- 2c. 统一停留：字幕/动画都就位后一起停留，补足本段时长 ----
            # 修复：这里用 seg_used（本段已用），不是全局 elapsed。
            stay = dur - seg_used - T_X - T_FADE
            if stay > 0.2:
                self.wait(stay)
                seg_used += stay
                elapsed += stay

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
