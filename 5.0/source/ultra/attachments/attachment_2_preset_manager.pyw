# -*- coding: utf-8 -*-
\"\"\"预设文件管理器：浏览 presets 文件夹，新建/打开/编辑 .rw 预设。\"\"\"
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PRESET_DIR = os.path.join(os.path.dirname(BASE), "presets")

class Manager:
    def __init__(self, root):
        self.root = root
        self.root.title("预设文件管理器")
        self.root.geometry("520x460")
        tk.Label(self.root, text="📋 预设文件管理器", font=("微软雅黑", 16, "bold"),
                 fg="#2c3e50").pack(pady=(12, 4))
        self.dir_lbl = tk.Label(self.root, text=PRESET_DIR, font=("微软雅黑", 8),
                                fg="#95a5a6")
        self.dir_lbl.pack()
        btns = tk.Frame(self.root)
        btns.pack(pady=6)
        for txt, cmd in [("新建", self.new_file), ("打开编辑", self.open_file),
                         ("打开文件夹", self.open_folder), ("刷新", self.refresh)]:
            tk.Button(btns, text=txt, command=cmd, font=("微软雅黑", 10),
                      relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=4)
        self.lb = tk.Listbox(self.root, font=("Consolas", 10), width=64, height=16,
                             exportselection=False)
        self.lb.pack(fill="both", expand=True, padx=12, pady=6)
        self.lb.bind("<Double-1>", lambda e: self.open_file())
        self.refresh()

    def _files(self):
        try:
            os.makedirs(PRESET_DIR, exist_ok=True)
            return [f for f in os.listdir(PRESET_DIR)
                    if f.lower().endswith((".rw", ".txt"))]
        except OSError:
            return []

    def refresh(self):
        self.lb.delete(0, tk.END)
        for f in sorted(self._files()):
            self.lb.insert(tk.END, f)

    def open_folder(self):
        os.startfile(PRESET_DIR)

    def new_file(self):
        name = simpledialog.askstring("新建预设", "文件名（不用写扩展名）：",
                                      parent=self.root)
        if not name:
            return
        if not name.endswith(".rw"):
            name += ".rw"
        p = os.path.join(PRESET_DIR, name)
        if os.path.exists(p):
            messagebox.showwarning("提示", "文件已存在", parent=self.root)
            return
        with open(p, "w", encoding="utf-8") as f:
            f.write("ver:3\\nmod:simple\\n\\npreset(\"示例\") {\\n    title:\"任务内容\"\\n}\\n")
        self.refresh()
        self._edit(p)

    def open_file(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showinfo("提示", "先选中一个文件", parent=self.root)
            return
        f = self._files()[sel[0]]
        self._edit(os.path.join(PRESET_DIR, f))

    def _edit(self, p):
        win = tk.Toplevel(self.root)
        win.title("编辑 " + os.path.basename(p))
        win.geometry("640x480")
        txt = tk.Text(win, font=("Consolas", 11), undo=True)
        txt.pack(fill="both", expand=True, padx=6, pady=6)
        with open(p, "r", encoding="utf-8") as f:
            txt.insert("1.0", f.read())
        def save():
            with open(p, "w", encoding="utf-8") as f:
                f.write(txt.get("1.0", "end"))
            messagebox.showinfo("已保存", "已保存到：\\n" + p, parent=win)
            win.destroy()
        tk.Button(win, text="保存", command=save, font=("微软雅黑", 11),
                  bg="#2ecc71", fg="white", relief=tk.FLAT).pack(side="bottom", pady=6)

if __name__ == "__main__":
    root = tk.Tk()
    Manager(root)
    root.mainloop()
