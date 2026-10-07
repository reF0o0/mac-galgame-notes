# 08 · 存档、备份与回滚

改游戏、试补丁、换容器之前，**先把存档拿出来**。这一节的所有内容都是因为
某次没备份而写的。

## 存档在哪

| 引擎 | 位置 |
|---|---|
| KiriKiri | 游戏目录下的 `savedata/`（和游戏文件放一起） |
| TyranoScript | 游戏目录下的 `*.sav` |
| Ren'Py | `~/Library/RenPy/<游戏名>/`，或游戏目录旁边的 `saves/` |

KiriKiri 的 `savedata/` 里通常有这几类：

- `datasu.ksd` —— **全局存档**：设置（音量、文字速度）、CG / 场景解锁标记、
  全局变量。这个文件决定"画廊里有多少张图"
- `datasu~.ksd` —— 同一份的备份副本，游戏自己维护的
- `data_anchor.ksd` —— anchor 存档
- 若干快速存档 —— 具体进度

**关键认知**：`datasu.ksd` 里存着解锁进度，不是可有可无的配置文件。
拿别人的全局存档覆盖过来，画廊全开，但你的设置也没了。

## 备份

最小操作，改任何东西之前先做一次：

```bash
cp -R ~/Games/<游戏名>/savedata \
      ~/Documents/galgame-backup/<游戏名>-savedata-$(date +%Y%m%d)
```

顺便把要动的东西也留个原档。比如改过的归档旁边放一份 `.pristine`：

```bash
cp data.xp3 data.xp3.pristine
```

容器侧的配置也一样，改 `Info.plist` 之前：

```bash
cp "$SIKA_APP/Contents/Info.plist" "$SIKA_APP/Contents/Info.plist.bak-$(date +%Y%m%d)"
cp "$WINEPREFIX/user.reg"          "$WINEPREFIX/user.reg.bak-$(date +%Y%m%d)"
```

`user.reg` 是那个瓶子的注册表，字体替换、DLL 覆盖全在里面。改坏了没有它就得
从头配一遍。

## 回滚

判断"换回来是不是真的换成功了"，**不要靠感觉**，做字节比对：

```bash
md5 ~/Games/<游戏名>/savedata/datasu.ksd \
    ~/Documents/galgame-backup/<游戏名>-savedata-20260919/datasu.ksd
```

两个哈希一样，才算换回去了。文件大小对不上就说明换的是另一个东西。

## 外来存档

网上流传的「全 CG 存档」「完美存档」能不能用，取决于引擎：

**能用的（KiriKiri）**：直接把 `datasu.ksd` 换掉就行。它里面是一堆变量和
`cg_*` 解锁标记，格式跟着游戏版本走，版本对得上就能读。用它可以解锁画廊来看
CG 有没有装对——比"玩到那一幕"快得多。

**不能用的（TyranoScript）**：这类引擎对存档做**哈希校验**，别人分享的存档跟
当前游戏数据对不上，校验失败就无限弹错误框、卡在 loading。这不是存档损坏，
是它本来就不认外来存档。

修法只有一个：把外来的移走，从新游戏开始。

```bash
mkdir -p ~/Games/<游戏名>/.backup-original-saves
mv ~/Games/<游戏名>/*.sav ~/Games/<游戏名>/.backup-original-saves/
```

**代价要提前说清楚**：分享者的进度和已解锁内容全没了。没有绕过哈希的正当做法，
别在这上面花时间。

## 一个真实的操作顺序

拿《千恋＊万花》装去码补丁那次举例，正确顺序是这样：

1. 整个 `savedata/` 拷一份出去
2. 记下当前全局存档的字节数和变量数（`md5` + `stat -f%z`），作为"我的那份"的指纹
3. 装上全 CG 存档 → 启动游戏 → 从画廊随机点几个 CG，看效果
4. 效果确认完，把**自己的** `datasu.ksd` 和 `datasu~.ksd` 换回去
5. 逐字节比对确认换对了

第 2 步和第 5 步是同一次操作的首尾。中间那段时间你用的是别人的全局存档，
你的快速存档和 anchor 从头到尾没被动过 —— 这一点也要在动手前就确认清楚，
免得回滚的时候担心"是不是把进度也弄丢了"。

## 换容器 / 换机器

存档在游戏目录里，所以**游戏搬走存档就跟着走**，不用单独处理。

换容器的情况：容器里只有软链接指向游戏目录，不存任何存档。所以换容器只要
重建软链接、改 `Info.plist`，存档不受影响。

真正会丢的是**瓶子的配置**：字体替换、DLL 覆盖、装的组件。这些在
`$WINEPREFIX/user.reg` 和 `system32/` 里，换容器就得重配。所以容器本身也值得
备份一份快照——见 [09-disk-and-cleanup.md](09-disk-and-cleanup.md)。
