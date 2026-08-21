"""桌面卡片 — 今日 Token 消耗小窗（Windows）。

一个钉在桌面层（WorkerW 子窗口）的小卡片，位于所有应用窗口之后、不浮于
其他应用之上，显示今日消耗的 token 总数与缓存命中率。数据来自本机管理
接口 ``/api/admin/stats/window``（seconds=0 即「今日」模式），每 5 分钟
轮询一次。

线程模型：``DesktopWidget.run()`` 在自己的线程中运行消息循环，与托盘
线程、uvicorn 线程互不阻塞。托盘通过调用实例方法（内部走 PostMessage）
显示/隐藏卡片。
"""
import json
import logging
import threading
import urllib.request
from pathlib import Path

logger = logging.getLogger("widget")

try:
    import win32api
    import win32con
    import win32gui
    WIDGET_AVAILABLE = True
except Exception as _e:  # pragma: no cover - win32-only module
    win32api = win32con = win32gui = None
    WIDGET_AVAILABLE = False
    _widget_import_error = _e

# ── 卡片布局（像素）───────────────────────────────────────────
WIDTH, HEIGHT = 220, 128
PAD_X, PAD_Y = 16, 12
_LABEL_Y = PAD_Y
_VALUE_Y = _LABEL_Y + 22
_HIT_LABEL_Y = _VALUE_Y + 18
_HIT_Y = _HIT_LABEL_Y + 20
_FOOTER_Y = _HIT_Y + 24

# 颜色（RGBA，与前端 Dashboard 深色卡片一致）
BG_COLOR = (0x1A, 0x1A, 0x2E)
BORDER_COLOR = (0x2E, 0x2E, 0x4A)
LABEL_COLOR = (0x8A, 0x8A, 0x9E)
VALUE_COLOR = (0xE8, 0xE8, 0xF4)
GREEN_COLOR = (0x4A, 0xDE, 0x80)
DIM_COLOR = (0x5A, 0x5A, 0x6E)

_REFRESH_MS = 5 * 60 * 1000      # 数据刷新周期
_CONFIG_CHECK_MS = 30 * 1000     # 「设置→桌面卡片」开关检查周期
_FIRST_DELAY_MS = 3 * 1000       # 启动后首次拉取延迟（等服务就绪）
_CONNECT_TIMEOUT = 2.5

_WM_REFRESH = win32con.WM_USER + 40
_WM_TOGGLE = win32con.WM_USER + 41
_WM_SET_ENABLED = win32con.WM_USER + 44  # 设置开关变化：wParam=1 显示 / 0 隐藏

_CONFIG_NAME = "desktop_widget.json"
# 前端「设置 → 桌面卡片」开关对应的系统配置项（默认开启）
_WIDGET_ENABLED_KEY = "desktop_widget_enabled"


def _fmt_int(n):
    return f"{int(n):,}"


