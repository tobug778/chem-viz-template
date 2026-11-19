"""主题与配置加载：全系列共用，换一期只改 config/*.yaml。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# manim.cfg: pixel 720x1280, frame_height=8 -> frame_width = 8 * 720/1280 = 4.5
FRAME_W = 4.5
FRAME_H = 8.0
SAFE_W = 4.05          # 左右安全边距内的可用宽度
TOP_Y = 3.45
BOTTOM_Y = -3.35

# Manim 的 Text.font 只接受单个字体名字符串（传列表会崩溃）。
# Noto Sans CJK SC 同时覆盖中文与 ⇌ ≠ ↑ ² 等化学符号，Actions 中已安装。
FONT_STACK = "Noto Sans CJK SC"


def load_config(name: str = "no2_equilibrium") -> dict:
    path = ROOT / "config" / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"找不到配置：{path}")
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if "segments" not in cfg or "style" not in cfg:
        raise ValueError("配置必须包含 style 与 segments 两个字段")
    return cfg


def style_of(cfg: dict) -> dict:
    return cfg["style"]
