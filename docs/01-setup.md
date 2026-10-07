# 01 · 环境搭建

目标：得到一个「双击就能跑 Windows 程序」的容器，并且它认日文。

## 装 Sikarugir

```bash
brew trust Sikarugir-App/sikarugir
brew install --cask Sikarugir-App/sikarugir/sikarugir
```

装完会有两个东西：

- `/Applications/Sikarugir Creator.app` —— 图形界面，用来建容器
- 首次启动时它去下载**模板**（Template）和**引擎**（Engine）

这两样都是运行时下载的，不在 cask 里。模板落在：

```
~/Library/Application Support/Sikarugir/Template/Template-1.0.15.app
```

引擎是一份打了包的 Wine 运行时，官方发布页在 `github.com/Sikarugir-App/Engines`，
按 `WS<模板版本><引擎名>_<revision>.tar.xz` 命名（本机用的是 `WS12WineCX24.0.7_7`，
即 CrossOver 24.0.7 内核、第 7 版打包）。

**引擎怎么选**：CrossOver 系（WineCX）的内核对日式 galgame 的视频和字体兼容最好，
它自带的那套 GStreamer 和媒体补丁最全。Sikarugir 自己的 wine-10.0 引擎更新，
跑新游戏（D3D11、E-mote、Electron）反而更好。两个都留着不亏。

> **Whisky 不要用。** 它 2025 年 5 月归档，Homebrew 的 cask 也标了废弃。
> 2024 年之前写的教程基本都在推它，照抄会浪费时间。

## 容器里有什么

一个 Sikarugir 容器就是普通的 `.app`，但结构值得先看清楚，后面所有调试都在
这几个目录里转：

```
你的容器.app/Contents/
├── MacOS/
│   ├── Sikarugir                  启动脚本：设好一堆环境变量再调 wine
│   ├── launcher                   把拖进来的文件交给 wine 跑
│   └── Sikarugir WSS-winetricks   容器自带的 winetricks 入口
├── Info.plist                     所有开关都在这里（见 03）
├── Configure.app                  图形配置面板，双击就能改 Info.plist
├── Frameworks/
│   ├── GStreamer.framework/       视频解码（ASF/WMV/MPEG 的 demuxer 和 decoder）
│   ├── libMoltenVK.dylib          Vulkan 到 Metal 的转译层
│   └── renderer/                  各个渲染后端，每个下面有自己那份 wine 模块
│       ├── cnc_ddraw/             旧版 2D 直绘（对应 CNC_DDRAW）
│       ├── d9vk/                  D3D9 到 Vulkan（对应 D9VK）
│       ├── dxvk/                  D3D10/11 到 Vulkan（对应 DXVK）
│       ├── d3dmetal/              D3D 到 Metal（对应 D3DMETAL）
│       ├── apple_gptk/            Apple Game Porting Toolkit
│       └── dxmt/                  D3D 到 Metal 的另一条路
├── SharedSupport/
│   ├── wine/                      Wine 引擎本体（bin/wine、lib、lib64）
│   └── prefix/                    Wine 瓶，也就是虚拟 C 盘
└── Resources/
    └── vulkan/icd.d/MVK_CW_icd.json   MoltenVK 的 ICD 清单
```

两个容易记错的点：

1. **Wine 引擎在 `Contents/SharedSupport/wine`，不在 `Frameworks`。**
   `Frameworks` 里只有动态库（GStreamer、MoltenVK、SDL 那些）。手工组装容器时
   把引擎放错位置，症状是「容器起来了但报找不到程序」。
2. **游戏不放进 `prefix` 里。** `prefix/drive_c` 是虚拟 C 盘，但游戏动辄几十 GB，
   拷进去既浪费空间又难管理。正确做法是放外面、在 `drive_c/Games` 建软链接。
   见 [02-install-game.md](02-install-game.md)。

## 建一个容器

### 正常路径：GUI

打开 `Sikarugir Creator`，下载模板，选引擎，给容器起名，创建。创建时选好：

- **Win 版本**：Win 10。很多新版游戏和 Electron 应用会检查这个
- **区域**：日本。后面还要补字体，见下节

