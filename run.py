"""AI Provider 启动入口 — 窗口化 + 系统托盘。

打包后双击运行：
  • 数据目录 = exe 同级的 ``data/``，拷到任何电脑直接运行，无需重新配置。
  • 程序运行在系统托盘（不显示黑窗口）。
  • 右键托盘 →「打开后台」打开浏览器，「退出程序」优雅关闭。

开发模式直接 ``python run.py``（保持原 console 行为）。

要优先于 ``main`` 的模块级配置（日志路径 / 数据库 URL）生效，
所有环境变量必须在 ``import uvicorn / main`` 之前设置。
"""
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── 可移植数据目录 ─────────────────────────────────────────────
IS_FROZEN = getattr(sys, "frozen", False)

# exe 同级目录（打包）<-> 项目根目录（开发）
_BASE_DIR = (Path(sys.executable).parent if IS_FROZEN else Path(__file__).resolve().parent)
_DATA_DIR = _BASE_DIR / "data"
_LOG_DIR = _DATA_DIR / "logs"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 持久化路径（必须在 import uvicorn / main 之前设置）───────────
_DB_PATH = (_DATA_DIR / "modelscope_provider.db").as_posix()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["LOG_DIR"] = str(_LOG_DIR)
os.environ.setdefault("LOG_LEVEL", "INFO")

# 运行参数
_HOST = os.getenv("HOST", "127.0.0.1")  # 托盘版默认只监听本机
_PORT = int(os.getenv("PORT", "8000"))
_APP_URL = f"http://127.0.0.1:{_PORT}"

# ── 托盘支持（仅 Windows）──────────────────────────────────────
_TRAY_AVAILABLE = False
_win32gui = _win32api = _win32con = None
try:
    import win32gui
    import win32api
    import win32con
    from PIL import Image, ImageDraw
    _win32gui, _win32api, _win32con = win32gui, win32api, win32con
    _TRAY_AVAILABLE = True
except ImportError:
    pass


# ── 托盘常量 ───────────────────────────────────────────────────
_TRAY_ID_OPEN = 1001
_TRAY_ID_EXIT = 1002
_TRAY_MSG = 0x1000 + 1  # WM_USER + 1


