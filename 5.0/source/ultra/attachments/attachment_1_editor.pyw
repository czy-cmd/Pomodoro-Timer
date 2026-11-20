# -*- coding: utf-8 -*-
\"\"\"自定义附件修改器：打开/新建/修改 rw、fqm、alfqm 文件。带常用字符快速插入。\"\"\"
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os

KEYWORDS = ["preset", "title", "priority", "subject", "category", "due",
            "note", "ver", "mod", "ext", "strict", "study_time", "break_time",
            "color_primary", "window_width", "window_height"]

class IDE:
    def __init__(self, root):
        self.root = root
        self.root.title("自定义附件修改器")
        self.root.geometry("720x560")
        self.path = None
        self._build_ui()

    def _build_ui(self):
        bar = tk.Frame(self.root)
        bar.pack(fill="x", padx=6, pady=4)
        for txt, cmd in [("打开", self.open_file), ("新建", self.new_file),
                         ("保存", self.save_file), ("另存为", self.save_as)]:
            tk.Button(bar, text=txt, command=cmd, font=("微软雅黑", 10),
                      relief=tk.FLAT, bg="#ecf0f1", cursor="hand2",
                      width=6).pack(side="left", padx=3)
        self.path_lbl = tk.Label(bar, text="（未打开文件）", font=("微软雅黑", 9),
                                 fg="#95a5a6")
        self.path_lbl.pack(side="left", padx=8)

        kw = tk.Frame(self.root)
        kw.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(kw, text="常用字符/关键字（点击插入）：", font=("微软雅黑", 9),
                 fg="#95a5a6").pack(side="left")
        for ch in ["{", "}", ":", "\"", "=", "preset()", "class ", "|"]:
            tk.Button(kw, text=ch, command=lambda c=ch: self.insert(c),
                      font=("Consolas", 9), relief=tk.FLAT, bg="#f0f3f5",
                      cursor="hand2").pack(side="left", padx=2)

        self.txt = tk.Text(self.root, font=("Consolas", 11), undo=True,
                           wrap=tk.NONE, bg="#fafbfc")
        self.txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        sb = tk.Scrollbar(self.txt)
        sb.pack(side="right", fill="y")
        self.txt.config(yscrollcommand=sb.set)
        sb.config(command=self.txt.yview)
        # 代码提示：输入关键字后弹补全
        self._tip = None

    def insert(self, s):
        self.txt.insert(tk.INSERT, s)
        self.txt.focus_set()

    def open_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("附件文件", "*.rw *.fqm *.alfqm *.txt"), ("所有文件", "*.*")])
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                self.txt.delete("1.0", "end")
                self.txt.insert("1.0", f.read())
            self.path = p
            self.path_lbl.config(text=os.path.basename(p))
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def new_file(self):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "ver:3\\nmod:simple\\n\\npreset(\"示例\") {\\n    title:\"任务内容\"\\n}\\n")
        self.path = None
        self.path_lbl.config(text="（新建，尚未保存）")

    def save_file(self):
        if not self.path:
            self.save_as()
            return
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.txt.get("1.0", "end"))
            messagebox.showinfo("已保存", "已保存到：\\n" + self.path)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def save_as(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".rw",
            filetypes=[("rw 预设", "*.rw"), ("fqm 主题", "*.fqm"),
                       ("almfq 主题", "*.almfq"), ("文本", "*.txt")])
        if not p:
            return
        self.path = p
        self.path_lbl.config(text=os.path.basename(p))
        self.save_file()

if __name__ == "__main__":
    root = tk.Tk()
    IDE(root)
    root.mainloop()
