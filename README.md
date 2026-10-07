# 在 Apple Silicon Mac 上玩 galgame

一份跑通了的实操记录：怎么在 macOS 上用 Wine 封装跑没有 Mac 版的日系
galgame，以及一路上踩过的坑、用过的工具、每个坑的根因和修法。

内容来自一台 Apple M5 / macOS 26.7 的机器上陆续装完 7 部作品的真实过程。
**不是综述，是日志**——每个结论后面都写着是怎么验证出来的，包括走错的路。

> **English TL;DR** — A field guide to running Windows-only Japanese visual
> novels on Apple Silicon macOS with Sikarugir (a Wineskin successor). Covers
> wrapper assembly, per-engine quirks, a symptom → root-cause → fix table for
> the problems that actually came up (black video, white screen, tofu text,
> crashes on startup, audio stuck on the wrong output device), and the small
> macOS-side toolchain used to debug them. No game assets are included.

## 这个仓库原来是什么

它起初只为记录一个问题：《千恋＊万花》在 Wine 下 ED 动画黑屏，根因是三层叠加
（dyld 顶替 libiconv 把 GStreamer 打崩 → `krmovie.dll` 里 12 个字节的越界判断
把影片挡在 layer 模式之外 → ED 音轨是 Wine 解不了的 WMA Pro）。

那部分完整保留在 [docs/case-senren-banka-ed.md](docs/case-senren-banka-ed.md)，
因为它是本仓库里最深的一个案例：把「猜缺什么」变成「找到那个字节」的完整过程。

后来游戏越装越多，坑也越踩越多，就把整个流程整理成了这份通盘文档。

## 先看这里：路线怎么选

先判断游戏引擎，再决定用哪条路。判断错方向会白花一整天。

| 引擎 / 来源 | 特征 | 建议路线 |
|---|---|---|
| **Ren'Py** | 目录里有 `game/`、`*.rpyc` | 官方就有 Mac 版；只有 Windows 版时用 Ren'Py SDK 直接跑，不用 Wine |
| **KiriKiri / KiriKiriZ** | 一堆 `*.xp3`，exe 里有 `TVP*` 符号 | Wine 封装最成熟的组合，本仓库主线 |
| **NScripter / ONS** | `nscript.dat`、`*.nsa` | OnscripterYuri 有原生 mac 构建 |
| **Unity / RPG Maker / 自研** | `*_Data/`、`Game.exe` | Wine；3D 的另算 |
| **带 DRM 的**（DMM/FANZA 客户端、SoftDenchi、PlayDRM） | 启动时要联网校验 | Wine 上大概率翻车，考虑虚拟机 |

macOS 上的 Wine 侧选择：

- **Sikarugir** —— Wineskin 的正统后继，Gcenx 维护，现在最活跃。本仓库全程用它。
- **CrossOver** —— 付费但省心，一瓶一键 Steam，视频兼容性最好。Sikarugir 的引擎
  （WineCX）就是从 CrossOver 来的。
- **Whisky** —— **2025 年停止维护，不要再用**。网上大部分 2024 年前的教程还在推荐它。
- **虚拟机**（VMware Fusion / UTM / Parallels）—— 兼容性兜底。2D 文字游戏切一半内存
  给虚拟机不划算，但遇到 DRM 类游戏是唯一出路。

原生模拟器（Tyranor Mac、AetherKiri）对**日文原版**的 KiriKiri 作品效果不错，但
**对汉化整合版挑食**（汉化基本是 exe 安装器或替换 xp3 的形式），所以如果你玩的是
汉化版，Wine 是更稳的选择。

## 五分钟上手

