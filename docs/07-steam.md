# 07 · 正版 Steam 路线

## 先说一个常见误解

**买了 Steam 正版不等于不用 Wine。** 绝大多数日系 galgame 在 Steam 上的平台字段
就是 `windows: True, mac: False`（千恋＊万花、ATRI、CLANNAD、Summer Pockets、
STEINS;GATE 之类全是）。所以正版路线和 Wine 封装是叠加关系，不是替代关系。

正版的好处不在"省掉封装"，在于**变量少**：没有二次封装启动器、没有破解补丁、
存档路径干净、版本对得上。同一款游戏的整合版能折腾一整天的问题，官方版可能
一次就过。字符编码、字体乱码、影片重压这类坑，九成来自汉化组重打包的过程。

## 两条路

### 路线 A：瓶子里装完整 Steam 客户端

推荐这条。一次装好以后，所有 Steam 上的 galgame 都能复用同一个瓶子，成就、
云存档、自动更新都正常。

```bash
source tools/mac/guest-env.sh <容器名>

# 1. 下载并安装 Windows 版 Steam
curl -L -o ~/Downloads/SteamSetup.exe \
  https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe
"$WINE" ~/Downloads/SteamSetup.exe
```

安装路径**保持默认**的 `C:\Program Files (x86)\Steam`，别改。装完 Steam 会自己
更新一次，要下几百 MB，慢是正常的。

登录窗口黑屏或者纯白的话，加参数重启：

```bash
"$WINESERVER" -k
"$WINE" "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steam.exe" -no-cef-sandbox
```

`-no-cef-sandbox` 是 Wine 下跑 Steam 的老朋友，界面的 Chromium 沙箱在 Wine 里
经常起不来。

然后让容器直接启动 Steam：

```bash
/usr/libexec/PlistBuddy -c "Set ':Program Name and Path' '/Program Files (x86)/Steam/steam.exe'" \
  "$SIKA_APP/Contents/Info.plist"
```

以后双击容器就是在瓶子里开 Steam。

### 路线 B：steamcmd 只拉文件

不装客户端，用 `steamcmd` 把游戏文件拉下来，直接跑 exe。

优点：占用小得多，不用养一个常驻的 Steam 客户端。缺点：如果游戏**依赖 Steam
进程活着才能启动**（很多商业 galgame 会检查），还得补一步；成就和云存档也享受不到。

对本仓库的场景（2D 文字游戏）A 更好——省下来的那点内存，不值得换来一堆不确定。

## 把游戏库放到容器外面

Windows 版 Steam 默认把游戏装在 `C:\Program Files (x86)\Steam\steamapps\`，
也就是**瓶子内部**。一个 10 GB 的游戏就这么进了容器，容器从 1.5 GB 涨到 12 GB，
备份快照变得很贵。

两种做法：

**做法一（推荐）**：在瓶子的 `drive_c` 里建一个库目录，然后让 Steam 把它加为
第二个库位置：

```bash
mkdir -p "$WINEPREFIX/drive_c/Games/SteamLibrary"
ln -sfn "$HOME/Games/SteamLibrary" "$WINEPREFIX/drive_c/Games/SteamLibrary"
```

Steam 里 `设置 → 存储 → 添加库文件夹`，选 `C:\Games\SteamLibrary`。之后新装的
游戏都在外面，备份容器时只备份那 1.5 GB。

**做法二**：装完游戏之后把 `steamapps` 整个搬出去再做软链接。麻烦，而且 Steam
对库位置的元数据比较敏感，不如一开始就规划好。

## 一些会遇到的

**代理**。Wine 里的程序**不继承** macOS 的系统代理设置。Steam 客户端里要单独配
一次（`设置 → 下载 → 代理服务器`）。如果登录界面一直转圈，先想到这个。

**首次启动卡的授权框**。跟其他 Wine 程序一样，第一次跑会弹麦克风之类的授权框，
而且它可能弹在游戏窗口后面。点掉。

**免费体验版**。不少作品在 Steam 上有免费 Demo（千恋＊万花是 appid 1221010）。
想零成本验证一套容器配置能不能跑，先拿 Demo 试是最省事的办法。

**官方 18+ 补丁**。部分在 Steam 上做了内容删减的作品，发行商会免费放出补丁
（例如 NekoNyan 的页面）。这类补丁是官方的、合法的，直接在发行商页面下载安装。
注意它恢复的是内容，**画面依然是打码的**——日本法规的要求，官方不可能提供无码。

## 已经验证过的

本机在 wine-10.0 的容器里跑通了 Windows 版 Steam 的安装和登录，账号库里的
Windows-only 作品可以正常下载安装。项目里没走完的部分是：装完之后游戏本身在
该容器里的渲染配置还是得按 [03-container-tuning.md](03-container-tuning.md)
一台一台调——Steam 只解决"怎么把文件拿到手"，不解决"它能不能出画面"。
