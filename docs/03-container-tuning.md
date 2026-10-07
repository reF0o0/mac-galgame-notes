# 03 · 容器配置

容器的所有开关都在 `你的容器.app/Contents/Info.plist`。图形界面改法和命令行
改法是同一份文件，所以下面一律用命令行写，方便复制。

```bash
APP="$HOME/Applications/Sikarugir/某容器.app"
PLIST="$APP/Contents/Info.plist"

/usr/libexec/PlistBuddy -c "Set :D9VK 1" "$PLIST"          # 改
/usr/libexec/PlistBuddy -c "Print :D9VK" "$PLIST"          # 查
cp "$PLIST" "$PLIST.bak-$(date +%Y%m%d)"                   # 改之前先备份
```

改完要**重启容器**才生效（`Info.plist` 只在启动时读一次）。

## 关键键位

这几个是决定"能不能出画面"的，实机试出来的默认值不一定对：

| 键 | 类型 | 说明 |
|---|---|---|
| `Program Name and Path` | string | 启动目标，容器内部的 Windows 路径（`/Games/.../x.exe`） |
| `Program Flags` | string | 传给主程序的命令行参数，空格分隔 |
| `D9VK` | 0/1 | D3D9 走 Vulkan（经 MoltenVK） |
| `DXVK` | 0/1 | D3D10/11 走 Vulkan |
| `D3DMETAL` | 0/1 | D3D 走 Apple 的 D3DMetal，也就是 Game Porting Toolkit |
| `CNC_DDRAW` | 0/1 | 旧版直接写 framebuffer 的 2D 绘制路径 |
| `MOLTENVKCX` | 0/1 | 用 MoltenVK，而不是系统自带那个老掉牙的 Vulkan 实现 |
| `WINEMSYNC` / `WINEESYNC` | 0/1 | 同步原语加速，一般两个都开着 |
| `WINEDEBUG` | string | Wine 日志开关，调试必用，见下 |
| `Locale` | string | Windows 侧的区域，日文是 `00000411` |
| `LSEnvironment` | dict | 进程环境变量，日文的 `LANG` / `LC_ALL` 放这里 |
| `Symlinks In User Folder` | 0/1 | 是否把 `~/Documents`、`~/Downloads`、`~/Desktop` 软链进瓶子 |
| `Winetricks force` / `Winetricks silent` | 0/1 | 装组件时的行为 |
| `CFBundleVersion` | string | 模板版本（1.0.15 / 1.0.18），决定默认有哪些库 |

### 关于 `Symlinks In User Folder`

它默认是 **1**，意思是瓶子里的 `C:\users\<你>\Documents` 直接指到你真实的
`~/Documents`。方便，但也意味着**瓶子里跑的任何 exe 都能读写你真实的这三个
目录**。跑来源不明的整合包时，把它关掉（设 0）更稳。

## 渲染后端怎么选

这是最容易踩坑的地方：**同一个游戏在不同后端下的表现可以差到"能玩"和"纯色屏"
两个极端**，而且没有通用答案。本机实测：

| 后端组合 | 适合 | 实测表现 |
|---|---|---|
| `MOLTENVKCX=1`，其余全 0 | 老的 KiriKiri Z 2D 作品 | 《千恋＊万花》《ATRI》正常 |
| `D9VK=1` | 需要 D3D9、或旧后端出蓝屏/黑屏的作品 | 《アマカノ3》《可塑性记忆》必需 |
| `DXVK=1` | D3D11 的新引擎、Electron 打包的游戏 | 《与奴隶的生活》必需 |
| `D3DMETAL=1` | 3D 游戏想省电 | 本仓库没用到，2D 游戏反而容易出问题 |
| `CNC_DDRAW=1` | 最老的 2D 绘制 | 默认就开着，一般不用动 |

调法就是一个一个换，每次只改一个，改完重启 —— 一次改两个变量，出了问题
你不知道是哪个。

**几个经验**：

