# Pikafish 象棋引擎安装指引

> game-client 的象棋模式依赖外部引擎 [Pikafish](https://github.com/official-pikafish/Pikafish)
> （UCI 协议子进程）。引擎文件不随仓库与官方分发包提供，请按本文自行下载安装。
> 未安装时程序自动禁用象棋：棋种下拉只有五子棋，其余功能不受影响。

## 一、下载

1. 打开发布页：<https://github.com/official-pikafish/Pikafish/releases>
2. 选择 Windows 版压缩包：

| 构建版本 | 适用 CPU | 说明 |
|---|---|---|
| **universal**（sse41-popcnt） | 绝大多数 x86-64 CPU | 不确定就选它，兼容性最好 |
| avx2 | 支持 AVX2（Haswell 及之后） | 更快 |
| bmi2 | 支持 BMI2（Skylake 及之后） | 通常最快 |

3. 压缩包内含 `pikafish.exe`、NNUE 权重 `pikafish.nnue` 与 GPL-3.0 许可文件。
   已验证版本：Pikafish.2026-09-06（universal，约 94 万 nps）。

## 二、安装

把解压出的**全部文件**放入项目（或分发包）的 `assets/engines/` 目录：

```
game-client/
└── assets/
    └── engines/
        ├── pikafish.exe
        ├── pikafish.nnue      # 必须与 exe 同目录（引擎按工作目录解析权重）
        └── COPYING.GPLv3 等
```

重新启动程序，「棋种」下拉出现「象棋」即安装成功。

`assets/engines/` 已被 `.gitignore` 忽略——引擎不会进入仓库。

## 三、自定义路径（可选）

引擎在其它位置时，编辑 `.env`：

```ini
XIANGQI_ENGINE_PATH=E:/tools/pikafish/pikafish.exe
```

权重文件仍须与该 exe 同目录。留空则使用默认的 `assets/engines/pikafish.exe`。

## 四、常见问题

- **下拉里没有「象棋」**：`assets/engines/pikafish.exe` 不存在或
  `XIANGQI_ENGINE_PATH` 指错；程序日志（`runtime/log/app.log`）会有
  「Pikafish 引擎未找到」警告；
- **提示引擎出错 / 可能是指令集版本不符**：换 universal 构建重试；
- **权重未就位**：`pikafish.nnue` 必须与 exe 同目录，缺失会导致引擎启动失败；
- **GPL-3.0 说明**：Pikafish 及其 NNUE 权重按 GPL-3.0 授权。自用打包时
  `build.py` 检测到本地引擎会随包拷贝，并在产物中附许可说明；再分发须遵守
  GPL-3.0（附许可文本与源码获取方式）。不带引擎分发则无此约束。
