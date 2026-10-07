# 05 · 实测记录：7 部作品

同一台机器（Apple M5 / macOS 26.7.1）上陆续装完并验证过能玩到正片的作品。
配置各不相同，**不要照抄**——这张表的价值在于说明"为什么没有一份通用配置"。

## 一览

| 作品 | 引擎 | 容器引擎 | D9VK | DXVK | MOLTENVKCX | Program Flags | 本体 |
|---|---|---|---|---|---|---|---|
| 千恋＊万花 | KiriKiri Z | WineCX 24.0.7 | 0 | 0 | 1 | 空 | 12 GB |
| ATRI -My Dear Moments- | KiriKiri Z | wine-10.0 | 0 | 0 | 1 | 空 | 3.9 GB |
| アマカノ3 | `.pfs` + E-mote | wine-10.0 | **1** | 0 | 0 | 空 | 11 GB |
| 不败世界与终焉之花 | KiriKiri Z | wine-10.0 | **1** | 0 | 0 | 空 | 4.4 GB |
| 灵感满溢的甜蜜创想 | KiriKiri Z | wine-10.0 | **1** | 0 | 0 | 空 | 7.8 GB |
| 可塑性记忆 | KiriKiri 系 | wine-10.0 | **1** | 0 | 1 | 空 | 1.5 GB |
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

---

## アマカノ3

- **引擎**：`.pfs` 容器，配合 E-mote 动态立绘，强制 D3D11。跟 KiriKiri 是两条路。
- **容器**：wine-10.0，**必须新引擎**——Wine 9 那个容器跑不起来。
- **配置**：`D9VK=1`，`MOLTENVKCX=0`。

这是本仓库里唯一需要"另建一个更新引擎的容器"的作品，也是 D9VK 的第一次登场。

**踩坑记录**：装之前要先确认它到底走哪条媒体链。这台机器上出现过
「`fixme:mfplat:topology_loader_Load ... stub!` 被当成别的游戏的日志」这种
串台，因为不同游戏的日志混在同一个目录里。**查日志前先确认你查的是哪个文件**。

---

## 不败世界与终焉之花

- **引擎**：KiriKiri Z（`KarenaiSekai.exe`）。
- **容器**：wine-10.0。**配置**：`D9VK=1`。

### 坑：汉化重打包带来的文件名编码错误

汉化组重打包的时候把一批内部文件名写成了 **GBK**，而 KiriKiri 是按 **Shift-JIS**
解析这些名字的，于是找不到资源。修法是批量把 `data.xp3` 里的文件名从 GBK 转成
Shift-JIS。

**改之前一定要留原档**：改过的 `data.xp3` 之外放一份 `data.xp3.pristine`。
以后如果再遇到"同一个包"，先拿大小和 `.pristine` 对一遍 —— 对得上说明是重复包，
**重装反而会退回有 bug 的原档**。

---

## 灵感满溢的甜蜜创想

- **引擎**：KiriKiri Z（`hamidashi_chs.exe`）。**容器**：wine-10.0，`D9VK=1`。

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

### 遗留

影片能"播"（占满片长再继续剧情），但**画面在 Wine 下画不出来**，那几秒是白屏，
点一下可以跳过。用纯红影片做过标记测试，确认是真没渲染，不是截图问题。

---

## 可塑性记忆

- **容器**：wine-10.0。**配置**：`D9VK=1`（**必需**），`MOLTENVKCX=1`。

**典型症状**：默认的 OpenGL 后端只出蓝屏或黑屏。开 D9VK 之后就正常了。

这是"能启动但画面纯色 → 换后端"这条经验最干净的一个例子。排查时先确认进程
活着、CPU 有占用（说明不是卡在等什么），然后一个后端一个后端换。

---

## 与奴隶的生活（Teaching Feeling V4.0.6）

- **引擎**：**不是** KiriKiri。目录里有 `chrome_100_percent.pak`、`icudtl.dat`、
  `libEGL.dll`、`LICENSES.chromium.html`、`locales/` —— 这是
  **Electron 打包的 TyranoScript**。
- **容器**：wine-10.0。**配置**：`DXVK=1` + `MOLTENVKCX=1`，
  `Program Flags = --no-sandbox --in-process-gpu`。

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
