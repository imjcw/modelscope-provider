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
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("tray")

# ── 可移植数据目录 ─────────────────────────────────────────────
IS_FROZEN = getattr(sys, "frozen", False)

# exe 同级目录（打包）<-> 项目根目录（开发）
_BASE_DIR = (Path(sys.executable).parent if IS_FROZEN else Path(__file__).resolve().parent)
_DATA_DIR = _BASE_DIR / "data"
_LOG_DIR = _DATA_DIR / "logs"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 持久化路径（必须在 import uvicorn / main 之前设置）───────────
_DB_NAME = "ai_provider.db"
_DB_PATH = (_DATA_DIR / _DB_NAME).as_posix()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["LOG_DIR"] = str(_LOG_DIR)
os.environ.setdefault("LOG_LEVEL", "INFO")

# 运行参数
_HOST = os.getenv("HOST", "127.0.0.1")  # 托盘版默认只监听本机
_PORT = int(os.getenv("PORT", "8000"))
_APP_URL = f"http://127.0.0.1:{_PORT}"


def _find_chrome():
    """定位 Chrome 可执行文件，用于在应用模式下打开已安装的 PWA 独立窗口。

    优先读注册表 App Paths，再回退到常见安装目录；找不到返回 None。
    """
    try:
        import winreg
    except Exception:
        winreg = None
    if winreg is not None:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    root,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                ) as k:
                    path, _ = winreg.QueryValueEx(k, "")
                    if path and os.path.exists(path):
                        return path
            except OSError:
                pass
    for cand in (
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ):
        if os.path.exists(cand):
            return cand
    return None

# ── 托盘支持（仅 Windows）──────────────────────────────────────
_TRAY_AVAILABLE = False
_win32gui = _win32api = _win32con = None
_tray_import_error = None
# PyInstaller onefile 下，pywin32 的 C 扩展 DLL（pywintypes*.dll /
# pythoncom*.dll）位于 _MEIPASS/pywin32_system32，需加入 PATH 才能被加载。
if getattr(sys, "frozen", False):
    _mp = getattr(sys, "_MEIPASS", "")
    if _mp:
        _sys32 = os.path.join(_mp, "pywin32_system32")
        if os.path.isdir(_sys32):
            os.environ["PATH"] = _sys32 + os.pathsep + os.environ.get("PATH", "")
try:
    import win32gui
    import win32api
    import win32con
    _win32gui, _win32api, _win32con = win32gui, win32api, win32con
    _TRAY_AVAILABLE = True
except Exception as _e:
    _tray_import_error = _e


# ── 托盘常量 ───────────────────────────────────────────────────
_TRAY_ID_OPEN = 1001
_TRAY_ID_EXIT = 1002
_TRAY_ID_LOGS = 1003
_TRAY_ID_WIDGET = 1004  # 桌面卡片显示/隐藏
_TRAY_MSG = 0x1000 + 1  # WM_USER + 1


