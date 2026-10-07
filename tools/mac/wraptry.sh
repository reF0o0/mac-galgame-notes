#!/bin/zsh
# 启动一个容器、等一会儿、把它的窗口截下来。
# 排查「白屏 / 黑屏 / 花屏」的时候这是最主要的取证手段：
# 不问它渲染得对不对，直接看像素。
#
# 用法: wraptry.sh <容器名> <输出png> [等待秒数]
#
# 依赖同目录编译出来的 winlist；等待时间默认 25 秒——Wine 冷启动一个
# 几 GB 的 xp3 游戏经常要 30~60 秒，太早截图会截到空窗口。
set -u

HERE="${0:A:h}"
NAME="$1"
OUTP="$2"
WAIT="${3:-25}"
APP="$HOME/Applications/Sikarugir/$NAME.app"

[[ -d "$APP" ]] || { print -ru2 -- "没有这个容器：$APP"; exit 1 }
[[ -x "$HERE/winlist" ]] || { print -ru2 -- "先跑 build.sh 编译 winlist"; exit 1 }

"$APP/Contents/MacOS/Sikarugir" >/tmp/wraptry_stdout.log 2>&1 &
print -r -- "wrapper pid=$!"
sleep "$WAIT"

"$HERE/winlist" | grep -E 'owner=wine' || true
W=$("$HERE/winlist" | grep 'owner=wine' | head -1 | sed -E 's/win=([0-9]+).*/\1/')
if [[ -n "$W" ]]; then
  screencapture -x -l "$W" "$OUTP" && print -r -- "wrote $OUTP size=$(stat -f%z "$OUTP")"
else
  print -ru2 -- "没有 wine 窗口（还没起来？或者启动就退了，看 /tmp/wraptry_stdout.log）"
fi
