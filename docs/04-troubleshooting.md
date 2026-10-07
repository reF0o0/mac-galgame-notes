# 04 · 故障排查

## 先讲方法

调这类问题的最大浪费是**猜**。三个习惯能省掉大部分时间。

**一、先量，不要看。** 屏幕全黑？连续截两次同一个窗口，比对文件大小和哈希。
两张字节级完全相同，说明画面根本没在更新，不是"解码慢"。进程 CPU 也是硬指标：
黑屏时通常低于 1%，正常渲染大概 20% 到 40%。

```bash
./tools/mac/winlist | grep owner=wine
screencapture -x -l <win号> /tmp/a.png; sleep 3
screencapture -x -l <win号> /tmp/b.png
md5 /tmp/a.png /tmp/b.png          # 一样 = 真的没动
ps -o pcpu,command -p <游戏pid>
```

**二、用 A/B 排除，一次只动一个变量。** 「换了 X 就好了」这种结论不算数，
除非换回去能复现。换影片、换后端、换配置，都要各跑一遍对照。

**三、优先读游戏自己写的日志，再读 Wine 的。** 游戏引擎打的日志干净得多。
KiriKiri 系的日志一般在游戏目录的 `savedata/krkr.console.log`，是 UTF-16LE，
要转一下码才能直接看。

```bash
iconv -f UTF-16LE -t UTF-8 savedata/krkr.console.log | tail -40
```

---

## 文字全是方块

**症状**：标题菜单正常，但所有正文、角色名都是 `□□□`。用 `screencapture`
截下来看得更清楚 —— 标题是预制图片，不走字体，所以它正常恰恰说明"只有字体错了"。

**根因**：游戏（通常是汉化脚本）把正文字体指定成了「微软雅黑」。
Wine 瓶子里没有这个字体，引擎拿不到字形就画方块。

**先确认游戏到底在要哪个字体**：

```bash
source tools/mac/guest-env.sh 某容器
grep -i -A5 "Fonts" "$WINEPREFIX/user.reg"
```

游戏目录里搜一遍字面量也行（`grep -r "微软雅黑" .` 或搜 `Microsoft YaHei`）。

**修法**：在瓶子的字体替换表里加一条映射，不动游戏文件。

```bash
"$WINE" reg add "HKCU\\Software\\Wine\\Fonts\\Replacements" \
  /v "Microsoft YaHei" /t REG_SZ /d "Hiragino Sans GB" /f
"$WINE" reg add "HKCU\\Software\\Wine\\Fonts\\Replacements" \
  /v "微软雅黑" /t REG_SZ /d "Hiragino Sans GB" /f
```

顺便把这个字体文件也拷进瓶子的 `drive_c/windows/Fonts/`，确保字形库里有。
重启游戏后正文就正常了。

**踩过的坑**：有的整合包会附一个 `fontfix.pck` / `fontfix.rar`，看着像字体
修复补丁。实际上汉化启动器里**根本没有引用它** —— 反编译 exe 看它加载哪几个包
就知道（只加载 `script.pck` / `image.pck` / `scenario.pck` / `video.pck`）。
`lsof` 看运行中的进程也能证明它没打开过那个文件。放不放都一样，别在它上面
浪费时间。

---

## 影片黑屏 / 白屏（游戏本身正常）

**症状**：正片、立绘、BGM 都正常，只有过场动画是黑屏或白屏（有声或无声）。

这是 galgame 在 Wine 上最普遍的坑，而且**根因有好几种，必须分开定位**。

### 先分三档

| 现象 | 大概方向 |
|---|---|
| 影片窗口黑，CPU 极低，进程活着 | 链路卡住，看引擎日志有没有走到影片渲染分支 |
| **一启动就崩**，游戏根本进不去 | 引擎在协商失败后踩空，见下一节 |
| 有画但没声 / 有声但花屏 | 偏解码，换影片编码 |

### 手段一：换影片编码（成本最低，先试这个）

**核心思路：不跟解码器死磕，把影片换成引擎吃得下的编码。**

```bash
ffprobe 影片.wmv                       # 先看它到底是什么
ffmpeg -i 影片.wmv -c:v copy -c:a wmav2 -b:a 192k -ar 44100 -ac 2 修好.wmv
```

实测结论：

