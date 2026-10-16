# 05 · 实测记录：7 部作品

同一台机器（Apple M5 / macOS 26.7.1）上陆续装完、至少进到标题画面的作品。
配置各不相同，**不要照抄**——这张表的价值在于说明"为什么没有一份通用配置"。

**验证到什么程度**：千恋＊万花 和 ATRI 是逐段玩过、影片段落都实机验证过的；
其余 5 部只做到"能启动、能进到标题"，影片段落只做了编码层面的核查，没实机
过场。每节末尾都写了这句结论属于哪一种。2026-10-16 做过一次复核，改掉的
几处在下文的「复核」段里说明。

## 一览

| 作品 | 引擎 | 容器引擎 | D9VK | DXVK | MOLTENVKCX | Program Flags | 本体 |
|---|---|---|---|---|---|---|---|
| 千恋＊万花 | KiriKiri Z | WineCX 24.0.7 | 0 | 0 | 1 | 空 | 12 GB |
| ATRI -My Dear Moments- | KiriKiri Z | wine-10.0 | 0 | 0 | 1 | 空 | 3.9 GB |
| アマカノ3 | Artemis Engine（x64，`.pfs` + E-mote） | wine-10.0 | **1** | 0 | 0 | 空 | 11 GB |
| 不败世界与终焉之花 | KiriKiri Z | wine-10.0 | **1** | 0 | 0 | 空 | 4.4 GB |
| 灵感满溢的甜蜜创想 | Artemis Engine（`.pfs`） | wine-10.0 | **1** | 0 | 0 | 空 | 7.8 GB |
| 可塑性记忆 | M2 引擎（PSB + Squirrel 脚本） | wine-10.0 | **1** | 0 | 1 | 空 | 1.5 GB |
| 与奴隶的生活 | Electron + TyranoScript | wine-10.0 | 0 | **1** | 1 | `--no-sandbox --in-process-gpu` | 2.8 GB |

规律：**老的 KiriKiri Z 2D 作品用默认的 OpenGL/CNC 路径就行；凡是画面不对的，
把 D9VK 打开基本都能救回来；Electron 打包的必须 DXVK 加那两个参数。**

---

## 千恋＊万花

- **引擎**：KiriKiri Z（柚子社魔改）。证据：资源是标准 `.xp3` 加 `.sig` 签名，
  主程序里有 `tTVP*` / `TVPWindowForm` / `TVPSystemSecurityOptions` 符号，
  `plugin/` 里是柚子社定制插件（`yuzuex.dll`、`k2compat.dll`、`PackinOne.dll`）。
- **容器**：WineCX 24.0.7（= Wine 9.0）。这一台机器上唯一的 Wine 9 容器，
  后面的游戏都在 wine-10.0 上。
- **配置**：`MOLTENVKCX=1`，其余后端全 0，`CNC_DDRAW=1`，`LANG/LC_ALL=ja_JP.UTF-8`。

### 坑一：中文全是方块

汉化脚本把正文字体写死成「微软雅黑」。修法是在瓶子里做字体替换
（`Microsoft YaHei` / `微软雅黑` → `Hiragino Sans GB`），不动游戏文件。
详见 [04-troubleshooting.md](04-troubleshooting.md)。

顺带排掉一个误导项：整合包里的 `fontfix.pck` 是**无效**的，汉化启动器压根没有
引用它，`lsof` 也证明运行中的进程没打开过它。

### 坑二：插耳机还是外放