def _make_icon_path() -> str:
    """在临时目录生成一个简单的圆形 A 字母图标，返回路径。"""
    import tempfile
    icon_path = os.path.join(tempfile.gettempdir(), "ai_provider_icon.ico")
    if not os.path.exists(icon_path):
        try:
            from PIL import Image, ImageDraw
            layers = []
            for size in (16, 32, 48):
                img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                margin = 2
                draw.ellipse([margin, margin, size - margin, size - margin],
                             fill=(240, 248, 255), outline=(33, 150, 243), width=2)
                draw.text((size // 2 - 4, size // 2 - 4), "A",
                          fill=(33, 150, 243))
                layers.append(img)
            layers[0].save(icon_path, format="ICO", sizes=[(l.width, l.height) for l in layers])
        except Exception:
            pass
    return icon_path if os.path.exists(icon_path) else ""


class TrayRunner:
    """封装托盘图标 + 菜单 + 事件循环。"""

    def __init__(self, server, port: int):
        self.server = server
        self.port = port
        self.hwnd = None
        self.icon_hicon = None
        self._menu = None
        self._exiting = False

    def run(self):
        self._create_window()
        self._register_icon()
        self._browser_timer()
        self._pump()

    def _create_window(self):
        W = _win32gui
        import ctypes
        WndProc = self._wnd_proc

        class_name = b"AIProviderTray"
        wc = W.WNDCLASS()
        wc.lpfnWndProc = WndProc
        wc.lpszClassName = class_name
        wc.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc.hCursor = W.LoadCursor(0, _win32con.IDC_ARROW)
        wc.hbrBackground = _win32con.COLOR_WINDOW + 1
        atom = W.RegisterClass(wc)

        self.hwnd = W.CreateWindow(
            atom, class_name.decode(),
            0, 0, 0, 0, 0,
            _win32con.HWND_MESSAGE,  # 消息窗口
            0, wc.hInstance, 0,
        )
        W.ShowWindow(self.hwnd, _win32con.SW_HIDE)

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == _win32con.WM_DESTROY:
            _win32gui.PostQuitMessage(0)
        elif msg == _TRAY_MSG:
            if lParam in (_win32con.WM_LBUTTONDOWN, _win32con.WM_LBUTTONUP):
                self._open()
            elif lParam in (_win32con.WM_RBUTTONDOWN, _win32con.WM_RBUTTONUP,
                            _win32con.WM_CONTEXTMENU):
                self._show_menu()
        elif msg == _win32con.WM_COMMAND:
            cmd_id = wParam & 0xFFFF
            if cmd_id == _TRAY_ID_OPEN:
                self._open()
            elif cmd_id == _TRAY_ID_EXIT:
                self._exit()
        return _win32gui.DefWindowProc(hwnd, msg, wParam, lParam)

    def _register_icon(self):
        import ctypes
        icon_path = _make_icon_path()
        if icon_path:
            hicon = _win32gui.LoadImageW(0, icon_path, _win32con.IMAGE_ICON,
                                         16, 16, _win32con.LR_LOADFROMFILE)
        else:
            hicon = _win32gui.LoadIcon(0, _win32con.IDI_APPLICATION)
        self.icon_hicon = hicon

        nid = _win32gui.NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = _win32con.NIF_ICON | _win32con.NIF_MESSAGE | _win32con.NIF_TIP
        nid.uCallbackMessage = _TRAY_MSG
        nid.hIcon = hicon
        nid.szTip = "AI Provider".encode("utf-16-le") + b"\x00\x00"

        Shell_NotifyIcon = ctypes.windll.shell32.Shell_NotifyIconW
        rc = Shell_NotifyIcon(ctypes.c_uint(_win32con.NIM_ADD), ctypes.byref(nid))
        if not rc:
            print("WARNING: failed to add tray icon (Shell_NotifyIcon returned 0)")

    def _show_menu(self):
        if not self.hwnd:
            return
        menu = _win32gui.CreatePopupMenu()
        _win32gui.AppendMenu(menu, _win32con.MF_STRING, _TRAY_ID_OPEN, "打开后台")
        _win32gui.AppendMenu(menu, _win32con.MF_STRING, _TRAY_ID_EXIT, "退出程序")

        x, y = _win32api.GetCursorPos()
        _win32gui.SetForegroundWindow(self.hwnd)
        _win32gui.TrackPopupMenu(
            menu, _win32con.TPM_CENTERALIGN | _win32con.TPM_RIGHTBUTTON,
            x, y, 0, self.hwnd, None
        )
        _win32gui.DestroyMenu(menu)

    def _open(self):
        try:
            webbrowser.open(f"http://127.0.0.1:{self.port}/web")
        except Exception:
            pass

    def _exit(self):
        self._exiting = True
        # 优雅关闭 uvicorn
        try:
            self.server.should_exit = True
            self.server.force_exit = True
        except Exception:
            pass
        # 移除托盘图标
        try:
            import ctypes
            nid = _win32gui.NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(nid)
            nid.hWnd = self.hwnd
            nid.uID = 1
            Shell_NotifyIcon = ctypes.windll.shell32.Shell_NotifyIconW
            Shell_NotifyIcon(ctypes.c_uint(_win32con.NIM_DELETE), ctypes.byref(nid))
        except Exception:
            pass
        _win32gui.PostMessage(self.hwnd, _win32con.WM_CLOSE, 0, 0)

    def _browser_timer(self):
        def _delayed_open():
            time.sleep(1.5)
            self._open()
        threading.Thread(target=_delayed_open, daemon=True).start()

    def _pump(self):
        """运行消息泵保持托盘图标存活。"""
        while True:
            if self._exiting:
                break
            try:
                _win32gui.PumpWaitingMessages()
            except Exception:
                break
            time.sleep(0.1)


def _run_uvicorn(server, event_loop_holder):
    """在独立线程中运行 uvicorn Server（带自己的事件循环）。"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    event_loop_holder[0] = loop
    loop.run_until_complete(server.serve())


def main():
    import uvicorn
    from uvicorn.config import Config
    from main import app

    # 某些 Windows 启动方式（pythonw、任务计划程序）会把 sys.stdout / sys.stderr
    # 置为 None；uvicorn 的日志配置会调用 sys.stdout.isatty() 而崩溃，需先恢复。
    # 注意：__stdout__ 也可能为 None，必须兜底到 devnull。
    if sys.stdout is None:
        sys.stdout = getattr(sys, "__stdout__", None) or open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = getattr(sys, "__stderr__", None) or open(os.devnull, "w")

    # 启动信息（开发模式可见）
    if not IS_FROZEN:
        print("=" * 52)
        print("  AI Provider")
        print(f"  数据目录 : {_DATA_DIR}")
        print(f"  数据库   : {_DB_PATH}")
        print(f"  访问地址 : {_APP_URL}")
        print(f"  文档     : {_APP_URL}/docs")
        print("=" * 52)

    config = Config(app, host=_HOST, port=_PORT, log_level="info", reload=False)
    server = uvicorn.Server(config)
    loop_holder = [None]

    if _TRAY_AVAILABLE and IS_FROZEN:
        # ── 窗口化模式：托盘 + uvicorn 后台线程 ──
        uvicorn_thread = threading.Thread(
            target=_run_uvicorn, args=(server, loop_holder),
            daemon=True, name="uvicorn"
        )
        uvicorn_thread.start()

        # 等 uvicorn 的 loop 就绪（最多 5 秒）
        for _ in range(50):
            if loop_holder[0] is not None:
                break
            time.sleep(0.1)

        tray = TrayRunner(server, _PORT)
        tray_thread = threading.Thread(target=tray.run, daemon=True, name="tray")
        tray_thread.start()

        # 主线程保持活动，直到 uvicorn 请求退出
        try:
            while not server.should_exit:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    else:
        # ── 开发模式 / 非 Windows：原 console 行为 ──
        threading.Thread(
            target=lambda: _open_browser(_PORT), daemon=True
        ).start()
        uvicorn.run(app, host=_HOST, port=_PORT, log_level="info", reload=False)


def _open_browser(port: int):
    time.sleep(1.5)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