- 如果游戏"能启动但画面是纯色"（蓝 / 黑 / 白），八成是后端选错，不是游戏坏了。
- 改后端之前先确认**进程活着、CPU 有占用**。CPU 只有一两个点，说明它卡在
  别的地方（等影片、等锁），换后端没用。
- `Frameworks/renderer/` 下面有什么目录，就说明这个容器支持哪些后端。
  `WINEDLLPATH` 里要列上对应的 `wine` 子目录，否则模块加载不到。

## `Program Flags`：命令行参数

有些引擎会读启动参数，比改游戏文件干净得多。本机用到的：

| 参数 | 用在 | 作用 |
|---|---|---|
| `--in-process-gpu` | Electron 打包的游戏（如 TyranoScript） | 把 GPU 进程合并进主进程，否则 Wine 下跨进程传不过去，纯白窗口 |
| `--no-sandbox` | 同上 | 关掉 Chromium 沙箱 |
| `-vomstyle=layer` | 部分 KiriKiri 作品 | 影响影片渲染路径，见 [case-senren-banka-ed.md](case-senren-banka-ed.md) |

## `WINEDEBUG`：日志

调不出画面的时候，日志是唯一可靠的信息来源。

```
WINEDEBUG = -plugplay,+loaddll
```

`-plugplay` 关掉一个噪音很大的 channel，`+loaddll` 打开模块加载记录 ——
查「DLL 被谁加载了」几乎全靠它。

改成 `WINEDEBUG = -all` 可以整体静音，日志量会小很多；排查时再按需要打开
具体 channel（`+quartz`、`+mfplat`、`+winegstreamer`、`+d3d` 等）。

日志默认写到容器的 `Contents/SharedSupport/Logs/`。手工跑 wine 时自己重定向：

```bash
source tools/mac/guest-env.sh 某容器
"$WINE" 'C:\Games\x\game.exe' > /tmp/game.log 2>&1
```

> Wine 的日志很吵：**大部分 `err:` 和 `fixme:` 都是无害的**。
> 找线索要抓这几个关键词：`SIGSEGV`、`Unhandled exception`、
> `not found`、`failed to load`，以及游戏自己打印的那几行。

## 往瓶子里塞东西：注册表

两个用得最多的注册表位置：

### 字体替换

```bash
"$WINE" reg add "HKCU\\Software\\Wine\\Fonts\\Replacements" \
  /v "Microsoft YaHei" /t REG_SZ /d "Hiragino Sans GB" /f
```

左边是游戏要的字体名，右边是瓶子里真实存在的字体。这是解决
「中文全是方块」的正解 —— 不用动游戏文件。详见
[04-troubleshooting.md](04-troubleshooting.md)。

### DLL 覆盖

```bash
"$WINE" reg add "HKCU\\Software\\Wine\\DllOverrides" \
  /v "version" /t REG_SZ /d "native,builtin" /f
```

`native,builtin` 的意思是：优先用游戏目录里那份（native），找不到再回落到
Wine 内置的（builtin）。把第三方 DLL 放进游戏目录来挂钩引擎时，**不加这条
多半不生效** —— Wine 默认优先加载自己的内置版本，无视游戏目录里的同名文件。

### 改 Windows 版本号

有些安装器会因为"系统太老"拒绝安装：

```bash
"$WINE" reg add "HKCU\\Software\\Wine" /v Version /t REG_SZ /d win10 /f
"$WINE" cmd /c ver      # 确认，应该看到 Microsoft Windows 10.0.xxxxx
```

## 装 Windows 组件

需要原生 DirectShow、解码器之类的时候用 winetricks：

```bash
"$APP/Contents/MacOS/Sikarugir WSS-winetricks" -q --no-isolate quartz
```

**注意**：容器自带的这个入口会 `cd` 进 `SharedSupport/wine/bin`，于是
`PATH` 里没有 `/opt/homebrew/bin`，找不到 `cabextract` 就会失败。
遇到这种失败就直接跑官方 winetricks、自己先 `source guest-env.sh` 把环境导好，
效果一样。

装 `quartz` 会顺带下载 1.4 GB 的 Win7 SP1 cab 到 `~/.cache/winetricks/`，
装完可以删。
