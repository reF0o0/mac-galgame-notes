#!/bin/zsh
# galgame-menu.sh -- 多游戏共用一个 / 多个容器的启动后端
#
# Sikarugir 的每个 .app 只记得「一个」启动目标（Info.plist 里的
# Program Name and Path）。游戏一多就有两种做法：
#   A. 每个游戏一个容器 —— 干净但每个都要占 1.5 GB，而且各个瓶子的
#      注册表 / 字体 / 组件要各配一遍；
#   B. 一个容器挂多个游戏 —— 省地方，但每次换游戏都得改 Info.plist。
# 这个脚本走的是 B，并且把「改配置」这一步自动化掉：
# 它按游戏名去 ~/Games/<游戏名> 找目录，读目录里的标记文件决定用哪个
# 容器、启动哪个 exe，然后在容器里建软链接、改 Info.plist、启动。
#
#   galgame-menu.sh list             列出 ~/Games 里的游戏
#   galgame-menu.sh plan   <游戏名>  只说要做什么，什么都不改
#   galgame-menu.sh launch <游戏名>  真的切过去并启动
#
# 游戏目录里可放两个标记文件（都是纯文本，第一行有效）：
#   .container     容器 .app 的绝对路径。没有就用默认容器。
#   .launch-exe    主程序 exe 的文件名（相对游戏目录）。
#                  没有就按名字打分猜（汉化版 > 与目录同名 > 含目录名）。
#
# 环境变量 GALGAME_GAMES_ROOT 可以覆盖游戏根目录（默认 ~/Games）。
#
# 配一个 GUI：用 Script Editor 打开 tools/mac/launcher.applescript 导出成
# .app 扔进 /Applications 即可。
emulate -L zsh
setopt null_glob
set -u

GAMES_ROOT="${GALGAME_GAMES_ROOT:-$HOME/Games}"
DEFAULT_WRAPPER="$HOME/Applications/Sikarugir/千恋＊万花.app"

die() { print -ru2 -- "错误: $*"; exit 1 }

# 游戏用哪个容器：游戏目录下放一个 .container 文件写容器路径即可单独指定，
# 没有的话就用默认容器
wrapper_for() {
  local dir="$1" marker="$1/.container" app
  if [[ -f "$marker" ]]; then
    app="$(head -n 1 "$marker" | tr -d '\r')"
    [[ -d "$app" ]] && { print -r -- "$app"; return 0 }
    print -ru2 -- "警告: $marker 里写的容器不存在（$app），改用默认容器"
  fi
  print -r -- "$DEFAULT_WRAPPER"
}

