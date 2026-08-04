"""PyInstaller 单文件 exe 打包入口。

将应用打包为单文件 exe 时，把数据库、日志、配置统一存放于 exe 同级目录的
``data/``（保证跨会话持久化，不会被 PyInstaller 的临时解压目录清掉）。
开发模式也可直接 ``python run.py`` 运行。

要优先于 ``main`` 的模块级配置（日志路径 / 数据库 URL）生效，所有环境变量
必须在 ``import main`` 之前设置。
"""
import os
import sys
import threading
import webbrowser
from pathlib import Path

IS_FROZEN = getattr(sys, "frozen", False)

# exe 同级目录(打包) <-> 项目根目录(开发)
_BASE_DIR = (Path(sys.executable).parent if IS_FROZEN else Path(__file__).resolve().parent)
_DATA_DIR = _BASE_DIR / "data"
_LOG_DIR = _DATA_DIR / "logs"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 持久化路径（必须在 import main 之前设置）───────────────────────────
_DB_PATH = (_DATA_DIR / "modelscope_provider.db").as_posix()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["LOG_DIR"] = str(_LOG_DIR)
os.environ.setdefault("LOG_LEVEL", "INFO")


def _open_browser(port: int, delay: float = 1.5):
    """延迟打开浏览器，等服务就绪。"""
    import time
    time.sleep(delay)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass


def main():
    import uvicorn
    from main import app  # 触发 main 侧初始化（此时已读到上述 env）

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print("=" * 52)
    print("  ModelScope Provider")
    print(f"  数据目录 : {_DATA_DIR}")
    print(f"  数据库   : {_DB_PATH}")
    print(f"  访问地址 : http://localhost:{port}")
    print(f"  文档     : http://localhost:{port}/docs")
    print("=" * 52)

    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info", reload=False)


if __name__ == "__main__":
    main()