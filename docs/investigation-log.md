# 排查过程原始记录

按时间顺序记，包括走错的路 —— 那些弯路对后来人可能比结论更有用。

## 阶段 0：先确认"真的没在动"

点了 ED 之后整个窗口纯白。连续截两次图，两张 JPEG 都是 16330 字节、
字节级完全相同，进程 CPU ~0.1%。结论：不是解码慢，是整条链路停住了。

## 阶段 1：挖到 GStreamer 里的空指针

让封装器把 `WINEDEBUG` 打开、复现一次，然后在 `~/Library/Logs/DiagnosticReports/`
里翻到了崩溃报告：

```
faulting thread: asfdemux0:sink
EXC_BAD_ACCESS (SIGSEGV) at 0x0
gst_asf_demux_process_language_list → g_convert → open_converter → 0x0
```

顺着 `open_converter` 查下去，找到了 dyld 的顶替问题（README 第 1 节）。
关键证据是崩溃报告里那句
`Expected in: <UUID> .../Contents/Frameworks/libiconv.2.dylib` ——
那个 UUID 就是 app 自带 libiconv 的 UUID，而不是系统的。

同时做一个 0.2 秒的命令行复现器，把问题缩到一行：

```bash
# 干净环境：rc=0，加载 /usr/lib/libiconv.2.dylib
# 加上封装器的 DYLD_*：rc=-11，加载 app 自带的 libiconv
gst-launch-1.0 filesrc location=sample.wmv ! asfdemux ! fakesink
```

补上 shim 之后 `rc=-11 → rc=0`，GStreamer 管道活了。
**但画面依然是白的** —— 这一段只是不再崩，没解决"没人出画"。

## 阶段 2：在渲染段上耗掉的一堆尝试（都是弯路）

`lsof -p` 看到的媒体栈：

```
krmovie.dll（解包到 Temp，已加载）
  ├─ mf.dll / mfplat.dll / winegstreamer.dll   ← Wine 自带
  ├─ evr.dll                                   ← Wine 自带
  └─ quartz.dll                                ← prefix 里的原生 Windows 版
```

当时的判断是"数据进了 winegstreamer 的队列没人消费，卡在呈现段"，
于是依次试了：

| 尝试 | 结果 |
|---|---|
| `quartz=b` 全用 Wine 版，避免原生/Wine 混搭 | 无变化 |
| `WINEDEBUG=+quartz,+mfplat,+evr` 复现 | 日志巨大，只确认了样本确实推到了 sink |
| 往 prefix 里装 LAVFilters | 装了，但管线走的还是 winegstreamer，根本没被用上 |
| 另建一个 `wine 10.0` 的封装试 | 也没解决，最后删掉了 |
| 怀疑影片编码本身 | 用系统播放器放原片，正常 |

这段没有产出结论，唯一的收获是**排除**：问题不在解码器有没有装、
不在 quartz 是谁家的。

## 阶段 3：真正的开关在 krmovie.dll 里

回头看日志，发现一个之前被忽略的细节 —— 黑屏时**根本没有**下面这行：

```
video mode:layer
```

搜索 `krmovie.dll` 的字符串，看到它会在几种渲染模式里挑一种。
反汇编之后定位到文件偏移 `0x20B6` 的 12 个字节（见 README 第 2 节）：
一个"参数越界就跳走"的判断，跳走之后就再也不会选 layer 模式。

NOP 掉这 12 个字节 → 日志立刻出现 `video mode:layer` + `layerResizeMode, 1`。

**不过这时候画面还是黑的** —— 因为读归档又失败了（下一节）。

## 阶段 4：把自己写坏的归档救回来

在阶段 2 试过"重建 xp3"这条路，把 `video720.xp3` 写坏了：
游戏 `失敗。`，`lsof` 看不到它打开归档，CPU 掉到 2%；
日志里是 `Trying to read XP3 ... video720.xp3` → `失敗。`。

先确认了归档本身能被工具正常解析、索引链完整、条目密文也能解出合法 MP4 ——
说明坏的不是数据，而是"引擎不接受的布局"。

于是换成最小改动方案（`docs/xp3-format-notes.md`）：数据区不动，
内容追加到尾部，只改条目偏移和一个指针。改完第一次跑通：

```
Trying to read XP3 ... video720.xp3
Done. (contains 7 file(s), 7 segment(s))
```

## 阶段 5：视频出来了，声音是乱的

画面通了之后声音支离破碎。把条目正文解出来喂 `ffprobe`：

```
Stream #0:0: Audio: wmapro, 44100 Hz, stereo, 440 kb/s      ← 原版
Stream #0:1: Video: wmv3 (Main), yuv420p, 1280x720, 2178 kb/s
```

`wmapro` 在 Wine 的媒体栈里没有可靠的解码器。重封装成 `wmav2` 之后
（视频流 `-c:v copy` 不重编码，所以画质无损），声音正常。

顺带确认了 ED 的**视频流从头到尾没有被动过**：原版和修好版的 `wmv3`
码率、尺寸完全一致。

## 阶段 6：验证，不靠"看着像好了"

- 录 166 秒，ED 放完自动回菜单，CPU 全程稳定 35%（黑屏时 ~1%）。
- 游戏实录和原始 ED 音轨做互相关，`mean cos 0.939`，时间轴 1:1，
  无 46 ms 周期性碎裂。
- Esc 能跳过。
- 日志全程无 `exception occured`。

## 复盘

三个问题互相掩盖，所以每一次"修好一个"都还是黑屏，容易让人以为方向错了：

1. libiconv → 崩溃（修好它只让程序不崩了）；
2. krmovie 的 12 字节 → 永远不选 layer 模式（修好它才第一次出现
   `video mode:layer`）；
3. 音轨 `wmapro` → 有声无画/声音乱（和渲染无关，但会一起出现）。

如果重来一次，最省时间的顺序是：**先看日志里有没有 `video mode:layer`**，
再确认归档能不能被引擎打开，最后才去管音频。前面两个是对的，
后面的问题会自己浮出来。
