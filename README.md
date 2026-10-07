# 《千恋＊万花》ED 动画黑屏 —— Wine 下的排查与修复

在 macOS + Wine（CrossOver 内核的封装）里跑《千恋＊万花》，游戏正片一切正常，
但**ED 动画只有黑屏**（有声无画）。这个仓库是完整的排查过程、根因、改法和验证方法。

> **English TL;DR** — Running *Senren＊Banka* under Wine on macOS, the ending
> movie rendered black. Three independent problems were stacked on top of each
> other: (1) a dyld fallback loaded a `libiconv` that lacks the POSIX `iconv`
> symbols, crashing GStreamer inside Wine's ASF demuxer; (2) `krmovie.dll`
> rejects the movie in a 12-byte bounds check, so the engine never takes the
> `layer` rendering path; (3) the ED's audio track is WMA **Pro**, which Wine's
> media stack cannot decode. Fix all three and the movie plays. Tools and format
> notes are in `tools/` and `docs/`. No game assets are included.

## 症状

- 正片、立绘、BGM 全部正常，只有 ED 动画窗口纯黑，声音也不对。
- 进程 CPU 掉到 1% 以下；截图前后两张字节级相同，说明画面根本没在更新。
- 游戏日志（`savedata/krkr.console.log`，UTF-16LE）里能看到
  `Trying to read XP3 ... video720.xp3` → `失敗。` →
  `An exception occured at movie.tjs(1)[(function) open]`。

## 根因：三个问题叠在一起

### 1. dyld 顶替 libiconv，把 GStreamer 打崩

封装器的 `DYLD_LIBRARY_PATH` 把 app 自带的 `Contents/Frameworks` 排在最前。
GStreamer 的 `libglib-2.0.0.dylib` 的 load command 写的是
`/usr/lib/libiconv.2.dylib` —— 这个路径在磁盘上并不存在（只在 dyld 共享缓存里），
于是 dyld 按叶子名回退，命中 app 自带的那份 libiconv。那份是 gcenx 构建的，
**只导出 `_libiconv*`，没有 `_iconv / _iconv_open / _iconv_close`**。

结果 glib 的 `_iconv_open` 绑成 NULL，`g_convert` 直接跳 0x0 → SIGSEGV。
触发点是 ASF 头的 LANGUAGE_LIST：

```
gst_asf_demux_process_language_list → g_convert → open_converter → 0x0
```

在 Wine 里这个段错误的表现就是播放器卡死 + 白屏。

证据：`~/Library/Logs/DiagnosticReports/gst-launch-1.0-*.ips`，崩溃线程
`asfdemux0:sink`，`EXC_BAD_ACCESS at 0x0`。另外用 0.2 秒的命令行复现器可以稳定
二分：干净环境 `gst-launch-1.0 filesrc location=X.wmv ! asfdemux ! fakesink`
返回 0，加上封装器那套 `DYLD_*` 就返回 -11。

修法：给 app 的 `Contents/Frameworks/` 塞一个 shim `libiconv.2.dylib`，
自己导出 POSIX 的 `iconv / iconv_open / iconv_close`（转发到 GNU 实现），
同时 `-reexport_library` 原件，保留全部 `_libiconv*` 符号。改完之后复现器
`rc=-11 → rc=0`，GStreamer 管道活了。

**但画面还是黑的。** 这一段只是把"崩"变成了"不崩"，离出画还差两件事。

### 2. krmovie.dll 里的 12 字节，把影片挡在 layer 模式之外

`krmovie.dll`（`patch.xp3` 里的一个条目，796,160 字节）在
**文件偏移 `0x20B6`** 处有这么 12 个字节：

```
85 C0              test eax, eax
74 08              je   +8
3B C8              cmp  ecx, eax
0F 8D 92 00 00 00  jge  +0x92
```

参数一旦被判定越界就直接跳走，绕开绘制到 offscreen layer 的那条分支，
于是影片永远走"交给系统媒体栈"的路 —— 在 Wine 上那条路是死的。

把这 12 个字节全部填 `90`（NOP），程序不再跳走，影片进 `video mode:layer`。
这是本仓库里 `tools/krmovie_nop12.py` 做的事，它会自己在归档里找到这个 DLL、
定位签名、原地替换，并且**先把新内容用条目自己的 `aldr` 重新加密**再写回。

改完之后日志里第一次出现这两行：

```
movieFileSelected, , ED3_Mura720, 1, ed3_mura
video mode:layer
layerResizeMode, 1
```

### 3. ED 的音轨是 WMA Pro，Wine 解不了

原始 ED（`ED3_Mura720`，1280x720，`wmv3` 视频）的音轨是 **`wmapro`**
（44100 Hz，立体声，440 kbps）。Wine 的媒体栈对它无能为力 —— 这也是为什么
之前"有声音但声音是乱的"。

修法：把整条片子重封装一次，音轨换成 Wine 能解的 `wmav2`：

```bash
ffmpeg -i original.wmv -c:v copy -c:a wmav2 -b:a 192k -ar 44100 -ac 2 fixed.wmv
```

