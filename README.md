# chem-viz-template

化学可视化科普短视频模板仓库。第一期复刻了参考视频的 NO₂ 平衡，六段式结构、竖屏 720×1280、**无任何水印**。

核心思路：**动画代码只写一次，每期只改一个 YAML 配置，GitHub Actions 云端渲染出片**。本机不需要装 Manim / Cairo / LaTeX。

## 目录结构

```
chem-viz-template/
├─ config/
│  └─ no2_equilibrium.yaml   ← 一期视频的全部文案/公式/参数（B 层）
├─ src/
│  ├─ theme.py               ← 配色、字体、竖屏坐标常量
│  └─ components.py          ← 可复用画面组件：粒子/曲线/柱状图/字幕/进度条（A 层）
├─ scenes/
│  └─ no2_equilibrium.py     ← 场景编排：按配置把六段拼起来
├─ .github/workflows/render.yml  ← 云端渲染 + 产物下载（C 层）
├─ manim.cfg                 ← 竖屏 720×1280
└─ requirements.txt
```

## 怎么用（云端，推荐）

1. 把本目录整体推到你的 GitHub 新仓库（main 分支）。
2. 打开 `Actions` 页 → 找到「渲染化学可视化视频」→ `Run workflow`。
3. 跑完后在本次运行页面底部 `Artifacts` 下载 `no2_equilibrium-mp4`，就是成片。

首次往 main 推送代码也会自动触发一次渲染。BGM 是可选的——把音乐文件命名为 `bgm.mp3` 放到 `assets/` 即可；不放就是静音视频。

## 做第二期

1. 复制 `config/no2_equilibrium.yaml` 为 `config/你的主题.yaml`，改 meta/style/segments 文字。
2. 复制 `scenes/no2_equilibrium.py` 为 `scenes/你的主题.py`，改类名与 `load_config("你的主题")`。
3. 如果六段式够用、**连场景文件都不用改**——直接改 YAML 里的 kind 与文案即可量产。
4. Actions 手动触发时填新的配置文件名和场景类名。

`segments[].kind` 决定画面类型，可选：

| kind | 画面 |
|---|---|
| `hook` | 悬念标题 + 注射器压缩示意 |
| `particle` | 分子粒子系统（自动演示压缩前后） |
| `equilibrium` | 正逆反应速率曲线收敛 |
| `bars` | 浓度三状态柱状图 |
| `lechatelier` | 勒夏特列原理大字 + 平衡常数 |
| `outro` | 选择题互动 + 评论区引导 |

要加新画面类型：在 `src/components.py` 写一个 builder 函数并加进 `BUILDERS` 字典，全系列即可复用。

## 本地渲染（可选，需自己装依赖）

本机若无 cairo/pango/brew 与足够磁盘，不建议本地渲染。若环境齐全：

```bash
pip install -r requirements.txt
manim -qh scenes/no2_equilibrium.py NO2Equilibrium
```

## 无水印说明

- 场景代码不添加任何作者名、账号名、角标、片尾署名。
- 配置中 `meta.watermark: false` 为全局开关，模板默认关闭；即使改为 true 也不会自动加作者信息，需显式在组件里实现。
- 参考视频右下角的账号水印没有被复刻，画面里不含任何水印。
