"""game-client 打包入口：PyInstaller 编程接口，目录模式，资源外置。

打包约定：
- 版本号取自 pyproject.toml，并写入 Windows exe 的版本信息；
- 产物目录带版本号：dist/game-client-v<version>/；
- 由 .env.example 生成产物中的 .env（不含真实 Key）；
- 随包附带 README、LICENSE、使用说明与版本信息；
- 本地装有 Pikafish（assets/engines/）时随包拷贝，并附 GPL-3.0 许可说明；
  未安装时在产物中放置下载指引，象棋模式按设计禁用；
- 每次打包前清理 build/ 与 dist/。

用法：
    uv run python build.py
"""

from __future__ import annotations

import importlib.metadata
import platform
import shutil
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "app" / "__main__.py"
ASSETS = ROOT / "assets"
ICON = ASSETS / "logo.ico"
ENGINES = ASSETS / "engines"
PIKAFISH_EXE = ENGINES / "pikafish.exe"
ENV_EXAMPLE = ROOT / ".env.example"
README_FILE = ROOT / "README.md"
LICENSE_FILE = ROOT / "LICENSE"
USER_GUIDE = ROOT / "docs" / "使用说明.txt"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "game-client"

# 引擎随包分发时的许可说明（Pikafish 为 GPL-3.0，需附来源与许可指引）
PIKAFISH_LICENSE_NOTE = """本分发包内的 assets/engines/ 包含 Pikafish 象棋引擎
（pikafish.exe 与 pikafish.nnue 权重文件）。

Pikafish 采用 GNU General Public License v3.0（GPL-3.0）授权，
源代码与完整许可文本见官方仓库：
    https://github.com/official-pikafish/Pikafish

若再分发本包，须同时遵守 GPL-3.0 的条款（附许可文本与源码获取方式）。
不带引擎分发包时，删除 assets/engines/ 下的引擎文件即可——
程序会自动禁用象棋模式（棋种下拉仅五子棋），五子棋不受影响。
"""

# 引擎未随包时的下载指引（放入 assets/engines/ 即可启用象棋）
PIKAFISH_DOWNLOAD_GUIDE = """象棋引擎（Pikafish）安装指引
================================

本包未内置象棋引擎，启动后「棋种」下拉中只有五子棋；
按以下步骤安装后即可启用象棋模式（无需重新安装本程序）。

1. 打开发布页：https://github.com/official-pikafish/Pikafish/releases
2. 下载 Windows 版压缩包（不知 CPU 型号就选 universal 版，
   其余按 CPU 指令集选 sse41-popcnt / avx2 / bmi2，棋力更强）；
3. 解压后把 pikafish.exe、pikafish.nnue 与许可文件一起
   放入本目录（assets/engines/），保持与 exe 同目录；
4. 重新启动 game-client.exe，「棋种」下拉出现「象棋」即成功。

Pikafish 为 GPL-3.0 开源项目；也可在 .env 中用 XIANGQI_ENGINE_PATH
指定其它位置的引擎 exe。详细说明见仓库 docs/pikafish-setup.md。
"""


def _info(message: str) -> None:
    """控制台输出：时间【打包】描述。"""
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}【打包】{message}")


