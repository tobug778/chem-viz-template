"""生成无版权轻音乐 BGM（纯合成，零外部素材）。

用 Python 标准库合成一段舒缓的循环音乐：
- 缓慢的和弦 pad（正弦叠加 + 淡入淡出）
- 轻琶音点缀
- 输出 44.1kHz 单声道 WAV，再由 ffmpeg 转 mp3

运行：
    python3 tools/make_bgm.py            # 生成 assets/bgm.wav
    ffmpeg -i assets/bgm.wav -codec:a libmp3lame -q:a 4 assets/bgm.mp3
"""
import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "bgm.wav"

SR = 44100
DURATION = 66.0          # 秒，略长于成片
FADE = 2.0               # 首尾淡入淡出（秒）

# 四个柔和和弦（根音频率 Hz），每个持续 8 秒，循环
CHORDS = [
    (220.00, 277.18, 329.63),   # Am
    (174.61, 220.00, 261.63),   # F
    (196.00, 246.94, 293.66),   # G
    (164.81, 207.65, 246.94),   # Em
]
CHORD_LEN = 8.0


def envelope(t, total, fade):
    """首尾淡入淡出，避免爆音。"""
    if t < fade:
        return t / fade
    if t > total - fade:
        return (total - t) / fade
    return 1.0


def pad_sample(t, chord_idx):
    """柔和和弦 pad：基频 + 轻微二次谐波，缓慢起伏。"""
    chord = CHORDS[chord_idx % len(CHORDS)]
    s = 0.0
    for f in chord:
        s += math.sin(2 * math.pi * f * t) * 0.6
        s += math.sin(2 * math.pi * (2 * f) * t) * 0.12
    # 缓慢的音量呼吸（0.7~1.0）
    s *= 0.85 + 0.15 * math.sin(2 * math.pi * 0.25 * t)
    return s / (len(chord) * 0.72)


def arp_sample(t, chord_idx):
    """轻琶音：每 0.5 秒一个音，短促衰减，音量很低。"""
    step = 0.5
    pos = t % step
    idx = int(t / step) % len(CHORDS[chord_idx % len(CHORDS)])
    f = CHORDS[chord_idx % len(CHORDS)][idx] * 2
    decay = math.exp(-pos * 6)
    return math.sin(2 * math.pi * f * t) * decay * 0.10


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = int(SR * DURATION)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for i in range(n):
            t = i / SR
            chord_idx = int(t / CHORD_LEN)
            val = (pad_sample(t, chord_idx) + arp_sample(t, chord_idx))
            val *= envelope(t, DURATION, FADE)
            pcm = int(max(-1.0, min(1.0, val)) * 12000)
            frames += struct.pack("<h", pcm)
        w.writeframes(bytes(frames))
    print(f"生成：{OUT} ({DURATION}s)")


if __name__ == "__main__":
    main()
