// winlist -- 列出当前屏幕上的窗口（窗口号 / 归属进程 / 尺寸 / 位置）
//
// 为什么需要它：Wine 跑起来的 galgame 窗口在 macOS 上没有可靠的查询手段。
//   - `osascript` 的 System Events 经常看不到非原生窗口；
//   - `screencapture -l <窗口号>` 需要一个窗口号，而这个号只能从
//     CGWindowListCopyWindowInfo 拿；
//   - 锁屏 / 屏幕休眠时也能用（只要进程有屏幕录制权限）。
// 拿到窗口号之后就能 `screencapture -x -l <号> out.png` 精确截那一扇窗，
// 不必截整屏再裁。
//
// 编译：cc -O2 -o winlist winlist.c -framework CoreGraphics -framework CoreFoundation
// 用法：./winlist | grep 'owner=wine'

#include <CoreGraphics/CoreGraphics.h>
#include <CoreFoundation/CoreFoundation.h>
#include <stdio.h>

static void dump(const void *value, void *ctx)
{
    CFDictionaryRef d = (CFDictionaryRef)value;
    CFStringRef owner = CFDictionaryGetValue(d, kCGWindowOwnerName);
    CFStringRef name = CFDictionaryGetValue(d, kCGWindowName);
    CFNumberRef layer = CFDictionaryGetValue(d, kCGWindowLayer);
    CFDictionaryRef bounds = CFDictionaryGetValue(d, kCGWindowBounds);
    CFNumberRef pid = CFDictionaryGetValue(d, kCGWindowOwnerPID);
    CFNumberRef num = CFDictionaryGetValue(d, kCGWindowNumber);
    int l = -1, p = -1, n = -1;
    double x = 0, y = 0, w = 0, h = 0;
    char ob[256] = "", nb[256] = "";

    if (owner) CFStringGetCString(owner, ob, sizeof(ob), kCFStringEncodingUTF8);
    if (name)  CFStringGetCString(name, nb, sizeof(nb), kCFStringEncodingUTF8);
    if (layer) CFNumberGetValue(layer, kCFNumberIntType, &l);
    if (pid)   CFNumberGetValue(pid, kCFNumberIntType, &p);
    if (num)   CFNumberGetValue(num, kCFNumberIntType, &n);
    if (bounds)
    {
        CGRect r;
        CGRectMakeWithDictionaryRepresentation(bounds, &r);
        x = r.origin.x; y = r.origin.y; w = r.size.width; h = r.size.height;
    }
    // 太小的多半是菜单栏图标、tooltip 之类，过滤掉
    if (w < 60 || h < 60) return;
    printf("win=%-8d owner=%-12s pid=%-6d layer=%-4d %.0fx%.0f @(%.0f,%.0f) name=\"%s\"\n",
           n, ob[0] ? ob : "?", p, l, w, h, x, y, nb);
}

int main(void)
{
    CFArrayRef arr = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID);
    if (!arr) { printf("no window list (permission?)\n"); return 1; }
    printf("on-screen windows: %ld\n", (long)CFArrayGetCount(arr));
    CFArrayApplyFunction(arr, CFRangeMake(0, CFArrayGetCount(arr)), dump, NULL);
    CFRelease(arr);
    return 0;
}