class DesktopWidget:
    """今日 Token 桌面卡片。

    卡片钉在 Windows 桌面层（WorkerW 子窗口），成为桌面的一部分 ——
    位于所有应用窗口之后（应用打开会盖住它，Win+D 显示桌面时可见），
    不浮于其他应用之上。

    可拖动（WM_NCHITTEST 返回 HTCAPTION）、固定位置（锁定后不响应拖动）。
    位置与状态持久化在 ``data/desktop_widget.json``。
    """

    window_title = "AI Provider 今日 Token"

    def __init__(self, base_url: str, data_dir: Path, port: int = None):
        self.base_url = base_url.rstrip("/")
        self.port = port
        self.data_dir = Path(data_dir)
        self.hwnd = None
        self._running = False

        # 数据（由轮询线程写入，绘制线程读取，单次赋值不成问题）
        self.today_tokens = 0
        self.cache_hit_rate = 0.0
        self.cached_tokens = 0
        self.input_tokens = 0
        self.updated_at = None  # datetime.datetime，最近一次成功拉取

        # 配置
        self.cfg_path = self.data_dir / _CONFIG_NAME
        self.cfg = self._load_config()

        self._menu_open = False
        self._lock = threading.Lock()
        self.enabled_by_config = True  # 前端「设置 → 桌面卡片」开关,同一线程读写

    # ── 配置持久化 ─────────────────────────────────────────────
    def _load_config(self) -> dict:
        # pinned: 钉在桌面层（WorkerW 子窗口）；卡片只钉桌面，不浮于应用之上
        cfg = {"x": None, "y": None, "pinned": True, "locked": False}
        try:
            if self.cfg_path.is_file():
                cfg.update(json.loads(self.cfg_path.read_text(encoding="utf-8")))
        except Exception as _e:
            logger.warning("widget config load failed: %s", _e)
        return cfg

    def _save_config(self):
        try:
            self.cfg_path.write_text(
                json.dumps(self.cfg, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as _e:
            logger.warning("widget config save failed: %s", _e)

    # ── 数据拉取 ───────────────────────────────────────────────
    def _stats_url(self) -> str:
        return f"{self.base_url}/api/admin/stats/window?seconds=0"

    def _fetch(self):
        """拉取今日统计并更新内部数据。失败时保留旧值。"""
        url = self._stats_url()
        try:
            with urllib.request.urlopen(url, timeout=_CONNECT_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            kpi = body.get("kpi") or {}
            with self._lock:
                self.today_tokens = int(kpi.get("total_tokens") or 0)
                self.cache_hit_rate = float(kpi.get("cache_hit_rate") or 0.0)
                self.cached_tokens = int(kpi.get("cached_tokens") or 0)
                self.input_tokens = int(kpi.get("input_tokens") or 0)
                import datetime
                self.updated_at = datetime.datetime.now()
            logger.info(
                "widget stats: tokens=%s hit=%s%%",
                _fmt_int(self.today_tokens), self.cache_hit_rate,
            )
        except Exception as _e:
            logger.debug("widget fetch failed: %s", _e)

    def _config_enabled(self) -> bool:
        """读系统配置里的「桌面卡片」开关（默认 true）。

        读不到或请求失败时保持开启，避免误隐藏。
        """
        url = f"{self.base_url}/api/admin/config"
        try:
            with urllib.request.urlopen(url, timeout=_CONNECT_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            entry = (body or {}).get(_WIDGET_ENABLED_KEY) or {}
            value = str(entry.get("value", "true")).strip().lower()
            return value != "false" and value != "0"
        except Exception as _e:
            logger.debug("widget config check failed: %s", _e)
            return True

    def _poll_loop(self):
        """后台轮询循环。

        开关检查每 30 秒一次（前端改设置后快速生效）；数据刷新每 5 分钟
        一次。顺带核对钉在桌面状态（桌面层被重建时重新挂载）。
        """
        try:
            import time
            time.sleep(_FIRST_DELAY_MS / 1000)
            last_enabled = True     # 本地缓存的上次开关状态
            last_config_check = 0.0
            last_fetch = 0.0
            while self._running and self.hwnd:
                now = time.time()
                # 1) 开关检查（30s 周期）
                if now - last_config_check >= _CONFIG_CHECK_MS / 1000:
                    last_config_check = now
                    enabled = self._config_enabled()
                    if enabled != last_enabled:
                        last_enabled = enabled
                        win32api.PostMessage(
                            self.hwnd, _WM_SET_ENABLED, int(enabled), 0,
                        )
                        logger.info("widget config toggled: enabled=%s", enabled)
                # 2) 数据刷新（5min 周期，开启时才拉）
                if last_enabled and now - last_fetch >= _REFRESH_MS / 1000:
                    last_fetch = now
                    self._fetch()
                # 3) 核对仍钉在桌面层（桌面层被重建时重新挂载）
                if self.hwnd:
                    try:
                        parent = win32gui.GetParent(self.hwnd)
                        if parent != self._workerw_hwnd or not parent:
                            self._ensure_pinned()
                    except Exception:
                        pass
                time.sleep(1)
        except Exception as _e:  # pragma: no cover
            logger.warning("widget poll loop exited: %s", _e)

    # ── 窗口生命周期 ───────────────────────────────────────────
    def run(self) -> None:
        """在当前线程运行卡片消息循环（阻塞）。"""
        if not WIDGET_AVAILABLE:
            logger.warning("widget unavailable (win32 import failed)")
            return
        self._running = True
        try:
            hinst = win32api.GetModuleHandle(None)
            wc = win32gui.WNDCLASS()
            wc.hInstance = hinst
            wc.lpszClassName = "AIProviderTokenWidget"
            wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
            wc.hbrBackground = 0
            wc.style = 0
            wc.lpfnWndProc = self._wnd_proc
            try:
                win32gui.RegisterClass(wc)
            except Exception:
                pass  # 已注册过则忽略

            x, y = self._initial_pos()
            style = win32con.WS_POPUP
            ex_style = win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE
            # 卡片只钉桌面，不浮于其他应用，所以不加 TOPMOST

            self.hwnd = win32gui.CreateWindowEx(
                ex_style, wc.lpszClassName, self.window_title, style,
                x, y, WIDTH, HEIGHT, 0, 0, hinst, None,
            )
            # 圆角：把窗口裁剪成圆角矩形
            hrgn = win32gui.CreateRoundRectRgn(0, 0, WIDTH + 1, HEIGHT + 1, 12, 12)
            try:
                win32gui.SetWindowRgn(self.hwnd, hrgn, True)
            except Exception:
                pass
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)

            # 钉桌面（卡片只钉桌面，不浮于其他应用）
            self._ensure_pinned()

            threading.Thread(target=self._poll_loop, daemon=True).start()

            win32gui.PumpMessages()
        except Exception as _e:  # pragma: no cover
            logger.warning("widget run failed: %s", _e)
        finally:
            self._running = False

    def _initial_pos(self) -> tuple:
        """初始位置：配置里的旧位置，或屏幕右下角（工作区右下角 - 卡片尺寸 - 20px 边距）。"""
        cfg_x, cfg_y = self.cfg.get("x"), self.cfg.get("y")
        if cfg_x is not None and cfg_y is not None:
            return int(cfg_x), int(cfg_y)
        try:
            wa = win32api.GetMonitorInfo(
                win32api.MonitorFromPoint((0, 0))
            )["Work"]
            return wa[2] - WIDTH - 20, wa[3] - HEIGHT - 60
        except Exception:  # pragma: no cover
            return 200, 200

    # ── 钉在桌面 ──────────────────────────────────────────────
    _DESKTOP_SPAWN_MSG = 0x052C  # 让 Progman 创建 WorkerW（桌面层）
    _workerw_hwnd = None

    def _find_desktop_layer(self):
        """定位桌面图标所在层（WorkerW，其子窗口为 SHELLDLL_DefView）。

        Windows 10/11 桌面由 Progman → WorkerW → SHELLDLL_DefView 组成；
        把卡片挂到带 SHELLDLL_DefView 的 WorkerW 上，就是把它嵌入桌面，
        跟随桌面出现在所有应用窗口之后（Win+D 可见）。找不到时返回 None。
        """
        try:
            # 1) 让 Progman 生成 WorkerW（若尚未创建）
            progman = win32gui.FindWindow("Progman", None)
            if progman:
                try:
                    win32gui.SendMessageTimeout(
                        progman, self._DESKTOP_SPAWN_MSG, 0, 0,
                        win32con.SMTO_NORMAL, 500,
                    )
                except Exception:
                    pass

            # 2) 枚举顶层窗口，找带 SHELLDLL_DefView 子窗口的那个
            def _is_desktop_layer(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    child = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                    if child:
                        self._workerw_hwnd = hwnd
                        return False  # 停止枚举
                return True

            self._workerw_hwnd = None
            win32gui.EnumWindows(_is_desktop_layer, None)
            return self._workerw_hwnd
        except Exception as _e:  # pragma: no cover
            logger.debug("find desktop layer failed: %s", _e)
            return None

    def _ensure_pinned(self):
        """确保钉在桌面层。如桌面层尚未就绪（Explorer 未启动）则下次轮询重试。"""
        if not self.hwnd:
            return
        try:
            layer = self._find_desktop_layer()
            if not layer:
                logger.warning("desktop layer not found, will retry")
                return
            self.cfg["pinned"] = True
            # 确保没有 TOPMOST（卡片只钉桌面，不浮于应用之上）
            ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            ex_style &= ~win32con.WS_EX_TOPMOST
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex_style)
            # 钉到桌面层
            win32gui.SetParent(self.hwnd, layer)
            style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
            style = (style & ~win32con.WS_POPUP) | win32con.WS_CHILD
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, style)
            win32gui.SetWindowPos(
                self.hwnd, 0, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
                | win32con.SWP_NOACTIVATE,
            )
            logger.info("widget pinned to desktop layer %d", layer)
        except Exception as _e:  # pragma: no cover
            logger.warning("ensure pinned failed: %s", _e)

    # ── 对外控制（供托盘线程调用，线程安全）──────────────────────
    def toggle_visible(self):
        """显示/隐藏卡片。任何线程可安全调用。"""
        if not self.hwnd:
            return
        win32api.PostMessage(self.hwnd, _WM_TOGGLE, 0, 0)

    def refresh_now(self):
        """立即拉一次数据（异步）。"""
        if not self.hwnd:
            return
        win32api.PostMessage(self.hwnd, _WM_REFRESH, 0, 0)

    def set_locked(self, locked: bool):
        self.cfg["locked"] = bool(locked)
        self._save_config()
        if self.hwnd:
            win32api.PostMessage(
                self.hwnd, win32con.WM_USER + 42, int(locked), 0,
            )

    def is_visible(self) -> bool:
        return bool(self.hwnd and win32gui.IsWindowVisible(self.hwnd))

    def is_alive(self) -> bool:
        return bool(self.hwnd)

    def destroy(self):
        if self.hwnd:
            try:
                win32api.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
            self.hwnd = None

    # ── 窗口绘制 ───────────────────────────────────────────────
    def _draw_card(self, hwnd):
        """双缓冲绘制卡片内容（纯 win32gui 句柄 API）。"""
        hdc = win32gui.GetDC(hwnd)
        hdc_mem = win32gui.CreateCompatibleDC(hdc)
        hbmp = win32gui.CreateCompatibleBitmap(hdc, WIDTH, HEIGHT)
        old_bmp = win32gui.SelectObject(hdc_mem, hbmp)

        try:
            # 背景
            brush = win32gui.CreateSolidBrush(RGB(*BG_COLOR))
            win32gui.FillRect(hdc_mem, (0, 0, WIDTH, HEIGHT), brush)
            win32gui.DeleteObject(brush)

            # 圆角边框（窗口整体已被 SetWindowRgn 剪裁成圆角）
            pen = win32gui.CreatePen(win32con.PS_SOLID, 1, RGB(*BORDER_COLOR))
            old_pen = win32gui.SelectObject(hdc_mem, pen)
            old_brush = win32gui.SelectObject(
                hdc_mem, win32gui.GetStockObject(win32con.NULL_BRUSH)
            )
            win32gui.RoundRect(hdc_mem, 0, 0, WIDTH - 1, HEIGHT - 1, 12, 12)
            win32gui.SelectObject(hdc_mem, old_pen)
            win32gui.SelectObject(hdc_mem, old_brush)
            win32gui.DeleteObject(pen)

            win32gui.SetBkMode(hdc_mem, win32con.TRANSPARENT)

            # 「今日 Token 总数」标签（~10pt）
            font = self._make_font("Microsoft YaHei", 18, 400)
            win32gui.SelectObject(hdc_mem, font)
            win32gui.SetTextColor(hdc_mem, RGB(*LABEL_COLOR))
            win32gui.DrawText(
                hdc_mem, "今日 Token 总数", len("今日 Token 总数"),
                (PAD_X, _LABEL_Y, WIDTH - PAD_X, _LABEL_Y + 24),
                win32con.DT_LEFT | win32con.DT_SINGLELINE | win32con.DT_VCENTER,
            )
            win32gui.DeleteObject(font)

            # 大数字（~24pt 等宽）
            font = self._make_font("Consolas", 26, 700)
            win32gui.SelectObject(hdc_mem, font)
            win32gui.SetTextColor(hdc_mem, RGB(*VALUE_COLOR))
            win32gui.DrawText(
                hdc_mem, _fmt_int(self.today_tokens), len(_fmt_int(self.today_tokens)),
                (PAD_X, _VALUE_Y, WIDTH - PAD_X, _VALUE_Y + 34),
                win32con.DT_LEFT | win32con.DT_SINGLELINE | win32con.DT_VCENTER,
            )
            win32gui.DeleteObject(font)

            # 缓存命中率标签
            font = self._make_font("Microsoft YaHei", 18, 400)
            win32gui.SelectObject(hdc_mem, font)
            win32gui.SetTextColor(hdc_mem, RGB(*LABEL_COLOR))
            win32gui.DrawText(
                hdc_mem, "缓存命中率", len("缓存命中率"),
                (PAD_X, _HIT_LABEL_Y, WIDTH - PAD_X, _HIT_LABEL_Y + 22),
                win32con.DT_LEFT | win32con.DT_SINGLELINE | win32con.DT_VCENTER,
            )
            win32gui.DeleteObject(font)

            # 命中率数值（绿色，~16pt）
            font = self._make_font("Consolas", 22, 700)
            win32gui.SelectObject(hdc_mem, font)
            win32gui.SetTextColor(hdc_mem, RGB(*GREEN_COLOR))
            win32gui.DrawText(
                hdc_mem, f"{self.cache_hit_rate:.1f}%", len(f"{self.cache_hit_rate:.1f}%"),
                (PAD_X, _HIT_Y, WIDTH - PAD_X, _HIT_Y + 28),
                win32con.DT_LEFT | win32con.DT_SINGLELINE | win32con.DT_VCENTER,
            )
            win32gui.DeleteObject(font)

            # 底部：更新时间
            font = self._make_font("Microsoft YaHei", 16, 400)
            win32gui.SelectObject(hdc_mem, font)
            win32gui.SetTextColor(hdc_mem, RGB(*DIM_COLOR))
            win32gui.DrawText(
                hdc_mem, self._footer_text(), len(self._footer_text()),
                (PAD_X, _FOOTER_Y, WIDTH - PAD_X, _FOOTER_Y + 20),
                win32con.DT_RIGHT | win32con.DT_SINGLELINE | win32con.DT_VCENTER,
            )
            win32gui.DeleteObject(font)

            # 拷贝到屏幕
            win32gui.BitBlt(
                hdc, 0, 0, WIDTH, HEIGHT, hdc_mem, 0, 0, win32con.SRCCOPY,
            )
        finally:
            win32gui.SelectObject(hdc_mem, old_bmp)
            win32gui.DeleteObject(hbmp)
            win32gui.DeleteDC(hdc_mem)
            win32gui.ReleaseDC(hwnd, hdc)

    @staticmethod
    def _make_font(face: str, height: int, weight: int):
        """创建 LOGFONT 字体，用完由调用方 DeleteObject。"""
        lf = win32gui.LOGFONT()
        lf.lfHeight = -height
        lf.lfFaceName = face
        lf.lfWeight = weight
        lf.lfQuality = 5  # CLEARTYPE_QUALITY
        return win32gui.CreateFontIndirect(lf)

    def _footer_text(self) -> str:
        import datetime
        if self.updated_at is None:
            return "等待数据…"
        delta = datetime.datetime.now() - self.updated_at
        mins = int(delta.total_seconds() // 60)
        if mins < 1:
            return "刚刚更新"
        if mins < 60:
            return f"{mins} 分钟前更新"
        return "1 小时前更新"

    # ── 窗口过程 ───────────────────────────────────────────────
    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == win32con.WM_PAINT:
            try:
                self._draw_card(hwnd)
            finally:
                win32gui.ValidateRect(hwnd, None)
            return 0
        if msg == _WM_REFRESH:
            threading.Thread(target=self._fetch, daemon=True).start()
            return 0
        if msg == _WM_TOGGLE:
            # 托盘手动显示/隐藏；设置开关关闭时不响应显示
            if self.enabled_by_config:
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            return 0
        if msg == _WM_SET_ENABLED:
            enabled = bool(wParam)
            self.enabled_by_config = enabled
            if enabled:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            return 0
        if msg == win32con.WM_USER + 42:  # 锁定/解锁
            self.cfg["locked"] = bool(wParam)
            return 0
        if msg == win32con.WM_NCHITTEST:
            # 锁定位置时不响应拖动；否则整卡可拖（返回 HTCAPTION）
            if not self.cfg.get("locked", False):
                return win32con.HTCAPTION
            return win32con.HTCLIENT
        if msg == win32con.WM_EXITSIZEMOVE:
            # 拖动结束，保存位置
            try:
                rect = win32gui.GetWindowRect(hwnd)
                self.cfg["x"], self.cfg["y"] = rect[0], rect[1]
                self._save_config()
            except Exception as _e:
                logger.debug("widget save pos failed: %s", _e)
            return 0
        if msg == win32con.WM_RBUTTONUP or msg == win32con.WM_NCRBUTTONUP or \
                msg == win32con.WM_CONTEXTMENU:
            self._show_menu()
            return 0
        if msg == win32con.WM_COMMAND:
            cmd = wParam & 0xFFFF
            if cmd == 1001:
                self.refresh_now()
            elif cmd == 1002:
                self.set_locked(not self.cfg.get("locked", False))
            elif cmd == 1004:
                win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return 0
        if msg == win32con.WM_CLOSE:
            self.cfg = self._load_config()  # 保留最新
            self._running = False
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            self.hwnd = None
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)

    def _show_menu(self):
        if self._menu_open:
            return
        self._menu_open = True
        menu = None
        try:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "立即刷新")
            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
            win32gui.AppendMenu(
                menu,
                win32con.MF_STRING | (
                    win32con.MF_CHECKED if self.cfg.get("locked") else win32con.MF_UNCHECKED
                ),
                1002, "固定位置",
            )
            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1004, "关闭卡片")
            win32gui.SetForegroundWindow(self.hwnd)
            x, y = win32api.GetCursorPos()
            win32gui.TrackPopupMenu(
                menu,
                win32con.TPM_LEFTALIGN | win32con.TPM_BOTTOMALIGN | win32con.TPM_RIGHTBUTTON,
                x, y, 0, self.hwnd, None,
            )
        except Exception as _e:
            logger.debug("widget menu failed: %s", _e)
        finally:
            if menu:
                try:
                    win32gui.DestroyMenu(menu)
                except Exception:
                    pass
            self._menu_open = False


def RGB(r, g, b):
    return win32api.RGB(r, g, b)