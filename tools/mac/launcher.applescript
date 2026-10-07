-- 给 galgame-menu.sh 套一个 GUI：列出 ~/Games 里的游戏，选一个启动。
-- 用「脚本编辑器」打开本文件，文件 → 导出 → 文件格式选「应用程序」，
-- 存成 /Applications/Galgame 启动器.app 即可。
--
-- 注意：下面的路径要改成你自己的 galgame-menu.sh 位置。

set helperPosix to (POSIX path of (path to home folder)) & "Games/.launcher/galgame-menu.sh"
set helperQuoted to quoted form of helperPosix

try
	set rawList to do shell script helperQuoted & " list"
on error errMsg
	display dialog "读取游戏列表失败：" & errMsg buttons {"好"} default button 1 with icon stop
	return
end try

if rawList is "" then
	display dialog "~/Games 里还没有游戏。" & return & return & "把游戏文件夹放进 ~/Games，再打开这个启动器即可。" buttons {"好"} default button 1 with icon note
	return
end if

set theGames to paragraphs of rawList
set chosen to choose from list theGames with prompt "想玩哪一个？" with title "Galgame 启动器" default items {item 1 of theGames} OK button name "启动" cancel button name "取消"
if chosen is false then return

set gameName to item 1 of chosen
try
	set resultText to do shell script helperQuoted & " launch " & quoted form of gameName
	display notification resultText with title "Galgame 启动器"
on error errMsg
	display dialog "启动「" & gameName & "」失败：" & errMsg buttons {"好"} default button 1 with icon stop
end try
