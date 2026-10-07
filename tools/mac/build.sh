#!/bin/zsh
# 编译 mac/ 下的两个小工具到同目录。
#   winlist  列窗口 + 窗口号
#   wclick   合成鼠标点击 / 按键
#
# 首次运行需要给「终端」（或你用的 host 程序）授予「屏幕录制」权限，
# 否则 winlist 拿不到窗口标题，wclick 的事件也可能被丢掉。
set -eu
cd "$(dirname "$0")"

cc -O2 -o winlist winlist.c -framework CoreGraphics -framework CoreFoundation
swiftc -O -o wclick wclick.swift

echo "built: $(pwd)/winlist"
echo "built: $(pwd)/wclick"
echo
echo "试一下： ./winlist | grep owner=wine"
