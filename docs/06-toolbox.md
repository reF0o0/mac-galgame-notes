# 06 · 工具箱

调 Wine 下的 galgame，缺的不是知识而是**观察手段**：能不能精确截到那一扇窗、
能不能知道它到底在读哪个文件、能不能拿到页面里的报错。这里是在这台机器上攒出来
的一套最小工具。

---

## macOS 侧

### `winlist` —— 找到窗口

```bash
cd tools/mac && ./build.sh          # 编译 winlist 和 wclick
./winlist | grep owner=wine
# win=12021  owner=wine  pid=12995  layer=0  1592x830 @(4,33)  name="TeachingFeeling_ver4.0.6"
```

输出里需要三样东西：**窗口号**（给 `screencapture -l` 用）、**尺寸和位置**
（给 `wclick` 算点击坐标）、**窗口标题**（确认游戏真的把窗口建出来了，
以及标题里的版本号对不对）。

**为什么要自己写**：`osascript` 的 System Events 经常看不到非原生窗口；
而窗口号只能从 `CGWindowListCopyWindowInfo` 拿。另外这个小工具在锁屏状态下也能用。

首次运行需要给宿主程序（终端 / Codex）**屏幕录制权限**，否则拿不到窗口标题。

### `wclick` —— 合成点击和按键

```bash
./wclick 800 500              # 点一下
./wclick 800 500 move         # 只移动光标（用来确认落点）
./wclick 53 0 key             # 按 Esc
```

常用虚拟键码：`36` 回车 / `49` 空格 / `53` Esc / `51` 退格 / `123`-`126` 方向键。

**注意**：事件是投递到**屏幕坐标**上的，所以对窗口层级很敏感 —— 别的窗口盖在
上面，点就落错了地方。先 `open -a` 把目标提到前面，或者在点之前先 `move`
确认一下落点。

### `wraptry.sh` —— 启动 + 等待 + 精确截图

```bash
./wraptry.sh 千恋＊万花 /tmp/shot.png 40
```

三个步骤：用真实封装启动容器、等指定秒数、用 `winlist` 找到 wine 窗口再
`screencapture -l` 只截那一扇。**这比截全屏再裁可靠得多**，尤其是多显示器或者
窗口被挡住的时候。

等待时间别省。一个几 GB 的 `.xp3` 游戏冷启动要 30 到 60 秒，太早截图只能
截到空窗口，然后你会误判成"启动失败"。

### `guest-env.sh` —— 进入瓶子

```bash
source tools/mac/guest-env.sh 千恋＊万花
"$WINE" notepad &
"$WINE" reg query "HKCU\\Software\\Wine\\Fonts\\Replacements"
grep -A5 winecoreaudio "$WINEPREFIX/user.reg"
```

这些环境变量（`WINEPREFIX`、`WINEDLLPATH`、`DYLD_FALLBACK_LIBRARY_PATH`、
`GST_PLUGIN_PATH`、`VK_DRIVER_FILES`、`LANG`）是从容器自己的启动脚本里反推的。
**少一个就会加载错 dylib**，症状是各种奇怪的崩溃 —— 所以不要手敲，用这个脚本。

### `galgame-menu.sh` —— 多游戏启动后端

见 [02-install-game.md](02-install-game.md)。配 `launcher.applescript` 就有
图形界面。

### `cdp.py` —— 看 Electron 游戏里到底发生了什么

TyranoScript + Electron 这类打包的游戏，画面是 Chromium 渲染的，出问题时
Wine 日志帮不上忙 —— 真正在报错的是页面里的 JavaScript。

给它加 `--remote-debugging-port=9222`（塞进容器 `Program Flags`），然后：

```bash
python3 tools/mac/cdp.py dialogs 60      # 盯着弹框和控制台报错
python3 tools/mac/cdp.py hook 45         # 注入钩子后刷新，把 alert / 异常都打出来
python3 tools/mac/cdp.py reload          # 刷新并打印控制台 + 网络失败
python3 tools/mac/cdp.py shot /tmp/x.png
python3 tools/mac/cdp.py 'Game.currentScene()'
```

`hook` 那个模式最有用：把 `alert` / `confirm` / `onerror` 全部改写成 `console.log`
再刷新，所有"弹个框然后卡住"的问题都会变成一行行可读的日志。

需要 `pip install websockets`。

---

## 判断"它到底在读什么"

排查"文件放对了没生效"这类问题，**文件访问时间是硬证据**（macOS 上读文件会更新
`atime`）：

```bash
# 记下基线
stat -f '%Sm %N' -t '%H:%M:%S' ~/Games/<游戏名>/unencrypted/*.pimg | head

# 启动游戏、操作一会儿，再看
stat -f '%Sm %N' -t '%H:%M:%S' ~/Games/<游戏名>/unencrypted/*.pimg | head
```

时间变了就说明它真的读了那几个文件。这比"肉眼看效果对不对"可靠得多，
而且能回答"它读的是我新放的那份，还是旧的缓存"。

另一个同类的：

```bash
lsof -p <pid> | grep -i xp3      # 它到底打开了哪个归档
```

---

## KiriKiri 归档工具（`tools/xp3/`）

只在需要改 `.xp3` 内容的时候用（换影片、打引擎补丁、验证改动）。**先在副本上练。**

```bash
export FILTER=~/Games/千恋＊万花/补丁/解密补丁/xp3filter.tjs

python3 tools/xp3/xp3tool.py list game/patch.xp3                 # 看有哪些条目
python3 tools/xp3/verify.py game/patch.xp3 --filter "$FILTER"    # 全量回读校验
python3 tools/xp3/xp3_replace.py ...                             # 替换一个条目
python3 tools/xp3/krmovie_nop12.py game/patch.xp3 --filter "$FILTER" --backup
```

| 脚本 | 作用 |
|---|---|
| `xp3tool.py` | 读归档：索引链、条目列表、单个条目解压 |
| `cxdec.py` | CX 加密/解密。密钥表从游戏自带的 `xp3filter.tjs` 读 |
| `xp3_replace.py` | **最小改动**替换一个条目，自动按条目自己的 `aldr` 回写加密 |
| `krmovie_nop12.py` | 那个 12 字节补丁，自己在归档里找 DLL、定位签名、原地改 |
| `verify.py` | 回读校验：把每个条目解密后打印 md5 和类型 |

**两条铁律**：

1. **不要重建归档。** 只改那一个条目的偏移和大小，数据区一个字节不动，
   新内容追加到文件尾部。重建索引会让游戏直接打不开归档。
2. **CX 的密钥流是位置相关的**，所以不能直接改密文 —— 必须用条目自己的
   `aldr` 重新加密一遍。`xp3_replace.py` 做的就是这个。

格式细节见 [kirikiri-xp3-format.md](kirikiri-xp3-format.md)。

---

## 通用工具（顺手提一下）

调这类问题会反复用到的几个：

```bash
file / ffprobe / ffmpeg        # 判断文件真实类型、影片编码、转码
lsar / unar                    # RAR5 + 加密头 + 非 ASCII 密码
lsof -p <pid>                  # 进程到底打开了什么
iconv -f UTF-16LE              # KiriKiri 的日志是 UTF-16
stat -f '%Sm %N'               # atime 取证
```

`ffmpeg` 一定用 Homebrew 装的正式版。本机踩过一次坑：`~/.local/bin/ffmpeg`
指向 nvm 里 2023 年的 `ffmpeg-static`，PATH 顺序让这个旧版本压住了新版 ——
行为不可预期，而且切 node 版本就消失。