# 内置图标（蓝色圆形，16/32/48 多分辨率 ICO，Base64 编码）。
# 不依赖 PIL：运行时解码成临时 .ico 文件，供 win32gui.LoadImageW 加载。
_ICON_B64 = "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Av80MAj/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/NDAI/8/OAv/+/gD//v4A/8/OAv80MAj/DwoK3w8KCv80MAj/d3UG/3d1Bv80MAj/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv80MAj/d3UG/3d1Bv80MAj/DwoK/w8KCt8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/x8JGv9gB13/hAWB/2AHXf8fCRr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrfDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/x8JGv+pBKf/+AD4//8A///4APj/qQSn/x8JGv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK3w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9gB13/+AD4//8A////AP///wD///gA+P9gB13/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCt8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/hAWB//8A////AP///wD///8A////AP//hAWB/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrfDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/2AHXf/4APj//wD///8A////AP//+AD4/2AHXf8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK3w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8fCRr/qQSn//gA+P//AP//+AD4/6kEp/8fCRr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCt8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/x8JGv9gB13/hAWB/2AHXf8fCRr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrfDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK3w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xsW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F//DA8H//wD///8A////AP///wD///8A//+0A7L/FwoS/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xUKEP+oBKb//wD///8A////AP///wD///8A//+WBJT/EQoM/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9PB0v/3wHf//8A////AP///wD//9YC1v9CCD7/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8RCgz/TwdL/6gEpv/DA8H/ogSg/0YIQv8QCgv/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xUKEP8cCRf/FAoP/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/HRgJ/1pWB/96dwb/VFAH/xkUCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8ZFAr/lpQE//PzAP///wD/8O8B/4iGBf8VEAr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9FQQj/6+sB////AP///wD///8A/+LiAf84NAj/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrcDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9UUQf/9fUA////AP///wD///8A/+/vAf9FQgj/DwoK/w8K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Cv8PCgr/DwoK/w8KCv8PCgr/DwoK/xYKEf8YChP/EgoO/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8WEQr/KSUJ/y0pCf8dGQn/EAsK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/yUJIP9hB17/kAWO/5sEmf9/BX3/RAhA/xUKEP8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8tCSn/lwSV/+cB5v/8APz//wD///cA9//LAsr/ZQZh/xUKEP8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/FgoS/4MFgP/xAfH//wD///8A////AP///wD///8A///LAsr/RAhA/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8yCS7/xQLE//8A////AP///wD///8A////AP///wD///cA9/9/BX3/EgoO/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/0QIQP/dAdz//wD///8A////AP///wD///8A////AP///wD//5sEmf8YChP/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/PQg5/9QC0///AP///wD///8A////AP///wD///8A///8APz/kAWO/xYKEf8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8iCR3/pgSk//0A/f//AP///wD///8A////AP///wD//+cB5v9hB17/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xAKC/9SB0//ygLJ//0A/f//AP///wD///8A///xAfH/lwSV/yUJIP8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xQKD/9SB0//pgSk/9QC0//dAdz/xQLE/4MFgP8tCSn/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xAKC/8iCR3/PQg5/0QIQP8yCS7/FgoS/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xALCv8sKAn/VFAH/19bB/9DPwj/GxYK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8RDAr/TUoH/7GvA//l5AH/7OwB/9XUAv+HhAX/JSEJ/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/zEsCf+1swP//f0A////AP///wD///8A/+zrAf92dAb/Ew4K/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/X1sH/+vqAf///wD///8A////AP///wD///8A/7a0A/8mIgn/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrRDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9uawb/9PQA////AP///wD///8A////AP///wD/xsUC/y4qCf8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCtEPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/1RQB//i4QH///8A////AP///wD///8A//7+AP+ppwT/IRwJ/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK0Q8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/JB8J/5yaBP/19AD///8A////AP/+/gD/2dgC/19cB/8RDAr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgrFDwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/Mi4J/4uIBf/GxQL/0dAC/7GwA/9jXwf/GBQK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK9w8KCosAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACgAAAAwAAAAMAAAAAEAIAAAAAAAACQAAAAAAAAAAAAAAAAAAAAAAAAPCgplDwoKlQ8KCrIPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKug8KCroPCgq6DwoKrg8KCo4PCgpaCwgIHAEBAQEPCgrHDwoK8g8KCv4PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/Q8KCu4PCgq7DwoKbwsICBwPCgr9DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr6DwoKuw8KCloPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK7g8KCo4PCgr/DwoK/w8KCv8PCgr/FA8K/x8aCf8kHwn/IBsJ/xUQCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/FxIK/yEdCf8kHwn/HRkJ/xINCv8PCgr/DwoK/w8KCv8PCgr/DwoK/Q8KCq4PCgr/DwoK/xMOCv81MQj/Yl8H/4B+Bf+LiQX/gn8F/2ZiBv85NQj/FRAK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xkUCv9CPgj/bGkG/4WDBf+LiAX/fHkF/1tXB/8tKAn/EQwK/w8KCv8PCgr/DwoK/w8KCroPCgr/FRAK/0xIB/+RjgX/x8YC/+bmAf/u7gH/6OcB/8vKAv+WlAT/U08H/xcTCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/HhkJ/2BdB/+hnwT/09IC/+rqAf/u7gH/4+IB/7+9A/+FgwX/PzsI/xEMCv8PCgr/DwoK/w8KCroQCwr/QT0I/5iWBP/j4gH//v4A////AP///wD///8A//7+AP/o5wH/oJ4E/0lFCP8RDAr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8VEAr/WVYH/6+tA//w8AH///8A////AP///wD///8A//39AP/Y1wL/iYYF/zIuCf8PCgr/DwoK/w8KCroeGQn/d3QG/9fWAv///wD///8A////AP///wD///8A////AP///wD/3t0B/4B+Bf8jHwn/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8wLAn/kpAF/+rqAf///wD///8A////AP///wD///8A////AP/9/QD/x8YC/2ViBv8WEQr/DwoK/w8KCro1MAj/npwE//X1AP///wD///8A////AP///wD///8A////AP///wD/+fkA/6imBP89OQj/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xALCv9RTQf/u7kD//7+AP///wD///8A////AP///wD///8A////AP///wD/7OsB/4uIBf8mIgn/DwoK/w8KCrpEQAj/sbAD//39AP///wD///8A////AP///wD///8A////AP///wD///8A/7u6A/9OSgf/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xMOCv9iXgf/z84C////AP///wD///8A////AP///wD///8A////AP///wD/9/cA/52bBP8yLgn/DwoK/w8KCrpCPgj/r64D//z8AP///wD///8A////AP///wD///8A////AP///wD//v4A/7m4A/9MSAf/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xINCv9gXQf/zcwC////AP///wD///8A////AP///wD///8A////AP///wD/9vYA/5yZBP8xLAn/DwoK/w8KCroxLQn/mJYE//LyAf///wD///8A////AP///wD///8A////AP///wD/9vYA/6KgBP85NQj/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv9MSAf/tbMD//z8AP///wD///8A////AP///wD///8A////AP///wD/5+cB/4WDBf8jHwn/DwoK/w8KCroaFQr/bmsG/83MAv/+/gD///8A////AP///wD///8A////AP/+/gD/1dQC/3d0Bv8fGgn/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8qJgn/iYYF/+PiAf///wD///8A////AP///wD///8A////AP/7+wD/vbsD/11ZB/8TDgr/DwoK/w8KCroPCgr/NjII/4uJBf/X1gL/+/sA////AP///wD///8A//z8AP/c2wH/k5AF/z46CP8QCwr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8SDQr/TUoH/6GfBP/m5QH//v4A////AP///wD///8A//j4AP/LyQL/fHkF/yklCf8PCgr/DwoK/w8KCroPCgr/Eg0K/z46CP+AfgX/tbQD/9fWAv/h4QH/2dgC/7m4A/+GgwX/REAI/xMOCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/GBMK/1FNB/+QjgX/wb8D/9zbAf/h4AH/09IC/62rA/91cgb/Mi4J/xALCv8PCgr/DwoK/w8KCroPCgr/DwoK/xALCv8nIwn/T0wH/21qBv93dAb/bmsG/1NPB/8rJgn/EQwK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xMPCv8yLgn/WVYH/3FuBv93dAb/aWUG/0hECP8hHAn/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/EAsK/xYRCv8aFQr/FhIK/xALCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xAKC/8YChP/Hgka/x4JGf8WChH/EAoL/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/EQwK/xcTCv8aFQr/FRAK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8RCgz/Kgkm/1IHT/9xBm7/gAV9/34FfP9tBmn/SwdI/yQJH/8QCgv/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xUKEP9HCEP/hgWE/7kDt//aAtr/6AHn/+YB5v/WAtX/sAOv/3sFef88CDf/EgoN/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/EgoN/0oIRv+aBJj/3gHe//wA/P//AP///wD///8A////AP//+gD6/9QC0/+MBYr/PAg3/xAKC/8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/MQks/4wFiv/hAeD//wD///8A////AP///wD///8A////AP///wD///4A/v/UAtP/ewV5/yQJH/8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8TCg7/Xgdb/8MDwf/9AP3//wD///8A////AP///wD///8A////AP///wD///8A///6APr/sAOv/0sHSP8QCgv/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8fCRv/gAV9/+UB5f//AP///wD///8A////AP///wD///8A////AP///wD///8A////AP//1gLV/20Gaf8WChH/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8qCSX/kgWQ//IB8f//AP///wD///8A////AP///wD///8A////AP///wD///8A////AP//5gHm/34FfP8eCRn/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8rCSb/lASS//MB8v//AP///wD///8A////AP///wD///8A////AP///wD///8A////AP//6AHn/4AFff8eCRr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8iCR3/hQWC/+kB6P//AP///wD///8A////AP///wD///8A////AP///wD///8A////AP//2gLa/3EGbv8YChP/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8VChD/ZQZi/8sCyv/+AP7//wD///8A////AP///wD///8A////AP///wD///8A///8APz/uQO3/1IHT/8QCgv/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/OQg1/5cElf/qAer//wD///8A////AP///wD///8A////AP///wD///8A///eAd7/hgWE/yoJJv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/FQoQ/1cHU/+oBKf/6gHq//4A/v//AP///wD///8A////AP///QD9/+EB4P+aBJj/RwhD/xEKDP8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xoKFv9XB1P/lwSV/8sCyv/pAej/8wHy//IB8f/lAeX/wwPB/4wFiv9KCEb/FQoQ/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8VChD/OQg1/2UGYv+FBYL/lASS/5IFkP+ABX3/Xgdb/zEJLP8SCg3/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xUKEP8iCR3/Kwkm/yoJJf8fCRv/EwoO/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/EAsK/x4ZCf81MAj/REAI/0I+CP8xLQn/GhUK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8VEAr/QT0I/3d0Bv+enAT/sbAD/6+uA/+YlgT/bmsG/zYyCP8SDQr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xMOCv9MSAf/mJYE/9fWAv/19QD//f0A//z8AP/y8gH/zcwC/4uJBf8+Ogj/EAsK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/zUxCP+RjgX/4+IB////AP///wD///8A////AP///wD//v4A/9fWAv+AfgX/JyMJ/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/FA8K/2JfB//HxgL//v4A////AP///wD///8A////AP///wD///8A//v7AP+1tAP/T0wH/xALCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/HxoJ/4B+Bf/m5gH///8A////AP///wD///8A////AP///wD///8A////AP/X1gL/bWoG/xYRCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/JB8J/4uJBf/u7gH///8A////AP///wD///8A////AP///wD///8A////AP/h4QH/d3QG/xoVCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/IBsJ/4J/Bf/o5wH///8A////AP///wD///8A////AP///wD///8A////AP/Z2AL/bmsG/xYSCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/FRAK/2ZiBv/LygL//v4A////AP///wD///8A////AP///wD///8A//z8AP+5uAP/U08H/xALCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCroPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/zk1CP+WlAT/6OcB////AP///wD///8A////AP///wD//v4A/9zbAf+GgwX/KyYJ/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/g8KCrIPCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/xUQCv9TTwf/oJ4E/97dAf/5+QD///8A//7+AP/29gD/1dQC/5OQBf9EQAj/EQwK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK8g8KCpUPCgr+DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8XEwr/SUUI/4B+Bf+opgT/u7oD/7m4A/+ioAT/d3QG/z46CP8TDgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr/DwoK/w8KCv8PCgr9DwoKxw8KCmUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

