#!/usr/bin/env python3
"""Check what the game actually played, without looking at the picture.

"换完归档、游戏能放了"不是结论，"放的是我换进去的那个文件"才是。这个脚本用
两个可计算的量把它变成数字：

  frame  把截图里影片区域裁出来，跟每部候选影片逐帧做归一化相关。
         相关度 0.9x 的那一部就是正在放的片子，别的都只有 0.4x 上下。
  audio  把两个音频解成 PCM 再互相关。能同时回答两件事：内容是不是同一段
         （相关度高）、有没有恒定偏移（最佳 lag）。换音轨的改动必须过这一关，
         画面动不代表声音对。

用法：
  match_media.py frame <screenshot.png> <movie> [<movie> ...]
  match_media.py audio <a.wmv> <b.wmv>

依赖：ffmpeg / ffprobe 在 PATH 里，python 装 numpy 和 Pillow。
截图按 2 倍 Retina 抓的（2560x1524 那种），脚本内部会先压到点坐标。
"""
import subprocess
import sys

import numpy as np
from PIL import Image

GW, GH = 160, 90          # 比对分辨率
WINDOW_W, WINDOW_H = 1280, 720   # 窗口内影片区域（点）
AUDIO_AR = 8000           # 音频比对用的采样率


def run(cmd):
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def movie_frames(path, step=1.0):
    """整片按 step 秒抽帧，返回 [(t, 小灰度帧)]"""
    dur = float(run(["ffprobe", "-v", "error", "-show_entries",
                     "format=duration", "-of", "csv=p=0", path]
                    ).decode().strip())
    raw = run(["ffmpeg", "-v", "error", "-i", path,
               "-vf", "fps=%f,scale=%d:%d,format=gray" % (1.0 / step, GW, GH),
               "-f", "rawvideo", "-"])
    frame = GW * GH
    n = min(int(dur / step), len(raw) // frame)
    return [((i + 0.5) * step,
             np.frombuffer(raw[i * frame:(i + 1) * frame], dtype=np.uint8
                           ).reshape(GH, GW).astype(np.float32))
            for i in range(n)]


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float((a * b).sum() / d) if d else 0.0


def crop(shot, y0, x0):
    im = Image.open(shot).convert("L")
    im = im.resize((im.width // 2, im.height // 2), Image.BILINEAR)  # Retina -> 点
    im = im.crop((x0, y0, x0 + WINDOW_W, y0 + WINDOW_H)).resize((GW, GH),
                                                                Image.BILINEAR)
    return np.asarray(im, dtype=np.float32)


def cmd_frame(shot, movies):
    frames = {m: movie_frames(m) for m in movies}
    best = None
    for y0 in range(20, 61, 4):          # 窗口装饰（标题栏、菜单栏）占多少，扫一下
        for x0 in range(-4, 5, 4):
            c = crop(shot, y0, x0)
            s = max(corr(c, f) for ms in frames.values() for _, f in ms[::17])
            if best is None or s > best[0]:
                best = (s, y0, x0, c)
    s, y0, x0, c = best
    print("crop y0=%d x0=%d (pre-score %.3f)" % (y0, x0, s))
    for m in movies:
        top = max(((corr(c, f), t) for t, f in frames[m]), key=lambda x: x[0])
        print("%-20s best corr %.3f at t=%.1fs"
              % (m.split("/")[-1], top[0], top[1]))


def pcm(path, ar=AUDIO_AR):
    return np.frombuffer(run(["ffmpeg", "-v", "error", "-i", path, "-vn",
                              "-ac", "1", "-ar", str(ar), "-f", "s16le", "-"]),
                         dtype="<i2").astype(np.float64)


def cmd_audio(pa, pb, max_shift=0.75):
    a, b = pcm(pa), pcm(pb)
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    lag, score = best_lag(a, b, int(max_shift * AUDIO_AR))
    win = AUDIO_AR // 10
    m = n // win * win
    env = lambda v: np.abs(v[:m]).reshape(-1, win).mean(1)
    ea, eb = env(a), env(b)
    ea, eb = ea - ea.mean(), eb - eb.mean()
    print("%d samples compared (%.1f s)" % (n, n / AUDIO_AR))
    for name, v in (("a", a), ("b", b)):
        print("  %s rms=%8.1f peak=%6d" % (name, np.sqrt((v ** 2).mean()),
                                           int(np.abs(v).max())))
    print("best corr %.3f at lag %+d samples (%+.1f ms)"
          % (score, lag, 1000.0 * lag / AUDIO_AR))
    print("envelope (100 ms) corr %.3f"
          % corr(ea, eb))


def best_lag(a, b, span, coarse=16):
    """最相关的时间偏移。先粗后细：整段直接扫 ±2M 个偏移太慢。"""
    def shift(x, y, d):
        n = len(x)
        return (x[:n - d], y[d:]) if d >= 0 else (x[-d:], y[:n + d])

    ca, cb = a[::coarse], b[::coarse]
    best = None
    for d in range(-span // coarse - 2, span // coarse + 3):
        s = corr(*shift(ca, cb, d))
        if best is None or abs(s) > abs(best[1]):
            best = (d * coarse, s)
    for d in range(max(best[0] - coarse, -span), min(best[0] + coarse, span) + 1):
        s = corr(*shift(a, b, d))
        if abs(s) > abs(best[1]):
            best = (d, s)
    return best


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    if sys.argv[1] == "frame":
        if len(sys.argv) < 4:
            raise SystemExit(__doc__)
        cmd_frame(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "audio":
        if len(sys.argv) != 4:
            raise SystemExit(__doc__)
        cmd_audio(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
