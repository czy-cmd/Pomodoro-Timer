# -*- coding: utf-8 -*-
"""
任务管理器 2.0  ——  Nexus 2
主体是任务列表（增删改 + 优先级 + 截止日期），外挂两个按钮：番茄钟、音乐。
只有两个模式：普通 / 性能，每个开关都有实际作用。
"""

import copy
import csv
import json
import os
import re
import sys
import subprocess
import time
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, filedialog, simpledialog

# ==================================================================
# 常量
# ==================================================================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)   # 打包后：exe 所在目录
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===================== Orbit3 接入点 =====================
# 数据统一走 Orbit3_data.json（由主程序注入 STORE），本模块不写任何源 JSON
STORE = None
MOD_VALUES = {}
DEV = {}
DATA_FILE = None          # 已废弃，仅为防止残留引用崩溃


def bind_store(store, mod_values=None):
    global STORE, MOD_VALUES
    STORE = store
    if mod_values:
        MOD_VALUES = mod_values


def ensure_presets():
    """presets 放 Orbit3 同目录；首次把源 presets 的 .rw/.txt 只读复制过来（不覆盖）"""
    d = os.path.join(BASE_DIR, "presets")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    src = r"C:\Users\54215\Desktop\czy文件\p\任务管理器\3.0\presets"
    if os.path.isdir(src):
        import shutil
        for f in os.listdir(src):
            if f.lower().endswith((".rw", ".txt")):
                dst = os.path.join(d, f)
                if not os.path.exists(dst):
                    try:
                        shutil.copy2(os.path.join(src, f), dst)
                    except Exception:
                        pass
    return d

# 旧版本的数据文件（用于首次迁移，按优先级从新到旧）
# 先认 2.0 的同目录文件；没有再找 1.0 的 tasks.json
LEGACY_FILES = [
    os.path.join(BASE_DIR, "tasks_v2.json"),
    os.path.join(BASE_DIR, "tasks.json"),
    os.path.join(os.path.dirname(BASE_DIR), "1.0", "tasks.json"),
]

APP_TITLE = "任务管理器"
APP_CODENAME = "Nexus 3"
APP_WINDOW_TITLE = "任务管理器 3.0"
APP_AUTHOR = "CZY"

# 预设文件（.rw / .txt）的版本号：只有 ver 等于它才能加载
PRESET_VER = 3
# 排序字段（沿用 2.0 的 6 个，不加新的）
SORT_FIELDS = [
    ("priority", "优先级"), ("due", "截止"), ("created", "创建时间"),
    ("category", "分类"), ("subject", "科目"), ("title", "内容"),
]


class PresetError(Exception):
    """预设文件解析出错（strict 模式 / 严重格式错误）时抛出"""
    pass

FONT = "微软雅黑"
PRIORITIES = ["高", "中", "低"]
CATEGORIES = ["学习", "生活", "工作", "其他"]
SUBJECTS = ["语文", "数学", "英语", "物理", "化学",
            "历史", "地理", "政治", "其他"]

# Orbit3：番茄钟即 Orbit3 主体，原外挂 exe 入口已移除（重复子项目）

# 任务颜色（默认跟 1.0 一致：高红 / 中蓝 / 低绿）
DEFAULT_COLORS = {
    "high": "#d32f2f",
    "mid": "#1976d2",
    "low": "#388e3c",
    "done": "#9e9e9e",
    "overdue": "#e74c3c",
}
COLOR_LABELS = [
    ("high", "高优先级"),
    ("mid", "中优先级"),
    ("low", "低优先级"),
    ("done", "已完成"),
    ("overdue", "逾期"),
]

COLOR_PRIMARY = "#2ecc71"
COLOR_DARK = "#2c3e50"
COLOR_ACCENT = "#e67e22"
COLOR_DANGER = "#e74c3c"
COLOR_GRAY = "#95a5a6"

WIN_W, WIN_H = 900, 640

# ------------------ 模式定义 ------------------
# key -> 显示名 / 图标 / 颜色 / 一句话说明 / 行为配置
MODES = {
    "normal": {
        "name": "学习 · 普通模式", "icon": "📋", "color": COLOR_PRIMARY,
        "desc": "七列全开，带颜色标记、科目概览和今日目标",
        "filter": "全部", "category": "全部", "new_cat": "学习", "sort": "priority",
        "cols": ["done", "priority", "title", "subject", "category", "due", "created"],
        "row": 26, "goal": True, "subjects": True,
    },
    "perf": {
        "name": "学习 · 性能模式", "icon": "⚡", "color": COLOR_ACCENT,
        "desc": "只看五列、只看未完成，任务多时更快",
        "filter": "未完成", "category": "全部", "new_cat": "学习", "sort": "priority",
        "cols": ["done", "priority", "title", "subject", "due"],
        "row": 22, "goal": False, "subjects": True,
    },
}
MODE_ORDER = ["normal", "perf"]

DEFAULT_SETTINGS = {
    "auto_save": True,          # 改动后自动保存
    "save_on_close": True,      # 关闭时保存
    "confirm_delete": True,     # 删除前弹确认
    "strike_done": True,        # 已完成任务加删除线
    "color_tasks": True,        # 彩色展示任务（不同优先级不同颜色）
    "multi_select": False,      # 列表多选（关闭时一次只能选一条）
    "colors": dict(DEFAULT_COLORS),
    "skip_mode_select": False,  # 启动时直接进入上次模式
    "bug_tools": True,          # 主界面 / 编辑窗 / 批量窗 是否显示「🩺 急救」入口
    "default_priority": "中",
    "row_height": 26,
    "daily_goal": 5,            # 每日完成几条算达标
    # ---- 3.0 新增设置 ----
    "add_ui": "new",           # 新建任务界面：new=弹窗 / classic=行内输入
    "sort_col": "priority",    # 全局排序字段
    "sort_reverse": False,     # 全局排序方向
    "sort_col_normal": "",     # 仅普通模式（空=跟随全局）
    "sort_reverse_normal": False,
    "sort_col_perf": "",       # 仅性能模式（空=跟随全局）
    "sort_reverse_perf": False,
    "preset_enabled": True,    # 启用预设功能
    "preset_default_format": "simple",  # 预设默认格式（simple / py）
    "preset_disabled_files": [],        # 被手动禁用的 rw 文件名（只存文件名）
}

COL_HEADINGS = {
    "done": ("状态", 54, "center"),
    "priority": ("优先级", 62, "center"),
    "title": ("任务内容", 286, "w"),
    "subject": ("科目", 62, "center"),
    "category": ("分类", 58, "center"),
    "due": ("截止", 92, "center"),
    "created": ("创建时间", 124, "center"),
}


# ==================================================================
# 小工具
# ==================================================================
def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def parse_date(s):
    """空 -> None；合法 -> date；非法 -> 抛 ValueError"""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if fmt == "%m-%d":
            d = d.replace(year=datetime.now().year)
        return d.date()
    raise ValueError("日期格式应为 YYYY-MM-DD")


def due_delta(due):
    """返回 (天数差, date)；due 为空返回 (None, None)"""
    if not due:
        return None, None
    try:
        d = parse_date(due)
    except ValueError:
        return None, None
    if d is None:
        return None, None
    return (d - datetime.now().date()).days, d


def due_text(due):
    delta, d = due_delta(due)
    if delta is None:
        return ""
    if delta < 0:
        return f"逾期{-delta}天"
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    return f"{d.strftime('%m-%d')}({delta}天)"


def text_on(hexcolor):
    """按背景亮度决定用黑字还是白字"""
    try:
        h = str(hexcolor).lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return "white"
    return "#000000" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#ffffff"


def center_window(win, w, h, parent=None):
    win.update_idletasks()
    if parent is not None:
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    else:
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")


class ScrolledFrame:
    """Orbit2 风格的可滚动内容区"""

    def __init__(self, master, width=None, bg="white"):
        outer = tk.Frame(master)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=bg)
        sb = tk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", width=width)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _wheel(event):
            try:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        self.canvas.bind_all("<MouseWheel>", _wheel)
        master.bind("<Destroy>", lambda e: self.canvas.unbind_all("<MouseWheel>"))


