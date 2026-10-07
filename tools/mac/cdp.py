#!/usr/bin/env python3
"""用 Chrome DevTools Protocol 观察 Electron 打包的 galgame。

为什么需要它：像 TyranoScript + Electron 这类打包的游戏，画面是 Chromium 渲染的。
它出问题的时候（白屏、卡 loading、不停弹框）——Wine 的日志帮不上忙，因为
真正在报错的是页面里的 JavaScript。

开启方式：给游戏加 `--remote-debugging-port=9222`（放在容器的 Program Flags 里，
或者手工跑 wine 时带上），然后：

    python3 cdp.py dialogs 60        # 盯著弹框和控制台报错 60 秒
    python3 cdp.py hook 45           # 注入钩子后刷新，把 alert/异常都打到 stdout
    python3 cdp.py reload            # 刷新并打印控制台 + 网络失败
    python3 cdp.py shot /tmp/x.png   # 截当前页面
    python3 cdp.py 'Game.currentScene()'      # 在页面里求值
    python3 cdp.py click 640 400     # 往页面里合成一次点击

需要 `pip install websockets`。
"""
import asyncio, json, sys, urllib.request

import websockets


def page_ws():
    data = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=10))
    for t in data:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise SystemExit("no page target")


async def main():
    url = page_ws()
    mode = sys.argv[1] if len(sys.argv) > 1 else "eval"
    async with websockets.connect(url, max_size=32 * 1024 * 1024) as ws:
        n = 0

        async def send(method, params=None):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
            return n

        await send("Runtime.enable")
        await send("Log.enable")
        await send("Page.enable")
        await send("Network.enable")

        if mode == "reload":
            await send("Page.reload", {"ignoreCache": False})
            deadline = asyncio.get_event_loop().time() + 40
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                m = msg.get("method")
                if m == "Runtime.consoleAPICalled":
                    args = [a.get("value", a.get("description", "")) for a in msg["params"]["args"]]
                    print("CONSOLE", msg["params"]["type"], args)
                elif m == "Runtime.exceptionThrown":
                    d = msg["params"]["exceptionDetails"]
                    print("EXCEPTION", d.get("text"), (d.get("exception") or {}).get("description"))
                elif m == "Log.entryAdded":
                    e = msg["params"]["entry"]
                    print("LOG", e.get("level"), e.get("text"), e.get("url", ""))
                elif m == "Network.loadingFailed":
                    p = msg["params"]
                    print("NETFAIL", p.get("type"), p.get("errorText"), p.get("requestId"))
                elif m == "Network.requestWillBeSent":
                    p = msg["params"]
                    if p.get("request", {}).get("url", "").startswith("file:"):
                        print("REQ", p["request"]["url"])
                elif m == "Page.loadEventFired":
                    print("LOAD fired")
            return

        if mode == "shot":
            out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/cdp-shot.png"
            i = await send("Page.captureScreenshot", {"format": "png"})
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == i:
                    import base64
                    data = msg["result"]["data"]
                    with open(out, "wb") as fh:
                        fh.write(base64.b64decode(data))
                    print("wrote", out)
                    break
            return

        if mode == "dialogs":
            # 卡在 loading 的常见原因就是有个 alert 弹着没人点，把内容打出来
            dur = float(sys.argv[2]) if len(sys.argv) > 2 else 60
            deadline = asyncio.get_event_loop().time() + dur
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                m = msg.get("method")
                if m == "Page.javascriptDialogOpening":
                    p = msg["params"]
                    print("DIALOG", p.get("type"), repr(p.get("message"))[:600])
                    await send("Page.handleJavaScriptDialog", {"accept": True})
                elif m == "Runtime.consoleAPICalled":
                    args = [a.get("value", a.get("description", "")) for a in msg["params"]["args"]]
                    if msg["params"]["type"] in ("error", "warning"):
                        print("CONSOLE", msg["params"]["type"], args)
                elif m == "Runtime.exceptionThrown":
                    d = msg["params"]["exceptionDetails"]
                    print("EXCEPTION", d.get("text"), (d.get("exception") or {}).get("description"),
                          d.get("url"), d.get("lineNumber"))
                elif m == "Log.entryAdded":
                    e = msg["params"]["entry"]
                    if e.get("level") == "error":
                        print("LOG", e.get("level"), e.get("text"), e.get("url", ""))
            return

        if mode == "hook":
            # 把 alert/confirm/onerror 都改写成 console.log，再刷新
            dur = float(sys.argv[2]) if len(sys.argv) > 2 else 45
            src = (
                "(function(){"
                "window.alert=function(m){console.log('ALERT: '+m);};"
                "window.confirm=function(m){console.log('CONFIRM: '+m);return true;};"
                "window.onerror=function(m,s,l){console.log('ONERROR: '+m+' @'+s+':'+l);};"
                "window.addEventListener('unhandledrejection',function(e){console.log('REJECT: '+e.reason);});"
                "})()"
            )
            await send("Page.addScriptToEvaluateOnNewDocument", {"source": src})
            await send("Page.reload", {"ignoreCache": False})
            deadline = asyncio.get_event_loop().time() + dur
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                m = msg.get("method")
                if m == "Runtime.consoleAPICalled":
                    args = [a.get("value", a.get("description", "")) for a in msg["params"]["args"]]
                    text = " ".join(str(a) for a in args)
                    if any(k in text for k in ("ALERT", "ONERROR", "REJECT", "CONFIRM", "not found", "Error", "error")):
                        print("CONSOLE", msg["params"]["type"], text[:400])
                elif m == "Runtime.exceptionThrown":
                    d = msg["params"]["exceptionDetails"]
                    print("EXCEPTION", d.get("text"), (d.get("exception") or {}).get("description"),
                          d.get("url"), d.get("lineNumber"))
                elif m == "Log.entryAdded":
                    e = msg["params"]["entry"]
                    if e.get("level") == "error":
                        print("LOGERR", e.get("text"), e.get("url", ""))
            return

        if mode == "click":
            x, y = float(sys.argv[2]), float(sys.argv[3])
            for t in ("mousePressed", "mouseReleased"):
                await send("Input.dispatchMouseEvent", {
                    "type": t, "x": x, "y": y, "button": "left",
                    "clickCount": 1, "buttons": 1 if t == "mousePressed" else 0,
                })
            await asyncio.sleep(1.5)
            print("clicked page", x, y)
            return

        for expr in sys.argv[1:]:
            i = await send("Runtime.evaluate", {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": False,
            })
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == i:
                    res = msg.get("result", {})
                    print(expr, "=>", json.dumps(res.get("result", res))[:2000])
                    break


asyncio.run(main())