- **VC-1（WVC1）在 Wine 下基本必挂**，换成 WMV2 就好。
- **WMA Pro 音轨 Wine 解不了**，换成 `wmav2`。它会表现为"有声音但声音是乱的"。
- 视频流用 `-c:v copy` 原样保留，只换音轨，画质不掉。

### 手段二：看引擎日志里有没有走到影片渲染分支

以 KiriKiri 为例，正常播放时日志里会有这么几行；黑屏时它们**根本不出现**：

```
movieFileSelected, , ED3_Mura720, 1, ed3_mura
video mode:layer
layerResizeMode, 1
```

没有这几行，说明引擎压根没选影片渲染路径，在解码器上怎么折腾都没用 ——
问题在更前面。这一档的完整剖析见
[case-senren-banka-ed.md](case-senren-banka-ed.md)（根因是 `krmovie.dll` 里
12 个字节的越界判断）。

### 手段三：DirectShow 侧补齐（辅助，不是万能药）

```bash
"$APP/Contents/MacOS/Sikarugir WSS-winetricks" -q --no-isolate quartz
```

装完原生 `quartz.dll` 会替换掉 Wine 内置那个。**这一步要谨慎**：本机实测在
《灵感满溢的甜蜜创想》上，装完原生 quartz 之后游戏从"白屏挂着"变成了"崩溃"，
真正解决问题的还是换影片编码。所以顺序应该是：先换编码，再看要不要补 quartz。

同时可以把 LAV Filters 装进瓶子、把首选解码器指过去，但要有心理准备 ——
很多时候引擎根本不走你装的那条链。

### 已知的、修不掉的遗留

**影片能"播"（占满片长再继续剧情）但画面是白的。** 这是引擎把影片画进自己
渲染目标时的老毛病，和编码、和装什么解码器都无关。实际影响很小：点一下屏幕
就能跳过。嫌碍事可以直接把 `movie/` 目录清空，引擎会跳过影片，这条路也验证过
不会崩。

---

## 一进游戏就崩

**症状**：双击启动，游戏窗口闪一下或者干脆不出现，进程没了。崩溃地址看着像
野指针（例如 `0x0042006E` 这种），而不是"文件找不到"那种干净报错。

**根因**：引擎从 DirectShow 拿到失败的返回之后，**自己往非法地址写**。
换句话说，这不是"缺解码器"，是"引擎对失败结果没做处理"。

**定位手法**：

1. 看崩溃地址。野指针地址加上一启动就崩，强烈指向媒体链。
2. **A/B 排除**：把 `movie/` 里的影片临时换掉或改名，崩溃消失，就锁定是影片。
3. `ffprobe` 看那个影片的编码。本机的案例是 **VC-1（WVC1）**。

**修法**：把影片换成 WMV2（转码，或直接换成补丁包里那份现成的 WMV2 版本）。
同一套配置 A/B 各跑一遍确认后，崩溃消失。

---

## 启动后纯白，CPU 只有几个点

**先回答一个问题：它到底在等什么。**

```bash
source tools/mac/guest-env.sh 某容器
"$WINE" 'C:\Games\x\game.exe' > /tmp/g.log 2>&1 &
tail -f /tmp/g.log                 # 看它停在哪一行
```

常见的三种"卡"：

**一是卡在某段影片上。** 日志显示影片被打开着，相关线程挂着不动，它在等一段
永远播不完的影片。把该影片换掉（见上一节）就能过。

**二是卡在一个系统弹窗后面。** Wine 第一次跑某个程序时会弹授权框（麦克风、
摄像头、网络卷）。这个框**在游戏窗口后面**，看起来就是纯白卡死。点掉它就行。
也可以在 `Info.plist` 里关掉 `Symlinks In User Folder` 减少弹窗。

**三是 Electron 打包的游戏。** 见下面单独一节。

---

## Electron / Chromium 打包的游戏纯白

**怎么认出来**：目录里有 `chrome_100_percent.pak`、`icudtl.dat`、
`libEGL.dll`、`LICENSES.chromium.html`、`locales/`。
有些 galgame（例如 TyranoScript + Electron 的打包方式）是这么发的。

**根因**：Chromium 默认把 GPU 放在独立进程里，Wine 下这条跨进程通道传不过去，
渲染出来就是纯白。

**修法**：`Program Flags` 里加两个参数。

