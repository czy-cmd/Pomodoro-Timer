# -*- coding: utf-8 -*-
\"\"\"数据备份工具：备份/恢复 Orbit3_data.json。\"\"\"
import tkinter as tk
from tkinter import messagebox, filedialog
import os, json, shutil
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "Orbit3_data.json")

class Backup:
    def __init__(self, root):
        self.root = root
        self.root.title("数据备份工具")
        self.root.geometry("460x360")
        tk.Label(self.root, text="💾 数据备份工具", font=("微软雅黑", 16, "bold"),
                 fg="#2c3e50").pack(pady=(14, 4))
        tk.Label(self.root, text="数据文件：\\n" + DATA, font=("微软雅黑", 8),
                 fg="#95a5a6", justify="center").pack()
        self.lb = tk.Listbox(self.root, font=("Consolas", 10), width=60, height=10,
                             exportselection=False)
        self.lb.pack(fill="both", expand=True, padx=14, pady=10)
        btns = tk.Frame(self.root)
        btns.pack(pady=6)
        tk.Button(btns, text="立即备份", command=self.do_backup, font=("微软雅黑", 11),
                  bg="#2ecc71", fg="white", relief=tk.FLAT, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btns, text="恢复所选", command=self.do_restore, font=("微软雅黑", 11),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)
        tk.Button(btns, text="刷新", command=self.refresh, font=("微软雅黑", 11),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)
        self.refresh()

    def _dir(self):
        d = os.path.join(os.path.dirname(BASE), "backups")
        os.makedirs(d, exist_ok=True)
        return d

    def refresh(self):
        self.lb.delete(0, tk.END)
        try:
            for f in sorted(os.listdir(self._dir())):
                if f.endswith(".json"):
                    self.lb.insert(tk.END, f)
        except OSError:
            pass

    def do_backup(self):
        if not os.path.exists(DATA):
            messagebox.showwarning("提示", "还没找到 Orbit3_data.json", parent=self.root)
            return
        name = "Orbit3_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        shutil.copy2(DATA, os.path.join(self._dir(), name))
        self.refresh()
        messagebox.showinfo("完成", "已备份为：\\n" + name, parent=self.root)

    def do_restore(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showinfo("提示", "先选中要恢复的备份", parent=self.root)
            return
        f = self.lb.get(sel[0])
        if not messagebox.askyesno("确认", "确定用这个备份覆盖当前数据吗？", parent=self.root):
            return
        shutil.copy2(os.path.join(self._dir(), f), DATA)
        messagebox.showinfo("完成", "已恢复：\\n" + f, parent=self.root)

if __name__ == "__main__":
    root = tk.Tk()
    Backup(root)
    root.mainloop()
