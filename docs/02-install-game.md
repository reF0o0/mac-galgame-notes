# 02 · 把游戏装进去

## 目录布局：游戏不进容器

先在脑子里定好一件事：**游戏本体放在外面，容器只放一个软链接**。

```
~/Games/<游戏名>/                        游戏本体，几十 GB
    .container                           标记：这个游戏用哪个容器
    .launch-exe                          标记：主程序 exe 的文件名

~/Applications/Sikarugir/<容器>.app      容器，约 1.5 GB
    Contents/SharedSupport/prefix/drive_c/Games/<链接名>  ->  指向 ~/Games/<游戏名>
```

这样做的三个好处：

1. 容器不会膨胀，备份容器快照很便宜。
2. 同一个游戏可以在不同容器之间切换（有些游戏换个引擎就跑起来了），只改链接。
3. 游戏目录可以随便搬，只要同步改链接。

代价是**不能随便移动或改名游戏目录**，链接断了游戏就启动不了。要搬就用
`galgame-menu.sh`，它会重建链接。

## 拿到压缩包之后

### 先看它到底是什么

资源包的伪装花样基本就那几种，先确认类型再动手：

```bash
file 可疑文件.mp4          # 看真实类型，别看后缀
xxd -l 16 可疑文件.mp4     # magic：Rar! = RAR，PK = ZIP，ftypmp42 也可能是假的
```

常见情况：

| 现象 | 真身 |
|---|---|
| `.mp4` / `.txt` / `.00` 后缀，`file` 说是 RAR/ZIP | 改名的压缩包 |
| ZIP 里套一个巨大 RAR | 两层，先解 ZIP 再解 RAR |
| `7z l` 说 `Cannot open encrypted archive` | 文件头也加密了，必须先有密码 |

### 解压密码

密码永远在下载来源的页面正文里（`解压密码：xxx`），不在文件里。
要点：

- **RAR5 的密码区分大小写、逐字符精确匹配**，标点和全角半角都算。
  强烈建议原样复制，不要凭记忆敲。
- **中文密码要用 `unar`，不要用 `7zz`。** `7zz` 对非 ASCII 密码会误报
  「密码错误」，会让人以为密码不对、白试半天。

```bash
unar -p '中文密码' 包.rar          # 正确姿势
lsar -p '中文密码' 包.rar           # 只看清单，不解压
```

`7zz x` 只在纯 ASCII 密码且非加密文件头时才省心。RAR5 加密头 + 中文密码这套组合，
`unar` 是唯一稳定能过的。

### 解到哪

直接解到 `~/Games/<游戏名>/`，并且**把多出来的嵌套目录拍平** ——
很多包解开是 `<游戏名>/<游戏名>/...` 这样两层，游戏主程序应该直接躺在
`~/Games/<游戏名>/` 这一层，中间不要再夹一层。

用 `lsar` 先看清单能省掉一次解压：

```bash
lsar -p 密码 包.rar | head -30
```

### 校验

解压完对一下文件数，别带着残包往下走：

```bash
lsar -p 密码 包.rar | wc -l
find ~/Games/<游戏名> -type f | wc -l
```

## 接进容器

```bash
source tools/mac/guest-env.sh <容器名>

# 1. 在虚拟 C 盘里建软链接
ln -sfn "$HOME/Games/<游戏名>" "$WINEPREFIX/drive_c/Games/<链接名>"

# 2. 告诉容器启动哪个 exe（路径是容器内部的，用正斜杠）
/usr/libexec/PlistBuddy -c "Set ':Program Name and Path' '/Games/<链接名>/游戏.exe'" \
  "$SIKA_APP/Contents/Info.plist"
```

改之前先备份一下 `Info.plist`，出问题好回滚：

```bash
cp "$SIKA_APP/Contents/Info.plist" "$SIKA_APP/Contents/Info.plist.bak"
```

## 用启动器管多个游戏

如果每个游戏一个容器，直接双击对应 app 就行。如果想一个容器挂多个游戏，
用 `galgame-menu.sh`：

```bash
./tools/mac/galgame-menu.sh list             # 列出 ~/Games 里的游戏
./tools/mac/galgame-menu.sh plan  游戏名      # 只说要改什么
./tools/mac/galgame-menu.sh launch 游戏名     # 切过去并启动
```

它做的事：找游戏目录 → 读 `.container` 决定用哪个容器 → 必要时建软链接 →
改 `Info.plist` 的启动目标 → `open` 容器。

两个标记文件（都放游戏目录下，纯文本，第一行有效）：

```
.container     /Users/you/Applications/Sikarugir/某容器.app
.launch-exe    游戏主程序.exe
```

`.launch-exe` 不写也行，脚本会按名字打分猜（带 `chs` / `汉化` 的优先，
和文件夹同名的次之），但猜到安装器或补丁工具上就麻烦了，**建议手写**。

### 同时只能跑一个

Wine 一个瓶子里同时跑两个游戏会互相抢。`galgame-menu.sh` 检测到还有游戏在跑
会直接拒绝启动第二个，并列出是谁：

```
错误: 还有游戏没退出（SenrenBankaCHS.exe）。先关掉它的游戏窗口，再启动别的。
```

真要并行就分开用两个容器。

## 首次启动

- **冷启动慢是正常的。** 一个几 GB 的 `.xp3` 游戏，第一次加载要 30 到 60 秒。
  `open` 完立刻 `winlist` 查不到窗口不代表启动失败，等一会儿再查。
- 界面第一次可能弹一个授权框（麦克风 / 摄像头 / 网络卷）。**这种系统弹窗会把
  游戏卡在白屏**，点「不允许」就行 —— 文字游戏不需要麦克风。
- 有些整合版第一次启动会问语言（UI / Main Text / Sub Text 三栏），
  三栏都选简体中文再确定。窗口菜单栏里通常也有 `Language` 可以改。
- 退出别直接 `kill`，走游戏自己的「退出游戏」。Wine 会话没干净收尾的话，
  下一次启动可能看到残留进程。

清理残留会话：

```bash
source tools/mac/guest-env.sh <容器名>
"$WINESERVER" -k
pkill -9 -f "Sikarugir/<容器名>.app"
```

## 顺手记一下每个游戏的信息

装完就写进 `.launch-exe` 之外的一个随便什么笔记里，尤其是**引擎、容器引擎、
关键开关**这三项。以后出问题要对照，靠回忆很容易配错。本仓库的
[05-observed-games.md](05-observed-games.md) 就是这么攒出来的。
