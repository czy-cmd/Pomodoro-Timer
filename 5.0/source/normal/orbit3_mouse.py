#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鼠标焦点检测器（Orbit3 内嵌版）
检测前台窗口程序名 + 专注/瞎玩双计时器 + 设置窗口。
数据统一存入 Orbit3_data.json（经 bind_store 注入），不再写任何源目录文件。
（夸夸机及相关 key 系统已移除，白名单改为独立管理窗口）
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import time
import random
import string
import winsound
from datetime import datetime
import ctypes
from ctypes import wintypes

# ===================== Windows API =====================
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi    = ctypes.windll.psapi


def get_foreground_process_name():
    """获取前台窗口的进程名（不含.exe）"""
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h_process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
    if not h_process:
        return ""
    buf = ctypes.create_unicode_buffer(512)
    psapi.GetModuleBaseNameW(h_process, None, buf, 512)
    kernel32.CloseHandle(h_process)
    name = buf.value
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name


def get_foreground_window_title():
    """获取前台窗口的标题"""
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


# ===================== 数据存储（由主程序注入） =====================
STORE = None          # Orbit3Store 实例


def bind_store(store):
    global STORE
    STORE = store


# ===================== 配色 =====================
BG          = "#ffffff"
FG_TEXT     = "#333333"
FG_FOCUS    = "#27ae60"
FG_WARNING  = "#f39c12"
FG_DISTRACT = "#e74c3c"
FG_WAIT     = "#999999"
BTN_BG      = "#3498db"
BTN_FG      = "#ffffff"
FONT        = "Microsoft YaHei"

DEFAULT_WARNING_SEC = 10
DEFAULT_AUTO_SAVE_MIN = 5
# 前台窗口标题/进程名含以下关键词时，一律算专注、不算瞎玩
DEFAULT_WHITELIST = ["Orbit3", "番茄钟", "任务管理器"]


