#!/bin/zsh
# 把某个容器的 GStreamer 环境导入当前 shell，用来验证"这个影片文件到底能不能解"。
# 用 `source` 执行，不要直接跑：
#
#   source tools/mac/gst-env.sh ATRI
#   GST_DEBUG=2 "$GSTLAUNCH" -q filesrc location=x.wmv ! decodebin ! fakesink
#
# 为什么非要这样跑：宿主机自己的 ffmpeg 自带完整 libav，能解 Wine 解不了的东西
# （WMA Pro 就是典型），照着它查永远显示"文件没问题"。游戏实际用的是容器
# Frameworks 里那套 GStreamer，只有它说的话算数。
#
# 变量取值和 guest-env.sh 同源，都是从容器自己的 Contents/MacOS/Sikarugir
# 启动脚本里反推的 —— 少一个就会加载错 dylib，结论也就不作数了。

if [[ -z "${1:-}" ]]; then
  print -ru2 -- "用法: source tools/mac/gst-env.sh <容器名>   # 例如 ATRI"
  print -ru2 -- "现有容器："
  ls -1 "$HOME/Applications/Sikarugir" 2>/dev/null | sed 's/\.app$//' | sed 's/^/  /' >&2
  return 1
fi

SIKA_APP="$HOME/Applications/Sikarugir/$1.app"
if [[ ! -d "$SIKA_APP" ]]; then
  print -ru2 -- "找不到容器：$SIKA_APP"
  return 1
fi

export SIKA_APP
export SIKA_SUPPORT="$SIKA_APP/Contents/SharedSupport"
export SIKA_FRAMEWORKS="$SIKA_APP/Contents/Frameworks"
export SIKA_GST="$SIKA_FRAMEWORKS/GStreamer.framework/Libraries"

export DYLD_FALLBACK_LIBRARY_PATH="$SIKA_SUPPORT/wine/lib:$SIKA_SUPPORT/wine/lib64:$SIKA_FRAMEWORKS:$SIKA_GST"
export GST_PLUGIN_PATH="$SIKA_GST/gstreamer-1.0"
export GST_PLUGIN_SYSTEM_PATH_1_0="$SIKA_GST/gstreamer-1.0"

# 日文区域：KiriKiri 系游戏靠这个决定读资源时用哪套编码
export LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

export GSTLAUNCH="$SIKA_FRAMEWORKS/GStreamer.framework/Versions/1.0/bin/gst-launch-1.0"
export GSTINSPECT="$SIKA_FRAMEWORKS/GStreamer.framework/Versions/1.0/bin/gst-inspect-1.0"

print -r -- "容器: $1"
print -r -- "  GStreamer : $(basename "$(dirname "$(dirname "$GSTLAUNCH")")")"
print -r -- "  命令      : \$GSTLAUNCH / \$GSTINSPECT"
