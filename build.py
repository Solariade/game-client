"""game-client 打包入口：PyInstaller 编程接口，目录模式，资源外置。

参考 tool_sync_pic 的打包约定：
- 版本号取自 pyproject.toml，并写入 Windows exe 的版本信息；
- 产物目录带版本号：dist/game-client-v<version>/；
- 由 .env.example 生成产物中的 .env（不含真实 Key）；
- 随包附带 README、LICENSE、使用说明与版本信息；
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
ENV_EXAMPLE = ROOT / ".env.example"
README_FILE = ROOT / "README.md"
LICENSE_FILE = ROOT / "LICENSE"
USER_GUIDE = ROOT / "docs" / "使用说明.txt"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "game-client"


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
        StringStruct('FileDescription', '五子棋 AI 对弈学习'),
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
    """资源外置：将 assets/ 拷到 exe 同级目录。"""
    target = dist_dir / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ASSETS, target)
    _info(f"assets/ 已拷贝至 {target}")


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
