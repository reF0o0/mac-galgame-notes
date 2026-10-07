#!/bin/zsh
# 把一个 Sikarugir 容器的 Wine 环境导入当前 shell。
# 用 `source` 执行，不要直接跑：
#
#   source guest-env.sh 千恋＊万花
#
# 之后就能直接用 $WINE / $WINEBOOT / $WINESERVER 在这个瓶子里干活
# （装组件、改注册表、手工跑某个 exe），不用去翻 Sikarugir 的内部路径。
#
# 这些变量的取值是从容器自己的 Contents/MacOS/Sikarugir 启动脚本里反推的，
# 和它内部跑 wine 时必须一模一样，少一个就会加载错 dylib。
#
# 注意：renderer 目录的存在与否取决于该容器建的时候开了哪些后端，
# 这里一律全部列上——不存在的目录只是被忽略，不会报错。

if [[ -z "${1:-}" ]]; then
  print -ru2 -- "用法: source guest-env.sh <容器名>   # 例如 千恋＊万花"
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

export WINEPREFIX="$SIKA_SUPPORT/prefix"
export WINEDLLPATH="$SIKA_FRAMEWORKS/renderer/cnc_ddraw/wine:$SIKA_FRAMEWORKS/renderer/d9vk/wine:$SIKA_FRAMEWORKS/renderer/dxvk/wine"
export DYLD_FALLBACK_LIBRARY_PATH="$SIKA_SUPPORT/wine/lib:$SIKA_SUPPORT/wine/lib64:$SIKA_FRAMEWORKS:$SIKA_GST"
export GST_PLUGIN_PATH="$SIKA_GST/gstreamer-1.0"
export VK_DRIVER_FILES="$SIKA_APP/Contents/Resources/vulkan/icd.d/MVK_CW_icd.json"
export W_NO_WIN64_WARNINGS=1

# 日文区域：KiriKiri 系游戏靠这个决定读资源时用哪套编码
export LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

export WINE="$SIKA_SUPPORT/wine/bin/wine"
export WINEBOOT="$SIKA_SUPPORT/wine/bin/wineboot"
export WINESERVER="$SIKA_SUPPORT/wine/bin/wineserver"

print -r -- "容器: $1"
print -r -- "  prefix : $WINEPREFIX"
print -r -- "  wine   : $("$WINE" --version 2>/dev/null)"
print -r -- "  区域   : $LANG"