# ==================================================================
# 主程序
# ==================================================================
class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_WINDOW_TITLE)
        self.root.geometry(f"{WIN_W}x{WIN_H}")
        self.root.minsize(760, 470)

        self.tasks = []
        self.next_id = 1
        self.settings = dict(DEFAULT_SETTINGS)
        self.last_mode = "normal"
        self.mode = "normal"
        self.undo_stack = []
        self.study_goal_log = {}    # {日期: True} 记录达成每日学习目标的日子

        self.filter_var = tk.StringVar(value="全部")
        self.category_var = tk.StringVar(value="全部")
        self.subject_var = tk.StringVar(value="全部")
        self.search_var = tk.StringVar(value="")
        self.sort_col = "priority"
        self.sort_reverse = False
        self.strike_font = None
        self._sel_anchor = None         # Shift 连选的起点
        self._last_click_row = None     # 用来认出「双击的第二下」
        self._last_click_time = 0
        self._ops_win = None            # 非模态「操作」窗口
        self._ops_sel_label = None      # 操作窗口顶部选中状态
        self._ops_btns = {}             # 操作窗口按钮（按名存）
        self._preset_list_frame = None  # 设置里预设文件列表

        self.load_data()
        self._bind_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_main_menu()

    # ==================================================================
    # 数据存取
    # ==================================================================
    def default_data(self):
        return {"next_id": 1, "tasks": [], "settings": dict(DEFAULT_SETTINGS),
                "last_mode": "normal"}

    def load_data(self):
        # Orbit3：从 Orbit3_data.json 的 tasks 段读取（源 tasks_v3.json 的合并由主程序负责）
        data = STORE.seg("tasks")
        if not isinstance(data, dict) or not data:
            data = self.default_data()

        raw = data.get("tasks", []) if isinstance(data, dict) else []
        if not isinstance(raw, list):
            raw = []

        self.tasks = []
        for t in raw:
            if not isinstance(t, dict):
                continue
            self.tasks.append({
                "id": int(t.get("id", 0)),
                "title": str(t.get("title", "")).strip(),
                "priority": t.get("priority", "中") if t.get("priority") in PRIORITIES else "中",
                "category": t.get("category", "") or "",
                "subject": t.get("subject", "") or "",
                "due": t.get("due", "") or "",
                "note": t.get("note", "") or "",
                "done": bool(t.get("done", False)),
                "created": t.get("created", "") or "",
                "done_at": t.get("done_at", "") or "",
            })
        self.tasks = [t for t in self.tasks if t["title"]]

        self.next_id = int(data.get("next_id", 1)) if isinstance(data, dict) else 1
        max_id = max([t["id"] for t in self.tasks] + [0])
        self.next_id = max(self.next_id, max_id + 1)

        st = data.get("settings", {}) if isinstance(data, dict) else {}
        if isinstance(st, dict):
            for k, v in DEFAULT_SETTINGS.items():
                self.settings[k] = st.get(k, v)
            # 预设禁用列表缺失或不是列表时补成空列表
            if not isinstance(self.settings.get("preset_disabled_files"), list):
                self.settings["preset_disabled_files"] = []
            # 颜色可能缺项（老存档），补齐
            colors = self.settings.get("colors")
            if not isinstance(colors, dict):
                colors = {}
            for k, v in DEFAULT_COLORS.items():
                colors.setdefault(k, v)
            self.settings["colors"] = colors
        self.last_mode = data.get("last_mode", "normal") if isinstance(data, dict) else "normal"
        if self.last_mode not in MODES:
            self.last_mode = "normal"
        self.mode = self.last_mode

        log = data.get("study_goal_log", {}) if isinstance(data, dict) else {}
        self.study_goal_log = log if isinstance(log, dict) else {}

    def _read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            messagebox.showwarning("读取失败", f"数据文件无法读取，将从空列表开始。\n{e}")
            return None

    def save_data(self, show_msg=False):
        data = {
            "next_id": self.next_id,
            "tasks": self.tasks,
            "settings": self.settings,
            "study_goal_log": self.study_goal_log,
            "last_mode": self.mode,
            "last_save": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            seg = STORE.seg("tasks")
            seg.clear()
            seg.update(data)
            STORE.save()
            if show_msg:
                messagebox.showinfo("提示", f"已保存到：\n{STORE.path}")
            return True
        except OSError as e:
            messagebox.showerror("保存失败", str(e))
            return False

    # ==================================================================
    # 撤销
    # ==================================================================
    def push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.tasks))
        if len(self.undo_stack) > 30:
            del self.undo_stack[0]

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("提示", "没有可撤销的操作")
            return
        self.tasks = self.undo_stack.pop()
        self.refresh()
        if self.settings["auto_save"]:
            self.save_data()

    # ==================================================================
    # 通用
    # ==================================================================
    def clear_root(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _bind_hotkeys(self):
        r = self.root

        def task_only(func):
            def wrapper(event=None):
                if self._in_task_ui():
                    func()
            return wrapper

        r.bind_all("<Control-s>", lambda e: self.save_data(show_msg=True))
        r.bind_all("<Control-z>", task_only(self.undo))
        r.bind_all("<Control-e>", task_only(self.edit_selected))
        r.bind_all("<Control-m>", task_only(self.open_batch_editor))
        r.bind_all("<Control-f>", task_only(self.focus_search))
        r.bind_all("<Control-n>", task_only(self.hotkey_new))

    def focus_search(self):
        if getattr(self, "search_entry", None):
            try:
                self.search_entry.focus_set()
                self.search_entry.select_range(0, "end")
            except tk.TclError:
                pass

    def focus_entry(self):
        if getattr(self, "entry", None):
            try:
                self.entry.focus_set()
            except tk.TclError:
                pass

    def _on_tree_select(self):
        self.update_status()
        self._update_ops_status()

    def hotkey_new(self):
        """Ctrl+N：new 模式弹新建窗口；classic 模式跳到输入框"""
        if self.settings.get("add_ui") == "new":
            self.open_new_task()
        else:
            self.focus_entry()

    # ==================================================================
    # 界面一：开头主菜单
    # ==================================================================
    def show_main_menu(self):
        self.clear_root()
        self.root.title(APP_WINDOW_TITLE)
        self.root.geometry(f"{WIN_W}x{WIN_H}")

        frame = tk.Frame(self.root)
        frame.place(relx=0.5, rely=0.42, anchor="center")

        tk.Label(frame, text=APP_TITLE, font=(FONT, 40, "bold"),
                 fg=COLOR_DARK).pack()
        tk.Label(frame, text=APP_CODENAME, font=(FONT, 13),
                 fg=COLOR_GRAY).pack(pady=(0, 8))
        tk.Label(frame, text="管任务 · 开番茄钟 · 放音乐 · 数据自动存",
                 font=(FONT, 10), fg=COLOR_GRAY).pack(pady=(0, 30))

        def mk_btn(text, cmd, bg="white", fg=COLOR_DARK, hover="#ecf0f1"):
            b = tk.Button(frame, text=text, command=cmd, font=(FONT, 14), width=18,
                          bg=bg, fg=fg, relief=tk.FLAT, cursor="hand2",
                          activebackground=hover, activeforeground=fg)
            b.pack(pady=5, ipady=4)
            return b

        mk_btn("开始使用", self.open_mode_selection_with_progress,
               bg=COLOR_PRIMARY, fg="white", hover="#27ae60")
        mk_btn("更新日志", self.show_changelog)
        mk_btn("设置", self.show_settings)
        mk_btn("快捷键说明", self.show_hotkeys)
        mk_btn("退出", self.on_close, fg=COLOR_DANGER, hover="#fdecea")

        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", pady=14)
        tk.Label(bottom, text=f"v3.0 · 作者 {APP_AUTHOR} · 数据由 Orbit3 统一管理（Orbit3_data.json）",
                 font=(FONT, 9), fg=COLOR_GRAY).pack()
        tk.Button(bottom, text="🩺 BUG 修复", command=self.show_repair,
                  font=(FONT, 9), fg=COLOR_DANGER, bg="white", relief=tk.FLAT,
                  cursor="hand2").pack(pady=(4, 0))

    # ==================================================================
    # 界面二：加载进度条 → 选择模式
    # ==================================================================
    def open_mode_selection_with_progress(self):
        # 设置了「直接进入上次模式」就跳过选择界面
        if self.settings.get("skip_mode_select") and self.last_mode in MODES:
            self.enter_mode(self.last_mode)
            return

        prog = tk.Toplevel(self.root)
        prog.title("加载中")
        prog.resizable(False, False)
        prog.transient(self.root)
        center_window(prog, 420, 140, self.root)
        prog.grab_set()

        tk.Label(prog, text="正在加载模式选择…", font=(FONT, 12)).pack(pady=(20, 8))
        bar = ttk.Progressbar(prog, orient="horizontal", length=340,
                              mode="determinate", maximum=100)
        bar.pack(pady=6)
        pct = tk.Label(prog, text="0%", font=(FONT, 10), fg=COLOR_GRAY)
        pct.pack()

        def step(v=0):
            if v > 100:
                try:
                    prog.grab_release()
                except tk.TclError:
                    pass
                prog.destroy()
                self.show_mode_selection()
                return
            bar["value"] = v
            pct.config(text=f"{v}%")
            prog.after(12, lambda: step(v + 4))

        step(0)

    def show_mode_selection(self, from_task_ui=False):
        self.clear_root()
        self.root.title(f"{APP_WINDOW_TITLE} - 选择模式")
        self.root.geometry(f"{WIN_W}x{WIN_H}")

        tk.Label(self.root, text="📌 选择使用模式",
                 font=(FONT, 20, "bold"), fg=COLOR_DARK).pack(pady=(18, 4))
        tk.Label(self.root, text="两个模式的区别：显示哪些列、要不要颜色、默认看哪些任务。数据完全共用",
                 font=(FONT, 9), fg=COLOR_GRAY).pack(pady=(0, 6))

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True)

        self.mode_var = tk.StringVar(value=self.last_mode if self.last_mode in MODES else "normal")

        for key in MODE_ORDER:
            m = MODES[key]
            row = tk.Frame(body)
            row.pack(fill="x", padx=110, pady=6)
            rb = tk.Radiobutton(
                row, text=f"{m['icon']}  {m['name']}", variable=self.mode_var,
                value=key, font=(FONT, 14, "bold"), fg=m["color"],
                activeforeground=m["color"], selectcolor="#eafaf1",
                cursor="hand2", anchor="w", width=14)
            rb.pack(side="left")
            tk.Label(row, text=m["desc"], font=(FONT, 10), fg=COLOR_GRAY,
                     anchor="w", justify="left").pack(side="left", padx=(8, 0))


        btn = tk.Frame(self.root)
        btn.pack(pady=18)
        tk.Button(btn, text="确认选择", command=self.confirm_mode,
                  font=(FONT, 12), bg=COLOR_PRIMARY, fg="white", width=12,
                  relief=tk.FLAT, cursor="hand2", activebackground="#27ae60").pack(side="left", padx=6)
        tk.Button(btn, text="返回主菜单" if not from_task_ui else "返回任务列表",
                  command=(self.show_main_menu if not from_task_ui else self.build_task_ui),
                  font=(FONT, 12), width=12, relief=tk.FLAT, cursor="hand2").pack(side="left", padx=6)

    def confirm_mode(self):
        key = self.mode_var.get()
        if key not in MODES:
            messagebox.showwarning("提示", "请选择一个模式！")
            return
        self.enter_mode(key)

    def enter_mode(self, key):
        conf = MODES[key]
        self.mode = key
        self.last_mode = key
        self.filter_var.set(conf["filter"])
        self.category_var.set(conf["category"])
        # 排序不再写死：按当前模式 + 设置里的排序生效（见 _eff_sort）
        self.build_task_ui()

    # ==================================================================
    # 界面三：任务列表（主体）
    # ==================================================================
    def build_task_ui(self):
        self.clear_root()
        conf = MODES[self.mode]
        self.root.title(f"{APP_WINDOW_TITLE} - {conf['name']}")
        self.root.geometry(f"{WIN_W}x{WIN_H}")
        # 重建前先关掉非模态操作窗口，避免引用到已销毁的列表
        if self._ops_win is not None:
            try:
                if self._ops_win.winfo_exists():
                    self._ops_win.destroy()
            except tk.TclError:
                pass
            self._ops_win = None
        # 当前生效的排序（按模式 + 设置取）
        self.sort_col, self.sort_reverse = self._eff_sort()

        # ---------- 顶部：标题 + 模式 ----------
        head = tk.Frame(self.root, bg=conf["color"])
        head.pack(fill="x")
        tk.Label(head, text=f"{conf['icon']} {APP_TITLE} · {conf['name']}",
                 font=(FONT, 15, "bold"), bg=conf["color"], fg="white").pack(side="left", padx=12, pady=8)
        if self.settings.get("bug_tools", True):
            tk.Button(head, text="🩺 急救", command=self.show_repair,
                      font=(FONT, 10), bg="#fdecea", fg=COLOR_DANGER, relief=tk.FLAT,
                      cursor="hand2").pack(side="right", padx=6)
        tk.Button(head, text="切换模式", command=lambda: self.show_mode_selection(from_task_ui=True),
                  font=(FONT, 10), bg="white", fg=conf["color"], relief=tk.FLAT,
                  cursor="hand2").pack(side="right", padx=6)
        tk.Button(head, text="主菜单", command=self.back_to_menu,
                  font=(FONT, 10), bg="white", fg=COLOR_DARK, relief=tk.FLAT,
                  cursor="hand2").pack(side="right", padx=6)

        # ---------- 今日目标 / 连续打卡 ----------
        if conf.get("goal"):
            goal_bar = tk.Frame(self.root, bg="#fdfefe")
            goal_bar.pack(fill="x", padx=12, pady=(6, 0))
            done_today, goal, streak = self.study_stats()
            pct = int(done_today * 100 / goal) if goal > 0 else 0
            pct = min(pct, 100)
            tk.Label(goal_bar, text="🎯 今日目标", font=(FONT, 10, "bold"),
                     bg="#fdfefe", fg=COLOR_DARK).pack(side="left")
            self.goal_pb = ttk.Progressbar(goal_bar, orient="horizontal", length=180,
                                           mode="determinate", maximum=100)
            self.goal_pb["value"] = pct
            self.goal_pb.pack(side="left", padx=8)
            self.goal_label = tk.Label(goal_bar, text=f"{done_today}/{goal} 条",
                                       font=(FONT, 10), bg="#fdfefe", fg=COLOR_DARK)
            self.goal_label.pack(side="left")
            self.streak_label = tk.Label(goal_bar, text=f"🔥 连续打卡 {streak} 天",
                                         font=(FONT, 10, "bold"), bg="#fdfefe",
                                         fg=COLOR_ACCENT)
            self.streak_label.pack(side="left", padx=16)
            tk.Label(goal_bar, text="（目标条数在设置里改）",
                     font=(FONT, 9), bg="#fdfefe", fg=COLOR_GRAY).pack(side="right")

        # ---------- 科目概览：点一下就只看这个科目 ----------
        if conf.get("subjects"):
            row_sub = tk.Frame(self.root)
            row_sub.pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(row_sub, text="📚 未完成：", font=(FONT, 10, "bold"),
                     fg=COLOR_DARK).pack(side="left")
            self.subj_bar = tk.Frame(row_sub)
            self.subj_bar.pack(side="left", fill="x", expand=True)

        # ---------- 筛选与搜索（独立一行，不进任何板块）----------
        bar = tk.Frame(self.root)
        bar.pack(fill="x", padx=12, pady=(6, 6))

        tk.Label(bar, text="显示：", font=(FONT, 10)).pack(side="left")
        f_cb = ttk.Combobox(bar, textvariable=self.filter_var, width=7, state="readonly",
                            values=["全部", "未完成", "已完成"], font=(FONT, 10))
        f_cb.pack(side="left", padx=(0, 10))
        f_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(bar, text="分类：", font=(FONT, 10)).pack(side="left")
        c_cb = ttk.Combobox(bar, textvariable=self.category_var, width=7, state="readonly",
                            values=["全部"] + CATEGORIES, font=(FONT, 10))
        c_cb.pack(side="left", padx=(0, 10))
        c_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(bar, text="科目：", font=(FONT, 10)).pack(side="left")
        s_cb = ttk.Combobox(bar, textvariable=self.subject_var, width=7, state="readonly",
                            values=["全部"] + SUBJECTS, font=(FONT, 10))
        s_cb.pack(side="left", padx=(0, 10))
        s_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(bar, text="🔍", font=(FONT, 10)).pack(side="left")
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=12, font=(FONT, 10))
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_var.trace_add("write", lambda *a: self.refresh())

        # ---------- 新建 / 操作入口（按 add_ui 切换）----------
        self._build_add_area()

        # ---------- 列表 ----------
        wrap = tk.Frame(self.root)
        wrap.pack(fill="both", expand=True, padx=12)

        style = ttk.Style()
        row_h = 22 if self.mode == "perf" else int(self.settings.get("row_height", 26))
        style.configure("Treeview", rowheight=row_h, font=(FONT, 10))
        style.configure("Treeview.Heading", font=(FONT, 10, "bold"))

        cols = conf["cols"]
        self.cols = cols
        self.tree = ttk.Treeview(wrap, columns=cols, displaycolumns=cols,
                                 show="headings",
                                 selectmode="extended" if self.settings.get("multi_select")
                                 else "browse")
        for c in cols:
            name, width, anchor = COL_HEADINGS[c]
            self.tree.heading(c, text=name, command=lambda cc=c: self.sort_by(cc))
            self.tree.column(c, width=width, anchor=anchor,
                             stretch=(c == "title"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ---------- 颜色标记 ----------
        self.colors_on = bool(self.settings.get("color_tasks", True))
        self.strike_font = tkfont.Font(family=FONT, size=10,
                                       overstrike=bool(self.settings["strike_done"]))
        self.bold_font = tkfont.Font(family=FONT, size=10, weight="bold")
        plain = "#2c3e50"
        self.tree.tag_configure(
            "done",
            foreground=self.color_of("done") if self.colors_on else plain,
            font=self.strike_font if self.settings["strike_done"] else "")
        for tag in ("high", "mid", "low"):
            self.tree.tag_configure(
                tag, foreground=self.color_of(tag) if self.colors_on else plain)
        self.tree.tag_configure(
            "overdue",
            foreground=self.color_of("overdue") if self.colors_on else plain,
            font=self.bold_font if self.colors_on else "")

        self.tree.bind("<ButtonPress-1>", self._on_tree_press)       # 点一下选一条
        self.tree.bind("<Double-1>", lambda e: self.toggle_done())   # 双击 = 切换完成
        self.tree.bind("<space>", lambda e: self.toggle_done())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Control-a>", lambda e: self.select_all())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())
        self.tree.bind("<Button-3>", self._popup_menu)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="编辑任务…（Ctrl+E）", command=self.edit_selected)
        self.menu.add_command(label="修改所选…（Ctrl+M）", command=self.open_batch_editor)
        self.menu.add_command(label="切换完成状态", command=self.toggle_done)
        self.menu.add_command(label="复制任务内容", command=self.copy_title)
        self.menu.add_separator()
        self.menu.add_command(label="删除任务", command=self.delete_selected)
        self.menu.add_separator()
        self.menu.add_command(label="全选（Ctrl+A）", command=self.select_all)
        self.menu.add_command(label="反选", command=self.invert_selection)
        # 索引：0 编辑 /1 修改所选 /2 完成 /3 复制 /4 分隔 /5 删除 /6 分隔 /7 全选 /8 反选

        # ---------- 状态栏 ----------
        self.status = tk.Label(self.root, text="", anchor="w", font=(FONT, 9),
                               fg=COLOR_DARK, padx=12, pady=4)
        self.status.pack(fill="x", side="bottom")

        self.focus_entry()
        self.refresh()

    def back_to_menu(self):
        if self.settings["auto_save"]:
            self.save_data()
        self.show_main_menu()

    def _popup_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
        # 全选 / 反选 只在多选模式下可用
        state = "normal" if self.multi_on() else "disabled"
        try:
            self.menu.entryconfig(7, state=state)
            self.menu.entryconfig(8, state=state)
        except tk.TclError:
            pass
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def copy_title(self):
        ids = self._selected_ids()
        if not ids:
            return
        texts = [t["title"] for t in self.tasks if t["id"] in ids]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(texts))

    # ==================================================================
    # 多选开关（工具栏按钮 + 设置里都能改）
    # ==================================================================
    def multi_on(self):
        return bool(self.settings.get("multi_select", False))

    def toggle_multi_select(self):
        """工具栏的「多选」按钮：开关 + 立刻应用到列表"""
        self.settings["multi_select"] = not self.multi_on()
        self.save_data()
        if not self.settings["multi_select"]:
            # 关掉多选时只留下第一条，避免误伤
            self._keep_single_selection()
        self._apply_selectmode()
        self._update_multi_btn()
        self._refresh_ops_buttons()
        self.update_status()

    def _apply_selectmode(self):
        if not self._in_task_ui():
            return
        try:
            self.tree.configure(
                selectmode="extended" if self.multi_on() else "browse")
        except tk.TclError:
            pass

    def _keep_single_selection(self):
        if not self._in_task_ui():
            return
        try:
            sel = list(self.tree.selection())
        except tk.TclError:
            return
        if len(sel) > 1:
            self.tree.selection_set(sel[0])

    def _update_multi_btn(self):
        if not getattr(self, "multi_btn", None):
            return
        try:
            if not self.multi_btn.winfo_exists():
                return
        except tk.TclError:
            return
        on = self.multi_on()
        self.multi_btn.config(
            text="☑ 多选" if on else "☐ 多选",
            bg=COLOR_PRIMARY if on else "#ecf0f1",
            fg="white" if on else COLOR_DARK,
            activebackground="#27ae60" if on else "#dfe6e9",
            activeforeground="white" if on else COLOR_DARK)

    def select_all(self):
        if not self.multi_on():
            messagebox.showinfo("提示", "多选现在是关闭的，点工具栏的「☐ 多选」开启后再全选")
            return
        self.tree.selection_set(self.tree.get_children())
        self.update_status()

    def invert_selection(self):
        if not self.multi_on():
            messagebox.showinfo("提示", "多选现在是关闭的，点工具栏的「☐ 多选」开启后再反选")
            return
        kids = list(self.tree.get_children())
        sel = set(self.tree.selection())
        new = [i for i in kids if i not in sel]
        if new:
            self.tree.selection_set(new)
        else:
            self.tree.selection_remove(*kids)
        self.update_status()

    # ==================================================================
    # 点击选中逻辑（自己接管，不再靠 Tk 那套时灵时不灵的 extended）
    # ==================================================================
    def _on_tree_press(self, event):
        """
        多选开启：点几行就选中几行（再点一下那行取消），不按 Ctrl / Shift 也累加；
        Shift 点 = 连选一段。
        多选关闭：不管怎么点（含 Ctrl / Shift）永远只留一条。
        """
        row = self.tree.identify_row(event.y)

        if not self.multi_on():
            # 单选模式：Ctrl / Shift 也别想多选，直接锁成一条
            if row and (event.state & 0x0005):        # Shift=0x1 / Ctrl=0x4
                self.tree.selection_set(row)
                return "break"
            return None                                # 其余交给 Tk 的 browse

        if not row:                                    # 点空白：默认清空
            self._sel_anchor = None
            return None

        now = int(time.time() * 1000)
        if row == self._last_click_row and now - self._last_click_time <= 400:
            # 双击的第二下：不动选中状态，交给 <Double-1> 切换完成
            self._last_click_time = 0
            return "break"
        self._last_click_row, self._last_click_time = row, now

        if (event.state & 0x0001) and self._sel_anchor:      # Shift：连选一段
            kids = self.tree.get_children()
            if row in kids and self._sel_anchor in kids:
                a, b = kids.index(self._sel_anchor), kids.index(row)
                for k in kids[min(a, b):max(a, b) + 1]:
                    self.tree.selection_add(k)
                return "break"

        if row in self.tree.selection():
            self.tree.selection_remove(row)
        else:
            self.tree.selection_add(row)
            self._sel_anchor = row
        self.update_status()
        return "break"

    # ==================================================================
    # 任务操作
    # ==================================================================
    def _append_task(self, title, priority, subject, category, due="", note="",
                     done=False, done_at="", created=None):
        """往列表追加一条任务（不写盘、不刷新、不 push_undo），供 add_task / 预设共用"""
        self.tasks.append({
            "id": self.next_id,
            "title": title,
            "priority": priority or "中",
            # 选了科目就是学习任务，分类自动跟着走
            "category": "学习" if subject else category,
            "subject": subject,
            "due": due,
            "note": note,
            "done": bool(done),
            "created": created or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "done_at": done_at,
        })
        self.next_id += 1

    def add_task(self):
        title = self.entry.get().strip() if self.entry else ""
        if not title:
            messagebox.showwarning("提示", "请输入任务内容")
            self.focus_entry()
            return
        subject = self.subject_cb.get().strip() if self.subject_cb else ""
        cat = self.cat_cb.get().strip() if self.cat_cb else ""
        self.push_undo()
        self._append_task(title, self.priority_cb.get() or "中", subject, cat)
        self.entry.delete(0, "end")
        self.refresh()
        if self.settings["auto_save"]:
            self.save_data()
        self.focus_entry()

    def _selected_ids(self):
        try:
            return [int(i) for i in self.tree.selection()]
        except (tk.TclError, ValueError):
            return []

    def _find(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                return t
        return None

    def toggle_done(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("提示", "请先选择任务")
            return
        self.push_undo()
        for t in self.tasks:
            if t["id"] in ids:
                t["done"] = not t["done"]
                t["done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M") if t["done"] else ""
        self.refresh()
        if self.settings["auto_save"]:
            self.save_data()

    def delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("提示", "请先选择要删除的任务")
            return
        if self.settings["confirm_delete"]:
            if not messagebox.askyesno("确认", f"确定要删除选中的 {len(ids)} 个任务吗？\n（可用 Ctrl+Z 撤销）"):
                return
        self.push_undo()
        self.tasks = [t for t in self.tasks if t["id"] not in ids]
        self.refresh()
        if self.settings["auto_save"]:
            self.save_data()

    def clear_done(self):
        n = sum(1 for t in self.tasks if t["done"])
        if n == 0:
            messagebox.showinfo("提示", "没有已完成的任务")
            return
        if not messagebox.askyesno("确认", f"确定要清空 {n} 个已完成的任务吗？\n（可用 Ctrl+Z 撤销）"):
            return
        self.push_undo()
        self.tasks = [t for t in self.tasks if not t["done"]]
        self.refresh()
        if self.settings["auto_save"]:
            self.save_data()

    # ---------- 编辑窗口（模态：不保存/取消就不能操作主界面）----------
    def edit_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("提示", "请先选择要编辑的任务")
            return
        if len(ids) > 1:
            messagebox.showinfo("提示", "一次只能编辑一个任务")
            return
        task = self._find(ids[0])
        if task:
            self.open_editor(task)

    def open_editor(self, task):
        win = tk.Toplevel(self.root)
        win.title("编辑任务")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 540, 500, self.root)

        header = tk.Frame(win, bg=COLOR_DARK)
        header.pack(fill="x")
        tk.Label(header, text="✎ 编辑任务", font=(FONT, 18, "bold"),
                 bg=COLOR_DARK, fg="white").pack(pady=(12, 2))
        tk.Label(header, text="修改完成前，主界面不可用（点“保存”或“取消”）",
                 font=(FONT, 9), bg=COLOR_DARK, fg="#bdc3c7").pack(pady=(0, 10))

        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=24, pady=(14, 0))

        # 任务内容
        tk.Label(body, text="任务内容 *", font=(FONT, 11, "bold"),
                 fg=COLOR_DARK, anchor="w").pack(fill="x")
        title_var = tk.StringVar(value=task["title"])
        title_en = ttk.Entry(body, textvariable=title_var, font=(FONT, 11))
        title_en.pack(fill="x", pady=(2, 10), ipady=3)

        # 优先级 / 分类
        row = tk.Frame(body)
        row.pack(fill="x", pady=(0, 10))
        tk.Label(row, text="优先级", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        pri_var = tk.StringVar(value=task["priority"])
        ttk.Combobox(row, textvariable=pri_var, values=PRIORITIES, width=5,
                     state="readonly", font=(FONT, 11)).pack(side="left", padx=(6, 18))
        tk.Label(row, text="科目", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        sub_var = tk.StringVar(value=task.get("subject", "") or "")
        ttk.Combobox(row, textvariable=sub_var, values=SUBJECTS, width=7,
                     font=(FONT, 11)).pack(side="left", padx=(6, 14))
        tk.Label(row, text="分类", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        cat_var = tk.StringVar(value=task["category"] or "")
        ttk.Combobox(row, textvariable=cat_var, values=CATEGORIES, width=7,
                     font=(FONT, 11)).pack(side="left", padx=6)
        done_var = tk.BooleanVar(value=task["done"])
        tk.Checkbutton(row, text="已完成", variable=done_var, font=(FONT, 11),
                       cursor="hand2").pack(side="right")

        # 截止日期
        tk.Label(body, text="截止日期（留空表示不限，格式 YYYY-MM-DD）",
                 font=(FONT, 11, "bold"), fg=COLOR_DARK, anchor="w").pack(fill="x")
        due_row = tk.Frame(body)
        due_row.pack(fill="x", pady=(2, 4))
        due_var = tk.StringVar(value=task["due"])
        ttk.Entry(due_row, textvariable=due_var, font=(FONT, 11), width=18).pack(side="left")

        def set_due(text):
            due_var.set(text)

        for label, val in [("今天", today_str()),
                           ("明天", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
                           ("一周后", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
                           ("清除", "")]:
            tk.Button(due_row, text=label, command=lambda v=val: set_due(v),
                      font=(FONT, 9), relief=tk.FLAT, bg="#ecf0f1",
                      cursor="hand2").pack(side="left", padx=2)

        # 备注
        tk.Label(body, text="备注", font=(FONT, 11, "bold"),
                 fg=COLOR_DARK, anchor="w").pack(fill="x", pady=(8, 0))
        note_box = tk.Text(body, height=7, font=(FONT, 10), wrap="word",
                           relief=tk.SOLID, bd=1)
        note_box.pack(fill="both", expand=True, pady=(2, 4))
        note_box.insert("1.0", task.get("note", ""))

        # 按钮
        btns = tk.Frame(win)
        btns.pack(fill="x", pady=(6, 14))

        def do_save():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("提示", "任务内容不能为空", parent=win)
                title_en.focus_set()
                return
            due_raw = due_var.get().strip()
            try:
                parse_date(due_raw)
            except ValueError:
                messagebox.showwarning("提示", "截止日期格式不对，应为 YYYY-MM-DD", parent=win)
                return
            self.push_undo()
            subject = sub_var.get().strip()
            task["title"] = title
            task["priority"] = pri_var.get()
            task["subject"] = subject
            # 填了科目就当学习任务，分类自动补上
            task["category"] = "学习" if subject and not cat_var.get().strip() \
                else cat_var.get().strip()
            task["due"] = due_raw
            task["note"] = note_box.get("1.0", "end").strip()
            if done_var.get() and not task["done"]:
                task["done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            elif not done_var.get():
                task["done_at"] = ""
            task["done"] = done_var.get()
            close()
            self.refresh()
            if self.tree.exists(str(task["id"])):
                self.tree.selection_set(str(task["id"]))
            if self.settings["auto_save"]:
                self.save_data()

        def do_delete():
            if messagebox.askyesno("确认", f"删除任务「{task['title']}」？", parent=win):
                self.push_undo()
                self.tasks = [t for t in self.tasks if t["id"] != task["id"]]
                close()
                self.refresh()
                if self.settings["auto_save"]:
                    self.save_data()

        def cancel():
            if title_var.get().strip() != task["title"] or \
                    pri_var.get() != task["priority"] or \
                    cat_var.get().strip() != (task["category"] or "") or \
                    sub_var.get().strip() != (task.get("subject", "") or "") or \
                    due_var.get().strip() != (task["due"] or "") or \
                    note_box.get("1.0", "end").strip() != (task.get("note", "") or "") or \
                    done_var.get() != task["done"]:
                if not messagebox.askyesno("放弃修改", "有未保存的修改，确定放弃吗？", parent=win):
                    return
            close()

        def on_x():
            cancel()

        def close():
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        tk.Button(btns, text="保存", command=do_save, font=(FONT, 12), width=10,
                  bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT, cursor="hand2",
                  activebackground="#27ae60").pack(side="left", padx=(40, 8))
        tk.Button(btns, text="取消", command=cancel, font=(FONT, 12), width=10,
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=8)
        tk.Button(btns, text="🩺 急救", command=lambda: self.open_repair_from(win),
                  font=(FONT, 11), relief=tk.FLAT, bg="#fdecea", fg=COLOR_DANGER,
                  cursor="hand2", activebackground="#f8d7da").pack(side="left", padx=8)
        tk.Button(btns, text="删除任务", command=do_delete, font=(FONT, 12), width=10,
                  relief=tk.FLAT, bg="#fdecea", fg=COLOR_DANGER, cursor="hand2",
                  activebackground="#f8d7da").pack(side="right", padx=40)

        win.protocol("WM_DELETE_WINDOW", on_x)
        title_en.focus_set()
        title_en.select_range(0, "end")
        win.grab_set()          # 模态：主界面不可操作
        win.wait_window()

    # ==================================================================
    # 批量修改：选中多条时走这个新窗口，单条仍用上面的老编辑窗口
    # ==================================================================
    def open_batch_editor(self):
        if not self._in_task_ui():
            return
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("提示", "先选中任务再改")
            return
        if len(ids) == 1:                       # 一条就用原来的编辑窗口
            task = self._find(ids[0])
            if task:
                self.open_editor(task)
            return

        picked = [t for t in self.tasks if t["id"] in ids]   # 只存引用，不复制任务内容
        if len(picked) < 2:
            return

        win = tk.Toplevel(self.root)
        win.title("批量修改")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 540, 470, self.root)

        header = tk.Frame(win, bg=COLOR_DARK)
        header.pack(fill="x")
        tk.Label(header, text=f"🛠 批量修改 {len(picked)} 条任务",
                 font=(FONT, 17, "bold"), bg=COLOR_DARK, fg="white").pack(pady=(12, 2))
        names = "、".join(t["title"] for t in picked[:3])
        if len(picked) > 3:
            names += f" 等 {len(picked)} 条"
        tk.Label(header, text=names, font=(FONT, 9), bg=COLOR_DARK,
                 fg="#bdc3c7", wraplength=480).pack(pady=(0, 10))

        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=24, pady=(10, 0))
        tk.Label(body, text="勾上要改的项目，没勾的原样不动",
                 font=(FONT, 10), fg=COLOR_GRAY, anchor="w").pack(fill="x")

        pri_on, sub_on, cat_on, due_on = (tk.BooleanVar(value=False) for _ in range(4))
        due_var = tk.StringVar(value="")

        def drop_row(var, text, values, width=10):
            """一整行：勾选框 + 名字 + 下拉"""
            f = tk.Frame(body)
            f.pack(fill="x", pady=6)
            tk.Checkbutton(f, variable=var, font=(FONT, 11),
                           cursor="hand2").pack(side="left")
            tk.Label(f, text=text, font=(FONT, 11, "bold"), fg=COLOR_DARK,
                     width=6, anchor="w").pack(side="left")
            v = tk.StringVar(value=values[0])
            ttk.Combobox(f, textvariable=v, values=values, width=width,
                         state="readonly", font=(FONT, 11)).pack(side="left", padx=(4, 0))
            return v

        p_var = drop_row(pri_on, "优先级", PRIORITIES, 6)
        s_var = drop_row(sub_on, "科目", ["（清空）"] + SUBJECTS, 9)
        c_var = drop_row(cat_on, "分类", ["（清空）"] + CATEGORIES, 9)

        # 截止日期：输入框 + 几个常用日期
        f = tk.Frame(body)
        f.pack(fill="x", pady=6)
        tk.Checkbutton(f, variable=due_on, font=(FONT, 11),
                       cursor="hand2").pack(side="left")
        tk.Label(f, text="截止", font=(FONT, 11, "bold"), fg=COLOR_DARK,
                 width=6, anchor="w").pack(side="left")
        due_en = ttk.Entry(f, textvariable=due_var, font=(FONT, 11), width=13)
        due_en.pack(side="left", padx=(4, 6))
        for label, val in [("今天", today_str()),
                           ("明天", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
                           ("一周后", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
                           ("清除", "")]:
            tk.Button(f, text=label, command=lambda v=val: due_var.set(v),
                      font=(FONT, 9), relief=tk.FLAT, bg="#ecf0f1",
                      cursor="hand2").pack(side="left", padx=2)

        preview = tk.Label(win, text="", font=(FONT, 10), fg=COLOR_PRIMARY,
                           anchor="w", justify="left", wraplength=490)
        preview.pack(fill="x", padx=24, pady=(10, 0))

        def plan():
            """算出要改哪些字段（不改的字段根本不进这个 dict）"""
            ch = {}
            if pri_on.get():
                ch["priority"] = p_var.get()
            if sub_on.get():
                ch["subject"] = "" if s_var.get() == "（清空）" else s_var.get()
            if cat_on.get():
                ch["category"] = "" if c_var.get() == "（清空）" else c_var.get()
            if due_on.get():
                ch["due"] = due_var.get().strip()
            return ch

        def refresh_preview(*_a):
            ch = plan()
            if not ch:
                preview.config(text="现在：一项都没勾，点“应用”不会有任何变化",
                               fg=COLOR_GRAY)
                return
            label = {"priority": "优先级", "subject": "科目",
                     "category": "分类", "due": "截止"}
            txt = "、".join(f"{label[k]} → {v if v else '（空）'}" for k, v in ch.items())
            preview.config(text=f"将把选中的 {len(picked)} 条一起改成：{txt}",
                           fg=COLOR_PRIMARY)

        for v in (pri_on, sub_on, cat_on, due_on, p_var, s_var, c_var, due_var):
            v.trace_add("write", refresh_preview)
        refresh_preview()

        def apply_changes():
            ch = plan()
            if not ch:
                messagebox.showinfo("提示", "上面一项都没勾", parent=win)
                return
            if "due" in ch:
                try:
                    parse_date(ch["due"])
                except ValueError:
                    messagebox.showwarning("提示", "截止日期格式不对，应为 YYYY-MM-DD",
                                           parent=win)
                    return
            label = {"priority": "优先级", "subject": "科目",
                     "category": "分类", "due": "截止"}
            detail = "、".join(f"{label[k]} → {v if v else '（空）'}" for k, v in ch.items())
            if not messagebox.askyesno(
                    "确认", f"把选中的 {len(picked)} 条任务的\n{detail}\n一起改掉？\n（可用 Ctrl+Z 撤销）",
                    parent=win):
                return
            self.push_undo()               # 只存一份快照，不在循环里反复拷贝
            for t in picked:               # 原地改，不重建列表
                t.update(ch)
                if ch.get("subject") and "category" not in ch:
                    t["category"] = "学习"  # 跟单条编辑一个规矩：填了科目就是学习任务
            close()
            self.refresh()
            if self.settings["auto_save"]:
                self.save_data()

        def close():
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(fill="x", pady=(12, 14))
        tk.Button(btns, text="应用", command=apply_changes, font=(FONT, 12), width=10,
                  bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT, cursor="hand2",
                  activebackground="#27ae60").pack(side="left", padx=(60, 8))
        tk.Button(btns, text="取消", command=close, font=(FONT, 12), width=10,
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=8)
        tk.Button(btns, text="🩺 急救", command=lambda: self.open_repair_from(win),
                  font=(FONT, 11), relief=tk.FLAT, bg="#fdecea", fg=COLOR_DANGER,
                  cursor="hand2", activebackground="#f8d7da").pack(side="left", padx=(60, 0))

        win.protocol("WM_DELETE_WINDOW", close)
        win.grab_set()
        win.wait_window()

    # ==================================================================
    # 新建任务弹窗（功能 1） + 主界面新建区（按 add_ui 切换）
    # ==================================================================
    def open_new_task(self):
        """＋ 新建：独立弹窗（布局照搬编辑窗口，无删除按钮），可连续添加"""
        old = getattr(self, "_new_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._new_win = win
        win.title("＋ 新建任务")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 540, 500, self.root)
        # 非模态：可连续添加多条

        header = tk.Frame(win, bg=COLOR_DARK)
        header.pack(fill="x")
        tk.Label(header, text="＋ 新建任务", font=(FONT, 18, "bold"),
                 bg=COLOR_DARK, fg="white").pack(pady=(12, 2))
        tk.Label(header, text="填完点“添加”可连续添加，点“取消”关闭",
                 font=(FONT, 9), bg=COLOR_DARK, fg="#bdc3c7").pack(pady=(0, 10))

        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=24, pady=(14, 0))

        tk.Label(body, text="任务内容 *", font=(FONT, 11, "bold"),
                 fg=COLOR_DARK, anchor="w").pack(fill="x")
        self.entry = ttk.Entry(body, font=(FONT, 11))
        self.entry.pack(fill="x", pady=(2, 10), ipady=3)

        row = tk.Frame(body)
        row.pack(fill="x", pady=(0, 10))
        tk.Label(row, text="优先级", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        self.priority_cb = ttk.Combobox(row, values=PRIORITIES, width=5,
                                        state="readonly", font=(FONT, 11))
        self.priority_cb.set(self.settings.get("default_priority", "中"))
        self.priority_cb.pack(side="left", padx=(6, 18))
        tk.Label(row, text="科目", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        self.subject_cb = ttk.Combobox(row, values=SUBJECTS, width=7, font=(FONT, 11))
        self.subject_cb.pack(side="left", padx=(6, 14))
        tk.Label(row, text="分类", font=(FONT, 11, "bold"), fg=COLOR_DARK).pack(side="left")
        self.cat_cb = ttk.Combobox(row, values=CATEGORIES, width=7, font=(FONT, 11))
        self.cat_cb.pack(side="left", padx=6)

        tk.Label(body, text="截止日期（留空表示不限，格式 YYYY-MM-DD）",
                 font=(FONT, 11, "bold"), fg=COLOR_DARK, anchor="w").pack(fill="x")
        due_row = tk.Frame(body)
        due_row.pack(fill="x", pady=(2, 4))
        self.due_var = tk.StringVar(value="")
        ttk.Entry(due_row, textvariable=self.due_var, font=(FONT, 11), width=18).pack(side="left")

        def set_due(text):
            self.due_var.set(text)

        for label, val in [("今天", today_str()),
                           ("明天", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
                           ("一周后", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
                           ("清除", "")]:
            tk.Button(due_row, text=label, command=lambda v=val: set_due(v),
                      font=(FONT, 9), relief=tk.FLAT, bg="#ecf0f1",
                      cursor="hand2").pack(side="left", padx=2)

        tk.Label(body, text="备注", font=(FONT, 11, "bold"),
                 fg=COLOR_DARK, anchor="w").pack(fill="x", pady=(8, 0))
        note_box = tk.Text(body, height=7, font=(FONT, 10), wrap="word",
                           relief=tk.SOLID, bd=1)
        note_box.pack(fill="both", expand=True, pady=(2, 4))

        btns = tk.Frame(win)
        btns.pack(fill="x", pady=(6, 14))

        def do_add():
            title = self.entry.get().strip()
            if not title:
                messagebox.showwarning("提示", "任务内容不能为空", parent=win)
                self.entry.focus_set()
                return
            due_raw = self.due_var.get().strip()
            try:
                parse_date(due_raw)
            except ValueError:
                messagebox.showwarning("提示", "截止日期格式不对，应为 YYYY-MM-DD", parent=win)
                return
            subject = self.subject_cb.get().strip()
            cat = self.cat_cb.get().strip()
            self.push_undo()
            self._append_task(title, self.priority_cb.get() or "中", subject, cat,
                              due_raw, note_box.get("1.0", "end").strip())
            self.refresh()
            if self.settings["auto_save"]:
                self.save_data()
            # 清空字段、焦点回内容框，和行内输入表现一致
            self.entry.delete(0, "end")
            self.subject_cb.set("")
            self.cat_cb.set("")
            self.due_var.set("")
            note_box.delete("1.0", "end")
            self.entry.focus_set()

        tk.Button(btns, text="添加", command=do_add, font=(FONT, 12), width=10,
                  bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT, cursor="hand2",
                  activebackground="#27ae60").pack(side="left", padx=(40, 8))
        tk.Button(btns, text="取消", command=win.destroy, font=(FONT, 12), width=10,
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=8)

        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def _build_add_area(self):
        """按 add_ui 决定新建区：new=两个小按钮；classic=行内输入 + 操作按钮。
        无论哪种都先造出 self.entry / priority_cb / subject_cb / cat_cb，
        否则 add_task() / focus_entry() 在 new 模式下会 AttributeError。"""
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=(10, 4))

        self.entry = ttk.Entry(top, font=(FONT, 10))
        self.entry.bind("<Return>", lambda e: self.add_task())
        self.priority_cb = ttk.Combobox(top, values=PRIORITIES, width=4, state="readonly",
                                        font=(FONT, 10))
        self.priority_cb.set(self.settings.get("default_priority", "中"))
        self.subject_cb = ttk.Combobox(top, values=SUBJECTS, width=6, font=(FONT, 10))
        self.subject_cb.set("")
        self.cat_cb = ttk.Combobox(top, values=CATEGORIES, width=6, font=(FONT, 10))
        self.cat_cb.set(MODES[self.mode].get("new_cat", ""))

        if self.settings.get("add_ui") == "classic":
            tk.Label(top, text="任务内容：", font=(FONT, 10)).pack(side="left")
            self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(top, text="优先级：", font=(FONT, 10)).pack(side="left")
            self.priority_cb.pack(side="left", padx=(0, 8))
            tk.Label(top, text="科目：", font=(FONT, 10)).pack(side="left")
            self.subject_cb.pack(side="left", padx=(0, 8))
            tk.Label(top, text="分类：", font=(FONT, 10)).pack(side="left")
            self.cat_cb.pack(side="left", padx=(0, 8))
            tk.Button(top, text="添加任务", command=self.add_task,
                      font=(FONT, 10), bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT,
                      cursor="hand2", activebackground="#27ae60").pack(side="left")
            self._make_ops_button(top)
        else:
            tk.Button(top, text="＋ 新建", command=self.open_new_task,
                      font=(FONT, 10), bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT,
                      cursor="hand2", activebackground="#27ae60").pack(side="left", padx=(0, 6))
            self._make_ops_button(top)

    def _make_ops_button(self, parent):
        tk.Button(parent, text="⚙ 操作", command=self.open_operations,
                  font=(FONT, 10), bg="#ecf0f1", fg=COLOR_DARK, relief=tk.FLAT,
                  cursor="hand2").pack(side="left", padx=(0, 6))

    # ==================================================================
    # 操作窗口（功能 4，非模态）
    # ==================================================================
    def open_operations(self):
        old = self._ops_win
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
        if not self._in_task_ui():
            return
        win = tk.Toplevel(self.root)
        self._ops_win = win
        win.title("操作")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 460, 380, self.root)
        # 非模态：编辑完再完成再删除连着来

        self._ops_sel_label = tk.Label(win, text="当前选中：无",
                                        font=(FONT, 10, "bold"), fg=COLOR_DARK,
                                        anchor="w", relief=tk.SOLID, bd=1)
        self._ops_sel_label.pack(fill="x", padx=12, pady=(10, 6))

        # ---- 排序控件 ----
        sort_f = tk.Frame(win)
        sort_f.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(sort_f, text="排序：", font=(FONT, 10)).pack(side="left")
        col, rev = self._eff_sort()
        scope = ("normal" if (self.mode == "normal" and self.settings.get("sort_col_normal"))
                 else "perf" if (self.mode == "perf" and self.settings.get("sort_col_perf"))
                 else "global")
        fvar = tk.StringVar(value=dict(SORT_FIELDS).get(col, "优先级"))
        fcb = ttk.Combobox(sort_f, textvariable=fvar, width=8, state="readonly",
                           font=(FONT, 10), values=[v for _, v in SORT_FIELDS])
        fcb.pack(side="left", padx=(0, 6))
        ovar = tk.StringVar(value="正序" if not rev else "倒序")
        ocb = ttk.Combobox(sort_f, textvariable=ovar, width=6, state="readonly",
                           font=(FONT, 10), values=["正序", "倒序"])
        ocb.pack(side="left", padx=(0, 6))
        scvar = tk.StringVar(value={"global": "全局", "normal": "仅普通", "perf": "仅性能"}[scope])
        sccb = ttk.Combobox(sort_f, textvariable=scvar, width=8, state="readonly",
                           font=(FONT, 10), values=["全局", "仅普通", "仅性能"])
        sccb.pack(side="left", padx=(0, 6))

        def apply_sort(_e=None):
            key = next((k for k, v in SORT_FIELDS if v == fvar.get()), "priority")
            reverse = (ovar.get() == "倒序")
            sc = {"全局": "global", "仅普通": "normal", "仅性能": "perf"}[scvar.get()]
            self._sort_scope_write(key, reverse, sc)

        fcb.bind("<<ComboboxSelected>>", apply_sort)
        ocb.bind("<<ComboboxSelected>>", apply_sort)
        sccb.bind("<<ComboboxSelected>>", apply_sort)

        # ---- 按钮区 ----
        grid = tk.Frame(win)
        grid.pack(fill="x", padx=12, pady=(4, 6))
        btns = {}
        spec = [
            ("edit", "编辑", self.edit_selected, "#ecf0f1", COLOR_DARK, 0, 0),
            ("toggle", "完成/取消", self.toggle_done, "#ecf0f1", COLOR_DARK, 0, 1),
            ("delete", "删除", self.delete_selected, "#fdecea", COLOR_DANGER, 0, 2),
            ("undo", "撤销", self.undo, "#ecf0f1", COLOR_DARK, 1, 0),
            ("clear", "清空已完成", self.clear_done, "#ecf0f1", COLOR_DARK, 1, 1),
            ("multi", "☐ 多选", self.toggle_multi_select, "#ecf0f1", COLOR_DARK, 1, 2),
            ("save", "保存", lambda: self.save_data(show_msg=True), "#ecf0f1", COLOR_DARK, 2, 0),
            ("preset", "📋 使用预设", self.open_use_preset, "#ecf0f1", COLOR_DARK, 2, 1),
        ]
        for key, text, cmd, bg, fg, r, c in spec:
            b = tk.Button(grid, text=text, command=cmd, font=(FONT, 10),
                          relief=tk.FLAT, bg=bg, fg=fg, cursor="hand2")
            span = 2 if key == "preset" else 1
            b.grid(row=r, column=c, columnspan=span, padx=3, pady=3, sticky="ew")
            btns[key] = b
        grid.columnconfigure((0, 1, 2), weight=1)
        self._ops_btns = btns
        self._refresh_ops_buttons()
        self._update_ops_status()

        tk.Button(win, text="关闭", command=win.destroy, font=(FONT, 11), width=10).pack(pady=(2, 12))

        def on_destroy(_e=None):
            if self._ops_win is win:
                self._ops_win = None

        win.bind("<Destroy>", on_destroy)

    def _update_ops_status(self):
        w = self._ops_win
        if not w or not w.winfo_exists():
            return
        ids = self._selected_ids()
        if not ids:
            self._ops_sel_label.config(text="当前选中：无")
        elif len(ids) == 1:
            t = self._find(ids[0])
            self._ops_sel_label.config(text=f"当前选中：{t['title'] if t else ''}")
        else:
            t0 = self._find(ids[0])
            self._ops_sel_label.config(text=f"当前选中：{t0['title'] if t0 else ''} 等 {len(ids)} 条")
        self._refresh_ops_buttons()

    def _refresh_ops_buttons(self):
        w = self._ops_win
        if not w or not w.winfo_exists():
            return
        b = self._ops_btns
        if not b:
            return
        n = len(self._selected_ids())
        b["edit"]["state"] = "normal" if n == 1 else "disabled"
        b["toggle"]["state"] = "normal" if n >= 1 else "disabled"
        b["delete"]["state"] = "normal" if n >= 1 else "disabled"
        b["undo"]["state"] = "normal" if self.undo_stack else "disabled"
        b["clear"]["state"] = "normal" if any(t["done"] for t in self.tasks) else "disabled"
        on = self.multi_on()
        b["multi"].config(text="☑ 多选" if on else "☐ 多选",
                          bg=COLOR_PRIMARY if on else "#ecf0f1",
                          fg="white" if on else COLOR_DARK)

    # ==================================================================
    # 预设任务（功能 2，.rw / .txt）
    # ==================================================================
    def preset_dir(self):
        d = os.path.join(BASE_DIR, "presets")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d

    def scan_presets(self, include_disabled=False):
        """扫描 presets 文件夹，返回 [(fname, info)]；info 含解析结果"""
        d = self.preset_dir()
        try:
            files = [f for f in os.listdir(d) if f.lower().endswith((".rw", ".txt"))]
        except OSError:
            return []
        files.sort()
        disabled = set(self.settings.get("preset_disabled_files", []) or [])
        result = []
        for f in files:
            path = os.path.join(d, f)
            info = self._parse_preset_file(path, f)
            info["disabled"] = f in disabled
            if info["disabled"] and not include_disabled:
                continue
            result.append((f, info))
        return result

    def _env_category(self, e):
        m = {"s": "学习", "w": "工作", "l": "生活", "o": "其他"}
        return m.get(e, e)     # 单字母映射；否则原样（如 e=考研 → 考研）

    def _norm_due(self, s):
        s = (s or "").strip()
        if not s:
            return ""
        if s == "今天":
            return today_str()
        if s == "明天":
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        if s == "后天":
            return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        if s.startswith("+"):
            try:
                return (datetime.now() + timedelta(days=int(s[1:]))).strftime("%Y-%m-%d")
            except ValueError:
                return None
        if s.startswith("-"):
            try:
                return (datetime.now() + timedelta(days=-int(s[1:]))).strftime("%Y-%m-%d")
            except ValueError:
                return None
        try:
            parse_date(s)
            return s
        except ValueError:
            return None

    def _parse_preset_file(self, path, fname):
        info = {"fname": fname, "ok": False, "error": "", "mod": "",
                "ver": None, "e": "", "name": fname, "author": "",
                "dup": "ask", "groups": [], "tasks": 0, "disabled": False}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as e:
            info["error"] = f"读不了：{e}"
            return info
        lines = raw.splitlines()
        KNOWN = {"mod", "ver", "ext", "e", "name", "author", "dup", "enc", "strict"}
        params = {}
        param_end = len(lines)
        for i, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue            # 注释行不结束参数区
            if "=" in s and not s.startswith("preset(") and "|" not in s:
                k, _, v = s.partition("=")
                k, v = k.strip().lower(), v.strip()
                if k in KNOWN:
                    params[k] = v
                    continue
            # 第一个任务行 / preset( / 非 key=value 行 → 参数区结束
            param_end = i
            break
        else:
            param_end = len(lines)

        mod = params.get("mod", "").strip().lower()
        if mod not in ("py", "simple"):
            info["error"] = "缺少 mod 或 mod 不合法（应为 py / simple）"
            return info
        ver_raw = params.get("ver", "")
        try:
            ver_n = int(ver_raw)
        except ValueError:
            info["error"] = f"ver 不合法：{ver_raw!r}"
            return info
        if ver_n != PRESET_VER:
            info["error"] = f"版本不符（文件 ver={ver_n}，程序 ver={PRESET_VER}）"
            return info

        ext = str(params.get("ext", "false")).lower() in ("1", "true", "yes", "on")
        e = ""
        if ext:
            e = params.get("e", "").strip()
            info["e"] = e
            info["name"] = params.get("name", "").strip() or fname
            info["author"] = params.get("author", "").strip()
            dup = params.get("dup", "").strip().lower()
            info["dup"] = dup if dup in ("skip", "add") else "ask"
        e_cat = self._env_category(e)
        strict = str(params.get("strict", "false")).lower() in ("1", "true", "yes", "on")

        try:
            if mod == "simple":
                groups = self._parse_simple(lines, param_end, e_cat, strict)
            else:
                groups = self._parse_py(lines, param_end, e_cat, strict)
        except PresetError as pe:
            info["error"] = str(pe)
            return info

        info["mod"] = mod
        info["ver"] = ver_n
        info["ok"] = True
        info["groups"] = groups
        info["tasks"] = sum(len(t) for _, t in groups)
        return info

    def _parse_simple(self, lines, param_end, e_cat, strict):
        groups = []
        cur_name = "默认"
        cur_tasks = []
        for line in lines[param_end:]:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if s.startswith("##"):
                    if cur_tasks or cur_name != "默认":
                        groups.append((cur_name, cur_tasks))
                    cur_name = s[2:].strip() or "默认"
                    cur_tasks = []
                continue
            if "|" not in s:
                if strict:
                    raise PresetError("simple 模式遇到无法解析的行：" + s[:40])
                continue
            parts = s.split("|", 5)
            content = parts[0].strip()
            if not content:
                if strict:
                    raise PresetError("simple 模式空内容行")
                continue
            priority = parts[1].strip() if len(parts) > 1 else ""
            subject = parts[2].strip() if len(parts) > 2 else ""
            category = parts[3].strip() if len(parts) > 3 else ""
            due = parts[4].strip() if len(parts) > 4 else ""
            note = parts[5].strip() if len(parts) > 5 else ""
            if not priority:
                priority = self.settings.get("default_priority", "中")
            if priority not in PRIORITIES:
                priority = "中"
            if not category and e_cat:
                category = e_cat
            due_norm = self._norm_due(due)
            if due_norm is None and due:
                if strict:
                    raise PresetError("simple 模式日期非法：" + due)
                due_norm = due
            cur_tasks.append({"title": content, "priority": priority, "subject": subject,
                              "category": category, "due": due_norm or "", "note": note})
        if cur_tasks or cur_name != "默认":
            groups.append((cur_name, cur_tasks))
        return groups

    def _strip_py_comment(self, line):
        out = ""
        q = None
        for ch in line:
            if q:
                out += ch
                if ch == q:
                    q = None
            elif ch in "\"'":
                q = ch
                out += ch
            elif ch == "#":
                break
            else:
                out += ch
        return out

    def _split_top(self, s):
        res = []
        depth = 0
        buf = ""
        q = None
        for ch in s:
            if q:
                buf += ch
                if ch == q:
                    q = None
                continue
            if ch in "\"'":
                q = ch
                buf += ch
                continue
            if ch in "([{":
                depth += 1
                buf += ch
                continue
            if ch in ")]}":
                depth -= 1
                buf += ch
                continue
            if ch == "," and depth == 0:
                res.append(buf)
                buf = ""
                continue
            buf += ch
        if buf.strip():
            res.append(buf)
        return res

    def _parse_kwargs(self, s, vars):
        # 中文关键字 → 程序内部用的拉丁键（内容/优先级/科目/分类/截止/备注/完成/创建…）
        ALIAS = {
            "内容": "title", "标题": "title",
            "优先级": "priority", "优先": "priority",
            "科目": "subject",
            "分类": "category",
            "截止": "due", "到期": "due",
            "备注": "note", "说明": "note",
            "完成": "done", "done_at": "done_at", "完成时间": "done_at",
            "创建": "created", "创建时间": "created",
        }
        out = {}
        for p in self._split_top(s):
            p = p.strip()
            if not p or "=" not in p:
                continue
            k, _, v = p.partition("=")
            k = ALIAS.get(k.strip().lower(), k.strip().lower())
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            else:
                v = vars.get(v, v)      # 变量引用
            out[k] = v
        return out

    def _parse_py(self, lines, param_end, e_cat, strict):
        cleaned = [self._strip_py_comment(ln) for ln in lines[param_end:]]
        text = "\n".join(cleaned)
        # 收集模块级变量：name = "值" / name = 值
        # 变量只在第一个 preset( 之前声明（块内的 科目=... 不算变量）
        # 变量名允许中文（人可读），用非分隔符字符匹配
        first = text.find("preset(")
        scope = text if first == -1 else text[:first]
        vars = {}
        for m in re.finditer(r'^\s*([^\s=(){}\[\],#]+)\s*=\s*("(?:[^"]*)"|\'(?:[^\']*)\'|[^#\n]+)',
                             scope, re.M):
            name = m.group(1)
            val = m.group(2).strip()
            if val and val[0] in "\"'":
                val = val[1:-1]
            vars[name] = val.strip()
        blocks = re.findall(r'preset\(\s*["\']([^"\']+)["\']\s*\)\s*\{(.*?)\}', text, re.S)
        groups = []
        for gname, body in blocks:
            defaults = {}
            for dm in re.finditer(r'default\(\s*(.*?)\s*\)', body, re.S):
                defaults.update(self._parse_kwargs(dm.group(1), vars))
            tasks = []
            for tm in re.finditer(r'task\(\s*(.*?)\s*\)', body, re.S):
                kw = self._parse_kwargs(tm.group(1), vars)
                merged = dict(defaults)
                merged.update(kw)
                title = (merged.get("title") or merged.get("内容") or "").strip()
                if not title:
                    if strict:
                        raise PresetError("py 模式 task 缺少 title：" + tm.group(0)[:30])
                    continue
                priority = merged.get("priority", "") or self.settings.get("default_priority", "中")
                if priority not in PRIORITIES:
                    priority = "中"
                subject = merged.get("subject", "") or ""
                category = merged.get("category", "") or ""
                if not category and e_cat:
                    category = e_cat
                due_raw = merged.get("due", "") or ""
                due_norm = self._norm_due(due_raw)
                if due_norm is None and due_raw:
                    if strict:
                        raise PresetError("py 模式日期非法：" + str(due_raw))
                    due_norm = due_raw
                note = merged.get("note", "") or ""
                done = str(merged.get("done", "")).strip().lower() in ("1", "true", "是", "yes")
                done_at = merged.get("done_at", "") or ""
                created = merged.get("created", "") or ""
                tasks.append({"title": title, "priority": priority, "subject": subject,
                              "category": category, "due": due_norm or "", "note": note,
                              "done": done, "done_at": done_at, "created": created})
            if tasks:
                groups.append((gname, tasks))
        return groups

    def open_preset_folder(self):
        d = self.preset_dir()
        try:
            os.startfile(d)
        except Exception:
            messagebox.showinfo("提示", f"文件夹路径：\n{d}")

    def _build_preset_list(self, frame):
        for w in frame.winfo_children():
            w.destroy()
        try:
            allf = [f for f in os.listdir(self.preset_dir())
                    if f.lower().endswith((".rw", ".txt"))]
        except OSError:
            allf = []
        disabled = set(self.settings.get("preset_disabled_files", []) or [])
        if not allf:
            tk.Label(frame, text="（presets 文件夹是空的）", font=(FONT, 9),
                     fg=COLOR_GRAY).pack(anchor="w")
            return
        for f in sorted(allf):
            var = tk.BooleanVar(value=f not in disabled)

            def on(fname=f, v=var):
                d = set(self.settings.get("preset_disabled_files", []) or [])
                if v.get():
                    d.discard(fname)
                else:
                    d.add(fname)
                self.settings["preset_disabled_files"] = sorted(d)
                self.save_data()

            row = tk.Frame(frame)
            row.pack(fill="x", pady=1)
            tk.Checkbutton(row, text="启用 " + f, variable=var, command=on,
                           font=(FONT, 10), cursor="hand2").pack(side="left")

    def rescan_presets(self):
        fr = self._preset_list_frame
        if fr is not None:
            try:
                if fr.winfo_exists():
                    self._build_preset_list(fr)
            except tk.TclError:
                pass
        messagebox.showinfo("完成", "已重新扫描 presets 文件夹")

    def open_preset_status(self):
        win = tk.Toplevel(self.root)
        win.title("当前预设状态")
        win.resizable(True, True)
        win.transient(self.root)
        center_window(win, 560, 520, self.root)
        tk.Label(win, text="📋 presets 文件夹里的所有 .rw / .txt", font=(FONT, 13, "bold"),
                 fg=COLOR_DARK).pack(pady=(12, 6))
        sf = ScrolledFrame(win, width=520)
        inner = sf.inner
        disabled = set(self.settings.get("preset_disabled_files", []) or [])
        try:
            files = [f for f in os.listdir(self.preset_dir())
                     if f.lower().endswith((".rw", ".txt"))]
        except OSError:
            files = []
        if not files:
            tk.Label(inner, text="（presets 文件夹是空的）", font=(FONT, 10),
                     fg=COLOR_GRAY).pack(anchor="w", padx=10)
        for f in sorted(files):
            info = self._parse_preset_file(os.path.join(self.preset_dir(), f), f)
            bad = (not info["ok"]) or info["error"]
            color = COLOR_DANGER if bad else COLOR_DARK
            line = (f"{f}　mod={info['mod'] or '-'}　ver={info['ver']}　"
                    f"e={info['e'] or '-'}　组数={len(info['groups'])}　任务数={info['tasks']}")
            if f in disabled:
                line += "　（已禁用）"
            tk.Label(inner, text=line, font=(FONT, 10, "bold"), fg=color,
                     anchor="w", wraplength=500, justify="left").pack(fill="x", padx=10, pady=(6, 0))
            if bad and info["error"]:
                tk.Label(inner, text="　⚠ " + info["error"], font=(FONT, 9),
                         fg=COLOR_DANGER, anchor="w", wraplength=500,
                         justify="left").pack(fill="x", padx=20)
        tk.Button(win, text="关闭", command=win.destroy, font=(FONT, 11),
                  width=10).pack(pady=(10, 14))

    def open_preset_help(self):
        win = tk.Toplevel(self.root)
        win.title("rw 使用方法")
        win.resizable(True, True)
        win.transient(self.root)
        center_window(win, 600, 600, self.root)
        sf = ScrolledFrame(win, width=560)
        inner = sf.inner
        help_text = [
            ("什么是 .rw 文件", None),
            ("纯文本 UTF-8，人可读，可直接用记事本改。放在程序旁边的 presets/ 文件夹里；"
             "扫描时同时认 .rw 和 .txt。", "gray"),
            ("文件开头：参数区（一行一个 key=value）", None),
            ("mod（必填）：py 或 simple，决定下面怎么解析", None),
            ("ver（必填）：必须等于程序版本 3，否则整文件拒绝加载", None),
            ("ext（选填）：true 才启用 e / name / author / dup / enc / strict", None),
            ("e（需 ext）：环境默认值，管分类兜底 / 分组显示", None),
            ("name（需 ext）：文件显示名", None),
            ("author（需 ext）：作者", None),
            ("dup（需 ext）：ask / skip / add，默认 ask", None),
            ("enc（需 ext）：文件编码，默认 utf-8", None),
            ("strict（需 ext）：true 时遇到错行就停", None),
            ("两种模式怎么选", None),
            ("simple：一行一个任务，竖线 | 分隔。格式：内容|优先级|科目|分类|截止|备注，"
             "只有内容必填，备注里有竖线也不怕（只切前五刀）。适合手写清单。", "gray"),
            ("py：外观像 Python 但不是真执行，逐行正则解析。支持 preset(\"组\"){...}、"
             "task(...)、default(...) 组级默认、变量引用、行内注释。不做 extend / 循环 / if / "
             "函数 / import，更不能用 exec 或 eval。适合批量、带默认值的预设。", "gray"),
            ("截止日期写法", None),
            ("留空=不限；今天 / 明天 / 后天；+7=一周后；-3=往前 3 天；绝对日期 2025-01-15", "gray"),
            ("e 的分类兜底", None),
            ("s→学习 w→工作 l→生活 o→其他；不是单字母就原样当字符串（如 考研→考研）", "gray"),
        ]
        for title, sub in help_text:
            if sub is None:
                tk.Label(inner, text="• " + title, font=(FONT, 11, "bold"),
                         fg=COLOR_DARK, anchor="w", justify="left",
                         wraplength=540).pack(fill="x", padx=12, pady=(8, 0))
            else:
                tk.Label(inner, text="    " + title, font=(FONT, 9), fg=COLOR_GRAY,
                         anchor="w", justify="left", wraplength=540).pack(fill="x", padx=12)
        tk.Button(win, text="关闭", command=win.destroy, font=(FONT, 11),
                  width=10).pack(pady=(12, 14))

    def generate_samples(self):
        d = self.preset_dir()
        simple_path = os.path.join(d, "sample_simple.rw")
        py_path = os.path.join(d, "sample_python.rw")
        simple_txt = (
            "# sample_simple.rw —— simple 模式\n"
            "# 参数区：mod 和 ver 必填\n"
            "mod=simple\n"
            "ver=3\n"
            "\n"
            "## 日常学习\n"
            "数学|高|数学|学习|+1|今天把卷子写了\n"
            "英语|中|英语|学习|明天|背 30 个单词\n"
            "# 这是注释，会被忽略\n"
            "语文|低|语文|学习||复习古诗\n"
            "\n"
            "## 生活杂事\n"
            "倒垃圾|中|||+7|\n"
            "运动|低|体育|生活|+2|\n"
        )
        py_txt = (
            "# sample_python.rw —— py 模式\n"
            "# ext=true 才会读 e / name / author / dup / enc / strict\n"
            "mod=py\n"
            "ver=3\n"
            "ext=true\n"
            "e=学习\n"
            "name=示例 Python 预设\n"
            "author=CZY\n"
            "dup=ask\n"
            "\n"
            'p = "高"          # 变量，下面 priority=p 引用它\n'
            "\n"
            'preset("日常学习") {\n'
            '    default(subject=数学, category=学习)   # 组级默认\n'
            '    task(title="数学卷子", priority=p, due=今天)\n'
            '    task(title="英语单词", priority="中", subject=英语, due=明天, note="背 30 个")\n'
            "}\n"
            "\n"
            'preset("生活杂事") {\n'
            '    task(title="倒垃圾", priority="中", due="+7")\n'
            '    task(title="运动", priority="低", category=生活, due="+2")\n'
            "}\n"
        )
        try:
            with open(simple_path, "w", encoding="utf-8") as f:
                f.write(simple_txt)
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(py_txt)
            messagebox.showinfo("完成", f"已生成示例：\n{simple_path}\n{py_path}")
            fr = self._preset_list_frame
            if fr is not None:
                try:
                    if fr.winfo_exists():
                        self._build_preset_list(fr)
                except tk.TclError:
                    pass
        except OSError as e:
            messagebox.showerror("生成失败", str(e))

    def open_use_preset(self):
        """使用预设：单击选中 / 双击直接应用该条 / 右键 修改·重命名·删除·复制。
        右键操作只改本次预览，不写回预设文件。"""
        if not self.settings.get("preset_enabled", True):
            messagebox.showinfo("提示", "预设功能已关闭（设置 → 预设任务）")
            return
        scanned = self.scan_presets()
        dup_map = {fname: info.get("dup", "ask") for fname, info in scanned}
        all_groups = []
        for fname, info in scanned:
            if not info["ok"]:
                continue
            for gname, tasks in info["groups"]:
                all_groups.append((fname, gname, tasks))
        if not all_groups:
            messagebox.showinfo("提示", "没有可用的预设组（文件可能都坏了）")
            return

        win = tk.Toplevel(self.root)
        win.title("使用预设")
        win.resizable(True, True)
        win.transient(self.root)
        center_window(win, 720, 560, self.root)
        win.grab_set()

        tk.Label(win, text="📋 使用预设", font=(FONT, 14, "bold"),
                 fg=COLOR_DARK).pack(pady=(10, 2))
        tk.Label(win, text="单击选中，双击直接应用该条；右键可 修改 / 重命名 / 删除 / 复制（只改本次预览）",
                 font=(FONT, 9), fg=COLOR_GRAY).pack()

        top = tk.Frame(win)
        top.pack(fill="x", padx=12, pady=(6, 0))
        tk.Label(top, text="选择组：", font=(FONT, 10)).pack(side="left")
        group_names = [f"{fname} › {gname}" for fname, gname, _ in all_groups]
        gvar = tk.StringVar(value=group_names[0])
        gcb = ttk.Combobox(top, textvariable=gvar, width=34, state="readonly", font=(FONT, 10))
        gcb['values'] = group_names
        gcb.pack(side="left", padx=6)

        cols = ("title", "priority", "subject", "category", "due")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14,
                            selectmode="browse")
        tree.heading("title", text="任务内容")
        tree.column("title", width=320, anchor="w")
        tree.heading("priority", text="优先级")
        tree.column("priority", width=60, anchor="center")
        tree.heading("subject", text="科目")
        tree.column("subject", width=70, anchor="center")
        tree.heading("category", text="分类")
        tree.column("category", width=70, anchor="center")
        tree.heading("due", text="截止")
        tree.column("due", width=90, anchor="center")
        tree.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        # 单选 / 多选切换（和任务管理器一致）
        multi_var = tk.BooleanVar(value=False)
        def _apply_selectmode():
            tree.config(selectmode="extended" if multi_var.get() else "browse")
        tk.Checkbutton(win, text="多选（可一次应用多条）", variable=multi_var,
                       command=_apply_selectmode, font=(FONT, 9), cursor="hand2",
                       anchor="w").pack(fill="x", padx=12)

        task_of = {}

        def load_group():
            for iid in tree.get_children():
                tree.delete(iid)
            task_of.clear()
            idx = group_names.index(gvar.get())
            fname, gname, tasks = all_groups[idx]
            import copy as _copy
            for t in tasks:
                t2 = _copy.deepcopy(t)
                iid = tree.insert("", "end", values=(t2["title"], t2["priority"],
                                                     t2["subject"] or "-", t2["category"] or "-",
                                                     due_text(t2["due"])))
                task_of[iid] = (fname, gname, t2)

        def selected_iid():
            sel = tree.selection()
            if sel:
                return sel[0]
            return tree.focus()

        def apply_tasks(items, gname):
            """把预览条目真正加进任务列表（含 dup 处理），返回添加条数"""
            if not items:
                return 0
            if len(items) > 20:
                messagebox.showwarning("提示", "一次最多添加 20 条，已截取前 20 条", parent=win)
                items = items[:20]
            fname = task_of[items[0]][0] if items and items[0] in task_of else ""
            existing = set(t["title"].strip() for t in self.tasks if not t["done"])
            picked = [task_of[i] for i in items if i in task_of]
            dups = [s for s in picked if s[2]["title"].strip() in existing]
            dup_mode = dup_map.get(fname, "ask")
            if dups and dup_mode == "ask":
                if messagebox.askyesno(
                        "重复任务",
                        f"其中有 {len(dups)} 条和列表里重名，跳过它们？\n"
                        "（选“否”则全部照加）", parent=win):
                    picked = [s for s in picked if s[2]["title"].strip() not in existing]
            elif dup_mode == "skip":
                picked = [s for s in picked if s[2]["title"].strip() not in existing]
            if not picked:
                return 0
            self.push_undo()
            n = 0
            for fname2, gname2, t in picked:
                self._append_task(t["title"], t["priority"], t["subject"], t["category"],
                                  t["due"], t["note"])
                n += 1
            self.refresh()
            if self.settings["auto_save"]:
                self.save_data()
            self.status.config(text=f"已从预设『{gname}』添加 {n} 条任务")
            return n

        def apply_one(iid, close=False):
            if iid not in task_of:
                return
            n = apply_tasks([iid], task_of[iid][1])
            if n and close:
                win.destroy()

        def apply_selected(close=False):
            """应用当前选中的（单选/多选都支持）"""
            ids = tree.selection()
            if not ids:
                f = tree.focus()
                ids = [f] if f else []
            if not ids:
                messagebox.showinfo("提示", "先选中要应用的预设任务", parent=win)
                return
            n = apply_tasks(list(ids), task_of[ids[0]][1])
            if n and close:
                win.destroy()

        def on_double(event):
            iid = tree.identify_row(event.y)
            if iid:
                apply_one(iid)

        tree.bind("<Double-1>", on_double)

        # ---- 右键：修改 / 重命名 / 删除 / 复制 ----
        def popup(event):
            iid = tree.identify_row(event.y)
            if not iid or iid not in task_of:
                return
            tree.selection_set(iid)
            m = tk.Menu(win, tearoff=0)
            m.add_command(label="修改…", command=lambda: edit_item(iid))
            m.add_command(label="重命名…", command=lambda: rename_item(iid))
            m.add_command(label="复制", command=lambda: copy_item(iid))
            m.add_separator()
            m.add_command(label="删除（仅从本次预览移除）", command=lambda: remove_item(iid))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()

        tree.bind("<Button-3>", popup)

        def sync_row(iid):
            t = task_of[iid][2]
            tree.item(iid, values=(t["title"], t["priority"], t["subject"] or "-",
                                   t["category"] or "-", due_text(t["due"])))

        def edit_item(iid):
            """修改预览条目的全部字段（不写回预设文件）"""
            fname, gname, t = task_of[iid]
            ew = tk.Toplevel(win)
            ew.title("修改预设任务（仅本次预览）")
            ew.resizable(False, False)
            ew.transient(win)
            center_window(ew, 440, 330, win)
            ew.grab_set()
            tk.Label(ew, text="✎ 修改这条预设任务", font=(FONT, 13, "bold"),
                     fg=COLOR_DARK).pack(pady=(10, 2))
            tk.Label(ew, text="只影响这次使用，不会改动预设文件本身",
                     font=(FONT, 9), fg=COLOR_GRAY).pack()
            body = tk.Frame(ew)
            body.pack(fill="x", padx=20, pady=8)

            tk.Label(body, text="内容", font=(FONT, 10, "bold")).grid(row=0, column=0, sticky="w")
            t_var = tk.StringVar(value=t["title"])
            ttk.Entry(body, textvariable=t_var, width=30, font=(FONT, 10)).grid(
                row=0, column=1, columnspan=3, sticky="w", pady=2)

            tk.Label(body, text="优先级", font=(FONT, 10, "bold")).grid(row=1, column=0, sticky="w")
            p_var = tk.StringVar(value=t["priority"])
            ttk.Combobox(body, textvariable=p_var, values=PRIORITIES, width=5,
                         state="readonly", font=(FONT, 10)).grid(row=1, column=1, sticky="w", pady=2)
            tk.Label(body, text="科目", font=(FONT, 10, "bold")).grid(row=1, column=2, sticky="w")
            s_var = tk.StringVar(value=t["subject"])
            ttk.Combobox(body, textvariable=s_var, values=SUBJECTS, width=7,
                         font=(FONT, 10)).grid(row=1, column=3, sticky="w", pady=2)

            tk.Label(body, text="分类", font=(FONT, 10, "bold")).grid(row=2, column=0, sticky="w")
            c_var = tk.StringVar(value=t["category"])
            ttk.Combobox(body, textvariable=c_var, values=CATEGORIES, width=7,
                         font=(FONT, 10)).grid(row=2, column=1, sticky="w", pady=2)
            tk.Label(body, text="截止", font=(FONT, 10, "bold")).grid(row=2, column=2, sticky="w")
            d_var = tk.StringVar(value=t["due"])
            ttk.Entry(body, textvariable=d_var, width=12, font=(FONT, 10)).grid(
                row=2, column=3, sticky="w", pady=2)

            tk.Label(body, text="备注", font=(FONT, 10, "bold")).grid(row=3, column=0, sticky="w")
            n_var = tk.StringVar(value=t.get("note", ""))
            ttk.Entry(body, textvariable=n_var, width=30, font=(FONT, 10)).grid(
                row=3, column=1, columnspan=3, sticky="w", pady=2)

            def ok():
                title = t_var.get().strip()
                if not title:
                    messagebox.showwarning("提示", "内容不能为空", parent=ew)
                    return
                if d_var.get().strip():
                    try:
                        parse_date(d_var.get().strip())
                    except ValueError:
                        messagebox.showwarning("提示", "截止日期格式不对", parent=ew)
                        return
                t["title"] = title
                t["priority"] = p_var.get() if p_var.get() in PRIORITIES else "中"
                t["subject"] = s_var.get().strip()
                t["category"] = c_var.get().strip()
                t["due"] = d_var.get().strip()
                t["note"] = n_var.get().strip()
                sync_row(iid)
                ew.destroy()

            bf = tk.Frame(ew)
            bf.pack(pady=(4, 12))
            tk.Button(bf, text="确定", command=ok, font=(FONT, 11), width=8,
                      bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT,
                      cursor="hand2").pack(side="left", padx=6)
            tk.Button(bf, text="取消", command=ew.destroy, font=(FONT, 11), width=8,
                      relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=6)

        def rename_item(iid):
            t = task_of[iid][2]
            new = simpledialog.askstring("重命名", "新的任务内容：",
                                         initialvalue=t["title"], parent=win)
            if new and new.strip():
                t["title"] = new.strip()
                sync_row(iid)

        def copy_item(iid):
            import copy as _copy
            fname, gname, t = task_of[iid]
            t2 = _copy.deepcopy(t)
            nid = tree.insert("", "end", values=(t2["title"], t2["priority"],
                                                 t2["subject"] or "-", t2["category"] or "-",
                                                 due_text(t2["due"])))
            task_of[nid] = (fname, gname, t2)
            tree.selection_set(nid)
            tree.see(nid)

        def remove_item(iid):
            task_of.pop(iid, None)
            tree.delete(iid)

        bottom = tk.Frame(win)
        bottom.pack(fill="x", padx=12, pady=(8, 10))
        tk.Button(bottom, text="应用所选预设",
                  command=lambda: apply_selected(close=True),
                  font=(FONT, 11), bg=COLOR_PRIMARY, fg="white", relief=tk.FLAT,
                  cursor="hand2", activebackground="#27ae60").pack(side="left", padx=4)
        tk.Button(bottom, text="应用本组全部",
                  command=lambda: (apply_tasks(list(tree.get_children()), gvar.get()),
                                   win.destroy()),
                  font=(FONT, 10), relief=tk.FLAT, bg="#ecf0f1",
                  cursor="hand2").pack(side="left", padx=4)
        tk.Button(bottom, text="🔄 刷新", command=load_group, font=(FONT, 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=4)
        tk.Button(bottom, text="取消", command=win.destroy, font=(FONT, 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="right", padx=4)

        gcb.bind("<<ComboboxSelected>>", lambda e: load_group())
        load_group()
        win.wait_window()

    # ==================================================================
    # 列表刷新 / 排序 / 状态栏
    # ==================================================================
    def _eff_sort(self):
        """按当前模式 + 设置取生效的排序（空的作用域跟随全局）"""
        if self.mode == "normal" and self.settings.get("sort_col_normal"):
            return self.settings["sort_col_normal"], bool(self.settings.get("sort_reverse_normal", False))
        if self.mode == "perf" and self.settings.get("sort_col_perf"):
            return self.settings["sort_col_perf"], bool(self.settings.get("sort_reverse_perf", False))
        return self.settings.get("sort_col", "priority"), bool(self.settings.get("sort_reverse", False))

    def _sort_scope_write(self, col, reverse, scope):
        """把排序写回对应作用域的设置并保存、刷新"""
        if scope == "normal":
            self.settings["sort_col_normal"] = col
            self.settings["sort_reverse_normal"] = reverse
        elif scope == "perf":
            self.settings["sort_col_perf"] = col
            self.settings["sort_reverse_perf"] = reverse
        else:
            self.settings["sort_col"] = col
            self.settings["sort_reverse"] = reverse
        self.save_data()
        self.sort_col, self.sort_reverse = self._eff_sort()
        self.refresh()

    def sort_by(self, col):
        """点列头排序：当前作用域已有专属设置就改它，否则改全局"""
        cur_col, cur_rev = self._eff_sort()
        if cur_col == col:
            rev = not cur_rev
        else:
            rev = False
        if self.mode == "normal" and self.settings.get("sort_col_normal"):
            scope = "normal"
        elif self.mode == "perf" and self.settings.get("sort_col_perf"):
            scope = "perf"
        else:
            scope = "global"
        self._sort_scope_write(col, rev, scope)

    def refresh(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())

        mode = self.filter_var.get()
        cat = self.category_var.get()
        sub = self.subject_var.get()
        kw = self.search_var.get().strip().lower()
        order = {"高": 0, "中": 1, "低": 2}
        color = {"高": "high", "中": "mid", "低": "low"}

        shown = []
        for t in self.tasks:
            if mode == "未完成" and t["done"]:
                continue
            if mode == "已完成" and not t["done"]:
                continue
            if cat and cat != "全部" and (t["category"] or "") != cat:
                continue
            if sub and sub != "全部" and (t.get("subject") or "") != sub:
                continue
            if kw and kw not in t["title"].lower() and kw not in (t["note"] or "").lower() \
                    and kw not in (t["category"] or "").lower() \
                    and kw not in (t.get("subject") or "").lower():
                continue
            shown.append(t)

        def key_fn(t):
            if self.sort_col == "priority":
                return (t["done"], order.get(t["priority"], 1), t["id"])
            if self.sort_col == "due":
                delta, _ = due_delta(t["due"])
                return (t["done"], delta is None, delta if delta is not None else 99999, t["id"])
            if self.sort_col == "created":
                return (t["done"], t["created"], t["id"])
            if self.sort_col == "category":
                return (t["done"], t["category"] or "", t["id"])
            if self.sort_col == "subject":
                return (t["done"], t.get("subject") or "", t["id"])
            return (t["done"], t["title"], t["id"])

        shown.sort(key=key_fn, reverse=self.sort_reverse)

        use_tag = bool(self.settings.get("color_tasks", True))
        for t in shown:
            delta, _ = due_delta(t["due"])
            overdue = (not t["done"]) and delta is not None and delta < 0
            if t["done"]:
                tags = ("done",)
            elif overdue and use_tag:
                tags = ("overdue",)
            elif use_tag:
                tags = (color.get(t["priority"], "mid"),)
            else:
                tags = ()
            val_map = {
                "done": "✔" if t["done"] else "☐",
                "priority": t["priority"],
                "title": t["title"],
                "category": t["category"] or "-",
                "subject": t.get("subject") or "-",
                "due": due_text(t["due"]),
                "created": t["created"],
            }
            self.tree.insert(
                "", "end", iid=str(t["id"]),
                values=tuple(val_map[c] for c in self.cols),
                tags=tags)

        for iid in sel:
            if self.tree.exists(iid):
                self.tree.selection_add(iid)
        self.update_status()
        self.update_goal_bar()

    def update_subject_bar(self):
        """科目概览：每个科目还剩几条未完成，点一下就筛选，再点一下取消"""
        if not getattr(self, "subj_bar", None):
            return
        try:
            if not self.subj_bar.winfo_exists():
                return
        except tk.TclError:
            return

        for w in self.subj_bar.winfo_children():
            w.destroy()

        counts = {}
        for t in self.tasks:
            if t["done"]:
                continue
            s = (t.get("subject") or "").strip()
            if s:
                counts[s] = counts.get(s, 0) + 1
        if not counts:
            tk.Label(self.subj_bar, text="（还没有分科目的任务，添加时选个科目试试）",
                     font=(FONT, 9), fg=COLOR_GRAY).pack(side="left")
            return

        ordered = [s for s in SUBJECTS if s in counts]
        ordered += [s for s in sorted(counts) if s not in SUBJECTS]

        def click(s):
            self.subject_var.set("全部" if self.subject_var.get() == s else s)
            self.refresh()

        for s in ordered:
            picked = self.subject_var.get() == s
            tk.Button(self.subj_bar, text=f"{s} {counts[s]}",
                      command=lambda ss=s: click(ss),
                      font=(FONT, 9, "bold" if picked else "normal"),
                      relief=tk.FLAT, cursor="hand2", padx=8,
                      bg=COLOR_PRIMARY if picked else "#ecf0f1",
                      fg="white" if picked else COLOR_DARK,
                      activebackground="#27ae60").pack(side="left", padx=3)

        if self.subject_var.get() != "全部":
            tk.Button(self.subj_bar, text="✕ 看全部", command=lambda: (self.subject_var.set("全部"), self.refresh()),
                      font=(FONT, 9), relief=tk.FLAT, bg="#fdecea", fg=COLOR_DANGER,
                      cursor="hand2", padx=8).pack(side="left", padx=6)

    def update_goal_bar(self):
        """今日目标 / 连续打卡，跟着任务状态实时变"""
        self.update_subject_bar()
        if not getattr(self, "goal_label", None):
            return
        try:
            if not self.goal_label.winfo_exists():
                return
        except tk.TclError:
            return
        done_today, goal, streak = self.study_stats()
        pct = min(int(done_today * 100 / goal), 100) if goal > 0 else 0
        self.goal_pb["value"] = pct
        self.goal_label.config(text=f"{done_today}/{goal} 条")
        self.streak_label.config(text=f"🔥 连续打卡 {streak} 天")

    def update_status(self):
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t["done"])
        today = today_str()
        today_done = sum(1 for t in self.tasks if t["done"] and (t["done_at"] or "").startswith(today))
        overdue = 0
        for t in self.tasks:
            if t["done"]:
                continue
            delta, _ = due_delta(t["due"])
            if delta is not None and delta < 0:
                overdue += 1
        shown = len(self.tree.get_children())
        try:
            picked = len(self.tree.selection())
        except tk.TclError:
            picked = 0
        pick = f"　已选 {picked} 条" if self.multi_on() else ""
        self.status.config(
            text=f"共 {total} 条　未完成 {total - done}　已完成 {done}（今日 +{today_done}）"
                 f"　逾期 {overdue}　|　当前显示 {shown} 条{pick}"
                 f"　模式：{MODES[self.mode]['name']}"
                 f"　排序：{COL_HEADINGS.get(self.sort_col, ('',))[0]}{'↓' if self.sort_reverse else '↑'}")

    # ==================================================================
    # 设置（Orbit2 风格）
    # ==================================================================
    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 500, 640, self.root)
        win.grab_set()

        tk.Label(win, text="⚙ 设置", font=(FONT, 18, "bold"),
                 fg=COLOR_DARK).pack(pady=(14, 6))
        tk.Label(win, text="所有改动即时生效并写入数据文件",
                 font=(FONT, 9), fg=COLOR_GRAY).pack()

        sf = ScrolledFrame(win, width=430)
        inner = sf.inner

        def sep():
            tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill="x", padx=30, pady=(16, 6))

        def group(title, color=COLOR_DARK):
            tk.Label(inner, text=title, font=(FONT, 12, "bold"),
                     fg=color, anchor="w").pack(fill="x", padx=30)

        def check(text, key, desc=None):
            var = tk.BooleanVar(value=self.settings.get(key, False))

            def on_change():
                self.settings[key] = var.get()
                self.save_data()
                if key in ("strike_done", "row_height", "color_tasks", "bug_tools") and self._in_task_ui():
                    self.build_task_ui()
                if key == "multi_select":
                    if not var.get():
                        self._keep_single_selection()
                    self._apply_selectmode()
                    self._update_multi_btn()
                    self.update_status()

            f = tk.Frame(inner)
            f.pack(fill="x", padx=30, pady=(8, 0))
            tk.Checkbutton(f, text=text, variable=var, command=on_change,
                           font=(FONT, 12), cursor="hand2").pack(anchor="w")
            if desc:
                tk.Label(inner, text=desc, font=(FONT, 9), fg=COLOR_GRAY,
                         wraplength=380, justify="left").pack(anchor="w", padx=50)

        def combo(text, values, key):
            f = tk.Frame(inner)
            f.pack(fill="x", padx=30, pady=(8, 0))
            tk.Label(f, text=text, font=(FONT, 12)).pack(side="left")
            var = tk.StringVar(value=str(self.settings.get(key, values[0])))
            cb = ttk.Combobox(f, textvariable=var, values=values, width=8,
                              state="readonly", font=(FONT, 11))
            cb.pack(side="left", padx=8)

            def on_change(_e=None):
                v = var.get()
                try:
                    self.settings[key] = int(v)
                except ValueError:
                    self.settings[key] = v
                self.save_data()
                if key == "row_height" and self._in_task_ui():
                    self.build_task_ui()

            cb.bind("<<ComboboxSelected>>", on_change)

        def mk_btn(text, cmd, desc=None, fg=COLOR_DARK, bg="#ecf0f1", hover="#dfe6e9"):
            b = tk.Button(inner, text=text, command=cmd, font=(FONT, 12), width=24,
                          relief=tk.FLAT, bg=bg, fg=fg, cursor="hand2", activebackground=hover)
            b.pack(pady=(12, 0), ipady=4)
            if desc:
                tk.Label(inner, text=desc, font=(FONT, 9), fg=COLOR_GRAY,
                         wraplength=380, justify="left").pack(anchor="w", padx=50)

        group("🧭 启动与模式")
        check("启动时直接进入上次模式", "skip_mode_select",
              "开启后不再弹模式选择，直接进上次用过的模式")
        combo("默认优先级", PRIORITIES, "default_priority")

        sep()
        group("🧾 列表显示")
        combo("行高", ["22", "26", "30"], "row_height")
        check("已完成任务加删除线", "strike_done")
        check("允许多选", "multi_select",
              "关闭时一次只能选中一条；开启后可 Ctrl / Shift 选多条，批量完成、批量删除，右键菜单还能「全选 / 反选」")

        # 新建任务界面：new=弹窗 / classic=行内输入
        f = tk.Frame(inner)
        f.pack(fill="x", padx=30, pady=(8, 0))
        tk.Label(f, text="新建任务界面", font=(FONT, 12)).pack(side="left")
        add_ui_var = tk.StringVar(value=self.settings.get("add_ui", "new"))
        add_ui_cb = ttk.Combobox(f, textvariable=add_ui_var, state="readonly", width=14,
                                font=(FONT, 11), values=["弹窗（new）", "行内（classic）"])
        add_ui_cb.set("弹窗（new）" if add_ui_var.get() == "new" else "行内（classic）")
        add_ui_cb.pack(side="left", padx=8)

        def on_add_ui(_e=None):
            self.settings["add_ui"] = "new" if add_ui_cb.get().startswith("弹窗") else "classic"
            self.save_data()
            if self._in_task_ui():
                self.build_task_ui()

        add_ui_cb.bind("<<ComboboxSelected>>", on_add_ui)

        sep()
        group("🎨 颜色", COLOR_ACCENT)
        check("彩色展示任务", "color_tasks",
              "像 1.0 那样：高 / 中 / 低优先级各一个颜色；关掉则统一深色")

        swatches = {}

        def make_pick(k, label):
            def pick():
                rgb, hexcolor = colorchooser.askcolor(
                    color=self.color_of(k), title=f"选择「{label}」的颜色", parent=win)
                if not hexcolor:
                    return
                self.settings["colors"][k] = hexcolor
                self.save_data()
                for b in swatches.get(k, []):
                    b.config(bg=hexcolor, text=hexcolor,
                             fg=text_on(hexcolor), activeforeground=text_on(hexcolor))
                if self._in_task_ui():
                    self.build_task_ui()
            return pick

        for key, label in COLOR_LABELS:
            line = tk.Frame(inner)
            line.pack(fill="x", padx=30, pady=(8, 0))
            tk.Label(line, text=label, font=(FONT, 11), width=10,
                     anchor="w").pack(side="left")
            sw = tk.Button(line, text=self.color_of(key), bg=self.color_of(key),
                           width=12, relief=tk.FLAT, cursor="hand2",
                           fg=text_on(self.color_of(key)),
                           activebackground=self.color_of(key),
                           activeforeground=text_on(self.color_of(key)),
                           command=make_pick(key, label))
            sw.pack(side="left", padx=6)
            swatches[key] = [sw]
            tk.Label(line, text="点色块换颜色", font=(FONT, 9),
                     fg=COLOR_GRAY).pack(side="left")

        def reset_colors():
            if not messagebox.askyesno("恢复默认", "把五个颜色都恢复成默认？", parent=win):
                return
            self.settings["colors"] = dict(DEFAULT_COLORS)
            self.save_data()
            for key, _label in COLOR_LABELS:
                for b in swatches.get(key, []):
                    b.config(bg=DEFAULT_COLORS[key], text=DEFAULT_COLORS[key])
            if self._in_task_ui():
                self.build_task_ui()

        tk.Button(inner, text="恢复默认颜色", command=reset_colors,
                  font=(FONT, 11), relief=tk.FLAT, bg="#ecf0f1", width=16,
                  cursor="hand2").pack(pady=(12, 0), ipady=3)

        sep()
        group("🔃 排序", "#16a085")
        sort_f = tk.Frame(inner)
        sort_f.pack(fill="x", padx=30, pady=(8, 0))
        sc, srev = self._eff_sort()
        sscope = ("normal" if (self.mode == "normal" and self.settings.get("sort_col_normal"))
                  else "perf" if (self.mode == "perf" and self.settings.get("sort_col_perf"))
                  else "global")
        sf_var = tk.StringVar(value=dict(SORT_FIELDS).get(sc, "优先级"))
        sf_cb = ttk.Combobox(sort_f, textvariable=sf_var, state="readonly", width=8,
                             font=(FONT, 11), values=[v for _, v in SORT_FIELDS])
        sf_cb.pack(side="left", padx=(0, 6))
        sr_var = tk.StringVar(value="正序" if not srev else "倒序")
        sr_cb = ttk.Combobox(sort_f, textvariable=sr_var, state="readonly", width=6,
                             font=(FONT, 11), values=["正序", "倒序"])
        sr_cb.pack(side="left", padx=(0, 6))
        ssc_var = tk.StringVar(value={"global": "全局", "normal": "仅普通", "perf": "仅性能"}[sscope])
        ssc_cb = ttk.Combobox(sort_f, textvariable=ssc_var, state="readonly", width=8,
                              font=(FONT, 11), values=["全局", "仅普通", "仅性能"])
        ssc_cb.pack(side="left", padx=(0, 6))

        def apply_settings_sort(_e=None):
            key = next((k for k, v in SORT_FIELDS if v == sf_var.get()), "priority")
            reverse = (sr_var.get() == "倒序")
            sc2 = {"全局": "global", "仅普通": "normal", "仅性能": "perf"}[ssc_var.get()]
            self._sort_scope_write(key, reverse, sc2)

        sf_cb.bind("<<ComboboxSelected>>", apply_settings_sort)
        sr_cb.bind("<<ComboboxSelected>>", apply_settings_sort)
        ssc_cb.bind("<<ComboboxSelected>>", apply_settings_sort)
        tk.Label(inner, text="作用域：全局两个模式共用；仅普通 / 仅性能 各自独立，没设过就用全局默认",
                 font=(FONT, 9), fg=COLOR_GRAY, wraplength=380, justify="left").pack(anchor="w", padx=50)

        sep()
        group("🎯 每日目标", "#8e44ad")
        f = tk.Frame(inner)
        f.pack(fill="x", padx=30, pady=(8, 0))
        tk.Label(f, text="每天完成几条算达标", font=(FONT, 12)).pack(side="left")
        goal_var = tk.StringVar(value=str(self.settings.get("daily_goal", 5)))
        g_cb = ttk.Combobox(f, textvariable=goal_var, width=6, state="readonly",
                            values=["1", "3", "5", "8", "10", "15"], font=(FONT, 11))
        g_cb.pack(side="left", padx=8)

        def change_goal(_e=None):
            try:
                self.settings["daily_goal"] = int(goal_var.get())
            except ValueError:
                return
            self.save_data()
            if self._in_task_ui():
                self.build_task_ui()

        g_cb.bind("<<ComboboxSelected>>", change_goal)
        tk.Label(inner, text="达标当天计入连续打卡（普通模式顶部看得到进度）",
                 font=(FONT, 9), fg=COLOR_GRAY, wraplength=380,
                 justify="left").pack(anchor="w", padx=50)

        sep()
        group("💾 数据与备份")
        check("改动后自动保存", "auto_save", "关闭后只在你点“保存”时写入文件")
        check("关闭窗口时保存", "save_on_close")
        check("删除前弹确认", "confirm_delete")
        mk_btn("备份 JSON", self.backup_json, "另存一份到自选位置")
        mk_btn("导出为 CSV", self.export_csv, "可用 Excel 打开")
        mk_btn("🩺 BUG 手动修复", lambda: self.show_repair(),
               "弹出独立的修复窗口（主界面标题栏的「🩺 急救」是同一个窗口）",
               fg=COLOR_DANGER, bg="#fdecea", hover="#f8d7da")
        check("标题栏显示「🩺 急救」", "bug_tools",
              "关掉后只有使用界面的标题栏不显示；主菜单、编辑窗口、批量修改窗口、"
              "设置里的入口永远都在——真出 BUG 时总有一条路能回来")

        sep()
        group("🍅 外挂")
        mk_btn("快捷键说明", self.show_hotkeys)

        sep()
        group("📋 预设任务", "#2980b9")
        check("启用预设功能", "preset_enabled",
              "关掉后使用界面不显示「使用预设」入口")
        mk_btn("打开 presets 文件夹", self.open_preset_folder)
        # 默认格式
        ff = tk.Frame(inner)
        ff.pack(fill="x", padx=30, pady=(8, 0))
        tk.Label(ff, text="默认格式", font=(FONT, 12)).pack(side="left")
        fmt_var = tk.StringVar(value=self.settings.get("preset_default_format", "simple"))
        fmt_cb = ttk.Combobox(ff, textvariable=fmt_var, state="readonly", width=10,
                              font=(FONT, 11), values=["simple", "py"])
        fmt_cb.pack(side="left", padx=8)

        def on_fmt(_e=None):
            self.settings["preset_default_format"] = fmt_var.get()
            self.save_data()

        fmt_cb.bind("<<ComboboxSelected>>", on_fmt)
        mk_btn("重新扫描 presets", self.rescan_presets, "重新读取 presets 文件夹里的 .rw / .txt")
        mk_btn("当前预设状态", self.open_preset_status)
        mk_btn("rw 使用方法", self.open_preset_help)
        mk_btn("生成示例预设", self.generate_samples, "生成 sample_simple.rw 与 sample_python.rw")
        tk.Label(inner, text="每个预设文件后面可勾选启用 / 禁用（禁用后不进“使用预设”下拉）",
                 font=(FONT, 9), fg=COLOR_GRAY, wraplength=380, justify="left").pack(anchor="w", padx=50)
        self._preset_list_frame = tk.Frame(inner)
        self._preset_list_frame.pack(fill="x", padx=30, pady=(4, 0))
        self._build_preset_list(self._preset_list_frame)

        sep()
        tk.Button(inner, text="新存档", command=lambda: self.new_archive(win),
                  font=(FONT, 12), width=24, relief=tk.FLAT, bg="#fdecea",
                  fg=COLOR_DANGER, cursor="hand2", activebackground="#f8d7da").pack(pady=(14, 0), ipady=4)
        tk.Label(inner, text="这会清空全部任务，建议先备份",
                 font=(FONT, 9), fg=COLOR_DANGER, wraplength=380,
                 justify="left").pack(anchor="w", padx=50, pady=(0, 20))

        tk.Button(win, text="关闭", command=win.destroy, font=(FONT, 11),
                  width=10).pack(pady=(10, 14))

    def _in_task_ui(self):
        return hasattr(self, "tree") and self.tree.winfo_exists()

    def color_of(self, key):
        """取某个角色的颜色（老存档缺项也能用默认值）"""
        colors = self.settings.get("colors") or {}
        return colors.get(key) or DEFAULT_COLORS.get(key, "#2c3e50")

    # ---------- 设置里的具体动作 ----------
    def backup_json(self):
        default = f"tasks_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path = filedialog.asksaveasfilename(
            title="备份数据", defaultextension=".json",
            initialfile=default, filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            data = dict(STORE.seg("tasks"))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("完成", f"已备份到：\n{path}")
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("备份失败", str(e))

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="导出 CSV", defaultextension=".csv",
            initialfile=f"tasks_{datetime.now().strftime('%Y%m%d')}.csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ID", "任务内容", "优先级", "科目", "分类", "截止日期",
                            "状态", "创建时间", "完成时间", "备注"])
                for t in self.tasks:
                    w.writerow([t["id"], t["title"], t["priority"],
                                t.get("subject", ""), t["category"],
                                t["due"], "已完成" if t["done"] else "未完成",
                                t["created"], t["done_at"], t["note"]])
            messagebox.showinfo("完成", f"已导出 {len(self.tasks)} 条任务到：\n{path}")
        except OSError as e:
            messagebox.showerror("导出失败", str(e))

    def new_archive(self, parent=None):
        p = parent or self.root
        if not messagebox.askyesno("危险操作", "这会清空当前所有任务且无法恢复！\n建议先“备份 JSON”。\n确定继续吗？", parent=p):
            return
        if not messagebox.askyesno("再次确认", "真的要新建空存档吗？", parent=p):
            return
        self.push_undo()
        self.tasks = []
        self.next_id = 1
        if self._in_task_ui():
            self.refresh()
        self.save_data()
        messagebox.showinfo("完成", "已清空，现在是全新的存档。", parent=p)

    # ==================================================================
    # BUG 手动修复（急救窗口：不看设置脸色，直接改数据 + 写 json）
    # ==================================================================
    def show_repair(self, parent=None, on_close=None):
        """
        BUG 修复框：独立于主界面的窗口
        —— 任务栏有自己的一条，能最大化 / 最小化 / 关闭，不锁主界面，随开随用。
        已经开着的时候再点一次，只是把它提到前面（不会开出第二个）。
        """
        old = getattr(self, "_repair_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.deiconify()
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
            self._repair_win = None

        # 不设 transient：它就是个独立窗口，父窗口最小化它还在
        win = tk.Toplevel(self.root)
        self._repair_win = win
        win.title("BUG 手动修复（独立窗口）")
        win.geometry("600x660")
        win.resizable(True, True)          # 保住最大化 / 最小化按钮
        try:
            x = self.root.winfo_rootx() + 60
            y = self.root.winfo_rooty() + 40
            win.geometry(f"600x660+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

        header = tk.Frame(win, bg=COLOR_DANGER)
        header.pack(fill="x")
        tk.Label(header, text="🩺 BUG 手动修复", font=(FONT, 17, "bold"),
                 bg=COLOR_DANGER, fg="white").pack(pady=(12, 2))
        tk.Label(header, text="独立窗口：能最大化 / 最小化 / 关掉再开，主界面照常能用；"
                              "这里的按钮不看「自动保存 / 删除确认」的脸色，点了就直接改数据、写 json",
                 font=(FONT, 9), bg=COLOR_DANGER, fg="#fdecea",
                 wraplength=540).pack(pady=(0, 10))

        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=20, pady=(10, 0))

        log_box = tk.Text(win, height=8, font=(FONT, 9), wrap="word",
                          relief=tk.SOLID, bd=1, state="disabled")
        log_box.pack(fill="both", expand=True, padx=20, pady=(10, 0))

        def log(text):
            log_box.configure(state="normal")
            log_box.insert("end", "· " + text + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        def after_change():
            """改完数据统一收尾：刷列表 + 无条件写盘"""
            if self._in_task_ui():
                self.refresh()
            self.save_data()

        def rebuild_ids():
            self.push_undo()
            for i, t in enumerate(self.tasks, 1):      # 原地编号，不建新列表
                t["id"] = i
            self.next_id = len(self.tasks) + 1
            log(f"已重新编号 {len(self.tasks)} 条（1…{len(self.tasks)}），下一个 ID = {self.next_id}")
            after_change()

        def drop_broken():
            self.push_undo()
            seen = set()
            keep = []
            removed = 0
            for t in self.tasks:                        # 一次遍历搞定，不额外拷贝
                if not t["title"].strip() or t["id"] in seen:
                    removed += 1
                    continue
                seen.add(t["id"])
                keep.append(t)
            self.tasks = keep
            log(f"删掉 {removed} 条（空标题 / 重复 ID），还剩 {len(self.tasks)} 条")
            after_change()

        def clean_fields():
            self.push_undo()
            fixed = 0
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            for t in self.tasks:
                if t.get("priority") not in PRIORITIES:
                    t["priority"] = "中"
                    fixed += 1
                if t.get("category") and t["category"] not in CATEGORIES:
                    t["category"] = ""
                    fixed += 1
                if t.get("subject") and t["subject"] not in SUBJECTS:
                    t["subject"] = ""
                    fixed += 1
                if t["done"] and not t["done_at"]:
                    t["done_at"] = now
                    fixed += 1
                if not t["done"] and t["done_at"]:
                    t["done_at"] = ""
                    fixed += 1
                if t["due"]:
                    try:
                        parse_date(t["due"])
                    except ValueError:
                        t["due"] = ""
                        fixed += 1
            log(f"清理了 {fixed} 处不合规的字段" if fixed else "字段都合规，没动")
            after_change()

        def reset_settings():
            self.settings = copy.deepcopy(DEFAULT_SETTINGS)
            log("设置已全部恢复到默认值")
            after_change()

        def fix_colors():
            colors = self.settings.get("colors")
            if not isinstance(colors, dict):
                colors = {}
            miss = [k for k in DEFAULT_COLORS if k not in colors]
            for k in miss:
                colors[k] = DEFAULT_COLORS[k]
            self.settings["colors"] = colors
            log(f"补齐 {len(miss)} 个颜色" if miss else "颜色配置齐全")
            after_change()

        def check_only():
            """只读检查，不碰数据"""
            ids = [t["id"] for t in self.tasks]
            issues = []
            dup = len(ids) - len(set(ids))
            if dup:
                issues.append(f"重复的 ID：{dup} 个")
            empty = sum(1 for t in self.tasks if not t["title"].strip())
            if empty:
                issues.append(f"空标题任务：{empty} 条")
            bad_pri = sum(1 for t in self.tasks if t.get("priority") not in PRIORITIES)
            if bad_pri:
                issues.append(f"非法优先级：{bad_pri} 条")
            bad_due = 0
            for t in self.tasks:
                if t["due"]:
                    try:
                        parse_date(t["due"])
                    except ValueError:
                        bad_due += 1
            if bad_due:
                issues.append(f"无法识别的截止日期：{bad_due} 条")
            top = max(ids) if ids else 0
            if self.next_id <= top:
                issues.append(f"next_id（{self.next_id}）不大于最大 ID（{top}），新任务会撞号")
            try:
                STORE.save()
                file_state = "Orbit3_data.json 能正常读写"
            except Exception as e:
                file_state = f"Orbit3_data.json 写不了：{e}"
                issues.append(str(e))
            log(file_state)
            if issues:
                for s in issues:
                    log("发现：" + s)
            else:
                log("检查完了，没发现问题")

        def save_now():
            if self.save_data():
                log("已写入 Orbit3_data.json")

        actions = [
            ("重建任务 ID（按当前顺序从 1 重排）", rebuild_ids),
            ("删除空标题 / 重复 ID 的任务", drop_broken),
            ("清理非法字段（优先级 / 分类 / 科目 / 截止 / 完成时间）", clean_fields),
            ("恢复默认设置", reset_settings),
            ("补齐颜色配置", fix_colors),
            ("检查数据完整性（只看不改）", check_only),
            ("立刻保存 JSON", save_now),
        ]
        for text, cmd in actions:
            tk.Button(body, text=text, command=cmd, font=(FONT, 11), anchor="w",
                      relief=tk.FLAT, bg="#ecf0f1", cursor="hand2",
                      activebackground="#dfe6e9").pack(fill="x", pady=2, ipady=4)

        bottom = tk.Frame(win)
        bottom.pack(fill="x", pady=(10, 12))
        tk.Button(bottom, text="保存并强制关闭", command=lambda: self._ask_force_quit(win),
                  font=(FONT, 12, "bold"), relief=tk.FLAT, bg=COLOR_DANGER, fg="white",
                  cursor="hand2", activebackground="#c0392b").pack(side="left", padx=(20, 8))
        tk.Button(bottom, text="关闭", command=lambda: close(),
                  font=(FONT, 11), width=8, relief=tk.FLAT).pack(side="right", padx=20)

        def forget(_e=None):
            """不管怎么被关掉（X / 关闭按钮 / 系统菜单），都把引用清干净"""
            if self._repair_win is win:
                self._repair_win = None

        def close():
            try:
                win.grab_release()
            except tk.TclError:
                pass
            forget()
            if self._in_task_ui():
                self.refresh()
            try:
                win.destroy()
            except tk.TclError:
                pass
            if on_close:
                on_close()

        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Destroy>", forget)
        win.lift()
        win.focus_force()          # 不 grab_set：主界面照样能点

    def open_repair_from(self, modal_win, on_close=None):
        """从模态窗口（编辑 / 批量修改）里开急救：
        先把模态放掉，否则新窗口点不动；急救框关了再把模态收回来"""
        if modal_win is not None:
            try:
                modal_win.grab_release()
            except tk.TclError:
                pass

        def back():
            if modal_win is not None:
                try:
                    if modal_win.winfo_exists():
                        modal_win.grab_set()
                        modal_win.lift()
                except tk.TclError:
                    pass
            if on_close:
                on_close()

        self.show_repair(on_close=back)

    def _ask_force_quit(self, parent):
        """强制关闭三选：是 / 否 / 检查设置"""
        box = tk.Toplevel(parent)
        box.title("强制关闭")
        box.resizable(False, False)
        box.transient(parent)
        center_window(box, 380, 170, parent)

        tk.Label(box, text="❗ 强制关闭程序？", font=(FONT, 14, "bold"),
                 fg=COLOR_DANGER).pack(pady=(18, 4))
        tk.Label(box, text="点「是」会先保存 json，然后无条件结束进程",
                 font=(FONT, 10), fg=COLOR_GRAY).pack()

        def yes():
            self.save_data()          # 先保住数据
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            os._exit(0)               # 真正的「强制」：不排队、不等窗口

        def no():
            box.destroy()

        def check_settings():
            box.destroy()
            try:
                parent.destroy()
            except tk.TclError:
                pass
            self.show_settings()

        row = tk.Frame(box)
        row.pack(pady=(14, 10))
        tk.Button(row, text="是", command=yes, font=(FONT, 12), width=6,
                  bg=COLOR_DANGER, fg="white", relief=tk.FLAT, cursor="hand2",
                  activebackground="#c0392b").pack(side="left", padx=6)
        tk.Button(row, text="否", command=no, font=(FONT, 12), width=6,
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=6)
        tk.Button(row, text="检查设置", command=check_settings, font=(FONT, 12),
                  width=10, relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=6)

        box.lift()
        box.focus_force()          # 同样不 grab，别把主界面锁死

    # ==================================================================
    # 番茄钟 / 音乐（标题栏两个外挂按钮）
    # ==================================================================
    # ==================================================================
    # 今日目标 / 连续打卡
    # ==================================================================
    def study_stats(self):
        """返回 (今日完成数, 目标, 连续打卡天数)"""
        today = today_str()
        goal = int(self.settings.get("daily_goal", 5) or 0)
        done_today = sum(1 for t in self.tasks
                         if t["done"] and (t["done_at"] or "").startswith(today))
        if goal > 0 and done_today >= goal and not self.study_goal_log.get(today):
            self.study_goal_log[today] = True
            if self.settings["auto_save"]:
                self.save_data()

        d = datetime.now().date()
        if not self.study_goal_log.get(today):
            d = d - timedelta(days=1)      # 今天还没达标，就从昨天往前数
        streak = 0
        while self.study_goal_log.get(d.strftime("%Y-%m-%d")):
            streak += 1
            d = d - timedelta(days=1)
        return done_today, goal, streak

    # ==================================================================
    # 更新日志（仿 Orbit2）
    # ==================================================================
    def show_changelog(self):
        win = tk.Toplevel(self.root)
        win.title("更新日志")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 640, 700, self.root)
        win.grab_set()

        header = tk.Frame(win, bg=COLOR_DARK)
        header.pack(fill="x")
        tk.Label(header, text=APP_WINDOW_TITLE, font=(FONT, 22, "bold"),
                 bg=COLOR_DARK, fg="white").pack(pady=(16, 0))
        tk.Label(header, text=APP_CODENAME, font=(FONT, 11),
                 bg=COLOR_DARK, fg="#bdc3c7").pack(pady=(0, 12))

        sf = ScrolledFrame(win, width=560)
        inner = sf.inner

        def section(title):
            tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill="x", pady=(14, 0))
            tk.Label(inner, text=title, font=(FONT, 14, "bold"),
                     fg=COLOR_DARK, anchor="w").pack(fill="x", pady=(10, 4))

        def item(text, sub=None):
            tk.Label(inner, text="• " + text, font=(FONT, 11), fg="#2c3e50",
                     anchor="w", justify="left", wraplength=550).pack(fill="x", pady=(2, 0))
            if sub:
                tk.Label(inner, text="    " + sub, font=(FONT, 9), fg=COLOR_GRAY,
                         anchor="w", justify="left", wraplength=550).pack(fill="x")

        tk.Label(inner, text=f"作者：{APP_AUTHOR}", font=(FONT, 12, "bold"),
                 fg=COLOR_PRIMARY).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text="一个轻量的本地任务管理器：\n管任务、开番茄钟、放音乐，数据存本地 JSON。",
                 font=(FONT, 10), fg="#7f8c8d", justify="left").pack(anchor="w")

        # ===================== Nexus 3.0 =====================
        section("Nexus 3.0（当前版本）")
        item("新建任务弹窗（功能 1）",
             "点「＋ 新建」弹出独立窗口，字段齐全 + 日期快捷按钮；也可在设置里切回行内输入（classic）")
        item("预设任务（功能 2）",
             "presets/ 里的 .rw / .txt 预设，simple 与 py 两种写法；设置里可启用、扫状态、看用法、生成示例")
        item("排序做成设置项（功能 3）",
             "6 个排序字段 + 正/倒序，作用域分全局 / 仅普通 / 仅性能，设置窗与操作窗都能改，点列头也写回")
        item("使用界面分两板块 + 操作窗口（功能 4）",
             "主界面清爽，所有操作收进非模态「⚙ 操作」窗口，选中状态实时联动")
        item("更新日志改番茄钟样式（功能 5）",
             "深色标题条 + 可滚动分区，按版本从新到旧排列，圆点条目")
        item("版本号升级到 3.0",
             "数据文件 tasks_v3.json；启动检测到 2.0 数据会问是否迁移，ID 与设置不变")

        # ===================== Nexus 2.0 =====================
        section("Nexus 2.0")
        item("启动与界面：进主菜单再选模式", "开始使用 / 更新日志 / 设置 / 快捷键说明 / 退出；可设置直接进入上次模式")
        item("两个模式共用一份数据", "普通（七列 + 今日目标 + 科目概览）/ 性能（五列、只看未完成、行高更小）")
        item("Orbit2 风格界面", "深色标题条 + 绿色主色 + flat 按钮 + 可滚动设置，标题条颜色随模式")
        item("窗口 900 × 640（最小 760 × 470）", "比 1.0 的 760 × 520 更大")
        item("独立设置窗口", "启动与模式 / 列表显示 / 颜色 / 每日目标 / 数据与备份 / 外挂")
        item("一条任务能记更多", "新增 科目 / 分类 / 截止日期 / 备注 / 完成时间；填了科目分类自动填「学习」")
        item("顶部科目概览", "未完成按科目计数，点一下只看该科目")
        item("列表显示截止", "今天 / 明天 / N天后 / 逾期N天，逾期红色加粗")
        item("编辑窗口", "Ctrl+E 或右键打开（模态，不保存/取消不能碰主界面）")
        item("多选开关", "默认关闭防误触；开启后点几行选几行、Shift 连选、Ctrl+A 全选、右键全选/反选")
        item("批量修改", "选中多条 → 右键「修改所选」或 Ctrl+M，勾哪改哪，可 Ctrl+Z 撤回")
        item("撤销 Ctrl+Z（最多 30 步）", "删除 / 清空已完成 / 编辑 / 新建存档都能撤回")
        item("删除确认可开关", "设置 → 数据与备份 → 删除前弹确认")
        item("搜索框（Ctrl+F）", "同时搜标题 / 备注 / 分类 / 科目")
        item("点列头排序", "优先级 / 截止 / 创建时间 / 分类 / 科目 / 内容，再点反向")
        item("筛选增强", "分类、科目下拉 + 搜索框 + 顶部科目按钮一键筛选")
        item("右键菜单升级", "编辑 / 切换完成 / 复制内容 / 删除 / 全选 / 反选")
        item("快捷键增多", "新增 Ctrl+N / Ctrl+F / Ctrl+E / Ctrl+Z / Delete / 空格 / Ctrl+A")
        item("优先级配色可自定义", "高/中/低/已完成/逾期 五个角色都能取色，可一键恢复默认")
        item("彩色总开关", "设置 → 彩色展示任务，关掉统一深色")
        item("已完成样式：灰 + 删除线", "删除线可在设置里关")
        item("今日目标 + 连续打卡", "普通模式顶部进度条 + 🔥 打卡天数，目标条数可选")
        item("外挂：番茄钟 + 音乐", "标题栏 🍅 启动番茄钟、🎵 打开 B 站音乐")
        item("状态栏信息更全", "今日完成 / 逾期数 / 当前显示 / 已选条数 / 当前模式 / 当前排序")
        item("数据文件 tasks_v2.json", "存任务 + 设置 + 打卡记录 + 上次模式 + 保存时间；1.0 数据可一键迁移")
        item("保存时机可调", "自动保存 / 关闭保存 / Ctrl+S 手动，三种都能在设置里开关")
        item("备份 JSON + 导出 CSV", "备份到自选位置、导出 Excel 直接打开")
        item("新存档 + 两次确认", "手滑了还能 Ctrl+Z 撤回来")
        item("🩺 急救 / BUG 修复窗口", "独立窗口重建 ID、清非法字段、恢复默认、完整性体检、强制关闭")

        # ===================== Nexus 1.0 =====================
        section("Nexus 1.0")
        item("最初的本地任务管理器", "三档优先级、双击切换完成、回车添加、旁边一个 JSON 存数据，不联网不要账号")

        tk.Button(win, text="关闭", command=win.destroy,
                  font=(FONT, 11), width=10).pack(pady=(10, 14))

    # ==================================================================
    # 快捷键说明
    # ==================================================================
    def show_hotkeys(self):
        win = tk.Toplevel(self.root)
        win.title("快捷键说明")
        win.resizable(False, False)
        win.transient(self.root)
        center_window(win, 470, 520, self.root)
        win.grab_set()

        tk.Label(win, text="⌨ 快捷键", font=(FONT, 18, "bold"),
                 fg=COLOR_DARK).pack(pady=(14, 10))

        rows = [
            ("Enter（输入框内）", "添加任务"),
            ("双击任务", "切换完成状态"),
            ("空格", "切换选中任务的完成状态"),
            ("Ctrl + E", "打开编辑窗口（改单条）"),
            ("Ctrl + M", "修改所选：1 条走编辑窗口，多条走批量修改窗口"),
            ("Delete", "删除选中任务"),
            ("Ctrl + N", "新建任务（弹窗）；classic 模式下跳到输入框"),
            ("Ctrl + F", "光标跳到搜索框"),
            ("Ctrl + A", "全选（需要先开「多选」，列表里生效）"),
            ("Ctrl + S", "立即保存"),
            ("Ctrl + Z", "撤销上一步操作"),
            ("鼠标右键", "编辑 / 修改所选 / 切换完成 / 复制 / 删除 / 全选 / 反选"),
        ]
        for k, v in rows:
            f = tk.Frame(win)
            f.pack(fill="x", padx=30, pady=4)
            tk.Label(f, text=k, font=(FONT, 11, "bold"), fg=COLOR_ACCENT,
                     width=20, anchor="w").pack(side="left")
            tk.Label(f, text=v, font=(FONT, 11), anchor="w").pack(side="left")

        tk.Button(win, text="关闭", command=win.destroy,
                  font=(FONT, 11), width=10).pack(pady=16)

    # ==================================================================
    def on_close(self):
        if self.settings.get("save_on_close", True):
            self.save_data()
        for seq in ("<Control-s>", "<Control-z>", "<Control-e>",
                    "<Control-m>", "<Control-f>", "<Control-n>"):
            try:
                self.root.unbind_all(seq)
            except tk.TclError:
                pass
        self.root.destroy()


def launch(parent, store, mod_values=None, dev=None):
    """由 Orbit3 调用：在独立 Toplevel 中打开任务管理器 3（SE 无标签版）"""
    bind_store(store, mod_values)
    if dev:
        DEV.update(dev)
    ensure_presets()
    top = tk.Toplevel(parent)
    TaskManager(top)
    return top