# 猜游戏主程序，返回 exe 文件名
pick_exe() {
  local dir="$1" name="${1:t}"
  local hint="$dir/.launch-exe"
  if [[ -f "$hint" ]]; then
    local h
    h="$(head -n 1 "$hint" | tr -d '\r')"
    [[ -n "$h" && -f "$dir/$h" ]] && { print -r -- "$h"; return 0 }
  fi

  local -a cands
  local f lb
  for f in "$dir"/*.exe(N); do
    lb="${${f:t}:l}"
    # 安装器 / 卸载器 / 配置工具不是主程序
    [[ "$lb" =~ '(unins|uninst|setup|install|config|patch|update|register|readme|crash|launcher|tool)' ]] && continue
    [[ "${f:t}" == *卸载* || "${f:t}" == *设置* || "${f:t}" == *补丁* || "${f:t}" == *说明* ]] && continue
    cands+=( "$f" )
  done
  (( ${#cands} )) || cands=( "$dir"/*.exe(N) )
  (( ${#cands} )) || return 1

  # 打分挑最像主程序的：汉化/中文版 > 与文件夹同名 > 名字里含文件夹名
  local best="" bestscore=-1 sc base noext
  for f in "${cands[@]}"; do
    base="${f:t}"
    lb="${base:l}"
    noext="${base:r}"
    sc=0
    [[ "$lb" =~ '(chs|hanhua|汉化|_cn|cn\.exe|zh)' ]] && sc=$(( sc + 4 ))
    [[ "${noext:l}" == "${name:l}" ]] && sc=$(( sc + 3 ))
    [[ "$base" == *"$name"* ]] && sc=$(( sc + 1 ))
    (( sc > bestscore )) && { bestscore=$sc; best="$base" }
  done
  print -r -- "$best"
}

# 容器里已经指向该游戏的软链接名（有就复用，不另建）
link_for_game() {
  local games_dir="$1" target="$2" l
  for l in "$games_dir"/*(N); do
    [[ -L "$l" ]] || continue
    [[ "$(readlink "$l")" == "$target" ]] && { print -r -- "${l:t}"; return 0 }
  done
  return 1
}

slugify() {
  local s="$1" out
  out="$(print -r -- "$s" | LC_ALL=C tr -dc 'A-Za-z0-9')"
  # 全是假名/汉字时，剔完可能只剩个位数字（比如「アマカノ3」→「3」），这种就别用
  (( ${#out} < 3 )) && out="game$(print -r -- "$s" | md5 | cut -c1-6)"
  print -r -- "$out"
}

ensure_link() {
  local games_dir="$1" dir="$2" link slug
  if link="$(link_for_game "$games_dir" "$dir")"; then
    print -r -- "$link"
    return 0
  fi
  slug="$(slugify "${dir:t}")"
  [[ -e "$games_dir/$slug" ]] && slug="${slug}-$(print -r -- "$dir" | md5 | cut -c1-4)"
  mkdir -p "$games_dir"
  ln -sfn "$dir" "$games_dir/$slug"
  print -r -- "$slug"
}

# 当前正在跑的 Windows 程序名（排除 wine 自己的系统进程）
running_wine_apps() {
  ps -eo args= 2>/dev/null | awk '
    /winetemp/ && /\.exe / {
      if ($0 ~ /C:\\windows/) next
      n = split($1, a, "/"); name = a[n]
      if (name ~ /\.exe$/) { if (!seen[name]++) print name }
    }'
}

do_launch() {
  local mode="$1" want="$2"
  local d exe link target app prefix c_games plist
  local found=0

  for d in "$GAMES_ROOT"/*(/N); do
    [[ "${d:t}" == .* ]] && continue
    [[ "${d:t}" == "$want" ]] || continue
    found=1
    app="$(wrapper_for "$d")"
    prefix="$app/Contents/SharedSupport/prefix"
    c_games="$prefix/drive_c/Games"
    plist="$app/Contents/Info.plist"
    [[ -d "$app" ]] || die "找不到容器：$app"
    [[ -f "$plist" ]] || die "容器里没有 Info.plist：$plist"
    exe="$(pick_exe "$d")" || die "在「${d:t}」里没找到主程序 exe。可以在这个目录下放一个 .launch-exe 文件，第一行写 exe 的文件名。"
    local link_note="已有"
    if [[ "$mode" == plan ]]; then
      if link="$(link_for_game "$c_games" "$d")"; then
        target="/Games/$link/$exe"
      else
        link="$(slugify "${d:t}")"
        link_note="将新建"
        target="/Games/$link/$exe"
      fi
    else
      link="$(ensure_link "$c_games" "$d")"
      target="/Games/$link/$exe"
    fi

    local -a running
    running=( ${(f)"$(running_wine_apps)"} )
    running=( ${running:#} )
    if (( ${#running} )); then
      if (( ${running[(I)$exe]} )); then
        if [[ "$mode" == plan ]]; then
          print -r -- "注意: 「${d:t}」已经在运行"
        else
          print -r -- "「${d:t}」已经在运行，把窗口切到前面。"
          open "$app"
        fi
        return 0
      fi
      [[ "$mode" == plan ]] || die "还有游戏没退出（${(j:、:)running}）。先关掉它的游戏窗口，再启动别的。"
    fi

    if [[ "$mode" == plan ]]; then
      print -r -- "游戏目录: $d"
      print -r -- "所在容器: $app"
      print -r -- "容器链接: $c_games/$link -> $d（$link_note）"
      print -r -- "启动目标: $target"
      print -r -- "配置文件: $plist"
      return 0
    fi

    plutil -replace "Program Name and Path" -string "$target" "$plist" \
      || die "写容器配置失败：$plist"
    [[ -f "$d/.launch-exe" ]] || print -r -- "$exe" > "$d/.launch-exe"
    open "$app" || die "启动容器失败"
    print -r -- "已启动「${d:t}」($target)"
    return 0
  done

  (( found )) || die "~/Games 里没有叫「$want」的游戏"
}

[[ -d "$DEFAULT_WRAPPER" ]] || die "找不到默认容器：$DEFAULT_WRAPPER"

case "${1:-list}" in
  list)
    for d in "$GAMES_ROOT"/*(/N); do
      [[ "${d:t}" == .* ]] && continue
      print -r -- "${d:t}"
    done
    ;;
  plan)
    [[ $# -ge 2 ]] || die "用法: $0 plan <游戏名>"
    do_launch plan "$2"
    ;;
  launch)
    [[ $# -ge 2 ]] || die "用法: $0 launch <游戏名>"
    do_launch launch "$2"
    ;;
  *)
    die "未知命令：$1（可用: list / plan / launch）"
    ;;
esac