def read_version() -> str:
    """读取 pyproject.toml 中的项目版本。"""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def write_version_file(path: Path, version: str) -> None:
    """生成 PyInstaller 版本信息文件（中文内容需 UTF-8 BOM）。"""
    nums = [int(part) for part in version.split(".")] + [0, 0, 0, 0]
    filevers = ", ".join(str(n) for n in nums[:4])
    content = f"""# UTF-8
#
# 此文件由 build.py 自动生成，请勿手工编辑。
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({filevers}),
    prodvers=({filevers}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('080404b0', [
        StringStruct('CompanyName', 'game-client'),
        StringStruct('FileDescription', '五子棋与象棋 AI 对弈'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'game-client'),
        StringStruct('OriginalFilename', 'game-client.exe'),
        StringStruct('ProductName', 'game-client'),
        StringStruct('ProductVersion', '{version}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])]),
  ],
)
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def clean() -> None:
    for p in (DIST, BUILD):
        if p.exists():
            shutil.rmtree(p)
    _info("已清理 build/ 与 dist/")


def copy_assets_to(dist_dir: Path) -> None:
    """资源外置：将 assets/ 拷到 exe 同级目录（含 engines/，若本地已安装）。"""
    target = dist_dir / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ASSETS, target)
    _info(f"assets/ 已拷贝至 {target}")


def finalize_engines(dist_dir: Path) -> None:
    """按引擎有无收尾：有引擎附 GPL 许可说明，无引擎放下载指引。"""
    engines_dir = dist_dir / "assets" / "engines"
    if PIKAFISH_EXE.exists():
        engines_dir.mkdir(parents=True, exist_ok=True)
        (engines_dir / "引擎许可说明.txt").write_text(PIKAFISH_LICENSE_NOTE, encoding="utf-8")
        _info("已随包拷贝 Pikafish 并附 GPL-3.0 许可说明（再分发须遵守 GPL）")
    else:
        engines_dir.mkdir(parents=True, exist_ok=True)
        (engines_dir / "下载指引.txt").write_text(PIKAFISH_DOWNLOAD_GUIDE, encoding="utf-8")
        _info("未检测到 Pikafish：产物含下载指引，象棋模式将按设计禁用")


def copy_extra_files(out_dir: Path, version: str) -> None:
    """拷贝配置、文档与许可证，并生成版本信息文件。"""
    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, out_dir / ".env")
        _info("已由 .env.example 生成 .env（不含真实 Key）")
    else:
        _info("警告：未找到 .env.example，产物中将不含 .env")

    for src in (ENV_EXAMPLE, README_FILE, LICENSE_FILE, USER_GUIDE):
        if src.exists():
            shutil.copy2(src, out_dir / src.name)
            _info(f"已拷贝 {src.name}")
        else:
            _info(f"警告：未找到 {src}，已跳过")

    try:
        pyinstaller_version = importlib.metadata.version("PyInstaller")
    except importlib.metadata.PackageNotFoundError:
        pyinstaller_version = "unknown"

    build_info = (
        f"{APP_NAME} {version}\n"
        f"构建时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Python：{platform.python_version()}\n"
        f"PyInstaller：{pyinstaller_version}\n"
    )
    (out_dir / "VERSION.txt").write_text(build_info, encoding="utf-8")
    _info("已生成 VERSION.txt")


def finalize_output(out_dir: Path, version: str) -> None:
    """把 PyInstaller 的默认产物整理成带版本号的目录。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)

    (DIST / APP_NAME).rename(out_dir)
    copy_assets_to(out_dir)
    finalize_engines(out_dir)
    copy_extra_files(out_dir, version)


def main() -> int:
    clean()

    version = read_version()
    version_file = BUILD / f"{APP_NAME}.txt"
    write_version_file(version_file, version)
    _info(f"版本信息已生成：{version_file}（v{version}）")

    import PyInstaller.__main__

    pyinstaller_args = [
        str(ENTRY),
        "--name",
        APP_NAME,
        "--onedir",
        "--windowed",
        "--icon",
        str(ICON),
        # specpath 在 build/，PyInstaller 会按 spec 目录解析相对路径，故传绝对路径
        "--version-file",
        str(version_file),
        # schema.sql 是运行时读取的数据文件，必须显式打包（Windows 用 ; 分隔）
        "--add-data",
        f"{ROOT / 'app' / 'db' / 'schema.sql'};app/db",
        # 注意：assets 不用 --add-data，由下方拷贝外置
        "--hidden-import",
        "pydantic",
        "--hidden-import",
        "pydantic_settings",
        "--hidden-import",
        "openai",
        "--collect-submodules",
        "app",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),  # 临时 spec 生成在 build/，不落根目录
    ]

    PyInstaller.__main__.run(pyinstaller_args)

    # 产物目录带版本号，并附带配置、文档与许可证
    out_dir = DIST / f"{APP_NAME}-v{version}"
    finalize_output(out_dir, version)
    _info(f"完成：{out_dir}（整个目录即为分发包）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
