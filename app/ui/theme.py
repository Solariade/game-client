"""颜色、字体等样式常量。"""

from __future__ import annotations

# 棋盘
BOARD_BG = "#DEB068"  # 木色底
BOARD_LINE = "#6B4423"  # 网格线
STAR_POINT = "#3B2314"  # 星位
COORD_TEXT = "#5A4632"  # 坐标标注
BLACK_STONE = "#1A1A1A"  # 黑子
WHITE_STONE = "#F5F5F0"  # 白子
BLACK_STONE_EDGE = "#555555"  # 黑子描边
WHITE_STONE_EDGE = "#B0B0B0"  # 白子描边
WIN_LINE = "#E53935"  # 获胜五连高亮
HINT_RING = "#1E9E5A"  # 建议落子外层虚线光环

# 象棋棋子
PIECE_BG = "#F7F1DE"  # 棋子底色（米白）
RED_PIECE = "#B03A2E"  # 红方字色与描边
BLACK_PIECE = "#262626"  # 黑方字色与描边
SELECT_RING = "#2E86C1"  # 选子光环（蓝，与绿色建议区分）
CAPTURE_RING = "#C62828"  # 可吃子的落点标记（红环）
CHECK_RING = "#D32F2F"  # 被将军的将/帅光环
RIVER_TEXT = "#8A6D3B"  # 楚河汉界题字

# 面板
BG = "#F4F1EA"  # 主背景
PANEL_BG = "#FFFFFF"  # 右侧面板背景
TEXT = "#2B2B2B"
MUTED = "#8A8A8A"
ACCENT = "#2E6E4E"  # 按钮/强调
LAST_MOVE_MARK = "#E53935"  # 最后一手标记

# 字体
FONT_NORMAL = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
FONT_COMMENTARY = ("Microsoft YaHei UI", 10)