def _make_icon_path() -> str:
    """返回托盘图标路径。

    优先级：
    1. 打包进 exe 的 ``web/favicon.ico``（与 EXE 图标一致，IS_FROZEN 时
       位于 ``sys._MEIPASS/web/favicon.ico``）；
    2. 开发模式下项目内的 ``web/favicon.ico``；
    3. 兜底：解码内置 Base64 图标为临时 .ico（无需 PIL）。
    """
    candidates = []
    if IS_FROZEN:
        _mp = getattr(sys, "_MEIPASS", "")
        if _mp:
            candidates.append(os.path.join(_mp, "web", "favicon.ico"))
    else:
        candidates.append(os.path.join(str(_BASE_DIR), "web", "favicon.ico"))
    for p in candidates:
        if p and os.path.isfile(p):
            return p

    import tempfile
    import base64
    icon_path = os.path.join(tempfile.gettempdir(), "ai_provider_icon.ico")
    if os.path.exists(icon_path):
        return icon_path
    try:
        data = base64.b64decode(_ICON_B64)
        with open(icon_path, "wb") as f:
            f.write(data)
    except Exception:
        return ""
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
        self.widget = None  # DesktopWidget（可用时）

    def run(self):
        try:
            self._create_window()
            self._register_icon()
            self._start_widget()
            self._browser_timer()
            self._pump()
        except Exception as _e:
            logger.error("tray runner failed: %s", _e, exc_info=_e)

    def _start_widget(self):
        """启动桌面卡片（单独线程），失败时静默降级。"""
        try:
            from core.desktop_widget import DesktopWidget, WIDGET_AVAILABLE
            if not WIDGET_AVAILABLE:
                return
            self.widget = DesktopWidget(
                base_url=f"http://127.0.0.1:{self.port}",
                data_dir=_DATA_DIR,
                port=self.port,
            )
            threading.Thread(target=self.widget.run, daemon=True, name="desktop-widget").start()
            logger.info("desktop widget thread started")
        except Exception as _e:
            logger.warning("desktop widget start failed: %s", _e)
            self.widget = None

    def _create_window(self):
        W = _win32gui
        import ctypes
        WndProc = self._wnd_proc

        # 类名必须是 str（pywin32 的 WNDCLASS.lpszClassName 不接受 bytes）
        class_name = "AIProviderTray"
        wc = W.WNDCLASS()
        wc.lpfnWndProc = WndProc
        wc.lpszClassName = class_name
        wc.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        # LoadCursor 的 hInstance 必须传 None（传 0 在部分 pywin32 构建下
        # 会抛 "This param must be None"）；CreateWindow(Ex) 的父窗口/hMenu
        # 传 0 即可。
        wc.hCursor = W.LoadCursor(None, _win32con.IDC_ARROW)
        wc.hbrBackground = _win32con.COLOR_WINDOW + 1
        W.RegisterClass(wc)

        # 用真实（隐藏）顶层窗口作为托盘图标与右键菜单的宿主窗口：
        # 以 HWND_MESSAGE 消息-only 窗口作为右键菜单 owner 时，菜单无法获得
        # 系统主题样式，会呈现为经典（非系统）样式；换成真实窗口并加
        # WS_EX_TOOLWINDOW 可避免任务栏/Alt+Tab 出现，同时让上下文菜单以
        # 系统原生样式呈现。
        self.hwnd = W.CreateWindowEx(
            _win32con.WS_EX_TOOLWINDOW,  # 不在任务栏 / Alt+Tab 出现
            class_name, "", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None,
        )
        W.ShowWindow(self.hwnd, _win32con.SW_HIDE)

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == _win32con.WM_DESTROY:
            _win32gui.PostQuitMessage(0)
        elif msg == _TRAY_MSG:
            if lParam == _win32con.WM_LBUTTONUP:
                self._open()
            # 在 RBUTTONUP / CONTEXTMENU 时弹出菜单（不要在 RBUTTONDOWN
            # 弹，否则菜单会在用户松开右键时立即消失）
            elif lParam in (_win32con.WM_RBUTTONUP, _win32con.WM_CONTEXTMENU):
                self._show_menu()
        elif msg == _win32con.WM_COMMAND:
            cmd_id = wParam & 0xFFFF
            if cmd_id == _TRAY_ID_OPEN:
                self._open()
            elif cmd_id == _TRAY_ID_LOGS:
                self._open_logs()
            elif cmd_id == _TRAY_ID_WIDGET:
                self._toggle_widget()
            elif cmd_id == _TRAY_ID_EXIT:
                self._exit()
        return _win32gui.DefWindowProc(hwnd, msg, wParam, lParam)

    def _register_icon(self):
        icon_path = _make_icon_path()
        if icon_path:
            # pywin32 只暴露 LoadImage（已是 Unicode/W 版本），没有 LoadImageW
            hicon = _win32gui.LoadImage(
                None, icon_path, _win32con.IMAGE_ICON, 16, 16, _win32con.LR_LOADFROMFILE)
        else:
            hicon = _win32gui.LoadIcon(None, _win32con.IDI_APPLICATION)
        self.icon_hicon = hicon

        # pywin32 的 Shell_NotifyIcon 接受元组形式：
        # (hWnd, id, flags, callbackMsg, hIcon, tooltip)
        # 注意 NIF_*/NIM_* 常量在 win32gui（而非 win32con）中。
        nid = (
            self.hwnd, 1,
            _win32gui.NIF_ICON | _win32gui.NIF_MESSAGE | _win32gui.NIF_TIP,
            _TRAY_MSG, hicon, "AI Provider",
        )
        # pywin32 成功时返回 None（失败时抛 pywintypes.error），故用 try/except 判断。
        try:
            _win32gui.Shell_NotifyIcon(_win32gui.NIM_ADD, nid)
            logger.info("tray icon registered successfully")
        except Exception as _e:
            logger.warning("failed to add tray icon: %s", _e)

    def _show_menu(self):
        # 防止右击的 RBUTTONUP / CONTEXTMENU 多次触发导致菜单叠加
        if not self.hwnd or getattr(self, "_menu_open", False):
            return
        self._menu_open = True
        menu = None
        try:
            menu = _win32gui.CreatePopupMenu()
            _win32gui.AppendMenu(menu, _win32con.MF_STRING, _TRAY_ID_OPEN, "打开应用")
            _win32gui.AppendMenu(menu, _win32con.MF_STRING, _TRAY_ID_LOGS, "查看日志")
            _win32gui.AppendMenu(
                menu,
                _win32con.MF_STRING | (
                    _win32con.MF_CHECKED if self._widget_visible() else _win32con.MF_UNCHECKED
                ),
                _TRAY_ID_WIDGET, "桌面卡片",
            )
            _win32gui.AppendMenu(menu, _win32con.MF_SEPARATOR, 0, "")
            _win32gui.AppendMenu(menu, _win32con.MF_STRING, _TRAY_ID_EXIT, "退出")
            # 以系统原生样式弹出：先把宿主窗口设为前台（否则菜单会以经典
            # 样式呈现且无法在外部点击关闭），弹出结束后再发还焦点。
            _win32gui.SetForegroundWindow(self.hwnd)
            x, y = _win32api.GetCursorPos()
            _win32gui.TrackPopupMenu(
                menu,
                _win32con.TPM_LEFTALIGN | _win32con.TPM_BOTTOMALIGN | _win32con.TPM_RIGHTBUTTON,
                x, y, 0, self.hwnd, None,
            )
            # 交还焦点，避免“第一次外部点击被吞掉”的问题
            _win32gui.PostMessage(self.hwnd, _win32con.WM_NULL, 0, 0)
        except Exception as _e:
            logger.warning("failed to show tray menu: %s", _e)
        finally:
            if menu:
                try:
                    _win32gui.DestroyMenu(menu)
                except Exception:
                    pass
            self._menu_open = False

    def _open(self):
        # 用 Chrome 应用模式（--app）打开，得到无地址栏的独立 PWA 窗口，
        # 而不是默认浏览器里的普通标签页。未找到 Chrome 时回退到默认浏览器。
        # 用 localhost 而非 127.0.0.1，以匹配从 http://localhost:8000 安装的 PWA 源。
        url = f"http://localhost:{self.port}/web"
        chrome = _find_chrome()
        if chrome:
            try:
                subprocess.Popen(
                    [chrome, f"--app={url}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                logger.info("以 PWA 应用模式打开: %s", url)
                return
            except Exception as _e:
                logger.warning("Chrome 应用模式启动失败，回退默认浏览器: %s", _e)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _open_logs(self):
        """用系统默认程序打开日志目录；目录不存在时回退到数据目录。"""
        target = _LOG_DIR if _LOG_DIR.is_dir() else _DATA_DIR
        try:
            os.startfile(str(target))
            logger.info("opened logs dir: %s", target)
        except Exception as _e:
            logger.warning("failed to open logs dir %s: %s", target, _e)

    def _toggle_widget(self):
        """桌面卡片显示/隐藏（已关闭时重新拉起）。"""
        if self.widget is None or not self.widget.is_alive():
            self._start_widget()
        else:
            self.widget.toggle_visible()

    def _widget_visible(self) -> bool:
        try:
            return bool(self.widget and self.widget.is_visible())
        except Exception:
            return False

    def _exit(self):
        self._exiting = True
        # 关闭桌面卡片窗口
        if self.widget is not None:
            try:
                self.widget.destroy()
            except Exception:
                pass
        # 优雅关闭 uvicorn
        try:
            self.server.should_exit = True
            self.server.force_exit = True
        except Exception:
            pass
        # 移除托盘图标
        try:
            nid = (self.hwnd, 1, 0, 0, 0, "")
            _win32gui.Shell_NotifyIcon(_win32gui.NIM_DELETE, nid)
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

    logger.info(
        "tray check: IS_FROZEN=%s _TRAY_AVAILABLE=%s", IS_FROZEN, _TRAY_AVAILABLE
    )
    if _tray_import_error is not None:
        logger.warning(
            "tray import failed: %s", _tray_import_error, exc_info=_tray_import_error
        )

    if _TRAY_AVAILABLE and IS_FROZEN:
        # ── 窗口化模式：托盘 + uvicorn 后台线程 ──
        logger.info(
            "tray mode enabled (IS_FROZEN=%s, _TRAY_AVAILABLE=%s)",
            IS_FROZEN, _TRAY_AVAILABLE,
        )
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