### 备用路径：手工组装

如果 Creator 的引擎选择弹窗被挡住点不到（多屏或窗口层级问题很容易触发），
可以直接从模板复制一份手工装：

```bash
TEMPLATE="$HOME/Library/Application Support/Sikarugir/Template/Template-1.0.15.app"
DEST="$HOME/Applications/Sikarugir/新容器.app"

mkdir -p "$HOME/Applications/Sikarugir"
cp -R "$TEMPLATE" "$DEST"

# 把下载好的引擎解开，放到 SharedSupport/wine
# 引擎包解开后是 bin/ lib/ lib64/ 这样的结构
tar -xJf ~/Downloads/WS12WineCX24.0.7_7.tar.xz -C /tmp/engine
mkdir -p "$DEST/Contents/SharedSupport"
mv /tmp/engine/wine "$DEST/Contents/SharedSupport/wine"

# 初始化瓶子，第一次要花几十秒，别以为卡死了
"$DEST/Contents/SharedSupport/wine/bin/wineboot" -u
```

模板默认的启动目标是记事本，所以第一次启动看到记事本窗口就是**成功**了 ——
说明引擎、瓶子、图形驱动这条链是活的。

## 配日文区域和字体

日文 galgame 的两个要求：**区域要是日本**（决定读资源时用哪套编码），
**字体要装进瓶子**（否则正文全是方块）。这两件事分开做。

### 区域

在 `Info.plist` 里加：

```xml
<key>LSEnvironment</key>
<dict>
    <key>LANG</key><string>ja_JP.UTF-8</string>
    <key>LC_ALL</key><string>ja_JP.UTF-8</string>
</dict>
```

命令行做法：

```bash
/usr/libexec/PlistBuddy -c "Add :LSEnvironment:LANG string ja_JP.UTF-8" "$DEST/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSEnvironment:LC_ALL string ja_JP.UTF-8" "$DEST/Contents/Info.plist"
```

Wine 自己的区域（`Locale`）也可以一并设成日文（`00000411`），让 Windows 侧的
`GetLocaleInfo` 也返回日本。

### 字体

macOS 自带日文字体，把它们拷进瓶子里：

```bash
source tools/mac/guest-env.sh 新容器
FONTS="$WINEPREFIX/drive_c/windows/Fonts"
cp "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc" "$FONTS/HiraginoKakuGothicW3.ttc"
cp "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"    "$FONTS/HiraginoMinchoProN.ttc"
cp "/System/Library/Fonts/BIZ UDGothic.ttc"         "$FONTS/BIZUDGothic.ttc"
```

再确认注册表能认出来 —— 这一步经常需要，因为游戏是按**字体名**要字体的，
不是按文件名：

```bash
"$WINE" reg add "HKCU\\Software\\Wine\\Fonts\\Replacements" \
  /v "MS Gothic" /t REG_SZ /d "Hiragino Kaku Gothic W3" /f
```

**为什么字体这么重要**：汉化版经常把正文字体写死成「微软雅黑」，而 Wine 里
根本没有这个字体，引擎拿不到字形就全部渲染成 `□□□`。修法不是去动游戏文件，
而是在瓶子的字体替换表里加一条映射。完整案例见
[04-troubleshooting.md](04-troubleshooting.md)。

## 验证：先跑一个日文测试

搭完之后不要直接上游戏，先花一分钟验证这条链：

```bash
source tools/mac/guest-env.sh 新容器

# 记事本应该弹到桌面上
"$WINE" notepad &

# 日文渲染要正常，不能是方块
"$WINE" cmd /c 'echo 日本語のテスト：千恋＊万花 / 柚子ソフト / RIDDLE JOKER'
```

记事本能弹出来但日文是方块，是字体没配对；记事本都弹不出来，是引擎或图形
驱动的问题，先别往下走。

窗口可以用 `tools/mac/winlist` 找出来、精确截图：

```bash
cc -O2 -o winlist tools/mac/winlist.c -framework CoreGraphics -framework CoreFoundation
./winlist | grep owner=wine
screencapture -x -l <上面输出的 win= 号> /tmp/test.png
```