```bash
# 1. 装 Sikarugir
brew trust Sikarugir-App/sikarugir
brew install --cask Sikarugir-App/sikarugir/sikarugir

# 2. 用它建一个容器（GUI 里：下载模板 -> 选引擎 -> 创建）
open -a "Sikarugir Creator"

# 3. 把游戏放进 ~/Games，在容器里建一个软链接指过去
mkdir -p ~/Games && mv ~/Downloads/你的游戏 ~/Games/

# 4. 让容器启动这个游戏
source tools/mac/guest-env.sh 你的容器名
ln -sfn "$HOME/Games/你的游戏" "$WINEPREFIX/drive_c/Games/你的游戏"
/usr/libexec/PlistBuddy -c "Set ':Program Name and Path' '/Games/你的游戏/游戏.exe'" \
  "$SIKA_APP/Contents/Info.plist"

# 5. 双击容器 app 进游戏
open "$SIKA_APP"
```

更完整的步骤见 [docs/01-setup.md](docs/01-setup.md) 和
[docs/02-install-game.md](docs/02-install-game.md)。

## 日常使用：一个启动器管所有游戏

容器一多，"双击哪个 app"就成了问题。这里用一套「容器 + 软链接 + 标记文件」
的布局，配合一个脚本来切换：

```
~/Games/<游戏名>/                游戏本体（不复制进容器）
    .container                   这个游戏用哪个容器（可省略）
    .launch-exe                  主程序 exe 的文件名（可省略，会自动猜）
~/Applications/Sikarugir/<容器>.app
    Contents/SharedSupport/prefix/drive_c/Games/<链接>  ->  指向游戏目录
```

```bash
./tools/mac/galgame-menu.sh list              # 列出所有游戏
./tools/mac/galgame-menu.sh plan  千恋＊万花   # 只说要改什么，不动手
./tools/mac/galgame-menu.sh launch 千恋＊万花  # 切过去并启动
```

再套一层 GUI 就是 [tools/mac/launcher.applescript](tools/mac/launcher.applescript)。
详细说明见 [docs/02-install-game.md](docs/02-install-game.md)。

## 故障速查

实际遇到过的症状，按这个表往下查。每一行在
[docs/04-troubleshooting.md](docs/04-troubleshooting.md) 里都有完整过程。

| 症状 | 最可能的原因 | 一句话修法 |
|---|---|---|
| 文字全是方块 □□□ | 游戏指定了 Wine 里没有的字体（汉化版常指定微软雅黑） | 在 `HKCU\Software\Wine\Fonts\Replacements` 里做字体替换 |
| 影片黑屏 / 白屏，游戏本身正常 | 影片编码 Wine 解不了，或引擎的 DirectShow 链路没建起来 | 把影片转成 WMV2；同时排掉 VC-1 |
| 一进游戏就崩，崩溃地址像野指针 | 引擎在 DirectShow 协商失败后自己踩空 | 同上——换影片编码，别去补解码器 |
| 启动后纯白，CPU 只有几个点 | 卡在建图 / 卡在等影片播完，不是"慢" | 先看日志里有没有 `video mode:layer`；见排查文档 |
| 3D / 新引擎的作品花屏或纯色 | 渲染后端选错 | 在 D9VK / DXVK / D3DMetal 之间换着试 |
| Electron 打包的游戏纯白 | Wine 下跨进程 GPU 传不过去 | `Program Flags` 加 `--in-process-gpu --no-sandbox` |
| 插了耳机还是外放 | Wine 在**启动时**枚举音频设备并绑死 | 先插耳机，再启动游戏 |
| 存档读不进去，无限弹错误框 | 引擎对存档做哈希校验，别人的存档对不上 | 把旧存档移走，重开一局 |
| 改了 `.xp3` 但游戏没变化 | KiriKiri 在启动时就把归档打开并缓存了 | 完全退出游戏再开 |

## 实测过的游戏

同一台机器上装完并验证能玩到正片的 7 部，配置各不相同——这张表本身就是
"为什么不能照抄一份配置"的最好说明。