见 [04-troubleshooting.md](04-troubleshooting.md#插了耳机还是外放)。
结论是"先插耳机再启动游戏"。证据在瓶子注册表 `winecoreaudio.drv\devices`
下只有启动那一刻写入的内建扬声器。

### 坑三：ED 动画黑屏（本仓库的起源）

三层问题叠在一起，任何一层没解决都看不到画面：

1. dyld 顶替 `libiconv`，把 Wine 里的 GStreamer 打崩（ASF 解复用器空指针）。
2. `krmovie.dll` 里 12 个字节的越界判断，让引擎永远不选 `layer` 渲染模式。
3. ED 的音轨是 Wine 解不了的 **WMA Pro**。

完整过程、工具和校验值见 [case-senren-banka-ed.md](case-senren-banka-ed.md)。

### 额外：去码补丁

装法不是打包成 `patch2.xp3`，而是把 KirikiriTools 的 `version.dll` 放进游戏根目录、
再放一个 `unencrypted/` 目录（里面是同名 `.pimg`，会顶替加密 xp3 里的原图）。

两个要点：

- **必须**在 Wine 注册表里加 `version = native,builtin`。Wine 默认优先加载自己
  内置的 `version.dll`，无视游戏目录里那份，不加这条完全不生效。
- 验证靠 **atime**：启动前后对比补丁图目录里文件的访问时间，能证明游戏真的读了
  那几张图。比"肉眼看马赛克没了"更硬。

---

## ATRI -My Dear Moments-

- **引擎**：KiriKiri Z，主程序是 32 位 PE（`PE32 (i386)`）。
- **容器**：wine-10.0，和 千恋＊万花 同族引擎，直接就能跑。
- **配置**：`MOLTENVKCX=1`，后端全 0。

### 注意点

**首次启动会问语言。** 弹一个「Language Display / 表示言語」对话框，
UI / Main Text / Sub Text 三栏都选简体中文再确定。以后想改，窗口菜单栏里有
`Language`。

### 一个被纠正过的误判

起初判定它的播片链"Media Foundation 残了"，后来证明是错的：它的
`plugin/krmovie.dll` 只依赖 `KERNEL32 / QUARTZ / USER32 / WINMM / ole32`，
走的是 DirectShow，整条链里**没有 Media Foundation**。
那几行 `fixme:mfplat:` 是从别的游戏的日志里串过来的。

顺带一个仓库：[Alcaro/krkrwine](https://github.com/Alcaro/krkrwine) 确实是干
这件事的（把 DirectShow 的 FilterGraph 指向自己的实现），但它自己的说明写着
「(Those bugs are fixed upstream in Wine 9.0)」，发布的也只有 Linux 的 `.so`，
macOS 被官方标为 not recommended。**结论是不用装。**

### 片尾影片卡死（已修）

结局那段影片（`vol1.xp3` 条目 206，4:22）一播就黑屏卡住，CPU 掉到 2%，
连续截图逐字节相同。原因是这段的音轨是 **WMA Pro**，Wine 的 libav
（`avdec_wmapro`）解不了；同目录另外四部影片（1:38 的 OP 一类）音轨是 `wmav2`，
所以只有这一段落网。

修法：只重封装音轨（`-c:v copy -c:a wmav2 -b:a 192k`），按条目自己的
keystream 重新加密，`xp3_replace.py` 追加式替换。完整过程（含这份归档
没有 `xp3filter.tjs`、密钥只能量不能算）见
[case-atri-ed.md](case-atri-ed.md)。

顺带一条经验：这部作品的片子条目名是哈希，认不出片名，**时长是最好用的指纹**。

---

## アマカノ3

- **引擎**：**Artemis Engine**（`.pfs` 是它的包格式，文件头 `pf8`），脚本层
  是 Lua（luabind 绑定），这一部是 **x64** 版（`Artemis Engine Rev.3258`），
  配 E-mote 动态立绘，只用 D3D11。跟 KiriKiri 是两条完全不同的路。
  与《灵感满溢的甜蜜创想》是**同一个引擎**，一个 D3D11 一个 D3D9。
- **容器**：wine-10.0，**必须新引擎**——Wine 9 那个容器跑不起来。
- **配置**：`D9VK=1`，`MOLTENVKCX=0`。

这是本仓库里唯一需要"另建一个更新引擎的容器"的作品，也是 D9VK 的第一次登场。

**踩坑记录**：装之前要先确认它到底走哪条媒体链。这台机器上出现过
「`fixme:mfplat:topology_loader_Load ... stub!` 被当成别的游戏的日志」这种
串台，因为不同游戏的日志混在同一个目录里。**查日志前先确认你查的是哪个文件**。

### 复核（2026-10-16）：`D9VK=1` 这条是误归因

`Amakano3.exe` 的导入表里只有 `d3d11.dll`（外加 `MFPlat`、`D3DCOMPILER_47`），
**没有 d3d9**。而 Sikarugir 的开关是分开的：`D9VK` 只往
`windows/system32/d3d9.dll` 放 DXVK 的 D3D9 实现，`DXVK` 才管
`d3d10core/d3d11/dxgi`（两包都在 `Contents/Frameworks/renderer/` 下，
版本 `DXVK-Sikarugir-async-v1.10.3`）。

容器自己的 `LastRunWine.log` 是决定性的：

```
Loaded L"C:\windows\system32\d3d11.dll" ... : builtin
Loaded L"C:\windows\system32\d3d9.dll"  ... : builtin
```

两条都是 `builtin` —— 也就是说这次跑的时候，DXVK/D9VK 的 DLL **一个都没被
加载**，D3D11 走的是 Wine 自己的 wined3d（日志里有 `wined3d/context_gl.c`）。
system32 里确实躺着一份 4.2 MB 的 DXVK `d3d11.dll`，但 Wine 默认优先内置，
它没被用上。

结论：这游戏能跑，靠的是 **wine-10.0 的 wined3d 能建 D3D11 设备**，
跟 `D9VK=1` 没关系（它根本不碰 D3D9）。笔记里"必须 D9VK"这句要改成
"换到 wine-10.0"。想真让 D3D11 走 Vulkan，该开的是 `DXVK=1`。
**没实测过**关掉 `D9VK` 会不会有别的副作用，所以先别急着动 Info.plist。

### 影片：五个都能解（复核已验证）

`movie/` 下 5 个 wmv，1920x1080。用容器自带的 GStreamer 逐个跑
`filesrc ! decodebin ! fakesink`，**全部 `rc=0`**：

| 文件 | 音轨 | 时长 | 解码 |
|---|---|---|---|
| `lx2ymbutf.wmv` | wmalossless | 6.0 s | 正常 |
| `ot4x86fie.wmv` | wmalossless | 94.3 s | 正常 |
| `ov8npfuty.wmv` | wmalossless | 9.9 s | 正常 |
| `op_chs.wmv` | wmav2 | 94.7 s | 正常 |
| `yukata_op_chs.wmv` | wmav2 | 10.4 s | 正常 |

这里容易虚惊一场：ATRI 出问题的是 `wmapro`，这三个是 `wmalossless`，
名字像但不是同一回事。同一套标定里 ATRI 的 `wmapro` 原片是 `rc=1`
（`avdec_wmapro: Could not decode stream`）、`wmav2` 是 `rc=0`，所以
这个测试确实能分出好坏 —— `wmalossless` 属于能解的那一类，**不用改**。
（`op_chs` / `yukata_op_chs` 是汉化补丁换过的版本，本来就是 `wmav2`。）

**这一节的影片结论只到"编码能解"这一步，没有实机放过一次 OP。**

---

## 不败世界与终焉之花

- **引擎**：KiriKiri Z（`KarenaiSekai.exe`）。
- **容器**：wine-10.0。**配置**：`D9VK=1`。

### 影片：OP / ED 都在独立的 `video.xp3` 里（复核新增）

这部有一个单独的 `video.xp3`（453 MB），**只有 2 个条目**，名字都认得出：

| 条目 | 大小 | 编码 |
|---|---|---|
| `OP.wmv` | 233 MB | wmv3 1280x720 + **wmav2** |
| `ED.wmv` | 221 MB | wmv3 1280x720 + **wmav2** |

`xp3tool.py dump` 出来就是合法 ASF，不用解密；两个都喂容器 GStreamer 解码，
`rc=0`。**音轨是 `wmav2`，不是 ATRI 那种 `wmapro`**，所以不吃"Wine 解不了
WMA Pro"那个坑。

顺便澄清一个容易照抄错的点：`krmovie.dll` 那 12 字节的补丁（千恋的 ED 黑屏根因）
**不适用于这部**。三部 KiriKiri 作品磁盘上的 `plugin/krmovie.dll` 是同一个文件
（sha256 前 16 位都是 `4140c86f6e4e1a1e`，278528 字节），里面**没有**那个
12 字节模式 `85 C0 74 08 3B C8 0F 8D 92 00 00 00` —— 出现这个模式的是千恋
`patch.xp3` 里的**另一份新版** DLL。ATRI / 不败世界 加载的是磁盘上这份，
所以不需要打补丁。要确认，看日志里有没有 `video mode:layer` 就够了。

**同样只到"编码能解"，没有实机放过 OP。**

### 坑：汉化重打包带来的文件名编码错误

汉化组重打包的时候把一批内部文件名写成了 **GBK**，而 KiriKiri 是按 **Shift-JIS**
解析这些名字的，于是找不到资源。修法是批量把 `data.xp3` 里的文件名从 GBK 转成
Shift-JIS。

**改之前一定要留原档**：改过的 `data.xp3` 之外放一份 `data.xp3.pristine`。
以后如果再遇到"同一个包"，先拿大小和 `.pristine` 对一遍 —— 对得上说明是重复包，
**重装反而会退回有 bug 的原档**。

---

## 灵感满溢的甜蜜创想

- **引擎**：**Artemis Engine**，不是 KiriKiri（复核更正，见下）。
  **容器**：wine-10.0。Info.plist 里写着 `D9VK=1` / `CNC_DDRAW=1`，但
  **两个都没生效**，实际跑的是 Wine 内置的 `d3d9`（见坑四）。prefix 里装了
  原生 `quartz`（winetricks 的 `wsh57` + `quartz`）和 LAV Filters 0.74.1
  （x86 + x64 都注册了）。

### 复核（2026-10-16）：它是 Artemis Engine，不是 KiriKiri Z

原记录写的是"KiriKiri Z"，但 `hamidashi_chs.exe` 里连 `TVP` 这三个字母都
**一次都没出现**（`tTVP`、`TVPWindowForm`、`KiriKiri`、`krkr` 全是 0），却有：

```
**** Artemis Engine Rev.2762 ****
C:\Users\mikage\...\Projects\Win32\Artemis\Release\Artemis.pdb
Copyright (C)2009 Daiju Hanaoka (Mikage) All rights reserved.
tJS3 / luabind / package.loaders      ← Lua 脚本层
```

资源也是 Artemis 的 `.pfs` 包（文件头 `pf8`），根目录里是
`hamidashi.pfs` 加一堆分卷，汉化补丁用 `hamidashi_chs.pfs.099`
（注意那一份的文件头是 `pf6`）。**和《アマカノ3》是同一个引擎**，
只不过这一部是 32 位 + D3D9 的老构建。

这条改动的意义：**krmovie 那套排查思路对它完全不适用**（没有 krmovie.dll，
也没有 `video mode:layer` 这行日志）。前面"坑一/坑二"里"按电影链路查"的
结论仍然成立——那是 A/B 出来的——但不要再往 KiriKiri 的方向找。

### 坑一：影片被改名成 `.dat`，游戏直接崩

网盘转存把 `movie/logo.wmv`、`movie/omt2rs7.wmv` 改名成了 `.dat`。
游戏按原名找不到文件就崩。

**修法**：`cp` 一份回来，保留 `.dat`。别只改名，两个都留着最稳。

```bash
cd ~/Games/<游戏名>/movie
cp logo.dat logo.wmv
cp omt2rs7.dat omt2rs7.wmv
```

### 坑二：片头是 VC-1，启动即崩

`logo.wmv` 是 **VC-1（WVC1）**。Wine 下 DirectShow 协商它必失败，引擎拿到失败
返回后往非法地址写，直接踩空。**A/B 验证**：换掉影片就不崩，换回来就崩。

**修法**：`logo.wmv` 转成 WMV2（166 KB 变 612 KB，内容一样）；`omt2rs7.wmv`
直接用补丁包里现成的 WMV2 版本，比转码干净。

### 坑三：容器根本起不来 —— `users/` 里一条悬空的软链接

**症状**：双击容器报错退出，什么都起不来：

```
ERROR: The file "crossover" couldn't be saved in the folder "users"
because a file with the same name already exists.
```

**根因**：`prefix/drive_c/users/` 下有一条**悬空**的软链接
`crossover -> Sikarugir`，而它指向的 `Sikarugir/` 目录根本不存在
（建瓶那一刻链接建出来了、目录没建）。启动时包装器要再建这条链接，
一看名字被占就整个失败。

**验证**：

```bash
U="$APP/Contents/SharedSupport/prefix/drive_c/users"
ls -la "$U"            # crossover 是软链接，readlink 出来是 Sikarugir
ls -d "$U/Sikarugir"   # No such file or directory → 悬空
```

对照一个正常的瓶子（千恋）`users/` 里应该是：一个真目录 `Sikarugir/`，
外加 `crossover -> Sikarugir` 和 `fanre -> Sikarugir` 两条链接。

**修法**：把这条坏链接**挪走**（挪，别删，留着好对账），下次启动就正常了。

```bash
mv "$U/crossover" /tmp/crossover.symlink.bak
```

挪走之后冷启动一次，实测能一路跑到标题画面（2026-10-16），
START / CONTINUE / LOAD / CONFIG / SPECIAL / EXIT 都在。
瓶子里的 `fanre/` 是游戏自己建/用的，**别手动动**。

### 坑四：`D9VK` / `CNC_DDRAW` 这两个开关改了等于没改

**症状**：Info.plist 写着 `D9VK=1`、`CNC_DDRAW=1`，但游戏实际用的还是
Wine 自带的 `d3d9`（走 wined3d/OpenGL），**没有**走 Vulkan。
所以"把 `D9VK` 关掉看 OP 会不会出画"这类实验，在这台容器上做不出任何区别。

**怎么看出来**（四条，互相独立）：

```bash
APP="$HOME/Applications/Sikarugir/灵感满溢的甜蜜创想.app"

# 1) 启动环境里只有 WINEDLLPATH_*，没有 WINEDLLOVERRIDES
ps eww -p $(pgrep -f "灵感满溢.*wineserver" | head -1) | tr ' ' '\n' | grep WINEDLL

# 2) 注册表里没有 d3d9 / ddraw 的 override，而且这一节从 10-06 起没再被写过
sed -n '/DllOverrides/,/^\[/p' "$APP/Contents/SharedSupport/prefix/user.reg"

# 3) 瓶子里那份 d3d9.dll 是 Wine 自带的大小
ls -l "$APP/Contents/SharedSupport/prefix/drive_c/windows/syswow64/d3d9.dll"
# 200704 B ← Wine 自带的；d9vk 那两份是 4160911 / 3948351 B，没被拷进来

# 4) 10-06 那次带 +loaddll 的日志里也是 builtin
grep -a "d3d9.dll" "$APP/Contents/Logs/LastRunWine.log"
# Loaded L"C:\windows\system32\d3d9.dll" at 7A590000: builtin
```

第 2 条那次查到的时间戳是 **2026-10-06 17:18**（也就是装 winetricks 那次），
今天（10-16）两次启动容器都没往那一节里添东西。作为对照，千恋的瓶子里
反而明确写了 `"d3d9"="builtin"`。

**结论**：开关只让包装器导出一个 `WINEDLLPATH_D9VK` 之类的环境变量，
**没有**往瓶子里写 dll override，Wine 于是照旧加载内置的 `d3d9` / `ddraw`。
`CNC_DDRAW=1` 同理：日志里那句 `fixme:ddraw:ddraw7_Initialize` 就是 Wine
内置 ddraw 打的，真的加载了 cnc-ddraw 不会有这行。

**没搞清的地方**：这些开关是不是只在**建容器那一刻**才写进瓶子 ——
证据是 `DXVK=0` 的几个 Sep-23 瓶子里照样躺着一份 4.2 MB 的 DXVK
`d3d11.dll`。想让 `D9VK` 真跑起来，要么手工补 override，要么重建一个容器，
**这两条都没试过**。

### 遗留

影片能"播"（占满片长再继续剧情），但**画面在 Wine 下画不出来**，那几秒是白屏，
点一下可以跳过。用纯红影片做过标记测试，确认是真没渲染，不是截图问题。

复核时补的两条事实：

- `movie/` 里只剩两个片子，都已换成 **WMV2**：`logo.wmv`（5.07 s，612 KB，
  只换了视频流）和 `omt2rs7.wmv`（89.7 s，180.9 MB，wmv2 + **wmav2**）。
  原版 VC-1 备份在 `movie_原版VC1备份/`（那份是 192 MB 的 VC-1）。
  两个都喂容器 GStreamer 解码，`rc=0` —— **编码这一步是通的，问题不在解码**。
- 所以"能播但没画面"更像是**渲染层**的问题：Artemis 把解出来的帧贴到 D3D9
  纹理上，这条路在 Wine 下没走通（类似千恋那个"没有 `video mode:layer`
  就没有人出画"的形状，但成因不同）。

原来打算先试的"关掉 `D9VK`、退回 wined3d 再放一次 OP"**作废**：这台容器上
`D9VK` 根本没生效，`d3d9` 一直是 Wine 内置的 wined3d（坑四），关它等于什么都没改。
剩下值得试的是 `D3DMETAL=1`。**改 Info.plist 前先关掉游戏。**

2026-10-16 的实机复核只走到**标题画面 + 开头几分钟剧情**（点 START → 一段黑屏
过场 → 卧室对话），**没有触发 OP**。所以"白屏"这条还是玩家原来的记录，
既没被复现、也没被推翻；要取证得真的点到影片那一段再截图。

---

## 可塑性记忆

- **引擎**：**M2 引擎**（PSB 资源 + Squirrel/Sqrat 脚本），**不是 KiriKiri**
  （复核更正，见下）。
- **容器**：wine-10.0。**配置**：`D9VK=1`（**必需**），`MOLTENVKCX=1`。

**典型症状**：默认的 OpenGL 后端只出蓝屏或黑屏。开 D9VK 之后就正常了。

这是"能启动但画面纯色 → 换后端"这条经验最干净的一个例子。排查时先确认进程
活着、CPU 有占用（说明不是卡在等什么），然后一个后端一个后端换。

### 复核（2026-10-16）：引擎是 M2，影片编解码本身没问题

原记录写的是"KiriKiri 系"，实际不是：

- `Plastic Memories.exe`（32 位 PE）里 **0 个 KiriKiri 符号**，也没有
  `tTVP` / `TVPWindowForm`；命中的是 `PSBObject`、`Sqrat`（Squirrel 的 C++
  绑定）。日志里能看到真的在调 `d3d9:Direct3DCreate9`。
- 资源形态也对得上：`windata/` 下是一组 `*_body.bin` + `*_info.psb.m`
  成对的文件（`image_`、`script_`、`sound_`、`movie` …），这是 M2/PSB 那套。

**影片（只做了编码核查）**：`windata/movie/` 下 20 个 **MP4**，清一色
**H.264 960x544 + AAC**（`op.mp4` 97.5 s、`PM_MV001..012`、`PM_bootMV` 14 s、
`pm_LAST0..5` 各 5 s、`END01..03` 190–309 s）。抽几个喂容器 GStreamer，
`rc=0` —— 编码是 Wine 能解的种类，**不需要转码**。

**但这里有个没验的环节**：这部的手册（`游戏启动操作说明必看！！.txt`）写着
"游戏启动前请先安装 K-Lite 播放器不然无法正常启动游戏"。也就是说它的播片
依赖 Windows 的 DirectShow 滤镜链，像 `PM_bootMV` 这种**开机就播**的片子
如果解不出来，可能连标题都进不去。Wine 侧的 `quartz` 是内置版、能不能拉起
这条链**没有实测过**。

顺带记两笔现状，都不在原来的笔记里：

- 这个 prefix 里已经装过一份 **LAVFilters 0.74.1**（winetricks 装的，
  `C:\Program Files (x86)\LAV Filters\`，x86 + x64，40 MB），
  安装日志在 `drive_c/lav_pm.log`。千恋的 prefix 里也有同一份。
  它到底有没有被游戏用上，日志里看不到痕迹，**先按"装了不一定生效"算**。
- 游戏目录里那份 `K-Lite_Codec_Pack_1612_Standard/` 是 Windows 安装包
  （32 MB），**不要**往 Wine 里装：它装的是 Windows 版 DirectShow 滤镜，
  和 LAV 一样未必被 Wine 的 quartz 采用，但会在 prefix 里解出几百 MB，
  还得靠容器快照才能干净回滚。

**这一节的结论只到"能进游戏、编码可解"，没有实机看过一部影片。**

---

## 与奴隶的生活（Teaching Feeling V4.0.6）

- **引擎**：**不是** KiriKiri。目录里有 `chrome_100_percent.pak`、`icudtl.dat`、
  `libEGL.dll`、`LICENSES.chromium.html`、`locales/` —— 这是
  **Electron 打包的 TyranoScript**。
- **容器**：wine-10.0。**配置**：`DXVK=1` + `MOLTENVKCX=1`，
  `Program Flags = --no-sandbox --in-process-gpu`。

**复核**：引擎判断是对的 —— `TeachingFeeling.exe` 里同样 **0 个 KiriKiri 符号**，
但有一堆 Chromium 的字符串；`resources/app/` 下是 `tyrano/`（TyranoScript）
加 `package.json` 和几个 node 模块。

**影片**：整个作品只有**一个**视频文件，`resources/app/data/video/logo.webm`
（677 KB）。WebM/VP8 是 Chromium 自带的 `ffmpeg.dll` 解的，不走 Wine 的媒体栈，
所以这部**没有"编码解不了"的风险**，白屏那类问题只会来自 GPU 进程
（也就是已经记下的 `--in-process-gpu`）。

### 坑一：纯白窗口

Chromium 默认把 GPU 放独立进程，Wine 下跨进程传不过去。
`--in-process-gpu` 是**必需**的，不是优化项。

### 坑二：分享者自带的存档会让游戏卡死

TyranoScript 对存档做哈希校验，别人的存档对不上就一直弹错误框、卡在 loading。
把 `.sav` 移进 `.backup-original-saves/` 后全新开始才正常。
代价是分享者的进度和已解锁内容没了。

### 坑三：解压

这个包是 RAR5 且**文件头也加密**，密码是中文。`7zz` 全程报
`Unsupported Method` / 密码错误，换成 `unar` 一次通过。

> **结论：RAR5 + 加密头 + 非 ASCII 密码，用 `unar`，不要用 `7zz`。**
> 这个坑在本仓库里出现过两次（另一次也是中文密码），每次都浪费了大把时间。

---

## 从这 7 部里能提炼出的规律

1. **引擎决定一切**。先 `file` 主程序、看目录里的资源格式，再决定用哪个容器、
   哪个后端。判断错了后面全是白工。
2. **2D 老游戏最省事**。KiriKiri Z + Wine 是甜蜜区，默认配置基本就能跑。
3. **画面纯色 = 后端问题**，先换后端再想别的。
4. **崩溃 = 影片问题**（在这台机器上命中率最高），先查 `movie/` 里的编码。
5. **汉化整合包自带三个坑**：字体指定了 Windows 专有字体、影片被改名或重压、
   存档带哈希校验。这三个都不是"游戏坏了"。
6. **别人给的容器配置不能照抄**。同一台机器上 7 部游戏就有 4 种不同的后端组合。

---

## 附录：给"还没玩到影片段落的那些"做一次静态复核（2026-10-16）

动机：7 部里有 5 部还没实际玩到影片段落，笔记里那些结论大多是装机那几天的
印象。这一轮的原则是**不猜，只查能查的东西**。

### 怎么判断引擎（不用启动游戏）

```bash
strings -a 主程序.exe | grep -iE 'TVPWindowForm|tTVP'   # KiriKiri
strings -a 主程序.exe | grep -iE 'Artemis Engine'       # Artemis
```

再对一眼资源格式：`*.xp3` = KiriKiri，`*.pfs`（文件头 `pf8`）= Artemis，
`*_info.psb.m` + `*_body.bin` 成对出现 = M2。

⚠️ **只看 `TVP` 三个字母会误报** —— Electron 那个 exe 也"命中"了 `TVP`，
那是随机字节。要认 `TVPWindowForm`、`tTVP` 这种完整符号。

### 怎么判断影片能不能解（先标定，再逐个测）

别用宿主机的 ffmpeg，它永远说"没问题"。用容器自带的 GStreamer：

```bash
source tools/mac/gst-env.sh <容器名>
"$GSTLAUNCH" -q filesrc location=<file> ! decodebin ! fakesink
```

`rc=0` 就是能解。这套测法先拿 ATRI 两个已知样本标定过，确认它分得开好坏：

| 样本 | 音轨 | 结果 |
|---|---|---|
| ATRI 原版 206 | wmapro | `rc=1` + `avdec_wmapro: Could not decode stream` |
| ATRI 修好版 206 | wmav2 | `rc=0` |
| アマカノ3 三个片子 | **wmalossless** | `rc=0` ← 名字像 wmapro，实际能吃 |

### 这一轮查出来的东西

- **引擎标错 2 处**：灵感满溢（KiriKiri Z → Artemis Engine Rev.2762）、
  可塑性记忆（KiriKiri 系 → M2）。アマカノ3 补上引擎名
  （Artemis Engine Rev.3258，x64）—— 它和灵感满溢是**同一个引擎**。
- **アマカノ3 的 `D9VK=1` 是误归因**：它只用 D3D11，日志里 d3d11 / d3d9
  都是 `builtin`，真正起作用的是 wine-10.0 的 wined3d。
- **不败世界的 OP / ED 音轨是 `wmav2`**，且不需要 krmovie 那 12 字节补丁。
- **灵感满溢"能播没画面"**：两个片子都 `rc=0`，编码是通的，问题在渲染层。
  原计划"关 `D9VK` 再放一次"**作废** —— 这台容器的 `D9VK=1` / `CNC_DDRAW=1`
  压根没写进瓶子，`d3d9` 一直是 Wine 内置（见该节坑四）。
- **顺手修掉一个容器启动缺陷**：灵感满溢的 `prefix/drive_c/users/` 里有一条
  悬空软链接 `crossover -> Sikarugir`，会让容器直接起不来（见该节坑三）。
  修完之后冷启动能正常到标题画面，这条是实机验证过的。
- **可塑性记忆**的 prefix 里躺着一份笔记没记过的 LAVFilters 0.74.1；
  它的影片是 H.264 + AAC，编码能解，但"开机就播的 `PM_bootMV` 经不经得起
  Wine 的 DirectShow 链"没验过。
- **与奴隶的生活**只有一个 `logo.webm`，Chromium 自己解，没有编码风险。

### 还没验、要等真玩到那儿才知道的

1. アマカノ3 / 不败世界 / 灵感满溢 / 可塑性记忆 的**影片过场**有没有正常出画。
   静态核查只能排除"编码解不了"，排除不了"渲染层不出画"（灵感满溢就是后者）。
2. 把 アマカノ3 的 `D9VK` 关掉会不会有别的副作用（理论上不会，没实测）。
3. 灵感满溢 开 `D3DMETAL=1` 能不能让 OP 出画（"关 `D9VK`" 这条已作废，
   见该节坑四）。
4. 可塑性记忆 的开机影片在 Wine 下到底走不走得通。
