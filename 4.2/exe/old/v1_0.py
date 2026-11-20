import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading


class StudyCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title("学习陪伴助手")
        self.root.geometry("600x600")
        self.root.resizable(False, False)

        # 时间设置（分钟）
        self.study_time = 25  # 学习时间
        self.break_time = 5  # 短休息时间
        self.long_break_time = 15  # 长休息时间
        self.pomodoro_count = 0  # 完成的番茄数

        # 状态变量
        self.is_running = False
        self.is_break = False
        self.current_seconds = self.study_time * 60
        self.timer_thread = None

        # 娱乐时间限制（秒）
        self.max_fun_time = self.break_time * 60
        self.fun_used_time = 0

        # 学习数据
        self.total_study_minutes = 0
        self.today_tasks = []

        # 脑筋急转弯题库
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

        # 励志名言
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

        self.create_widgets()
        self.show_random_quote()

    def create_widgets(self):
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
        self.pomodoro_label = tk.Label(self.progress_frame, text="0", font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.pomodoro_label.grid(row=0, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="今日学习时长：", font=("微软雅黑", 12)).grid(row=1, column=0, sticky=tk.W)
        self.study_time_label = tk.Label(self.progress_frame, text="0分钟", font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.study_time_label.grid(row=1, column=1, sticky=tk.W)

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

        # 娱乐时间提醒
        self.fun_time_label = tk.Label(self.fun_frame, text="", font=("微软雅黑", 10), fg="#e74c3c")
        self.fun_time_label.pack(pady=5)

    def format_time(self, seconds):
        """将秒数格式化为 MM:SS 格式"""
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def start_timer(self):
        """开始计时器"""
        if not self.is_running:
            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)

            if not self.is_break:
                self.status_label.config(text="专注学习中...")
            else:
                self.status_label.config(text="休息时间，放松一下~")
                self.enable_fun_buttons()

            self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
            self.timer_thread.start()

    def update_timer(self):
        """更新计时器"""
        while self.is_running and self.current_seconds > 0:
            time.sleep(1)
            self.current_seconds -= 1

            # 更新界面
            self.root.after(0, lambda: self.timer_label.config(text=self.format_time(self.current_seconds)))

            # 如果是休息时间，记录娱乐使用时间
            if self.is_break:
                self.fun_used_time += 1
                remaining_fun = self.max_fun_time - self.fun_used_time
                self.root.after(0, lambda: self.fun_time_label.config(
                    text=f"剩余娱乐时间：{self.format_time(remaining_fun)}"))

                # 娱乐时间快结束时提醒
                if remaining_fun == 60:
                    self.root.after(0, lambda: messagebox.showwarning("提醒", "休息时间还有1分钟结束！"))
                elif remaining_fun == 10:
                    self.root.after(0, lambda: messagebox.showwarning("提醒", "休息时间还有10秒结束！"))

        # 时间到
        if self.current_seconds == 0:
            self.is_running = False
            self.root.after(0, self.timer_finished)

    def timer_finished(self):
        """计时器结束处理"""
        if not self.is_break:
            # 学习时间结束
            self.pomodoro_count += 1
            self.total_study_minutes += self.study_time
            self.pomodoro_label.config(text=str(self.pomodoro_count))
            self.study_time_label.config(text=f"{self.total_study_minutes}分钟")

            # 每4个番茄钟给长休息
            if self.pomodoro_count % 4 == 0:
                self.current_seconds = self.long_break_time * 60
                self.max_fun_time = self.long_break_time * 60
                messagebox.showinfo("太棒了！",
                                    f"你已经完成了{self.pomodoro_count}个番茄钟！\n奖励你一个{self.long_break_time}分钟的长休息！")
            else:
                self.current_seconds = self.break_time * 60
                self.max_fun_time = self.break_time * 60
                messagebox.showinfo("学习时间结束", f"干得漂亮！休息{self.break_time}分钟再继续吧~")

            self.is_break = True
            self.fun_used_time = 0
            self.enable_fun_buttons()
        else:
            # 休息时间结束
            self.current_seconds = self.study_time * 60
            self.is_break = False
            self.disable_fun_buttons()
            messagebox.showinfo("休息结束", "休息好了吗？让我们继续学习吧！")
            self.status_label.config(text="准备开始学习")

        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)

    def pause_timer(self):
        """暂停计时器"""
        if self.is_running:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL, text="继续")
            self.pause_btn.config(state=tk.DISABLED)
            self.status_label.config(text="已暂停")

    def reset_timer(self):
        """重置计时器"""
        self.is_running = False
        self.is_break = False
        self.current_seconds = self.study_time * 60
        self.fun_used_time = 0

        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.status_label.config(text="准备开始学习")
        self.start_btn.config(state=tk.NORMAL, text="开始学习")
        self.pause_btn.config(state=tk.DISABLED)
        self.disable_fun_buttons()
        self.fun_time_label.config(text="")

    def enable_fun_buttons(self):
        """启用娱乐按钮"""
        self.riddle_btn.config(state=tk.NORMAL)
        self.number_guess_btn.config(state=tk.NORMAL)

    def disable_fun_buttons(self):
        """禁用娱乐按钮"""
        self.riddle_btn.config(state=tk.DISABLED)
        self.number_guess_btn.config(state=tk.DISABLED)
        self.fun_time_label.config(text="")

    def show_riddle(self):
        """显示脑筋急转弯"""
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩脑筋急转弯哦！")
            return

        riddle = random.choice(self.riddles)
        answer = messagebox.askquestion("脑筋急转弯", f"{riddle['question']}\n\n点击'是'查看答案")

        if answer == 'yes':
            messagebox.showinfo("答案", f"答案是：{riddle['answer']}")

    def start_number_guess(self):
        """开始猜数字游戏"""
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩猜数字游戏哦！")
            return

        # 创建游戏窗口
        game_window = tk.Toplevel(self.root)
        game_window.title("猜数字游戏")
        game_window.geometry("300x200")
        game_window.resizable(False, False)

        # 游戏逻辑
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

        # 游戏界面
        tk.Label(game_window, text="我想了一个1-100之间的数字", font=("微软雅黑", 12)).pack(pady=10)

        guess_entry = tk.Entry(game_window, font=("微软雅黑", 12), width=10)
        guess_entry.pack(pady=5)
        guess_entry.focus()

        check_btn = tk.Button(game_window, text="猜一下", command=check_guess, font=("微软雅黑", 12))
        check_btn.pack(pady=5)

        result_label = tk.Label(game_window, text="", font=("微软雅黑", 12))
        result_label.pack(pady=10)

        # 绑定回车键
        game_window.bind('<Return>', lambda event: check_guess())

    def show_random_quote(self):
        """显示随机励志名言"""
        quote = random.choice(self.quotes)
        messagebox.showinfo("励志名言", f"✨ {quote}")


if __name__ == "__main__":
    root = tk.Tk()
    app = StudyCompanion(root)
    root.mainloop()