| 游戏 | 引擎 | 容器引擎 | 关键开关 | 主要坑 |
|---|---|---|---|---|
| 千恋＊万花 | KiriKiri Z | WineCX 24.0.7 | `MOLTENVKCX=1` | 字体乱码、影片黑屏 |
| ATRI -My Dear Moments- | KiriKiri Z | wine-10.0 | `MOLTENVKCX=1` | 首启语言对话框 |
| アマカノ3 | `.pfs` + E-mote | wine-10.0 | `D9VK=1` | 强制 D3D11，旧引擎跑不起来 |
| 不败世界与终焉之花 | KiriKiri Z | wine-10.0 | `D9VK=1` | 汉化重打包造成的文件名编码错误 |
| 灵感满溢的甜蜜创想 | KiriKiri Z | wine-10.0 | `D9VK=1` + 原生 quartz | 片头 VC-1 导致启动即崩 |
| 可塑性记忆 | KiriKiri 系 | wine-10.0 | `D9VK=1` | 默认 OpenGL 后端只出蓝/黑屏 |
| 与奴隶的生活 | Electron + TyranoScript | wine-10.0 | `DXVK=1` + `--in-process-gpu` | 白屏；存档哈希校验 |

详见 [docs/05-observed-games.md](docs/05-observed-games.md)。

## 仓库结构

```
README.md                            本文件：路线选择 + 速查
docs/01-setup.md                     装 Sikarugir、手工组装容器、日文区域与字体
docs/02-install-game.md              解包、目录布局、软链接、启动器
docs/03-container-tuning.md          Info.plist 全键位说明、渲染后端怎么选
docs/04-troubleshooting.md           症状 -> 根因 -> 修法，含验证手段
docs/05-observed-games.md            7 部作品的实测配置与踩坑记录
docs/06-toolbox.md                   调试工具链说明
docs/case-senren-banka-ed.md         案例：《千恋＊万花》ED 黑屏的三层根因
docs/kirikiri-xp3-format.md          KiriKiri 的 XP3 容器格式与本项目用到的写入策略

tools/mac/build.sh                   编译 winlist / wclick
tools/mac/winlist.c                  列出屏幕上的窗口 + 窗口号（截屏要用）
tools/mac/wclick.swift               合成鼠标点击 / 按键
tools/mac/wraptry.sh                 启动容器 -> 等 -> 精确截它的窗口
tools/mac/guest-env.sh               source 一下，拿到容器里的 wine 环境
tools/mac/galgame-menu.sh            多游戏启动后端
tools/mac/launcher.applescript       给上面那个后端套 GUI

tools/xp3/xp3tool.py                 XP3 读取（索引链、条目、解压）
tools/xp3/cxdec.py                   CX 加密/解密（密钥表从游戏自带脚本读）
tools/xp3/xp3_replace.py             最小改动替换一个条目（自动回写加密）
tools/xp3/krmovie_nop12.py           本仓库发现的 12 字节补丁，一键完成
tools/xp3/verify.py                  回读校验：解密每个条目并打印 md5 / 类型
```

## 环境

本文所有结论来自：Apple M5 / 16 GB / macOS 26.7.1，Sikarugir 模板 1.0.15，
引擎为 WineCX 24.0.7（= Wine 9.0，CrossOver 系）与 Sikarugir wine-10.0 两种。

不同引擎版本、不同封装器细节会有出入，但**故障的类别**是一样的：字体、
影片编码、渲染后端、音频设备枚举时机、归档缓存时机。这几类问题跟引擎版本
关系不大，换个封装器照样会遇到。

## 免责声明

本仓库只包含分析笔记和工具，**不含任何游戏资源**（DLL、影片、脚本、密钥表
都没有，也没有任何下载地址和压缩包密码）。所有改动都作用于你自己合法持有的
那份游戏副本，目的是让它在非 Windows 平台上能正常播放。

`tools/xp3/cxdec.py` 复现的是引擎自身的归档读取过程，用来做兼容性修复和存档
保护。请支持正版；本仓库不提供获取游戏的途径。