```bash
/usr/libexec/PlistBuddy -c "Set ':Program Flags' '--no-sandbox --in-process-gpu'" "$PLIST"
```

同时把后端换成 `DXVK=1`（这类引擎走 D3D11）。

---

## 插了耳机还是外放

**症状**：游戏开着的时候插耳机，声音还在扬声器；macOS 系统声音已经切到耳机了。

**根因**：Wine 的 CoreAudio 层是**在程序启动时**枚举输出设备、并把音频流绑到
当时的默认设备上的。之后插耳机，macOS 换了默认输出，但游戏那条已经打开的流还
挂在旧设备上。这跟游戏内设置无关，KiriKiri 的配置里只有音量，没有输出设备。

**证据**：翻 Wine 注册表里的音频设备记录，只有启动那一刻写入的那几个设备。

```bash
grep -A10 "winecoreaudio" "$WINEPREFIX/user.reg"
```

**修法**：**先插耳机（等它成为系统默认输出），再启动游戏。**
已经在玩的就存档、退出、重开，十秒钟的事。

两个次生的坑：

- 蓝牙耳机连上后会延迟几秒才成为默认设备。游戏已经开着的话注定还是走扬声器。
- 蓝牙耳机切到通话/HFP 模式会变采样率，Wine 下容易爆音。有条件优先用有线。

顺带：macOS 没有 Windows 11 那种"按应用指定输出设备"的原生功能。对 Wine
封装来说音频客户端就是那个 wrapper 进程，真想按应用分流得靠 SoundSource
或 Loopback 这类工具。

---

## 存档读不进去，无限弹错误框

**症状**：进游戏卡在 loading，不停弹错误框。换回自己的存档就正常。

**根因**：某些引擎（实测是 TyranoScript）对存档做**哈希校验**，别人分享的
存档跟当前这份游戏数据对不上，校验失败就一直弹。这不是存档损坏，是它本来就
不认外来存档。

**修法**：把外来的存档移走，从新游戏开始。

```bash
mkdir -p ~/Games/<游戏名>/.backup-original-saves
mv ~/Games/<游戏名>/*.sav ~/Games/<游戏名>/.backup-original-saves/
```

代价是分享者的进度和已解锁内容没了。这是必须接受的取舍，没有绕过哈希的正当做法。

---

## 改了 `.xp3` 但游戏没变化

**根因**：KiriKiri 在**启动时**就把归档打开并缓存了。游戏还开着的时候换文件，
它读的还是旧的那份。

**修法**：完全退出游戏再开。这一点非常容易误判，会让人以为"改了没用"，
然后去改别的地方。

---

## 崩溃日志在哪

| 类型 | 位置 |
|---|---|
| 游戏引擎自己打的日志 | 游戏目录里，常见于 `savedata/`（KiriKiri 是 `krkr.console.log`） |
| Wine 的 stderr | `容器.app/Contents/SharedSupport/Logs/`，或自己重定向 |
| macOS 层面的原生崩溃 | `~/Library/Logs/DiagnosticReports/`，看 `<程序名>-<日期>.ips` |

`.ips` 里最好用的是这三点：崩溃线程名、`EXC_BAD_ACCESS` 的地址、以及
"期望加载的库"和"实际加载的库"。本仓库最深的那个案例就是靠"崩溃报告里某个
`libiconv.2.dylib` 的 UUID 不是系统那个"定位到 dyld 顶替问题的。

---

## 别做的事

这几条都是实际浪费过时间的。

**不要"干净重建" `.xp3`。** 试过重新排布条目、重建索引，结果游戏直接报错、
根本打不开归档、CPU 掉到 2%。正确做法是**最小改动**：数据区一个字节不动，
新内容追加到文件尾部，只改那一个条目的偏移和大小。见
[kirikiri-xp3-format.md](kirikiri-xp3-format.md)。

**不要一上来就装一堆解码器。** LAV Filters 装进去，管线走的还是 Wine 自己的
`winegstreamer`，根本用不上。先确认问题在解码器还是别处。

**不要怀疑影片文件"坏了"。** 用系统播放器放一下就知道。本机所有"影片问题"
最终都落在这三条之一：编码引擎吃不下、引擎没选影片渲染路径、DirectShow 建图
失败 —— 没有一次是文件本身坏了。

**不要一次改两个变量。** 换了后端又换了注册表，出问题就无从下手。