def fmt(seconds):
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ===================== 主程序 =====================
class FocusTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("鼠标检测器")
        self.root.geometry("240x280")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(200, 240)

        # 设置
        self.settings = self.load_settings()
        self.warning_sec = self.settings.get("warning_sec", DEFAULT_WARNING_SEC)
        self.auto_save_ms = self.settings.get("auto_save_min", DEFAULT_AUTO_SAVE_MIN) * 60 * 1000
        self.app_name_mode = self.settings.get("app_name_mode", "process")  # process / title
        self.whitelist = self.settings.get("whitelist", list(DEFAULT_WHITELIST))

        self._last_beep_sec = -1                     # 瞎搞蜂鸣节流

        # 计时状态
        self.is_focused = False
        self.in_warning = False
        self.is_distracted = False
        self.warning_deadline = 0.0
        self.last_tick = time.time()

        # 数据
        self.session_focus = 0.0
        self.session_distracted = 0.0
        self.total_focus = 0.0
        self.total_distracted = 0.0

        self.load_data()
        self.build_ui()
        self.bind_events()
        self.tick()
        self.schedule_auto_save()

    # ---------- store 存取 ----------
    def _seg(self):
        """mouse 段，确保存在"""
        return STORE.seg("mouse")

    # ---------- 设置加载/保存 ----------
    def load_settings(self):
        s = self._seg().get("settings", {})
        return s if isinstance(s, dict) else {}

    def save_settings(self):
        try:
            self._seg()["settings"] = self.settings
            STORE.save()
        except Exception as e:
            messagebox.showerror("保存设置失败", str(e))

    # ---------- UI ----------
    def build_ui(self):
        f = (FONT, 10)
        f_bold = (FONT, 10, "bold")

        # 当前软件名
        self.app_lbl = tk.Label(
            self.root, text="", font=(FONT, 11),
            bg=BG, fg="#666666"
        )
        self.app_lbl.pack(pady=(10, 2))

        # 状态
        self.status_lbl = tk.Label(
            self.root, text="等待中…", font=(FONT, 16, "bold"),
            bg=BG, fg=FG_WAIT
        )
        self.status_lbl.pack(pady=(2, 6))

        # 分隔线
        tk.Frame(self.root, bg="#dddddd", height=1).pack(fill=tk.X, padx=16, pady=4)

        # 专注时间行
        row1 = tk.Frame(self.root, bg=BG)
        row1.pack(fill=tk.X, padx=20, pady=(4, 2))
        tk.Label(row1, text="专注", font=f_bold, bg=BG, fg=FG_FOCUS).pack(side=tk.LEFT)
        self.focus_lbl = tk.Label(row1, text="00:00:00", font=(FONT, 18, "bold"), bg=BG, fg=FG_FOCUS)
        self.focus_lbl.pack(side=tk.RIGHT)

        # 瞎玩时间行
        row2 = tk.Frame(self.root, bg=BG)
        row2.pack(fill=tk.X, padx=20, pady=(2, 4))
        tk.Label(row2, text="瞎玩", font=f_bold, bg=BG, fg=FG_DISTRACT).pack(side=tk.LEFT)
        self.distract_lbl = tk.Label(row2, text="00:00:00", font=(FONT, 18, "bold"), bg=BG, fg=FG_DISTRACT)
        self.distract_lbl.pack(side=tk.RIGHT)

        # 分隔线
        tk.Frame(self.root, bg="#dddddd", height=1).pack(fill=tk.X, padx=16, pady=4)

        # 按钮行
        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(pady=(6, 10))

        self.btn_save = tk.Label(
            btn_row, text="保存", font=f_bold,
            bg=BTN_BG, fg=BTN_FG, cursor="hand2",
            width=8, height=1
        )
        self.btn_save.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_save.bind("<Button-1>", lambda e: self.save_data())
        self.btn_save.bind("<Enter>", lambda e: self.btn_save.configure(bg="#2980b9"))
        self.btn_save.bind("<Leave>", lambda e: self.btn_save.configure(bg=BTN_BG))

        self.btn_settings = tk.Label(
            btn_row, text="⚙ 设置", font=f_bold,
            bg="#ecf0f1", fg=FG_TEXT, cursor="hand2",
            width=8, height=1
        )
        self.btn_settings.pack(side=tk.LEFT)
        self.btn_settings.bind("<Button-1>", lambda e: self.open_settings())
        self.btn_settings.bind("<Enter>", lambda e: self.btn_settings.configure(bg="#d5dbdb"))
        self.btn_settings.bind("<Leave>", lambda e: self.btn_settings.configure(bg="#ecf0f1"))

    # ---------- 事件 ----------
    def bind_events(self):
        self.root.bind("<FocusIn>", self.on_focus_in)
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_focus_in(self, event):
        if event.widget is not self.root:
            return
        self.is_focused = True
        self.in_warning = False
        self.is_distracted = False
        self.status_lbl.config(text="深度专注中", fg=FG_FOCUS)

    def on_focus_out(self, event):
        if event.widget is not self.root:
            return
        self.is_focused = False
        self.in_warning = True
        self.is_distracted = False
        self.warning_deadline = time.time() + self.warning_sec

    # ---------- 计时 ----------
    def tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now

        # 更新当前软件名
        process = get_foreground_process_name()
        title = get_foreground_window_title()
        if self.app_name_mode == "process":
            name = process
        elif self.app_name_mode == "title":
            name = title
        else:
            name = f"{process} | {title}" if process and title else (process or title or "未知")
        self.app_lbl.config(text=name)

        # 白名单：前台窗口是番茄钟/任务管理器等，一律算专注
        is_whitelisted = any(k and (k in title or k in process) for k in self.whitelist)

        # 计时逻辑
        if self.is_focused or is_whitelisted:
            if is_whitelisted and (self.in_warning or self.is_distracted):
                self.in_warning = False
                self.is_distracted = False
            self.session_focus += dt
            self.status_lbl.config(text="深度专注中", fg=FG_FOCUS)
        elif self.in_warning:
            self.session_focus += dt
            remaining = max(0, int(self.warning_deadline - now))
            if remaining > 0:
                self.status_lbl.config(text=f"走神警告 {remaining}", fg=FG_WARNING)
            else:
                self.in_warning = False
                self.is_distracted = True
                self.status_lbl.config(text="瞎玩瞎搞中", fg=FG_DISTRACT)
        elif self.is_distracted:
            self.session_distracted += dt
            self.status_lbl.config(text="瞎玩瞎搞中", fg=FG_DISTRACT)
            # 瞎搞模式：每秒一声尖锐蜂鸣
            sec = int(now)
            if sec != self._last_beep_sec:
                self._last_beep_sec = sec
                try:
                    winsound.Beep(2500, 120)
                except Exception:
                    pass

        self.focus_lbl.config(text=fmt(self.total_focus + self.session_focus))
        self.distract_lbl.config(text=fmt(self.total_distracted + self.session_distracted))

        self.root.after(200, self.tick)

    # ---------- 自动保存 ----------
    def schedule_auto_save(self):
        self.save_data()
        self.root.after(self.auto_save_ms, self.schedule_auto_save)

    # ---------- 数据 ----------
    def load_data(self):
        data = self._seg()
        try:
            self.total_focus = float(data.get("total_focus", 0))
            self.total_distracted = float(data.get("total_distracted", 0))
        except Exception:
            pass

    def save_data(self):
        try:
            data = self._seg()

            data["total_focus"] = data.get("total_focus", 0) + self.session_focus
            data["total_distracted"] = data.get("total_distracted", 0) + self.session_distracted

            today = datetime.now().strftime("%Y-%m-%d")
            if "daily" not in data:
                data["daily"] = {}
            if today not in data["daily"]:
                data["daily"][today] = {}
            data["daily"][today]["focus"] = data["daily"][today].get("focus", 0) + self.session_focus
            data["daily"][today]["distracted"] = data["daily"][today].get("distracted", 0) + self.session_distracted

            STORE.save()

            self.total_focus += self.session_focus
            self.total_distracted += self.session_distracted
            self.session_focus = 0.0
            self.session_distracted = 0.0

            orig = self.btn_save.cget("text")
            self.btn_save.config(text="✓")
            self.root.after(800, lambda: self.btn_save.config(text=orig))
        except Exception:
            pass

    def on_close(self):
        self.save_data()
        self.root.destroy()

    # ---------- 设置窗口 ----------
    def open_settings(self):
        if hasattr(self, "settings_win") and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("300x400")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self.root)
        self.settings_win = win

        f = (FONT, 10)
        f_bold = (FONT, 10, "bold")
        pad = {"padx": 16, "pady": 4}

        # --- 走神警告时间 ---
        tk.Label(win, text="走神警告时间（秒）", font=f_bold, bg=BG, fg=FG_TEXT).pack(anchor=tk.W, **pad)
        warning_var = tk.StringVar(value=str(self.warning_sec))
        tk.Entry(win, textvariable=warning_var, font=f, width=10).pack(anchor=tk.W, padx=16, pady=(0, 4))

        # --- 自动保存间隔 ---
        tk.Frame(win, bg="#dddddd", height=1).pack(fill=tk.X, **pad)
        tk.Label(win, text="自动保存间隔（分钟）", font=f_bold, bg=BG, fg=FG_TEXT).pack(anchor=tk.W, **pad)
        auto_var = tk.StringVar(value=str(self.auto_save_ms // 60000))
        tk.Entry(win, textvariable=auto_var, font=f, width=10).pack(anchor=tk.W, padx=16, pady=(0, 4))

        # --- 软件名显示方式 ---
        tk.Frame(win, bg="#dddddd", height=1).pack(fill=tk.X, **pad)
        tk.Label(win, text="软件名显示方式", font=f_bold, bg=BG, fg=FG_TEXT).pack(anchor=tk.W, **pad)

        mode_var = tk.StringVar(value=self.app_name_mode)
        mode_frame = tk.Frame(win, bg=BG)
        mode_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        for val, label in [("process", "进程名（如 chrome）"),
                           ("title", "窗口标题"),
                           ("both", "两者都显示")]:
            tk.Radiobutton(mode_frame, text=label, variable=mode_var, value=val,
                           bg=BG, fg=FG_TEXT, selectcolor=BG, font=f,
                           activebackground=BG, activeforeground=FG_TEXT).pack(anchor=tk.W)

        # --- 白名单关键词（改成「修改」按钮） ---
        tk.Frame(win, bg="#dddddd", height=1).pack(fill=tk.X, **pad)
        wl_row = tk.Frame(win, bg=BG)
        wl_row.pack(anchor=tk.W, padx=16, pady=(4, 2))
        tk.Label(wl_row, text="白名单（不算瞎玩）", font=f_bold, bg=BG, fg=FG_TEXT).pack(side=tk.LEFT)
        tk.Label(wl_row, text=f"（{len(self.whitelist)} 个）", font=f, bg=BG,
                 fg=FG_WAIT).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(wl_row, text="修改", font=f, bg="#ecf0f1", fg=FG_TEXT,
                  command=self._open_whitelist).pack(side=tk.LEFT, padx=(10, 0))

        # --- 数据重置 ---
        tk.Frame(win, bg="#dddddd", height=1).pack(fill=tk.X, **pad)
        reset_btn = tk.Label(
            win, text="⚠ 重置所有数据", font=f_bold,
            bg="#e74c3c", fg="#ffffff", cursor="hand2",
            width=16, height=1
        )
        reset_btn.pack(pady=(10, 4))
        reset_btn.bind("<Button-1>", lambda e: self._confirm_reset(win))
        reset_btn.bind("<Enter>", lambda e: reset_btn.configure(bg="#c0392b"))
        reset_btn.bind("<Leave>", lambda e: reset_btn.configure(bg="#e74c3c"))

        # --- 按钮区 ---
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill=tk.X, pady=(10, 8))

        tk.Button(btn_row, text="应用", font=f_bold,
                  command=lambda: self._apply_settings(warning_var, auto_var, mode_var, win),
                  bg=BTN_BG, fg=BTN_FG).pack(side=tk.RIGHT, padx=(4, 16))

        tk.Button(btn_row, text="取消", font=f,
                  command=win.destroy,
                  bg="#ecf0f1", fg=FG_TEXT).pack(side=tk.RIGHT, padx=(4, 4))

    # ---------- 白名单修改 / 管理窗口 ----------
    def _open_whitelist(self):
        if hasattr(self, "wl_win") and self.wl_win.winfo_exists():
            self.wl_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("白名单")
        win.geometry("420x430")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self.root)
        self.wl_win = win

        f = (FONT, 10)
        f_bold = (FONT, 10, "bold")
        tk.Label(win, text="白名单（不算瞎玩的关键词）", font=f_bold, bg=BG, fg=FG_TEXT).pack(anchor=tk.W, padx=16, pady=(12, 2))
        tk.Label(win, text="前台窗口标题/进程名含这些关键词时，一律算专注",
                 font=f, bg=BG, fg=FG_WAIT).pack(anchor=tk.W, padx=16)

        # 输入框 + 增加
        add_row = tk.Frame(win, bg=BG)
        add_row.pack(fill=tk.X, padx=16, pady=(10, 4))
        entry_var = tk.StringVar()
        tk.Entry(add_row, textvariable=entry_var, font=f, width=24).pack(side=tk.LEFT)
        tk.Button(add_row, text="增加", font=f, bg=BTN_BG, fg=BTN_FG,
                  command=lambda: self._wl_add(entry_var, txt)).pack(side=tk.LEFT, padx=(6, 0))

        # 多行输入框
        tk.Label(win, text="已添加（每行一个，可直接增删改）", font=f, bg=BG,
                 fg=FG_WAIT).pack(anchor=tk.W, padx=16, pady=(6, 0))
        txt = tk.Text(win, font=("Consolas", 10), width=46, height=10, wrap=tk.WORD)
        txt.pack(padx=16, pady=4)
        txt.insert("1.0", "\n".join(self.whitelist))

        # 按钮区
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill=tk.X, pady=(6, 8))
        tk.Button(btn_row, text="管理", font=f_bold, bg="#ecf0f1", fg=FG_TEXT,
                  command=self._open_whitelist_manage).pack(side=tk.LEFT, padx=(16, 4))
        tk.Button(btn_row, text="保存", font=f_bold,
                  command=lambda: self._wl_save(txt, win), bg=BTN_BG, fg=BTN_FG).pack(side=tk.RIGHT, padx=(4, 16))
        tk.Button(btn_row, text="关闭", font=f,
                  command=win.destroy, bg="#ecf0f1", fg=FG_TEXT).pack(side=tk.RIGHT, padx=(4, 4))

    def _wl_add(self, var, txt):
        k = var.get().strip()
        if not k:
            return
        cur = txt.get("1.0", "end").strip()
        lines = [l.strip() for l in cur.splitlines() if l.strip()]
        if k not in lines:
            lines.append(k)
            txt.delete("1.0", "end")
            txt.insert("1.0", "\n".join(lines))
        var.set("")

    def _wl_save(self, txt, win):
        lines = [l.strip() for l in txt.get("1.0", "end").splitlines() if l.strip()]
        self.whitelist = lines
        self.settings["whitelist"] = lines
        self.save_settings()
        messagebox.showinfo("已保存", f"白名单已更新（{len(lines)} 个关键词）。", parent=win)
        win.destroy()

    def _open_whitelist_manage(self):
        """管理窗口：可选中删除、双击/按钮修改关键词"""
        win = tk.Toplevel(self.root)
        win.title("白名单 · 管理")
        win.geometry("380x380")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self.root)

        f = (FONT, 10)
        f_bold = (FONT, 10, "bold")
        tk.Label(win, text="管理白名单", font=f_bold, bg=BG, fg=FG_TEXT).pack(anchor=tk.W, padx=16, pady=(12, 4))
        tk.Label(win, text="选中后点「删除」；双击或点「修改」可重命名",
                 font=f, bg=BG, fg=FG_WAIT).pack(anchor=tk.W, padx=16)

        lb = tk.Listbox(win, font=("Consolas", 11), width=44, height=12,
                        selectmode=tk.EXTENDED, exportselection=False)
        lb.pack(padx=16, pady=8)
        for k in self.whitelist:
            lb.insert(tk.END, k)

        def refresh():
            lb.delete(0, tk.END)
            for k in self.whitelist:
                lb.insert(tk.END, k)

        def do_delete():
            sel = list(lb.curselection())
            if not sel:
                messagebox.showinfo("提示", "先选中要删除的关键词", parent=win)
                return
            for i in reversed(sel):
                del self.whitelist[i]
            self.settings["whitelist"] = self.whitelist
            self.save_settings()
            refresh()

        def do_rename(event=None):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            new = tk.simpledialog.askstring("修改关键词", "新的关键词：",
                                            initialvalue=self.whitelist[i], parent=win)
            if new and new.strip():
                self.whitelist[i] = new.strip()
                self.settings["whitelist"] = self.whitelist
                self.save_settings()
                refresh()

        lb.bind("<Double-1>", do_rename)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill=tk.X, pady=8)
        tk.Button(btn_row, text="修改", command=do_rename, font=f,
                  bg="#ecf0f1", fg=FG_TEXT).pack(side=tk.LEFT, padx=(16, 4))
        tk.Button(btn_row, text="删除", command=do_delete, font=f,
                  bg="#e74c3c", fg="#ffffff").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="关闭", command=win.destroy, font=f,
                  bg="#ecf0f1", fg=FG_TEXT).pack(side=tk.RIGHT, padx=(4, 16))

    def _confirm_reset(self, win):
        if messagebox.askyesno("确认重置", "确定要清空所有专注/瞎玩数据吗？\n此操作不可撤销。"):
            try:
                seg = self._seg()
                for k in ("total_focus", "total_distracted"):
                    seg[k] = 0
                seg["daily"] = {}
                STORE.save()
                self.total_focus = 0.0
                self.total_distracted = 0.0
                self.session_focus = 0.0
                self.session_distracted = 0.0
                self.focus_lbl.config(text="00:00:00")
                self.distract_lbl.config(text="00:00:00")
                messagebox.showinfo("已重置", "所有数据已清空。")
            except Exception as e:
                messagebox.showerror("重置失败", str(e))

    def _apply_settings(self, warning_var, auto_var, mode_var, win):
        try:
            w = int(warning_var.get())
            a = int(auto_var.get())
            if w < 0 or a < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("输入错误", "警告时间和保存间隔必须是正整数。")
            return

        self.warning_sec = w
        self.auto_save_ms = a * 60 * 1000
        self.app_name_mode = mode_var.get()

        self.settings["warning_sec"] = self.warning_sec
        self.settings["auto_save_min"] = a
        self.settings["app_name_mode"] = self.app_name_mode
        self.settings["whitelist"] = self.whitelist
        self.save_settings()
        win.destroy()
