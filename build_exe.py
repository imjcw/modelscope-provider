"""打包脚本：将 AI Provider 打包为单文件 .exe（Windows）。

用法（在项目根目录下执行）::

    python build_exe.py

前置条件：Python 3.10+，Node.js 18+（用于前端构建）。
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
NAME = "AIProvider"
DIST = ROOT / "dist"


def build_frontend():
    """构建前端到 web/dist。

    若构建失败（例如在 WSL 中 rollup 缺少平台原生模块），只要已有
    ``web/dist`` 就继续使用现有产物，绝不因构建失败清空 dist。
    """
    print(">>> 构建前端...")
    dist_dir = WEB / "dist"
    try:
        subprocess.run(["npm", "run", "build"], cwd=str(WEB), check=True)
        print("    前端构建完成。")
    except Exception as exc:
        if dist_dir.exists():
            print(f"    ⚠ 前端构建失败（{exc}），沿用已有 dist 产物。")
        else:
            print(f"    前端构建失败且无现有 dist，中止：{exc}")
            sys.exit(1)


def ensure_pyinstaller():
    """确保 PyInstaller 已安装。"""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(">>> 安装 PyInstaller...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True, capture_output=True,
        )
        print("    PyInstaller 安装完成。")


def build_exe():
    """执行 PyInstaller 打包。"""
    print(">>> PyInstaller 打包中...")

    dist_dir = DIST
    if dist_dir.exists():
        print("    清理旧 dist...")
        shutil.rmtree(dist_dir)

    sep = ";" if sys.platform == "win32" else ":"
    add_data_web = f"{WEB / 'dist'}{sep}web/dist"
    add_data_migrations = f"{ROOT / 'core' / 'migrations' / 'migrations'}{sep}core/migrations/migrations"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", NAME,
        "--noconsole",
        "--add-data", add_data_web,
        "--add-data", add_data_migrations,
        "--collect-all", "uvicorn",
        "--collect-all", "PIL",
        "--collect-submodules", "core.migrations.migrations",
        "--hidden-import", "main",
        "--hidden-import", "multiprocessing",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        str(ROOT / "run.py"),
    ]

    start = time.time()
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    elapsed = time.time() - start

    exe_path = DIST / f"{NAME}.exe"
    size_mb = exe_path.stat().st_size / (1024 * 1024) if exe_path.exists() else 0

    print()
    print("=" * 52)
    print("  ✅ 打包完成！")
    print(f"  输出文件: {exe_path}")
    print(f"  文件大小: {size_mb:.1f} MB")
    print(f"  耗时: {elapsed:.0f}s")
    print("=" * 52)
    print()
    print("  使用方法：")
    print(f"    1. 将 {NAME}.exe 复制到目标电脑")
    print("    2. 双击运行（首次启动自动创建 data/ 目录）")
    print("    3. 程序运行在系统托盘，右键图标可打开后台或退出")
    print(f"    4. 浏览器自动打开 http://localhost:8000")
    print()


def main():
    build_frontend()
    ensure_pyinstaller()
    build_exe()


if __name__ == "__main__":
    main()