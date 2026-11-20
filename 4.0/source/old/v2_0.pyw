import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading
import json
import os

# 数据保存路径
DATA_FILE = "study_data.json"


class StudyCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title("学习陪伴助手")
        self.root.geometry("600x600")
        self.root.resizable(False, False)

        # 模式相关（选后锁定）
        self.mode = None  # learning/challenge/exam
        self.mode_locked = False

        # 加载保存的数据
        self.load_data()

        # 基础时间配置
        self.study_time = 25 * 60  # 学习时间（秒）
        self.break_time = 5 * 60  # 短休息（秒）
        self.long_break_time = 15 * 60  # 长休息（秒）
        self.pomodoro_count = self.data.get("pomodoro_count", 0)  # 番茄数
        self.total_study_seconds = self.data.get("total_study_seconds", 0)  # 总学习秒数

        # 挑战模式配置
        self.challenge_times = [100, 200, 300]  # 挑战时间（秒）
        self.challenge_selected = None
        self.challenge_score = self.data.get("challenge_score", 0)  # 挑战积分
        self.free_time = self.data.get("free_time", 0)  # 自由时间（秒）

        # 考试模式配置
        self.exam_times = [90 * 60, 70 * 60, 60 * 60, 45 * 60]  # 考试时间（秒）：90/70/60/45分钟
        self.exam_selected = None

        # 状态变量
        self.is_running = False
        self.is_break = False
        self.current_seconds = 0
        self.timer_thread = None
        self.max_fun_time = self.break_time
        self.fun_used_time = 0

        # 脑筋急转弯和励志名言（仅学习模式用）
        self.riddles = [
            {"question": "什么门永远关不上？", "answer": "球门"},
            {"question": "什么水永远用不完？", "answer": "泪水"},
            {"question": "什么书里毛病最多？", "answer": "医学书"},
            {"question": "什么球离你最近？", "answer": "眼球"},
            {"question": "什么路最窄？", "answer": "冤家路窄"},
            {"question": "什么东西越生气越大？", "answer": "脾气"},
            {"question": "什么东西有五个头，但人不觉得它怪？", "answer": "手和脚"},
            {"question": "什么东西越洗越脏？", "answer": "水"},
            {"question": "什么动物你打死了它，却流了你的血？", "answer": "蚊子"},
            {"question": "什么时候有人敲门，你绝不会说请进？", "answer": "在厕所里的时候"}
        ]
        self.quotes = [
            "书山有路勤为径，学海无涯苦作舟。",
            "宝剑锋从磨砺出，梅花香自苦寒来。",
            "不积跬步，无以至千里；不积小流，无以成江海。",
            "业精于勤，荒于嬉；行成于思，毁于随。",
            "天才是百分之一的灵感加百分之九十九的汗水。",
            "黑发不知勤学早，白首方悔读书迟。",
            "学而不思则罔，思而不学则殆。",
            "知之者不如好之者，好之者不如乐之者。"
        ]

        # 先显示模式选择窗口
        self.show_mode_selection()

    def load_data(self):
        """加载JSON保存的数据"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except:
                self.data = self.get_default_data()
        else:
            self.data = self.get_default_data()

    def get_default_data(self):
        """默认数据"""
        return {
            "pomodoro_count": 0,
            "total_study_seconds": 0,
            "challenge_score": 0,
            "free_time": 0
        }

    def save_data(self):
        """保存数据到JSON文件"""
        self.data.update({
            "pomodoro_count": self.pomodoro_count,
            "total_study_seconds": self.total_study_seconds,
            "challenge_score": self.challenge_score,
            "free_time": self.free_time
        })
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("错误", f"保存数据失败：{str(e)}")

    def show_mode_selection(self):
        """显示模式选择窗口"""
        mode_win = tk.Toplevel(self.root)
        mode_win.title("选择模式")
        mode_win.geometry("400x300")
        mode_win.resizable(False, False)
        mode_win.grab_set()  # 锁定焦点

        # 居中显示
        mode_win.update_idletasks()
        x = (mode_win.winfo_screenwidth() // 2) - (400 // 2)
        y = (mode_win.winfo_screenheight() // 2) - (300 // 2)
        mode_win.geometry(f"400x300+{x}+{y}")

        tk.Label(mode_win, text="📌 选择使用模式", font=("微软雅黑", 18, "bold")).pack(pady=20)

        # 模式选择变量
        self.mode_var = tk.StringVar(value="")

        # 单选按钮
        tk.Radiobutton(mode_win, text="学习模式（番茄钟）", variable=self.mode_var,
                       value="learning", font=("微软雅黑", 12)).pack(pady=8)
        tk.Radiobutton(mode_win, text="挑战模式（赢积分兑自由时间）", variable=self.mode_var,
                       value="challenge", font=("微软雅黑", 12)).pack(pady=8)
        tk.Radiobutton(mode_win, text="考试模式（极简倒计时）", variable=self.mode_var,
                       value="exam", font=("微软雅黑", 12)).pack(pady=8)

        # 确认按钮
        def confirm_mode():
            selected = self.mode_var.get()
            if not selected:
                messagebox.showwarning("提示", "请选择一个模式！")
                return

            self.mode = selected
            self.mode_locked = True
            mode_win.destroy()
            self.init_mode_ui()  # 初始化对应模式界面

        tk.Button(mode_win, text="确认选择", command=confirm_mode,
                  font=("微软雅黑", 12), bg="#2ecc71", fg="white", width=15).pack(pady=20)

    def init_mode_ui(self):
        """根据选择的模式初始化界面"""
        if self.mode == "learning":
            self.init_learning_mode()
        elif self.mode == "challenge":
            self.init_challenge_mode()
        elif self.mode == "exam":
            self.init_exam_mode()

    def init_learning_mode(self):
        """初始化学习模式（原功能）"""
        self.root.title("学习陪伴助手 - 学习模式")
        self.current_seconds = self.study_time
        self.create_learning_widgets()
        self.show_random_quote()

    def init_challenge_mode(self):
        """初始化挑战模式"""
        self.root.title("学习陪伴助手 - 挑战模式")

        # 挑战时间选择
        challenge_win = tk.Toplevel(self.root)
        challenge_win.title("选择挑战时间")
        challenge_win.geometry("300x200")
        challenge_win.resizable(False, False)
        challenge_win.grab_set()

        tk.Label(challenge_win, text="选择挑战时长（秒）", font=("微软雅黑", 14)).pack(pady=15)

        def select_time(seconds):
            self.challenge_selected = seconds
            self.current_seconds = seconds
            challenge_win.destroy()
            self.create_challenge_widgets()

        # 时间选择按钮
        frame = tk.Frame(challenge_win)
        frame.pack(pady=10)
        for t in self.challenge_times:
            tk.Button(frame, text=f"{t}秒", command=lambda x=t: select_time(x),
                      font=("微软雅黑", 12), width=8).grid(row=0, column=self.challenge_times.index(t), padx=5)

    def init_exam_mode(self):
        """初始化考试模式"""
        self.root.title("学习陪伴助手 - 考试模式")

        # 考试时间选择
        exam_win = tk.Toplevel(self.root)
        exam_win.title("选择考试时间")
        exam_win.geometry("350x200")
        exam_win.resizable(False, False)
        exam_win.grab_set()

        tk.Label(exam_win, text="选择考试时长（分钟）", font=("微软雅黑", 14)).pack(pady=15)

        def select_time(seconds):
            self.exam_selected = seconds
            self.current_seconds = seconds
            exam_win.destroy()
            self.create_exam_widgets()

        # 时间选择按钮（转换为分钟显示）
        frame = tk.Frame(exam_win)
        frame.pack(pady=10)
        for t in self.exam_times:
            mins = t // 60
            tk.Button(frame, text=f"{mins}分钟", command=lambda x=t: select_time(x),
                      font=("微软雅黑", 12), width=8).grid(row=0, column=self.exam_times.index(t), padx=5)

    def create_learning_widgets(self):
        """创建学习模式界面（原界面）"""
        # 顶部标题
        title_label = tk.Label(self.root, text="📚 学习陪伴助手", font=("微软雅黑", 20, "bold"))
        title_label.pack(pady=10)

        # 计时器显示
        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)

        self.timer_label = tk.Label(self.timer_frame, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"), fg="#2c3e50")
        self.timer_label.pack(pady=20)

        self.status_label = tk.Label(self.timer_frame, text="准备开始学习",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)

        # 控制按钮
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        self.start_btn = tk.Button(self.button_frame, text="开始学习", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)

        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)

        self.reset_btn = tk.Button(self.button_frame, text="重置", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)

        # 进度显示
        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(self.progress_frame, text="今日完成番茄数：", font=("微软雅黑", 12)).grid(row=0, column=0, sticky=tk.W)
        self.pomodoro_label = tk.Label(self.progress_frame, text=str(self.pomodoro_count),
                                       font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.pomodoro_label.grid(row=0, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="今日学习时长：", font=("微软雅黑", 12)).grid(row=1, column=0, sticky=tk.W)
        self.study_time_label = tk.Label(self.progress_frame, text=f"{self.total_study_seconds // 60}分钟",
                                         font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.study_time_label.grid(row=1, column=1, sticky=tk.W)

        # 自由时间显示（挑战模式积分兑换）
        tk.Label(self.progress_frame, text="可用自由时间：", font=("微软雅黑", 12)).grid(row=2, column=0, sticky=tk.W)
        self.free_time_label = tk.Label(self.progress_frame, text=f"{self.free_time // 60}分钟",
                                        font=("微软雅黑", 12, "bold"), fg="#3498db")
        self.free_time_label.grid(row=2, column=1, sticky=tk.W)

        # 娱乐功能区（默认禁用）
        self.fun_frame = tk.LabelFrame(self.root, text="休息娱乐区（仅休息时间可用）", font=("微软雅黑", 12))
        self.fun_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        self.riddle_btn = tk.Button(self.fun_frame, text="猜个脑筋急转弯", command=self.show_riddle,
                                    font=("微软雅黑", 11), state=tk.DISABLED)
        self.riddle_btn.pack(pady=5, fill=tk.X, padx=20)

        self.number_guess_btn = tk.Button(self.fun_frame, text="玩猜数字游戏", command=self.start_number_guess,
                                          font=("微软雅黑", 11), state=tk.DISABLED)
        self.number_guess_btn.pack(pady=5, fill=tk.X, padx=20)

        self.quote_btn = tk.Button(self.fun_frame, text="看句励志名言", command=self.show_random_quote,
                                   font=("微软雅黑", 11))
        self.quote_btn.pack(pady=5, fill=tk.X, padx=20)

        # 积分兑换按钮（如果有积分）
        self.exchange_btn = tk.Button(self.fun_frame, text="积分兑换自由时间（1积分=1分钟）",
                                      command=self.exchange_score, font=("微软雅黑", 11))
        self.exchange_btn.pack(pady=5, fill=tk.X, padx=20)
        self.update_exchange_btn_state()

        # 娱乐时间提醒
        self.fun_time_label = tk.Label(self.fun_frame, text="", font=("微软雅黑", 10), fg="#e74c3c")
        self.fun_time_label.pack(pady=5)

    def create_challenge_widgets(self):
        """创建挑战模式界面"""
        # 顶部标题
        tk.Label(self.root, text="🔥 挑战模式", font=("微软雅黑", 20, "bold")).pack(pady=10)

        # 积分显示
        self.score_label = tk.Label(self.root, text=f"当前积分：{self.challenge_score}",
                                    font=("微软雅黑", 14), fg="#e67e22")
        self.score_label.pack(pady=5)

        # 计时器显示
        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)

        self.timer_label = tk.Label(self.timer_frame, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"), fg="#2c3e50")
        self.timer_label.pack(pady=20)

        self.status_label = tk.Label(self.timer_frame, text=f"挑战时长：{self.challenge_selected}秒",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)

        # 控制按钮
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        self.start_btn = tk.Button(self.button_frame, text="开始挑战", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)

        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)

        self.reset_btn = tk.Button(self.button_frame, text="重置挑战", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)

        # 挑战说明
        tk.Label(self.root,
                 text="✅ 挑战规则：完成计时不暂停/重置即可获得对应积分\n100秒=1积分 | 200秒=2积分 | 300秒=3积分",
                 font=("微软雅黑", 10), fg="#7f8c8d").pack(pady=10)

    def create_exam_widgets(self):
        """创建考试模式界面（极简）"""
        self.root.geometry("800x400")  # 调整窗口大小更适合考试

        # 清空所有控件
        for widget in self.root.winfo_children():
            widget.destroy()

        # 考试提示大字
        exam_label = tk.Label(self.root, text="认真考试，禁止作弊",
                              font=("微软雅黑", 36, "bold"), fg="#e74c3c")
        exam_label.pack(expand=True, pady=20)

        # 倒计时（超大字体）
        self.timer_label = tk.Label(self.root, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 72, "bold"), fg="#2c3e50")
        self.timer_label.pack(expand=True)

        # 仅保留开始按钮（考试开始后隐藏）
        self.start_btn = tk.Button(self.root, text="开始考试", command=self.start_timer,
                                   font=("微软雅黑", 14), width=15, bg="#2ecc71", fg="white")
        self.start_btn.pack(pady=20)

    def format_time(self, seconds):
        """将秒数格式化为 MM:SS 或 HH:MM:SS（超过1小时）"""
        if seconds >= 3600:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        else:
            mins, secs = divmod(seconds, 60)
            return f"{mins:02d}:{secs:02d}"

    def start_timer(self):
        """开始计时器（通用）"""
        if not self.is_running and self.mode_locked:
            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)

            # 考试模式隐藏开始按钮
            if self.mode == "exam":
                self.start_btn.pack_forget()

            # 挑战/学习模式启用暂停按钮
            if self.mode in ["learning", "challenge"]:
                self.pause_btn.config(state=tk.NORMAL)

            # 设置状态文本
            if self.mode == "learning":
                self.status_label.config(text="专注学习中..." if not self.is_break else "休息时间，放松一下~")
                if self.is_break:
                    self.enable_fun_buttons()
            elif self.mode == "challenge":
                self.status_label.config(text="挑战进行中...")
            elif self.mode == "exam":
                pass  # 考试模式无状态文本

            # 启动计时线程
            self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
            self.timer_thread.start()

    def update_timer(self):
        """更新计时器（通用）"""
        while self.is_running and self.current_seconds > 0:
            time.sleep(1)
            self.current_seconds -= 1

            # 更新倒计时显示
            self.root.after(0, lambda: self.timer_label.config(text=self.format_time(self.current_seconds)))

            # 学习模式：休息时间统计娱乐用时
            if self.mode == "learning" and self.is_break:
                self.fun_used_time += 1
                remaining_fun = self.max_fun_time + self.free_time - self.fun_used_time
                if remaining_fun < 0:
                    remaining_fun = 0
                self.root.after(0, lambda: self.fun_time_label.config(
                    text=f"剩余娱乐时间：{self.format_time(remaining_fun)}"))

                # 娱乐时间提醒
                if remaining_fun == 60:
                    self.root.after(0, lambda: messagebox.showwarning("提醒", "休息时间还有1分钟结束！"))
                elif remaining_fun == 10:
                    self.root.after(0, lambda: messagebox.showwarning("提醒", "休息时间还有10秒结束！"))

        # 计时结束处理
        if self.current_seconds == 0:
            self.is_running = False
            self.root.after(0, self.timer_finished)

    def timer_finished(self):
        """计时结束处理（分模式）"""
        if self.mode == "learning":
            self.handle_learning_finish()
        elif self.mode == "challenge":
            self.handle_challenge_finish()
        elif self.mode == "exam":
            self.handle_exam_finish()

    def handle_learning_finish(self):
        """学习模式计时结束"""
        if not self.is_break:
            # 学习时间结束
            self.pomodoro_count += 1
            self.total_study_seconds += self.study_time
            self.pomodoro_label.config(text=str(self.pomodoro_count))
            self.study_time_label.config(text=f"{self.total_study_seconds // 60}分钟")
            self.save_data()  # 保存数据

            # 长/短休息判断
            if self.pomodoro_count % 4 == 0:
                self.current_seconds = self.long_break_time
                self.max_fun_time = self.long_break_time
                messagebox.showinfo("太棒了！",
                                    f"你已经完成了{self.pomodoro_count}个番茄钟！\n奖励你一个{self.long_break_time // 60}分钟的长休息！")
            else:
                self.current_seconds = self.break_time
                self.max_fun_time = self.break_time
                messagebox.showinfo("学习时间结束", f"干得漂亮！休息{self.break_time // 60}分钟再继续吧~")

            self.is_break = True
            self.fun_used_time = 0
            self.enable_fun_buttons()
        else:
            # 休息时间结束
            self.current_seconds = self.study_time
            self.is_break = False
            self.disable_fun_buttons()
            messagebox.showinfo("休息结束", "休息好了吗？让我们继续学习吧！")
            self.status_label.config(text="准备开始学习")

        # 重置按钮状态
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL, text="开始学习")
        self.pause_btn.config(state=tk.DISABLED)

    def handle_challenge_finish(self):
        """挑战模式计时结束"""
        # 计算获得积分
        score_gain = self.challenge_selected // 100
        self.challenge_score += score_gain
        self.score_label.config(text=f"当前积分：{self.challenge_score}")
        self.save_data()  # 保存数据

        messagebox.showinfo("挑战成功！",
                            f"恭喜你完成{self.challenge_selected}秒挑战！\n获得{score_gain}积分，当前总积分：{self.challenge_score}")

        # 重置挑战
        self.current_seconds = self.challenge_selected
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"挑战时长：{self.challenge_selected}秒")

    def handle_exam_finish(self):
        """考试模式计时结束"""
        messagebox.showinfo("考试结束", "时间到！请停止作答，准备交卷~")
        # 考试结束后重置（可重新开始）
        self.current_seconds = self.exam_selected
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        self.start_btn.pack(pady=20)

    def pause_timer(self):
        """暂停计时器（学习/挑战模式）"""
        if self.is_running and self.mode in ["learning", "challenge"]:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL, text="继续")
            self.pause_btn.config(state=tk.DISABLED)

            if self.mode == "learning":
                self.status_label.config(text="已暂停")
            elif self.mode == "challenge":
                self.status_label.config(text="挑战已暂停")

    def reset_timer(self):
        """重置计时器（学习/挑战模式）"""
        self.is_running = False
        self.is_break = False
        self.fun_used_time = 0

        if self.mode == "learning":
            self.current_seconds = self.study_time
            self.status_label.config(text="准备开始学习")
            self.start_btn.config(state=tk.NORMAL, text="开始学习")
            self.disable_fun_buttons()
            self.fun_time_label.config(text="")
        elif self.mode == "challenge":
            self.current_seconds = self.challenge_selected
            self.status_label.config(text=f"挑战时长：{self.challenge_selected}秒")
            self.start_btn.config(state=tk.NORMAL)

        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.pause_btn.config(state=tk.DISABLED)

    def enable_fun_buttons(self):
        """启用娱乐按钮（学习模式）"""
        self.riddle_btn.config(state=tk.NORMAL)
        self.number_guess_btn.config(state=tk.NORMAL)

    def disable_fun_buttons(self):
        """禁用娱乐按钮（学习模式）"""
        self.riddle_btn.config(state=tk.DISABLED)
        self.number_guess_btn.config(state=tk.DISABLED)
        self.fun_time_label.config(text="")

    def show_riddle(self):
        """显示脑筋急转弯（学习模式）"""
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩脑筋急转弯哦！")
            return

        riddle = random.choice(self.riddles)
        answer = messagebox.askquestion("脑筋急转弯", f"{riddle['question']}\n\n点击'是'查看答案")
        if answer == 'yes':
            messagebox.showinfo("答案", f"答案是：{riddle['answer']}")

    def start_number_guess(self):
        """猜数字游戏（学习模式）"""
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩猜数字游戏哦！")
            return

        game_window = tk.Toplevel(self.root)
        game_window.title("猜数字游戏")
        game_window.geometry("300x200")
        game_window.resizable(False, False)

        secret_number = random.randint(1, 100)
        attempts = 0

        def check_guess():
            nonlocal attempts
            try:
                guess = int(guess_entry.get())
                attempts += 1

                if guess < secret_number:
                    result_label.config(text="太小了，再试试！", fg="#e74c3c")
                elif guess > secret_number:
                    result_label.config(text="太大了，再试试！", fg="#e74c3c")
                else:
                    result_label.config(text=f"恭喜你猜对了！用了{attempts}次", fg="#27ae60")
                    guess_entry.config(state=tk.DISABLED)
                    check_btn.config(state=tk.DISABLED)

                guess_entry.delete(0, tk.END)
            except ValueError:
                result_label.config(text="请输入一个有效的数字！", fg="#e74c3c")

        tk.Label(game_window, text="我想了一个1-100之间的数字", font=("微软雅黑", 12)).pack(pady=10)
        guess_entry = tk.Entry(game_window, font=("微软雅黑", 12), width=10)
        guess_entry.pack(pady=5)
        guess_entry.focus()

        check_btn = tk.Button(game_window, text="猜一下", command=check_guess, font=("微软雅黑", 12))
        check_btn.pack(pady=5)

        result_label = tk.Label(game_window, text="", font=("微软雅黑", 12))
        result_label.pack(pady=10)

        game_window.bind('<Return>', lambda event: check_guess())

    def show_random_quote(self):
        """显示励志名言（学习模式）"""
        quote = random.choice(self.quotes)
        messagebox.showinfo("励志名言", f"✨ {quote}")

    def exchange_score(self):
        """积分兑换自由时间（学习模式）"""
        if self.challenge_score <= 0:
            messagebox.showwarning("提示", "当前没有可兑换的积分！")
            return

        def confirm_exchange():
            try:
                exchange_num = int(entry.get())
                if exchange_num <= 0 or exchange_num > self.challenge_score:
                    messagebox.showwarning("提示", f"请输入1-{self.challenge_score}之间的数字！")
                    return

                # 兑换逻辑
                self.challenge_score -= exchange_num
                self.free_time += exchange_num * 60  # 1积分=1分钟
                self.score_label.config(text=f"当前积分：{self.challenge_score}")
                self.free_time_label.config(text=f"{self.free_time // 60}分钟")
                self.save_data()
                messagebox.showinfo("兑换成功", f"成功兑换{exchange_num}分钟自由时间！")
                win.destroy()
            except ValueError:
                messagebox.showwarning("提示", "请输入有效的数字！")

        win = tk.Toplevel(self.root)
        win.title("积分兑换")
        win.geometry("300x150")
        win.resizable(False, False)

        tk.Label(win, text=f"当前可兑换积分：{self.challenge_score}\n1积分=1分钟自由时间",
                 font=("微软雅黑", 12)).pack(pady=10)

        entry = tk.Entry(win, font=("微软雅黑", 12), width=10)
        entry.pack(pady=5)
        entry.insert(0, "1")

        tk.Button(win, text="确认兑换", command=confirm_exchange,
                  font=("微软雅黑", 12), bg="#3498db", fg="white").pack(pady=5)

    def update_exchange_btn_state(self):
        """更新兑换按钮状态"""
        if self.challenge_score <= 0:
            self.exchange_btn.config(state=tk.DISABLED)
        else:
            self.exchange_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = StudyCompanion(root)
    root.mainloop()