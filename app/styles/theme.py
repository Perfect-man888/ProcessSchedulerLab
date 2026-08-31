APP_NAME = "ProcessSchedulerLab"
APP_SUBTITLE = "操作系统进程调度与资源管理可视化仿真平台"
APP_VERSION = "1.1.0"

WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 760
WINDOW_DEFAULT_WIDTH = 1480
WINDOW_DEFAULT_HEIGHT = 900

TOTAL_MEMORY_MB = 8192
TOTAL_IO_DEVICES = 8

COLORS = {
    "primary": "#4F6EF7",
    "primary_dark": "#3F5AE0",
    "sidebar": "#111827",
    "sidebar_deep": "#0B1220",
    "background": "#F6F8FC",
    "card": "#FFFFFF",
    "text_primary": "#172033",
    "text_secondary": "#667085",
    "text_muted": "#98A2B3",
    "border": "#E7ECF3",
    "success": "#16A36A",
    "warning": "#F59E0B",
    "danger": "#E5484D",
    "purple": "#8B5CF6",
    "cyan": "#0EA5E9",
    "ready": "#4F6EF7",
    "running": "#16A36A",
    "blocked": "#F59E0B",
    "suspended": "#8B5CF6",
    "finished": "#98A2B3",
}


def rgba(hex_color: str, alpha: int) -> str:
    """将 #RRGGBB 转为 Qt QSS 可用的 rgba(...)。"""
    color = hex_color.lstrip("#")
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


APP_FORM_QSS = """
/* Stable controls: avoid platform-sensitive spin/combo subcontrols. */
QLineEdit {
    background-color: #FFFFFF;
    color: #24324A;
    border: 1px solid #D7DFEB;
    border-radius: 10px;
    min-height: 42px;
    padding-left: 13px;
    padding-right: 13px;
    font-size: 12px;
}

QLineEdit:hover {
    border-color: #B9C6DD;
}

QLineEdit:focus {
    border-color: #4F6EF7;
}

QLineEdit:disabled {
    background-color: #F3F5F8;
    color: #98A2B3;
    border-color: #E4E7EC;
}
"""