然后整条替换回 `video720.xp3` 的对应条目（`tools/xp3_replace.py`）。

| | 视频 | 音频 |
|---|---|---|
| 原版 | `wmv3` 1280x720 2178 kbps | `wmapro` 44100 立体声 440 kbps |
| 修好 | `wmv3` 1280x720 2178 kbps | `wmav2` 44100 立体声 192 kbps |

顺带一提，重封装会把音频流挪到视频流后面，流顺序和原版相反 —— 对播放没影响。

### 附带的一处配置

游戏存档目录的 `savedata/senrenbankachs.cfu` 里加了一条 `vomstyle="layer"`，
和上面的 krmovie 补丁配套。**这条没有单独做过 A/B 测试**，不确定是否必要，
但它是最终能跑的配置的一部分，这里如实记录。

## 最终验证

改完后逐项确认，不是"看着像好了"：

- **日志**从 `失敗。 / exception at movie.tjs open` 变成
  `video mode:layer → Done. (contains 7 file(s), 7 segment(s))`，全程无异常。
- **画面**：录制 166 秒，ED 从头放到尾自动回菜单；进程 CPU 稳定在 ~35%
  （黑屏时是 ~1%）。
- **音频**：把游戏实录和原始 ED 音轨做相关比对，`mean cos 0.939`，
  时间轴 1:1，没有周期性碎裂。
- **跳过**：按 Esc 能正常跳过。

## 踩过的坑

- **改完必须完全退出游戏再开。** KiriKiri 启动时就把 `.xp3` 打开并缓存，
  停在游戏里换文件是看不到变化的 —— 这会让人以为"改了没用"。我们因此白跑了
  两轮。
- **不要试图"干净重建" `.xp3`。** 试过重新排布条目、重建索引，
  结果游戏直接 `失敗。`、`lsof` 里根本看不到它打开归档、CPU 掉到 2%。
  正确做法是**最小改动**：数据区一个字节不动，新内容追加到文件尾部，
  只改那一个条目的偏移/大小，再把索引块重写一份、重指一个指针
  （`tools/xp3_replace.py` 就是这么做的）。
- **索引指针在 `0x0b`，不是 `0x20`。** 归档头之后是 `u64` 指针链，
  每个索引块的编码方式在 flag 的低 3 位，`0x80` 表示后面还跟着下一块的指针。
  详见 `docs/xp3-format-notes.md`。
- **条目内容是 zlib 压缩 + CX 加密两层**，直接改字节不会生效；
  而且 CX 的密钥流是**位置相关**的，必须用条目自己的 `aldr` 走一遍才行。

## 仓库内容

```
tools/xp3tool.py        XP3 读取（索引链、条目、解压）
tools/cxdec.py          CX 加密/解密（密钥表从游戏自带的 xp3filter.tjs 读）
tools/xp3_replace.py    最小改动替换一个条目（自动回写加密）
tools/krmovie_nop12.py  本文第 2 节那个 12 字节补丁，一键完成
tools/verify.py         回读校验：解密每个条目并打印 md5 / 类型
docs/xp3-format-notes.md  XP3 / CX 格式与本项目用到的写入策略
docs/investigation-log.md 排查过程原始记录（含 libiconv 那段）
```

典型用法（全部在你自己那份归档上操作，建议先用副本）：

```bash
export FILTER=~/Games/千恋＊万花/补丁/解密补丁/xp3filter.tjs

python3 tools/verify.py game/patch.xp3 --filter "$FILTER" | head
python3 tools/krmovie_nop12.py game/patch.xp3 --filter "$FILTER" --backup
python3 tools/verify.py game/patch.xp3 --filter "$FILTER" --entry 137
```

校验期望值（本机 1.0.15 版封装、日文原版 + 汉化补丁）：

| 对象 | md5 |
|---|---|
| 打补丁前的 `krmovie.dll` | `8786829478b842058145d06d02e95e68` |
| 打补丁后（也就是能跑的那份） | `13361afe2826bede41d7bcab61e0ba5a` |

`tools/krmovie_nop12.py` 在一份干净的 `patch.xp3` 上跑完，得到的正是
`13361afe...` 这一份 —— 也就是说仓库里的脚本能完整复现出这台机器上跑通的改动。

## 环境

macOS 26.7.1 / Apple M5，封装器内核 `WineCX 24.0.7`（CrossOver 系）。
不同引擎版本、不同封装器（Whisky / Wineskin / Porting Kit 等）细节会有出入，
但第 2 节的 12 字节签名和第 3 节的音轨问题和引擎版本无关，通常可以直接套用。

## 免责声明

本仓库只包含分析笔记和工具，**不含任何游戏资源**（DLL、影片、脚本、密钥表都没有）。
所有改动都作用于你自己合法持有的那份游戏副本，目的是让它在非 Windows 平台上能正常
播放。`cxdec.py` 复现的是引擎自身的归档读取过程，用来做兼容性修复和存档保护。
