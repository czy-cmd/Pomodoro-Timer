import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import random
import time
import threading
import json
import os
import csv
import datetime
import re
import sys
import shutil
import subprocess
import traceback
import webbrowser
import gc

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ===== 数据文件（Orbit3 统一数据仓，见下方 Orbit3Store） =====
DATA_FILE = None  # 已废弃：一切读写走 STORE
V4_DATA_FILE = "study_dataV4.json"
V33_DATA_FILE = "study_dataV3.3.json"
V32_DATA_FILE = "study_dataV3.2.json"
V31_DATA_FILE = "study_dataV3.1.json"
V3_DATA_FILE = "study_dataV3.json"
OLD_DATA_FILE = "study_dataV2.json"
OLDER_DATA_FILE = "study_data.json"

APP_TITLE = "番茄钟5.0"     # 大标题
APP_BETA = "Orbit 3"         # 小标题
APP_WINDOW_TITLE = "番茄钟5.0"  # 窗口标题条上的字，独立于 APP_TITLE
ORBIT3_EDITION = "pro"  # 构建期写入：normal / pro / ultra
IS_PRO = ORBIT3_EDITION in ("pro", "ultra")
IS_ULTRA = ORBIT3_EDITION == "ultra"

# mod 可改的 key 白名单
MOD_ALLOWED_KEYS = {
    "title", "window_title", "beta", "author", "desc", "motto",
    "mod_name", "mod_version",
    "study_time", "break_time", "long_break_time", "simple_pomodoro_time",
    "color_primary", "color_timer", "color_bg", "color_accent",
    "challenge_times", "default_mode", "window_width", "window_height",
    # ---- Orbit3 新增 ----
    "task_manager_btn_text", "small_tools_btn_text",
    "tag_normal_text", "tag_effort_text", "tag_effort_color",
    "task_default_category", "task_default_tag",
}


# ==================================================================
# mod 解析辅助函数
# ==================================================================
def _parse_fqm_value(value):
    value = value.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_fqm(path):
    """解析 .fqm 文件为 dict"""
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key not in MOD_ALLOWED_KEYS:
                continue
            if key == "challenge_times":
                try:
                    parts = [x.strip() for x in value.strip('"').split(",")]
                    result[key] = [int(x) for x in parts if x]
                except Exception:
                    continue
            else:
                result[key] = _parse_fqm_value(value)
    return result


def parse_almfq(path):
    """解析 .almfq 文件"""
    class_defs = []
    let_order = None
    let_no = set()
    let_no_all = False
    kill_rules = []

    with open(path, "r", encoding="utf-8") as f:
        raw_lines = [ln.rstrip("\n") for ln in f]

    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # ---- let ----
        if line.startswith("let "):
            content = line[4:].strip()
            if content.startswith("no "):
                mods_str = content[3:].strip()
                for m in mods_str.split(","):
                    m = m.strip().lower()
                    if m == "all":
                        let_no_all = True
                    elif m:
                        let_no.add(m)
            else:
                toks_c = [x.strip() for x in content.split(",") if x.strip()]
                toks_s = content.split()
                all_toks = toks_c if len(toks_c) > 1 else toks_s
                if any(t.lower().endswith((".fqm", ".py", ".pyw")) for t in all_toks):
                    let_order = ("files", [t.lower() for t in all_toks])
                else:
                    if "," in content:
                        letters = [x.strip().lower() for x in content.split(",") if x.strip()]
                    else:
                        letters = [x.strip().lower() for x in content.split() if x.strip()]
                    let_order = ("letters", letters)

        # ---- class ----
        elif line.startswith("class"):
            content = line[5:].strip()
            end_amp = False
            if content.endswith(" &"):
                end_amp = True
                content = content[:-2].strip()

            if content.startswith("&"):
                if class_defs:
                    class_defs[-1]["disabled"] = True
                rest = content[1:].strip()
                if rest.startswith("class"):
                    rest2 = rest[5:].strip()
                    parts = rest2.split(None, 1)
                    if len(parts) == 2:
                        cat = parts[0].strip()
                        strats = [s.strip() for s in parts[1].split(",") if s.strip()]
                        class_defs.append({
                            "category": cat, "strategies": strats, "disabled": False,
                        })
            else:
                parts = content.split(None, 1)
                if len(parts) == 2:
                    cat = parts[0].strip()
                    strats = [s.strip() for s in parts[1].split(",") if s.strip()]
                    class_defs.append({
                        "category": cat, "strategies": strats, "disabled": end_amp,
                    })

        # ---- kill ----
        elif line.startswith("kill "):
            content = line[5:].strip()
            except_set = set()
            except_all = False
            if "@" in content:
                main_part, _, except_part = content.partition("@")
                for e in except_part.split(","):
                    e = e.strip().lower()
                    if e == "all":
                        except_all = True
                    elif e:
                        except_set.add(e)
            else:
                main_part = content

            if "-" in main_part:
                scope_part, _, key = main_part.rpartition("-")
                scope_part = scope_part.strip()
                key = key.strip()
                scope_set = set()
                scope_all = False
                for s in scope_part.split(","):
                    s = s.strip().lower()
                    if s == "all":
                        scope_all = True
                    elif s:
                        scope_set.add(s)
                kill_rules.append({
                    "scope_set": scope_set, "scope_all": scope_all,
                    "key": key,
                    "except_set": except_set, "except_all": except_all,
                })

    return {
        "class_defs": class_defs,
        "let_order": let_order,
        "let_no": let_no,
        "let_no_all": let_no_all,
        "kill_rules": kill_rules,
    }




# ==================================================================
# Orbit3 数据仓：唯一可写文件 Orbit3_data.json
# ==================================================================
ORBIT3_VERSION = "5.0"
if getattr(sys, "frozen", False):
    ORBIT3_DIR = os.path.dirname(sys.executable)      # 打包后：exe 所在目录
else:
    ORBIT3_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
ORBIT3_DATA_FILE = os.path.join(ORBIT3_DIR, "Orbit3_data.json")
ORBIT3_LOG_DIR = os.path.join(ORBIT3_DIR, "log")

# 源 JSON（只读，永不写入）。
# 应用户要求：不读任何番茄钟学习存档（真实存档在 4.2\番茄钟4.2_exe版\study_dataV4.2.json，一律不碰）。
# 只合并任务管理器 / 鼠标检测器两个程序数据（夸夸机已移除）。
SRC_JSONS = {
    "tasks":  r"C:\Users\54215\Desktop\czy文件\p\任务管理器\3.0\tasks_v3.json",
    "mouse":  r"C:\Users\54215\Desktop\czy文件\p\鼠标检测器\data.json",
}
# 源目录其它只读小文件（合并时一并搬走内容，不写回）
SRC_MOUSE_SETTINGS = r"C:\Users\54215\Desktop\czy文件\p\鼠标检测器\settings.json"

RECENT_ERRORS = []


def _read_json_safe(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_txt_safe(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


class Orbit3Store:
    """Orbit3_data.json 统一数据仓。分段：orbit2 / tasks / mouse / kuakua / orbit3"""

    def __init__(self, path):
        self.path = path
        self.root = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            d = _read_json_safe(self.path)
            if isinstance(d, dict):
                self.root = d
            else:
                self.root = {}
        else:
            self.root = {}

    def seg(self, name):
        s = self.root.get(name)
        if not isinstance(s, dict):
            s = {}
            self.root[name] = s
        return self.root[name]

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.root, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def merge_from_sources(self):
        """只读源 JSON + 附属小文件，把缺失内容补进 Orbit3_data.json（学习存档除外）。
        只补缺的，绝不覆盖已有数据，绝不写源文件。返回合并说明列表。"""
        merged = []

        if not self.seg("tasks") and os.path.exists(SRC_JSONS["tasks"]):
            d = _read_json_safe(SRC_JSONS["tasks"])
            if isinstance(d, dict):
                self.root["tasks"] = d
                merged.append("任务管理器（tasks_v3.json）")

        ms = self.seg("mouse")
        if "total_focus" not in ms and os.path.exists(SRC_JSONS["mouse"]):
            d = _read_json_safe(SRC_JSONS["mouse"])
            if isinstance(d, dict):
                for k in ("total_focus", "total_distracted", "daily"):
                    if k in d:
                        ms[k] = d[k]
                merged.append("鼠标检测器（data.json）")
        if "settings" not in ms and os.path.exists(SRC_MOUSE_SETTINGS):
            d = _read_json_safe(SRC_MOUSE_SETTINGS)
            if isinstance(d, dict):
                ms["settings"] = d

        self.seg("orbit3")  # 确保存在
        if merged:
            self.save()
        return merged


STORE = Orbit3Store(ORBIT3_DATA_FILE)


def orbit3_write_crash(exc_type, exc, tb):
    """类 Minecraft 格式崩溃日志：写 log/，并按配置复制到传输路径（默认桌面）"""
    try:
        cfg = STORE.seg("orbit3")
        if not cfg.get("crash_log_enabled", True):
            return
        os.makedirs(ORBIT3_LOG_DIR, exist_ok=True)
        now = datetime.datetime.now()
        fname = "crash_" + now.strftime("%Y-%m-%d_%H-%M-%S") + ".log"
        body = traceback.format_exception(exc_type, exc, tb)
        text = (
            "---- Orbit3 崩溃报告 ----\n"
            "（别怕，这玩意和 Minecraft 崩溃日志一个格式）\n\n"
            "Time: " + now.strftime("%Y-%m-%d %H:%M:%S") + "\n"
            "Version: Orbit3 " + ORBIT3_VERSION + "\n"
            "Python: " + sys.version.split()[0] + "\n"
            "Description: " + exc_type.__name__ + ": " + str(exc) + "\n\n"
            "-- 调用栈 --\n" + "".join(body) + "\n"
            "-- 系统信息 --\n"
            "OS: " + sys.platform + "\n"
            "Data file: " + ORBIT3_DATA_FILE + "\n"
        )
        RECENT_ERRORS.append(now.strftime("%H:%M:%S") + " " + exc_type.__name__
                             + ": " + str(exc)[:120])
        del RECENT_ERRORS[:-20]
        crash_path = os.path.join(ORBIT3_LOG_DIR, fname)
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(text)
        dest_dir = cfg.get("crash_log_dir") or os.path.join(os.path.expanduser("~"), "Desktop")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            with open(os.path.join(dest_dir, fname), "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
    except Exception:
        pass


def orbit3_install_crash_hooks(root):
    def _exc(exc_type, exc, tb):
        orbit3_write_crash(exc_type, exc, tb)
        sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = _exc

    def _tk_exc(exc, val, tb):
        orbit3_write_crash(exc, val, tb)
        try:
            messagebox.showerror("出错了", f"{exc.__name__}: {val}\n\n崩溃日志已写入 log 文件夹。")
        except Exception:
            pass
    root.report_callback_exception = _tk_exc


# ==================================================================
# 主程序
# ==================================================================
class StudyCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_WINDOW_TITLE)
        self.root.geometry("640x820")
        self.root.resizable(False, False)

        self.data_file = DATA_FILE
        self.mode = None
        self.mode_locked = False

        self.load_data()

        # ---------- mod 加载 ----------
        self.almfq_path = self.data.get("almfq_path", "")
        self.mod_values = {}
        self.mod_files_loaded = []
        self.scan_and_load_mods()
        self.apply_mod_values()
        # mod 生效后，重新应用一次窗口标题
        try:
            self.root.title(APP_WINDOW_TITLE)
        except Exception:
            pass

        # ---------- 从 mod 或默认值取参数 ----------
        self.study_time = self.get_mod_value("study_time", 25) * 60
        self.break_time = self.get_mod_value("break_time", 5) * 60
        self.long_break_time = self.get_mod_value("long_break_time", 15) * 60
        self.pomodoro_simple_time = self.get_mod_value("simple_pomodoro_time", 25) * 60

        self.color_primary = self.get_mod_value("color_primary", "#2ecc71")
        self.color_timer = self.get_mod_value("color_timer", "#2c3e50")
        self.color_bg = self.get_mod_value("color_bg", "#ffffff")
        self.color_accent = self.get_mod_value("color_accent", "#e67e22")

        self.challenge_times = self.get_mod_value(
            "challenge_times", [1, 10, 100, 200, 300, 500, 1000, 10000, 100000, 999999])
        self.default_mode = self.get_mod_value("default_mode", "main")
        self.win_w = self.get_mod_value("window_width", 640)
        self.win_h = self.get_mod_value("window_height", 820)

        self.root.geometry(f"{self.win_w}x{self.win_h}")

        # ---------- 数据字段 ----------
        self.pomodoro_count = self.data.get("pomodoro_count", 0)
        self.total_study_seconds = self.data.get("total_study_seconds", 0)
        self.challenge_selected = None
        self.challenge_score = self.data.get("challenge_score", 0)
        self.free_time = self.data.get("free_time", 0)
        self.custom_time = 0
        self.exam_time = 0
        self.pomodoro_simple_count = self.data.get("simple_pomodoro_count", 0)
        self.motto = self.data.get("motto", "")

        self.simple_mode_seconds = self.data.get("simple_mode_seconds", 0)
        self.simple_mode_count = self.data.get("simple_mode_count", 0)
        self.exam_mode_seconds = self.data.get("exam_mode_seconds", 0)
        self.exam_mode_count = self.data.get("exam_mode_count", 0)
        self.challenge_total_seconds = self.data.get("challenge_total_seconds", 0)
        self.challenge_count = self.data.get("challenge_count", 0)
        self.simple_pomodoro_seconds = self.data.get("simple_pomodoro_seconds", 0)
        self.simple_pomodoro_total_count = self.data.get("simple_pomodoro_total_count", 0)
        self.count_up_seconds = self.data.get("count_up_seconds", 0)
        self.count_up_count = self.data.get("count_up_count", 0)

        self.auto_learning = self.data.get("auto_learning", False)
        self.custom_size = self.data.get("custom_size", False)

        self.daily_study = self.data.get("daily_study", {})
        if not isinstance(self.daily_study, dict):
            self.daily_study = {}

        # ---------- 运行状态 ----------
        self.is_running = False
        self.is_break = False
        self.current_seconds = 0
        self.timer_thread = None
        self.max_fun_time = self.break_time
        self.fun_used_time = 0
        self.exam_start_timestamp = None
        self.exam_recorded = False
        self.compact_view = False
        self.used_riddles_this_break = set()

        # ---------- 题库 / 名言 ----------
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
            {"question": "什么时候有人敲门，你绝不会说请进？", "answer": "在厕所里的时候"},
            {"question": "冬瓜、黄瓜、西瓜、南瓜都能吃，什么瓜不能吃？", "answer": "傻瓜"},
            {"question": "盆里有6只馒头，6个小朋友每人分到1只，但盆里还留着1只，为什么？",
             "answer": "最后一个小朋友把盆子一起拿走了"},
            {"question": "你能以最快速度，把冰变成水吗？", "answer": "把“冰”字两点去掉"},
            {"question": "冬天宝宝怕冷，到了屋里也不肯脱帽，见了谁才肯脱帽？", "answer": "理发师"},
            {"question": "老王一天要刮四五十次脸，脸上仍有胡子，为什么？", "answer": "他在帮别人刮胡子"},
            {"question": "有一个字，人人见了都会念错，是什么字？", "answer": "错字"},
            {"question": "小华在家里，和谁长得最像？", "answer": "镜中的小华"},
            {"question": "鸡蛋壳有什么用处？", "answer": "包住蛋清和蛋黄"},
            {"question": "不必花钱就能住的房是什么房？", "answer": "牢房"},
            {"question": "什么车子寸步难行？", "answer": "风车"},
            {"question": "什么酒不能喝？", "answer": "碘酒"},
            {"question": "什么蛋打不烂、煮不熟，更不能吃？", "answer": "考试得的零蛋"},
            {"question": "火车由北京到上海需6小时，行驶3小时后在哪？", "answer": "铁轨上"},
            {"question": "时钟什么时候不会走？", "answer": "时钟本来就不会走路"},
            {"question": "从来没见过的爷爷他是什么爷爷？", "answer": "老天爷"},
            {"question": "什么东西打破了才能用？", "answer": "鸡蛋"},
            {"question": "什么东西越热越爱出来？", "answer": "汗水"},
            {"question": "什么人始终不敢洗澡？", "answer": "泥人"},
            {"question": "小明知道试卷答案，为什么还频频看同学的？", "answer": "小明是老师"},
            {"question": "什么事每人每天都必须认真做？", "answer": "睡觉"},
            {"question": "偷什么东西不犯法？", "answer": "偷笑"},
            {"question": "什么东西当你说到它名字，就把它打破了？", "answer": "沉默"},
            {"question": "大象的左耳朵像什么？", "answer": "右耳朵"},
            {"question": "什么东西有四条腿却不能走路？", "answer": "桌子"},
            {"question": "什么人一年只上一天班？", "answer": "圣诞老人"},
            {"question": "什么布剪不断？", "answer": "瀑布"},
            {"question": "什么动物最容易摔倒？", "answer": "狐狸，因为它很狡猾（脚滑）"},
            {"question": "用什么可以解开所有的谜？", "answer": "答案"},
            {"question": "什么东西晚上才会长出尾巴？", "answer": "流星"},
            {"question": "太平洋的中间是什么？", "answer": "平字"},
            {"question": "世界上最小的岛是什么？", "answer": "马路上的安全岛"},
            {"question": "把8分成两半，是多少？", "answer": "0"},
            {"question": "什么人最喜欢别人叫他滚？", "answer": "监狱里的犯人"},
            {"question": "用椰子和西瓜打头哪一个比较痛？", "answer": "头比较痛"},
            {"question": "什么东西没吃的时候是绿的，吃的时候是红的，吐出来是黑的？", "answer": "西瓜"},
            {"question": "为什么自由女神像老站在纽约港？", "answer": "因为她坐不下去"},
            {"question": "一头公牛加一头母牛，打三个字？", "answer": "两头牛"},
            {"question": "什么东西满屋走，但碰不着物件？", "answer": "声音"},
            {"question": "什么动物最没有方向感？", "answer": "麋鹿（迷路）"},
            {"question": "什么书不可能在书店里买到？", "answer": "秘书"},
            {"question": "什么东西人们都不喜欢吃？", "answer": "吃亏"},
            {"question": "大象为什么会有那么长的鼻子？", "answer": "因为它爱说谎"},
            {"question": "什么人站在刀尖上生活？", "answer": "滑冰的人"},
            {"question": "放大镜不能放大的东西是什么？", "answer": "角度"},
            {"question": "什么东西倒立后会增加一半？", "answer": "数字6"},
            {"question": "什么东西明明是你的，别人却用得比你多？", "answer": "你的名字"},
            {"question": "有一只狼来到了北极，变成了什么？", "answer": "槟榔（冰狼）"},
            {"question": "什么动物天天熬夜？", "answer": "熊猫，有黑眼圈"},
            {"question": "什么桥下没有水？", "answer": "立交桥"},
            {"question": "麒麟到了北极会变成什么？", "answer": "冰淇淋（冰麒麟）"},
            {"question": "四个人在屋子里打麻将，警察来了却带走五个人，为什么？", "answer": "被打的人叫麻将"},
            {"question": "什么鱼最聪明？", "answer": "鲸（精）鱼"},
            {"question": "什么鱼最笨？", "answer": "鲨（傻）鱼"},
            {"question": "一颗心值多少钱？", "answer": "一亿，一心一意（亿）"},
            {"question": "狼来了，猜一个水果？", "answer": "杨桃（羊逃）"},
            {"question": "哪个英文字母大家最爱听？", "answer": "CD"},
            {"question": "小白加小白等于什么？", "answer": "小白兔（two）"},
            {"question": "什么植物最老实？", "answer": "芭蕉，老实巴交"},
            {"question": "为什么大雁秋天要飞到南方过冬？", "answer": "走过去太慢了"},
            {"question": "什么交通工具速度越慢越让人恐惧？", "answer": "正在飞行的飞机"},
            {"question": "世界上什么人一下子变老？", "answer": "新娘，第二天变成老婆"},
            {"question": "一颗绿豆从楼上跳下来变成了什么？", "answer": "红豆，摔流血了"},
            {"question": "什么门没有门扇？", "answer": "脑门"},
            {"question": "什么线看得见却抓不着？", "answer": "光线"},
            {"question": "什么掌不能拍？", "answer": "仙人掌"},
            {"question": "什么笔不能写字？", "answer": "电笔"},
            {"question": "什么马不会跑？", "answer": "木马"},
            {"question": "什么虎不吃人？", "answer": "壁虎"},
            {"question": "什么帽不能戴？", "answer": "螺丝帽"},
            {"question": "什么牛不会吃草？", "answer": "蜗牛"},
            {"question": "什么鸡没有翅膀？", "answer": "田鸡"},
            {"question": "什么猫不吃鱼？", "answer": "熊猫"},
            {"question": "什么鸟不会飞？", "answer": "鸵鸟"},
            {"question": "什么羊不吃草？", "answer": "替罪羊"},
            {"question": "什么池里没有水？", "answer": "电池"},
            {"question": "什么网不能捕鱼？", "answer": "电网"},
            {"question": "什么床不能睡？", "answer": "机床"},
            {"question": "什么火不燃烧？", "answer": "怒火"},
            {"question": "什么风看不见摸不着，人人都经历？", "answer": "耳边风"},
            {"question": "什么客不会上门？", "answer": "侠客"},
            {"question": "什么果不能吃？", "answer": "后果"},
            {"question": "什么表没有指针？", "answer": "图表"},
            {"question": "什么梯不走人？", "answer": "电梯"},
            {"question": "什么光不会亮？", "answer": "时光"},
            {"question": "什么花没有叶子？", "answer": "雪花"},
            {"question": "什么河没有水？", "answer": "银河"},
            {"question": "什么饼不能吃？", "answer": "铁饼"},
            {"question": "什么枪把人打跑却不伤人？", "answer": "发令枪"},
            {"question": "有样东西你只能用左手拿，右手永远拿不到？", "answer": "右手"},
        ]
        self.quotes = [
            "书山有路勤为径，学海无涯苦作舟。",
            "宝剑锋从磨砺出，梅花香自苦寒来。",
            "不积跬步，无以至千里；不积小流，无以成江海。",
            "业精于勤，荒于嬉；行成于思，毁于随。",
            "天才是百分之一的灵感加百分之九十九的汗水。",
            "黑发不知勤学早，白首方悔读书迟。",
            "学而不思则罔，思而不学则殆。",
            "知之者不如好之者，好之者不如乐之者。",
            "少壮不努力，老大徒伤悲。",
            "一寸光阴一寸金，寸金难买寸光阴。",
            "少年易老学难成，一寸光阴不可轻。",
            "路漫漫其修远兮，吾将上下而求索。",
            "千淘万漉虽辛苦，吹尽狂沙始到金。",
            "天行健，君子以自强不息。",
            "地势坤，君子以厚德载物。",
            "穷且益坚，不坠青云之志。",
            "老当益壮，宁移白首之心。",
            "会当凌绝顶，一览众山小。",
            "欲穷千里目，更上一层楼。",
            "读书破万卷，下笔如有神。",
            "腹有诗书气自华，读书万卷始通神。",
            "读书百遍，而义自见。",
            "温故而知新，可以为师矣。",
            "三人行，必有我师焉。择其善者而从之。",
            "见贤思齐焉，见不贤而内自省也。",
            "君子坦荡荡，小人长戚戚。",
            "言必信，行必果。",
            "有志者事竟成。",
            "志不强者智不达，言不信者行不果。",
            "丈夫志四海，万里犹比邻。",
            "志当存高远。",
            "燕雀安知鸿鹄之志哉。",
            "绳锯木断，水滴石穿。",
            "锲而不舍，金石可镂；锲而舍之，朽木不折。",
            "驽马十驾，功在不舍。",
            "精诚所至，金石为开。",
            "莫道君行早，更有早行人。",
            "不经一番寒彻骨，怎得梅花扑鼻香。",
            "板凳要坐十年冷，文章不写半句空。",
            "立身以立学为先，立学以读书为本。",
            "为学须刚与恒，不刚则隋隳，不恒则退。",
            "学如逆水行舟，不进则退。",
            "勤学如春起之苗，不见其增，日有所长。",
            "辍学如磨刀之石，不见其损，日有所亏。",
            "勿谓今日不学而有来日，勿谓今年不学而有来年。",
            "日月逝矣，岁不我与。",
            "书山高峻难极顶，学海浩渺无边际。",
            "博览群书添雅趣，勤挥翰墨伴晨昏。",
            "勤能补拙是良训，一分辛劳一分才。",
            "聪明出于勤奋，天才在于积累。",
            "天赋如同自然花木，要用学习来修剪。",
            "学习从来无捷径，循序渐进登高峰。",
            "读书需用意，一字值千金。",
            "人不学，不知义；玉不琢，不成器。",
            "学然后知不足，教然后知困。",
            "广积知识眼界宽，久历世事心胸阔。",
            "读书有三到，谓心到、眼到、口到。",
            "旧书不厌百回读，熟读深思子自知。",
            "立身莫忘求知路，处世常怀律己心。",
            "淡泊以明志，宁静以致远。",
            "非学无以广才，非志无以成学。",
            "静以修身，俭以养德。",
            "忧劳可以兴国，逸豫可以亡身。",
            "生于忧患，死于安乐。",
            "穷则独善其身，达则兼善天下。",
            "勿以恶小而为之，勿以善小而不为。",
            "莫等闲，白了少年头，空悲切。",
            "壮志饥餐胡虏肉，笑谈渴饮匈奴血。",
            "黄沙百战穿金甲，不破楼兰终不还。",
            "追风赶月莫停留，平芜尽处是春山。",
            "追风逐光行致远，笃行不怠向未来。",
            "心有山海，静而无边；步履不停，终抵远方。",
            "星光不问赶路人，时光不负有心人。",
            "纵有狂风平地起，我亦乘风破万里。",
            "追风者终会遇见星光，笃行者定能抵达理想。",
            "以梦为马，不负韶华。",
            "鲜衣怒马少年时，不负韶华行且知。",
            "追风逐月不停歇，逐梦前行勇争先。",
            "心若向阳，无畏悲伤；步履向前，自有光芒。",
            "深耕当下，静待花开。",
            "默默耕耘，终有回甘。",
            "凡心所向，素履所往；生如逆旅，一苇以航。",
            "千磨万击还坚劲，任尔东西南北风。",
            "咬定青山不放松，立根原在破岩中。",
            "删繁就简三秋树，领异标新二月花。",
            "纸上得来终觉浅，绝知此事要躬行。",
            "操千曲而后晓声，观千剑而后识器。",
            "耳闻之不如目见之，目见之不如足践之。",
            "力行而后知之真。",
            "行动是治愈恐惧的良药，犹豫不断滋生恐惧。",
            "成功的秘诀，在永不改变既定的目的。",
            "耐心和持久胜过激烈和狂热。",
            "每一个努力的当下，都是未来惊喜的铺垫。",
            "前路漫漫亦灿灿，往事堪堪亦澜澜。",
            "道阻且长，行则将至；行而不辍，未来可期。",
            "但行好事，莫问前程；心有暖阳，何惧风霜。",
            "一念执着，万般坚持；一寸光阴，一寸耕耘。",
            "勤学善思积底蕴，笃行实干展风华。",
            "日日行，不怕千万里；常常做，不怕千万事。",
            "立志宜思真品格，读书须尽苦功夫。",
            "勤读诗书增智慧，苦磨心志炼精神。",
            "风雨兼程路漫漫，初心不改向高山。",
            "积累在于点滴，成就源于坚持。",
            "这句话看到了还不学习！1/101之一的概率都被你抽中了，不说明你是天选之子吗！！！",
        ]

        self._schedule_auto_save()
        self._schedule_auto_gc()
        self.show_main_menu()

    def _schedule_auto_save(self):
        """每 1 分钟检查一次；到达「自动保存间隔」就保存（设置里可改，0=关闭）"""
        try:
            minutes = int(self.data.get("auto_save_min", 1) or 0)
        except Exception:
            minutes = 1
        self._auto_save_counter = getattr(self, "_auto_save_counter", 0) + 1
        if minutes > 0 and self._auto_save_counter >= minutes:
            self._auto_save_counter = 0
            try:
                self.save_data()
            except Exception:
                pass
        try:
            self.root.after(60000, self._schedule_auto_save)
        except Exception:
            pass

    # ==================================================================
    # mod 加载
    # ==================================================================
    def scan_and_load_mods(self):
        self.mod_values = {}
        self.mod_files_loaded = []
        if not self.feature_on("mod_fqm"):
            return

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()
        mods_dir = os.path.join(base_dir, "mods")
        if not os.path.isdir(mods_dir):
            return

        fqm_files = []
        try:
            for fn in sorted(os.listdir(mods_dir)):
                if fn.lower().endswith(".fqm"):
                    fqm_files.append(fn)
        except Exception as e:
            messagebox.showerror("mod 错误", f"读取 mods 文件夹失败：\n{e}")
            return

        if not fqm_files:
            return

        fqm_data = {}
        for fn in fqm_files:
            full_path = os.path.join(mods_dir, fn)
            try:
                data = parse_fqm(full_path)
                fqm_data[fn] = data
            except Exception as e:
                messagebox.showerror("mod 加载错误", f"无法解析 {fn}:\n{e}")

        if not fqm_data:
            return

        if len(fqm_data) == 1:
            fn = list(fqm_data.keys())[0]
            self.mod_values = fqm_data[fn]
            self.mod_files_loaded = [fn]
            return

        if not self.feature_on("mod_almfq"):
            fn = sorted(fqm_data.keys())[0]
            self.mod_values = fqm_data[fn]
            self.mod_files_loaded = [fn]
            messagebox.showinfo("almfq 已关闭",
                                f"almfq 开关已关闭，只加载第一个 fqm：{fn}")
            return

        if not self.almfq_path or not os.path.exists(self.almfq_path):
            messagebox.showwarning(
                "mod 未生效",
                f"检测到 {len(fqm_data)} 个 .fqm 文件，\n"
                f"必须提供 .almfq 冲突规则文件才能生效。\n\n"
                f"请前往：主菜单 → 设置 → 选择 almfq 文件")
            return

        try:
            rules = parse_almfq(self.almfq_path)
        except Exception as e:
            messagebox.showerror("almfq 错误", f"解析 almfq 失败：\n{e}")
            return

        if rules["let_no_all"]:
            fqm_data = {}
        else:
            fqm_data = {k: v for k, v in fqm_data.items()
                        if k.lower() not in rules["let_no"]}

        if not fqm_data:
            return

        ordered = self._sort_fqm(list(fqm_data.keys()), rules["let_order"])

        all_keys = set()
        for d in fqm_data.values():
            all_keys.update(d.keys())

        final_values = {}
        for key in all_keys:
            candidates = []
            for fn in ordered:
                if fn in fqm_data and key in fqm_data[fn]:
                    if self._is_key_killed(fn, key, rules["kill_rules"]):
                        continue
                    candidates.append((fn, fqm_data[fn][key]))

            if not candidates:
                continue

            category = self._get_mod_category(key)
            class_rule = None
            if category:
                for cd in rules["class_defs"]:
                    if cd["category"] == category and not cd["disabled"]:
                        class_rule = cd
                        break

            if class_rule and len(candidates) > 1:
                strategies = class_rule["strategies"]
                if len(candidates) <= 2:
                    strategy = strategies[0] if strategies else "last"
                else:
                    strategy = strategies[1] if len(strategies) > 1 else (
                        strategies[0] if strategies else "last")
                value = self._apply_strategy(strategy, candidates, ordered)
            else:
                value = candidates[-1][1]
            final_values[key] = value

        self.mod_values = final_values
        self.mod_files_loaded = ordered

    def _sort_fqm(self, files, let_order):
        if not let_order:
            return sorted(files)
        order_type, items = let_order
        result = []
        if order_type == "letters":
            for letter in items:
                for f in sorted(files):
                    if f.lower().startswith(letter) and f not in result:
                        result.append(f)
        elif order_type == "files":
            for item in items:
                for f in files:
                    if f.lower() == item and f not in result:
                        result.append(f)
        for f in sorted(files):
            if f not in result:
                result.append(f)
        return result

    def _is_key_killed(self, fqm_filename, key, kill_rules):
        fl = fqm_filename.lower()
        for rule in kill_rules:
            if rule["key"] != key:
                continue
            in_scope = rule["scope_all"] or fl in rule["scope_set"]
            if not in_scope:
                continue
            if rule["except_all"]:
                continue
            if fl in rule["except_set"]:
                continue
            return True
        return False

    def _get_mod_category(self, key):
        if key in ("study_time", "break_time", "long_break_time",
                   "simple_pomodoro_time", "window_width", "window_height"):
            return "number"
        if key in ("title", "window_title", "beta", "author", "desc", "motto",
                   "mod_name", "mod_version", "default_mode"):
            return "string"
        if key in ("color_primary", "color_timer", "color_bg", "color_accent"):
            return "color"
        if key == "challenge_times":
            return "list"
        # ---- Orbit3 新增类别 ----
        if key in ("task_default_category", "task_default_tag",
                   "tag_normal_text", "tag_effort_text"):
            return "task"
        if key in ("task_manager_btn_text", "small_tools_btn_text"):
            return "ui"
        if key == "tag_effort_color":
            return "color"
        return None

    def _apply_strategy(self, strategy, candidates, ordered):
        if not candidates:
            return None
        if strategy == "big":
            try:
                return max(candidates, key=lambda x: x[1])[1]
            except Exception:
                return candidates[-1][1]
        if strategy == "small":
            try:
                return min(candidates, key=lambda x: x[1])[1]
            except Exception:
                return candidates[-1][1]
        if strategy == "middle":
            try:
                sv = sorted(candidates, key=lambda x: x[1])
                return sv[len(sv) // 2][1]
            except Exception:
                return candidates[-1][1]
        if strategy == "last":
            return candidates[-1][1]
        if strategy == "first":
            return candidates[0][1]
        try:
            idx = int(strategy)
            if 1 <= idx <= len(ordered):
                target = ordered[idx - 1]
                for fn, val in candidates:
                    if fn == target:
                        return val
        except ValueError:
            pass
        return candidates[-1][1]

    def get_mod_value(self, key, default):
        if key in self.mod_values:
            return self.mod_values[key]
        return default

    def apply_mod_values(self):
        global APP_TITLE, APP_BETA, APP_WINDOW_TITLE
        v = self.mod_values
        if "title" in v:
            APP_TITLE = str(v["title"])
        if "window_title" in v:
            APP_WINDOW_TITLE = str(v["window_title"])
        if "beta" in v:
            APP_BETA = str(v["beta"])

    # ==================================================================
    # 数据加载 / 保存 / 迁移
    # ==================================================================
    def get_default_data(self):
        return {
            "pomodoro_count": 0,
            "total_study_seconds": 0,
            "challenge_score": 0,
            "free_time": 0,
            "simple_pomodoro_count": 0,
            "motto": "",
            "simple_mode_seconds": 0,
            "simple_mode_count": 0,
            "exam_mode_seconds": 0,
            "exam_mode_count": 0,
            "challenge_total_seconds": 0,
            "challenge_count": 0,
            "simple_pomodoro_seconds": 0,
            "simple_pomodoro_total_count": 0,
            "count_up_seconds": 0,
            "count_up_count": 0,
            "auto_learning": False,
            "custom_size": False,
            "daily_study": {},
            "last_save_time": "",
            "save_history": [],
            "almfq_path": "",
        }

    def load_data(self):
        # Orbit3：数据在 Orbit3_data.json 的 orbit2 段
        if not os.path.exists(ORBIT3_DATA_FILE):
            merged = STORE.merge_from_sources()
            if merged:
                messagebox.showinfo(
                    "数据合并",
                    "检测到源程序数据，已只读合并生成 Orbit3_data.json：\n"
                    + "\n".join("  • " + m for m in merged)
                    + "\n\n四个源文件均未被修改。")
        seg = STORE.seg("orbit2")
        if seg:
            self.data = seg
            for k, v in self.get_default_data().items():
                self.data.setdefault(k, v)
            return

        migrations = [
            (V4_DATA_FILE, "V4.0"),
            (V33_DATA_FILE, "V3.3"),
            (V32_DATA_FILE, "V3.2"),
            (V31_DATA_FILE, "V3.1"),
            (V3_DATA_FILE, "V3.0"),
            (OLD_DATA_FILE, "V2.0"),
            (OLDER_DATA_FILE, "V1.0"),
        ]
        for path, ver in migrations:
            if not os.path.exists(path):
                continue
            answer = messagebox.askyesno(
                "数据迁移",
                f"检测到 {ver} 数据文件 ({path})，是否迁移到 Orbit3？\n"
                "选择“是”将保留所有数据，选择“否”将从头开始。")
            if answer:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                    new_data = self.get_default_data()
                    for k in new_data:
                        if k in old_data:
                            new_data[k] = old_data[k]
                    self.data = new_data
                    self.save_data_direct()
                    messagebox.showinfo("迁移成功", "数据已迁移至 Orbit3_data.json")
                    return
                except Exception as e:
                    messagebox.showerror("错误", f"迁移失败：{str(e)}\n将使用默认数据")
                    break
            else:
                self.data = self.get_default_data()
                self.save_data_direct()
                return

        self.data = self.get_default_data()
        self.save_data_direct()

    def save_data_direct(self):
        try:
            new = dict(self.data)
            seg = STORE.seg("orbit2")
            seg.clear()
            seg.update(new)
            self.data = seg
            STORE.save()
        except Exception as e:
            messagebox.showerror("错误", f"保存数据失败：{str(e)}")

    def save_data(self):
        self.data.update({
            "pomodoro_count": self.pomodoro_count,
            "total_study_seconds": self.total_study_seconds,
            "challenge_score": self.challenge_score,
            "free_time": self.free_time,
            "simple_pomodoro_count": self.pomodoro_simple_count,
            "motto": self.motto,
            "simple_mode_seconds": self.simple_mode_seconds,
            "simple_mode_count": self.simple_mode_count,
            "exam_mode_seconds": self.exam_mode_seconds,
            "exam_mode_count": self.exam_mode_count,
            "challenge_total_seconds": self.challenge_total_seconds,
            "challenge_count": self.challenge_count,
            "simple_pomodoro_seconds": self.simple_pomodoro_seconds,
            "simple_pomodoro_total_count": self.simple_pomodoro_total_count,
            "count_up_seconds": self.count_up_seconds,
            "count_up_count": self.count_up_count,
            "auto_learning": self.auto_learning,
            "custom_size": self.custom_size,
            "daily_study": self.daily_study,
            "almfq_path": self.almfq_path,
        })
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["last_save_time"] = now_str
        hist = self.data.setdefault("save_history", [])
        hist.append(now_str)
        if len(hist) > 50:
            del hist[:-50]
        self.save_data_direct()

    def apply_data_to_state(self):
        d = self.data
        self.pomodoro_count = d.get("pomodoro_count", 0)
        self.total_study_seconds = d.get("total_study_seconds", 0)
        self.challenge_score = d.get("challenge_score", 0)
        self.free_time = d.get("free_time", 0)
        self.pomodoro_simple_count = d.get("simple_pomodoro_count", 0)
        self.motto = d.get("motto", "")
        self.simple_mode_seconds = d.get("simple_mode_seconds", 0)
        self.simple_mode_count = d.get("simple_mode_count", 0)
        self.exam_mode_seconds = d.get("exam_mode_seconds", 0)
        self.exam_mode_count = d.get("exam_mode_count", 0)
        self.challenge_total_seconds = d.get("challenge_total_seconds", 0)
        self.challenge_count = d.get("challenge_count", 0)
        self.simple_pomodoro_seconds = d.get("simple_pomodoro_seconds", 0)
        self.simple_pomodoro_total_count = d.get("simple_pomodoro_total_count", 0)
        self.count_up_seconds = d.get("count_up_seconds", 0)
        self.count_up_count = d.get("count_up_count", 0)
        self.auto_learning = d.get("auto_learning", False)
        self.custom_size = d.get("custom_size", False)
        self.daily_study = d.get("daily_study", {})
        if not isinstance(self.daily_study, dict):
            self.daily_study = {}

    # ==================================================================
    # 通用小工具
    # ==================================================================
    def clear_root(self):
        for widget in self.root.winfo_children():
            if widget.winfo_class() == "Toplevel":
                continue
            widget.destroy()

    def apply_window_resizable(self, default=False):
        try:
            if self.custom_size:
                self.root.resizable(True, True)
            else:
                self.root.resizable(default, default)
        except Exception:
            pass

    def format_duration(self, seconds):
        seconds = int(seconds)
        if seconds <= 0:
            return "0 分钟"
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours} 小时 {mins} 分钟"
        if mins > 0:
            return f"{mins} 分钟"
        return f"{seconds} 秒"

    def format_time(self, seconds):
        seconds = int(seconds)
        if seconds >= 3600:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def today_key(self):
        return datetime.date.today().strftime("%Y-%m-%d")

    def add_study_time(self, seconds):
        if seconds <= 0:
            return
        k = self.today_key()
        self.daily_study[k] = self.daily_study.get(k, 0) + int(seconds)

    def calc_total_study_all(self):
        return (self.total_study_seconds + self.simple_pomodoro_seconds
                + self.challenge_total_seconds + self.simple_mode_seconds
                + self.exam_mode_seconds + self.count_up_seconds)

    def get_record_rows(self):
        return [
            ("📚 学习模式", f"{self.pomodoro_count} 个番茄", self.total_study_seconds),
            ("🍅 极简番茄", f"{self.simple_pomodoro_total_count} 个番茄", self.simple_pomodoro_seconds),
            ("⏳ 正计时", f"{self.count_up_count} 次计时", self.count_up_seconds),
            ("🔥 挑战模式", f"{self.challenge_count} 次挑战", self.challenge_total_seconds),
            ("⏱ 极简模式", f"{self.simple_mode_count} 次计时", self.simple_mode_seconds),
            ("📝 考试模式", f"{self.exam_mode_count} 次考试", self.exam_mode_seconds),
        ]

    def set_timer_text(self, text):
        try:
            if hasattr(self, "timer_label") and self.timer_label.winfo_exists():
                self.timer_label.config(text=text)
        except Exception:
            pass

    # ==================================================================
    # 主菜单
    # ==================================================================
    def show_main_menu(self):
        self.clear_root()
        self.root.title(APP_WINDOW_TITLE)
        self.root.geometry(f"{self.win_w}x{self.win_h}")
        self.apply_window_resizable(False)
        self.mode = None
        self.mode_locked = False
        self.compact_view = False

        frame = tk.Frame(self.root)
        frame.place(relx=0.5, rely=0.42, anchor="center")

        self.title_lbl = tk.Label(frame, text=APP_TITLE, font=("微软雅黑", 40, "bold"),
                 fg=self.color_timer)
        self.title_lbl.pack()
        if IS_PRO:
            self.title_lbl.bind("<Button-1>", self._title_click)
        tk.Label(frame, text=APP_BETA, font=("微软雅黑", 13),
                 fg="#95a5a6").pack(pady=(0, 6))

        # 内存占用显示（开发者开关，默认关）
        if IS_PRO and STORE.seg("orbit3").get("show_memory", False):
            self._mem_lbl = tk.Label(frame, text="", font=("微软雅黑", 10),
                                     fg="#95a5a6")
            self._mem_lbl.pack(pady=(0, 20))
            self._memory_tick()
        else:
            self._mem_lbl = None

        def menu_btn(text, cmd, primary=False):
            if primary:
                b = tk.Button(frame, text=text, command=cmd,
                              font=("微软雅黑", 15), width=16,
                              bg=self.color_primary, fg="white",
                              activebackground="#27ae60", relief=tk.FLAT,
                              cursor="hand2")
            else:
                b = tk.Button(frame, text=text, command=cmd,
                              font=("微软雅黑", 15), width=16, relief=tk.FLAT,
                              cursor="hand2")
            b.pack(pady=6)
            return b

        if self._any_mode_on():
            menu_btn("选择模式", self.open_mode_selection_with_progress, primary=True)
        if self.feature_on("task_manager"):
            menu_btn(self.get_mod_value("task_manager_btn_text", "任务管理器"),
                     self.open_task_manager)
        if self.feature_on("small_tools"):
            menu_btn(self.get_mod_value("small_tools_btn_text", "小功能"),
                     self.open_small_tools)
        if self.feature_on("mod_fqm"):
            menu_btn("mod 使用方法", self.show_mod_help)
        menu_btn("📖 教程", self.show_tutorial)
        menu_btn("更新日志", self.show_updates)
        menu_btn("设置", self.show_settings)

        if IS_ULTRA:
            menu_btn("📦 附件系统", self.open_attachment_entry)

        self._dev_btn_shown = False
        if IS_PRO and self.dev_mode_on():
            menu_btn("🛠 开发者模式", self.open_dev_settings)
            self._dev_btn_shown = True
        if self._multi_on():
            menu_btn("隐藏窗口", self.hide_window)
        menu_btn("关闭窗口", self.quit_app)

    def back_to_main_menu(self):
        self._settle_unfinished_study()
        self.is_running = False
        self.mode_locked = False
        self.mode = None
        self.compact_view = False
        self.show_main_menu()

    # ==================================================================
    # Orbit3：任务管理器 / 小功能 入口
    # ==================================================================
    def feature_on(self, name):
        # 普通版：只有任务管理器，没有小功能
        if name in ("small_tools", "tool_mouse"):
            return False
        return True

    def _any_mode_on(self):
        return True

    def _multi_on(self):
        return False

    def _maybe_restore_main(self):
        self.root.deiconify()
        self.show_main_menu()

    def dev_log(self, msg):
        pass

    def show_updates(self):
        """更新日志：Ultra 默认打开 HTML（README.html），开发者可切回 tk 窗口"""
        mode = STORE.seg("orbit3").get("changelog_mode", "html" if IS_ULTRA else "tk")
        if IS_ULTRA and mode == "html":
            self._open_changelog_html()
        else:
            self.show_about()

    def _open_changelog_html(self):
        path = os.path.join(ORBIT3_DIR, "README.html")
        if os.path.exists(path):
            try:
                webbrowser.open("file://" + path.replace("\\", "/"))
            except Exception:
                self.show_about()
        else:
            self.show_about()

    def open_task_manager(self):
        old = getattr(self, "_tm_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
        import orbit3_tm
        dev = {"allow_delete_effort": False, "is_pro": False, "logger": None}
        self.root.withdraw()                 # 主界面让位给任务管理器
        top = orbit3_tm.launch(self.root, STORE, self.mod_values, dev)
        def _restore(e):
            if e.widget is top:
                self._tm_win = None
                self.root.deiconify()
                self.show_main_menu()
        top.bind("<Destroy>", _restore)
        self._tm_win = top

    def open_small_tools(self):
        self.clear_root()
        self.root.title(f"{APP_WINDOW_TITLE} - 小功能")
        self.apply_window_resizable(False)
        self.root.geometry(f"{self.win_w}x{self.win_h}")

        tk.Label(self.root, text="🧰 小功能",
                 font=("微软雅黑", 20, "bold")).pack(pady=15)
        tk.Label(self.root, text="小工具和番茄钟共用一份数据（Orbit3_data.json）",
                 font=("微软雅黑", 9), fg="#95a5a6").pack(pady=(0, 12))

        def tool_btn(text, cmd, primary=False):
            b = tk.Button(self.root, text=text, command=cmd,
                          font=("微软雅黑", 13), width=18, relief=tk.FLAT,
                          cursor="hand2",
                          bg=(self.color_primary if primary else "#ecf0f1"),
                          fg=("white" if primary else "#2c3e50"),
                          activebackground=("#27ae60" if primary else "#d5dbdb"))
            b.pack(pady=5, ipady=4)
            return b

        tool_btn("🖱 鼠标检测器", self.open_mouse_tool, primary=True)
        tool_btn("🎵 音乐", self.open_music_tool)
        tool_btn("⏳ 倒计时 / 纪念日", self.open_countdown_tool)
        tool_btn("🎲 随机决定器", self.open_random_tool)

        tk.Button(self.root, text="返回主菜单", command=self.back_to_main_menu,
                  font=("微软雅黑", 12), width=12,
                  relief=tk.FLAT, cursor="hand2").pack(pady=18)

    def open_mouse_tool(self):
        old = getattr(self, "_mouse_win", None)
        if old is not None and not self._multi_on():
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
        import orbit3_mouse
        orbit3_mouse.bind_store(STORE)
        if not self._multi_on():
            self.root.withdraw()             # 主界面让位给鼠标检测器
        top = tk.Toplevel(self.root)
        self._mouse_win = top
        orbit3_mouse.FocusTracker(top)
        def _restore(e):
            if e.widget is top:
                if getattr(self, "_mouse_win", None) is top:
                    self._mouse_win = None
                self._maybe_restore_main()
        top.bind("<Destroy>", _restore)

    def _music_list(self):
        cfg = STORE.seg("orbit3")
        ml = cfg.get("music_list", [])
        if not isinstance(ml, list) or not ml:
            ml = [
                ["华语老歌 10 小时纯享", "https://www.bilibili.com/video/BV1MfR4BFEun/"],
                ["纯音乐神曲", "https://www.bilibili.com/video/BV1UaFZeTEdx/"],
                ["在纯音乐里面，我们就是歌词", "https://www.bilibili.com/video/BV1UtcKzHEQY"],
            ]
        return ml

    def open_music_tool(self):
        old = getattr(self, "_music_win", None)
        if old is not None and not self._multi_on():
            try:
                if old.winfo_exists():
                    old.lift()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._music_win = win
        win.title("音乐")
        win.resizable(False, False)
        win.transient(self.root)
        tk.Label(win, text="🎵 听点什么", font=("微软雅黑", 17, "bold"),
                 fg="#2c3e50").pack(pady=(14, 4))
        tk.Label(win, text="选一个，会用默认浏览器打开",
                 font=("微软雅黑", 9), fg="#95a5a6").pack(pady=(0, 10))
        for name, url in self._music_list():
            tk.Button(win, text=name,
                      command=lambda u=url: webbrowser.open(u),
                      font=("微软雅黑", 12), relief=tk.FLAT, bg="#ecf0f1",
                      width=36, cursor="hand2").pack(pady=4, ipady=4)
        tk.Button(win, text="⚙ 管理网址", command=self._manage_music,
                  font=("微软雅黑", 11), relief=tk.FLAT, bg="#ecf0f1",
                  cursor="hand2").pack(pady=6)
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=8)

    def _manage_music(self):
        cfg = STORE.seg("orbit3")
        win = tk.Toplevel(self.root)
        win.title("管理音乐网址")
        win.resizable(False, False)
        win.transient(self.root)
        tk.Label(win, text="🎵 音乐网址（名称 | 网址，每行一条）",
                 font=("微软雅黑", 12, "bold"), fg="#2c3e50").pack(pady=(12, 6))
        txt = tk.Text(win, font=("Consolas", 10), width=60, height=14)
        txt.pack(padx=12, pady=4)
        lines = []
        for name, url in self._music_list():
            lines.append(f"{name} | {url}")
        txt.insert("1.0", "\n".join(lines))

        def save():
            result = []
            for ln in txt.get("1.0", "end").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if "|" in ln:
                    name, url = ln.split("|", 1)
                    name, url = name.strip(), url.strip()
                else:
                    name, url = ln, ln
                if name and url:
                    result.append([name, url])
            cfg["music_list"] = result
            STORE.save()
            messagebox.showinfo("完成", "已保存。重新打开「音乐」即可看到新列表。",
                                parent=win)
            win.destroy()

        tk.Button(win, text="保存", command=save, font=("微软雅黑", 11),
                  bg=self.color_primary, fg="white", width=10,
                  relief=tk.FLAT, cursor="hand2").pack(pady=(4, 10))

    def open_countdown_tool(self):
        old = getattr(self, "_cd_win", None)
        if old is not None and not self._multi_on():
            try:
                if old.winfo_exists():
                    old.lift()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._cd_win = win
        win.title("倒计时 / 纪念日")
        win.resizable(False, False)
        win.transient(self.root)
        tk.Label(win, text="⏳ 倒计时 / 纪念日", font=("微软雅黑", 16, "bold"),
                 fg="#2c3e50").pack(pady=(14, 6))
        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=16, pady=4)

        def load():
            for w in body.winfo_children():
                w.destroy()
            cds = STORE.seg("orbit3").get("countdowns", [])
            if not isinstance(cds, list) or not cds:
                tk.Label(body, text="还没有倒计时，点下面「新增」添加一个吧",
                         font=("微软雅黑", 10), fg="#95a5a6").pack(pady=10)
                return
            today = datetime.date.today()
            for title, date_str in cds:
                try:
                    d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    days = (d - today).days
                    if days > 0:
                        s = f"距 {title} 还有 {days} 天"
                    elif days == 0:
                        s = f"就是今天！{title}"
                    else:
                        s = f"{title} 已过 {-days} 天"
                except Exception:
                    s = f"{title}（{date_str}）"
                row = tk.Frame(body)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=s, font=("微软雅黑", 12),
                         fg="#2c3e50").pack(side="left")
                tk.Label(row, text=date_str, font=("微软雅黑", 9),
                         fg="#95a5a6").pack(side="right")
        load()

        def add():
            dlg = tk.Toplevel(win)
            dlg.title("新增倒计时")
            dlg.resizable(False, False)
            dlg.transient(win)
            tk.Label(dlg, text="标题", font=("微软雅黑", 11)).grid(row=0, column=0, padx=10, pady=6)
            t_var = tk.StringVar()
            tk.Entry(dlg, textvariable=t_var, width=20).grid(row=0, column=1, padx=10, pady=6)
            tk.Label(dlg, text="日期（YYYY-MM-DD）", font=("微软雅黑", 11)).grid(row=1, column=0, padx=10, pady=6)
            d_var = tk.StringVar()
            tk.Entry(dlg, textvariable=d_var, width=20).grid(row=1, column=1, padx=10, pady=6)
            def ok():
                title = t_var.get().strip()
                ds = d_var.get().strip()
                if not title or not ds:
                    return
                try:
                    datetime.datetime.strptime(ds, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("格式错误", "日期要写成 YYYY-MM-DD", parent=dlg)
                    return
                cds = STORE.seg("orbit3").setdefault("countdowns", [])
                cds.append([title, ds])
                STORE.save()
                dlg.destroy()
                load()
            tk.Button(dlg, text="添加", command=ok, font=("微软雅黑", 11),
                      bg=self.color_primary, fg="white", relief=tk.FLAT,
                      cursor="hand2").grid(row=2, column=0, columnspan=2, pady=10)
            tk.Button(dlg, text="取消", command=dlg.destroy, font=("微软雅黑", 11),
                      relief=tk.FLAT).grid(row=3, column=0, columnspan=2, pady=(0, 10))

        def clear_all():
            if messagebox.askyesno("确认", "清空所有倒计时 / 纪念日？", parent=win):
                STORE.seg("orbit3")["countdowns"] = []
                STORE.save()
                load()

        bf = tk.Frame(win)
        bf.pack(pady=8)
        tk.Button(bf, text="新增", command=add, font=("微软雅黑", 11),
                  bg=self.color_primary, fg="white", relief=tk.FLAT,
                  cursor="hand2").pack(side="left", padx=5)
        tk.Button(bf, text="清空", command=clear_all, font=("微软雅黑", 11),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)
        tk.Button(bf, text="关闭", command=win.destroy, font=("微软雅黑", 11),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)

    def open_random_tool(self):
        old = getattr(self, "_rnd_win", None)
        if old is not None and not self._multi_on():
            try:
                if old.winfo_exists():
                    old.lift()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._rnd_win = win
        win.title("随机决定器")
        win.resizable(False, False)
        win.transient(self.root)
        tk.Label(win, text="🎲 随机决定器", font=("微软雅黑", 16, "bold"),
                 fg="#2c3e50").pack(pady=(14, 6))
        tk.Label(win, text="下面每行一个选项，点「抽一个」帮你决定",
                 font=("微软雅黑", 9), fg="#95a5a6").pack()
        txt = tk.Text(win, font=("微软雅黑", 12), width=36, height=10)
        txt.pack(padx=14, pady=8)
        opts = STORE.seg("orbit3").get("random_options", [])
        if isinstance(opts, list):
            txt.insert("1.0", "\n".join(opts))
        result = tk.Label(win, text="", font=("微软雅黑", 18, "bold"),
                          fg=self.color_primary)
        result.pack(pady=6)

        def pick():
            opts = [l.strip() for l in txt.get("1.0", "end").splitlines() if l.strip()]
            if not opts:
                messagebox.showinfo("提示", "先填几个选项吧", parent=win)
                return
            result.config(text="👉 " + random.choice(opts))

        bf = tk.Frame(win)
        bf.pack(pady=6)
        tk.Button(bf, text="抽一个", command=pick, font=("微软雅黑", 12),
                  bg=self.color_primary, fg="white", relief=tk.FLAT,
                  cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(bf, text="记住选项", command=lambda: (
            STORE.seg("orbit3").__setitem__(
                "random_options", [l.strip() for l in txt.get("1.0", "end").splitlines() if l.strip()]),
            STORE.save()), font=("微软雅黑", 10), relief=tk.FLAT,
            bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)
        tk.Button(bf, text="关闭", command=win.destroy, font=("微软雅黑", 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side="left", padx=5)

    def _settle_unfinished_study(self):
        """中途退出计时模式时，结算已经学习的时长（不浪费）。
        极简模式 / 学习·极简展示：按已用时间记录到学习数据并立即保存。"""
        if not getattr(self, "is_running", False):
            return
        self.is_running = False
        mode = getattr(self, "mode", None)
        try:
            if mode == "simple":
                learned = max(0, int(getattr(self, "custom_time", 0)
                                     - getattr(self, "current_seconds", 0)))
                if learned > 0:
                    self.simple_mode_seconds += learned
                    self.simple_mode_count += 1
                    self.add_study_time(learned)
                    self.save_data()
            elif mode == "learning" and getattr(self, "compact_view", False):
                learned = max(0, int(getattr(self, "study_time", 0)
                                     - getattr(self, "current_seconds", 0)))
                if learned > 0:
                    self.total_study_seconds += learned
                    self.add_study_time(learned)
                    self.save_data()
        except Exception:
            pass

    def quit_app(self):
        try:
            self._settle_unfinished_study()
        except Exception:
            pass
        try:
            self.save_data()
        except Exception:
            pass
        self.root.destroy()

    def _get_memory_mb(self):
        """当前进程工作集内存（MB）"""
        try:
            import ctypes
            from ctypes import wintypes
            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(pmc), pmc.cb)
            return pmc.WorkingSetSize / 1024.0 / 1024.0
        except Exception:
            return -1.0

    def optimize_memory(self, silent=False):
        """内存优化：gc 回收 + 清空进程工作集（模仿 PCL 的「一键优化」）。"""
        import gc
        before = self._get_memory_mb()
        gc.collect()
        try:
            import ctypes
            ctypes.windll.psapi.EmptyWorkingSet(
                ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
        after = self._get_memory_mb()
        freed = (before - after) if (before > 0 and after > 0) else -1.0
        if not silent:
            if freed >= 0:
                messagebox.showinfo("内存优化",
                                    f"优化完成！\n释放了约 {freed:.1f} MB 内存。")
            else:
                messagebox.showinfo("内存优化", "优化完成！已回收垃圾对象、清空工作集。")
        return freed

    def _schedule_auto_gc(self):
        """Ultra：定时自动内存优化（静默，默认关闭，开发者设置可开）"""
        cfg = STORE.seg("orbit3")
        if IS_ULTRA and cfg.get("auto_gc_enabled", False):
            try:
                self.optimize_memory(silent=True)
            except Exception:
                pass
        try:
            self.root.after(5 * 60 * 1000, self._schedule_auto_gc)  # 每 5 分钟检查
        except Exception:
            pass

    # ==================================================================
    # Pro：开发者模式
    # ==================================================================
    DEFAULT_FLAGS = {
        "mode_learning": True, "mode_clock": True, "mode_challenge": True,
        "mode_simple": True, "mode_exam": True, "mode_simple_pomodoro": True,
        "mode_count_up": True, "mode_records": True,
        "task_manager": True, "small_tools": True,
        "tool_mouse": True,
        "mod_fqm": True, "mod_almfq": True,
        "allow_delete_effort": False,
        "multi_instance": False,
    }

    def _flags(self):
        f = STORE.seg("orbit3").setdefault("flags", {})
        for k, v in self.DEFAULT_FLAGS.items():
            f.setdefault(k, v)
        return f

    def feature_on(self, name):
        return bool(self._flags().get(name, self.DEFAULT_FLAGS.get(name, True)))

    def _any_mode_on(self):
        f = self._flags()
        return any(f.get(k, True) for k in self.DEFAULT_FLAGS if k.startswith("mode_"))

    def _multi_on(self):
        return IS_PRO and self.feature_on("multi_instance")

    def open_task_manager(self):
        old = getattr(self, "_tm_win", None)
        if old is not None and not self._multi_on():
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass
        import orbit3_tm
        dev = {"allow_delete_effort": self.feature_on("allow_delete_effort"),
               "is_pro": True, "logger": self.dev_log}
        if not self._multi_on():
            self.root.withdraw()             # 主界面让位给任务管理器
        top = orbit3_tm.launch(self.root, STORE, self.mod_values, dev)
        def _restore(e):
            if e.widget is top:
                if getattr(self, "_tm_win", None) is top:
                    self._tm_win = None
                self._maybe_restore_main()
        top.bind("<Destroy>", _restore)
        self._tm_win = top

    def dev_mode_on(self):
        return bool(STORE.seg("orbit3").get("dev_mode", False))

    def _set_dev_mode(self, on):
        STORE.seg("orbit3")["dev_mode"] = bool(on)
        STORE.save()

    def _bind_scroll_canvas(self, canvas, win):
        """可滚动窗口的滚轮绑定：后开的窗口接管滚轮，关闭时还给上一个活着的窗口
        （bind_all 是全局单槽，不配对管理会出现滚错窗口的情况）"""
        def _make_wheel(cv):
            def _wheel(e):
                try:
                    cv.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass
            return _wheel
        pairs = [p for p in getattr(self, "_scroll_pairs", [])
                 if p[1] is not win]
        pairs.append((canvas, win, _make_wheel(canvas)))
        self._scroll_pairs = pairs
        canvas.bind_all("<MouseWheel>", pairs[-1][2])

        def _on_destroy(e):
            if e.widget is not win:
                return
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
            self._scroll_pairs = [p for p in getattr(self, "_scroll_pairs", [])
                                  if p[1] is not win]
            for c, w, fn in reversed(self._scroll_pairs):
                try:
                    if w.winfo_exists():
                        c.bind_all("<MouseWheel>", fn)
                        return
                except Exception:
                    pass
        win.bind("<Destroy>", _on_destroy)

    def dev_log(self, msg):
        try:
            cfg = STORE.seg("orbit3")
            if not cfg.get("log_enabled", True):
                return
            os.makedirs(ORBIT3_LOG_DIR, exist_ok=True)
            fn = "dev_" + datetime.datetime.now().strftime("%Y-%m-%d") + ".log"
            with open(os.path.join(ORBIT3_LOG_DIR, fn), "a", encoding="utf-8") as f:
                f.write("[" + datetime.datetime.now().strftime("%H:%M:%S") + "] "
                        + str(msg) + "\n")
        except Exception:
            pass

    def _title_click(self, _e=None):
        now = time.time()
        if now - getattr(self, "_title_last", 0) > 2.0:
            self._title_clicks = 0
        self._title_last = now
        self._title_clicks = getattr(self, "_title_clicks", 0) + 1
        if self._title_clicks >= 8:
            self._title_clicks = 0
            if not self.dev_mode_on():
                self._set_dev_mode(True)
                self.dev_log("开发者模式开启")
                messagebox.showinfo("开发者模式",
                                    "你已开启开发者模式，再次点击8下标题即可关闭")
            else:
                self._set_dev_mode(False)
                self.dev_log("开发者模式关闭")
                messagebox.showinfo("开发者模式", "开发者模式已关闭")
            self.show_main_menu()

    # ---------- 开发者设置主窗口 ----------
    def open_dev_settings(self):
        if not self.dev_mode_on():
            return
        old = getattr(self, "_dev_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._dev_win = win
        win.title("开发者模式")
        win.geometry("460x600")
        win.resizable(False, False)
        win.transient(self.root)
        self.dev_log("打开开发者设置")

        tk.Label(win, text="🛠 开发者模式", font=("微软雅黑", 18, "bold"),
                 fg=self.color_timer).pack(pady=(14, 6))

        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=430)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._bind_scroll_canvas(canvas, win)

        def mk(text, cmd, desc=None, fg="#2c3e50", bg="#ecf0f1"):
            b = tk.Button(inner, text=text, command=cmd, font=("微软雅黑", 12),
                          width=24, relief=tk.FLAT, bg=bg, fg=fg, cursor="hand2")
            b.pack(pady=(10, 0), ipady=4)
            if desc:
                tk.Label(inner, text=desc, font=("微软雅黑", 9), fg="#95a5a6",
                         wraplength=380, justify="left").pack(anchor="w", padx=50)
            return b

        mk("1. 功能开关", self.dev_feature_switches,
           "模式 / 任务管理器 / 小功能 / mod / 允许删除「努力的我」")
        mk("2. 开发者源码展示", self.dev_show_sources,
           "点击文件名，用记事本打开对应源码")
        mk("3. 多开（多实例）", self.dev_multi_instance,
           "开启后打开功能不隐藏主界面，可同时开多个窗口")
        mk("4. 学习·极简展示修改", self.dev_compact_config,
           "显示项增删 / 自定义大小 / 宽高 / 字号")
        mk("5. 崩溃日志自动传输", self.dev_crash_path,
           "设置崩溃日志传输路径（默认桌面）")
        mk("6. 崩溃日志读取与分析", self.dev_crash_analyze,
           "翻译成中文并指出错误，导出 txt")
        mk("7. 数据与存档工具", self.dev_data_tools,
           "校验数据 / 只读检查源 JSON / 触发合并")
        mk("8. 开发者诊断面板", self.dev_diag,
           "版本 / 路径 / 线程 / mod / 最近错误")
        mk("9. 界面调试工具", self.dev_ui_debug,
           "控件树 / 隐藏按钮 / UI 重载 / 临时尺寸字体")
        mk("日志开关", self.dev_log_toggle,
           "关闭开发者日志；关闭时会问要不要连崩溃日志一起关")
        mk("内存占用显示", self.dev_memory_display,
           "开启后主界面显示当前内存占用（实时刷新）")
        if IS_ULTRA:
            mk("定时自动内存优化", self.dev_auto_gc,
               "每 5 分钟静默回收一次内存（仅 Ultra）")
            mk("更新日志显示方式", self.dev_changelog_mode,
               "HTML（默认，浏览器阅读）/ tk 窗口 切换")

        tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, padx=30, pady=(16, 0))
        mk("10. 千万别点", self.dev_dont_click,
           "作者概不负责", fg="#ffffff", bg="#e74c3c")

        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=10)

    # ---------- 1. 功能开关 ----------
    def dev_feature_switches(self):
        win = tk.Toplevel(self._dev_win)
        win.title("功能开关")
        win.geometry("420x640")
        win.resizable(False, False)
        win.transient(self._dev_win)

        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(body, highlightthickness=0)
        sb = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=390)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._bind_scroll_canvas(canvas, win)

        flags = self._flags()

        def make(key, text, desc=None, danger=False):
            var = tk.BooleanVar(value=bool(flags.get(key, True)))
            def on_change():
                flags[key] = var.get()
                if key == "mod_fqm" and not var.get():
                    flags["mod_almfq"] = False   # 关 fqm 自动关 almfq
                    for v, k in almfq_vars:
                        if k == "mod_almfq":
                            v.set(False)
                STORE.save()
                self.dev_log(f"功能开关 {key} -> {var.get()}")
            tk.Checkbutton(inner, text=text, variable=var, command=on_change,
                           font=("微软雅黑", 12),
                           fg="#e74c3c" if danger else "#2c3e50",
                           cursor="hand2").pack(anchor="w", padx=30, pady=(8, 0))
            if desc:
                tk.Label(inner, text=desc, font=("微软雅黑", 9), fg="#95a5a6",
                         wraplength=340, justify="left").pack(anchor="w", padx=50)
            almfq_vars.append((var, key))
            return var

        almfq_vars = []
        tk.Label(inner, text="选择模式里的模式", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=30, pady=(10, 0))
        for key, text in [
            ("mode_learning", "★ 学习模式"), ("mode_clock", "现在时间"),
            ("mode_challenge", "挑战模式"), ("mode_simple", "极简模式"),
            ("mode_exam", "考试模式"), ("mode_simple_pomodoro", "极简番茄"),
            ("mode_count_up", "正计时模式"), ("mode_records", "我的学习记录"),
        ]:
            make(key, text)
        tk.Label(inner, text="入口", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=30, pady=(14, 0))
        make("task_manager", "任务管理器")
        make("small_tools", "小功能（总开关）")
        make("tool_mouse", "└ 鼠标检测器")
        tk.Label(inner, text="mod 系统", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=30, pady=(14, 0))
        make("mod_fqm", "fqm（关闭时 almfq 自动关闭）")
        make("mod_almfq", "almfq（关闭时只加载一个 fqm）")
        tk.Label(inner, text="任务管理器", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=30, pady=(14, 0))
        make("allow_delete_effort", "允许删除「努力的我」",
             "默认关闭。开启后删除需二次确认并写入开发者日志", danger=True)
        tk.Label(inner, text="多开", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=30, pady=(14, 0))
        make("multi_instance", "多开（多实例）",
             "开启后打开功能不隐藏主界面，可同时开多个窗口；关闭窗口多一个「隐藏窗口」")
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=10)

    # ---------- 2. 源码展示 ----------
    def dev_show_sources(self):
        win = tk.Toplevel(self._dev_win)
        win.title("开发者源码展示")
        win.geometry("420x360")
        win.resizable(False, False)
        win.transient(self._dev_win)
        tk.Label(win, text="📄 本版全部源码", font=("微软雅黑", 14, "bold"),
                 fg=self.color_timer).pack(pady=(12, 6))
        try:
            files = [f for f in sorted(os.listdir(ORBIT3_DIR))
                     if f.lower().endswith((".py", ".pyw"))]
        except Exception:
            files = []
        if not files:
            tk.Label(win, text="（没找到源码文件）", font=("微软雅黑", 10),
                     fg="#95a5a6").pack()
        for fn in files:
            p = os.path.join(ORBIT3_DIR, fn)
            tk.Button(win, text=fn, font=("微软雅黑", 11), width=30,
                      relief=tk.FLAT, bg="#ecf0f1", cursor="hand2",
                      command=lambda pp=p: (subprocess.Popen(["notepad.exe", pp]),
                                            self.dev_log("查看源码 " + os.path.basename(pp)))
                      ).pack(pady=3, ipady=3)
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=10)

    def _dev_parent(self):
        """返回安全的 messagebox parent：开发者窗口还在就用它，否则回退主窗口。
        防止 _dev_win 被销毁后 parent=已销毁窗口 抛 TclError。"""
        w = getattr(self, "_dev_win", None)
        if w is not None:
            try:
                if w.winfo_exists():
                    return w
            except tk.TclError:
                pass
        return self.root

    # ---------- 3. 多开（多实例）开关 ----------
    def dev_multi_instance(self):
        f = self._flags()
        cur = f.get("multi_instance", False)
        f["multi_instance"] = not cur
        STORE.save()
        self.dev_log("多开（多实例）-> " + str(not cur))
        if not cur:
            messagebox.showinfo("已开启",
                                "多开已开启：打开任务管理器/小功能时主界面不再隐藏，\n"
                                "也可以重复打开多个窗口。\n"
                                "关闭窗口时会多一个「隐藏窗口」选项。",
                                parent=self._dev_parent())
        else:
            messagebox.showinfo("已关闭",
                                "多开已关闭：恢复原来的单窗口模式。",
                                parent=self._dev_parent())
        self.show_main_menu()

    def hide_window(self):
        """隐藏主界面（不是退出、不是最小化）。功能窗口关闭后的行为见设置。"""
        if not messagebox.askyesno(
                "隐藏窗口",
                "确定隐藏主界面吗？\n\n这不是退出、也不是最小化——只是把主界面藏起来。\n"
                "你可以在任务管理器/小功能窗口关闭后，按设置里的选项决定是否重新出现。"):
            return
        self.root.withdraw()
        self._hidden = True
        self.dev_log("隐藏主界面")

    def _maybe_restore_main(self):
        """功能窗口关闭后，按「关闭后主界面操作」设置决定主界面是否重新出现"""
        if not self._multi_on():
            self.root.deiconify()
            self.show_main_menu()
            return
        beh = STORE.seg("orbit3").get("close_behavior", "open")
        if beh == "open":
            try:
                self.root.deiconify()
            except Exception:
                pass
        # "hide"：保持隐藏，不做任何事

    # ---------- 4. 学习·极简展示修改 ----------
    def _compact_cfg(self):
        cfg = STORE.seg("orbit3").setdefault("simple_display", {})
        cfg.setdefault("items", {"timer": True, "back": True,
                                 "clock": False, "today": False})
        cfg.setdefault("custom", False)
        cfg.setdefault("w", 360)
        cfg.setdefault("h", 200)
        cfg.setdefault("font", 56)
        return cfg

    def dev_compact_config(self):
        cfg = self._compact_cfg()
        win = tk.Toplevel(self._dev_win)
        win.title("学习·极简展示修改")
        win.geometry("400x470")
        win.resizable(False, False)
        win.transient(self._dev_win)

        tk.Label(win, text="学习模式「极简展示」的显示项",
                 font=("微软雅黑", 13, "bold"), fg=self.color_timer).pack(pady=(14, 6))
        items = cfg["items"]
        item_vars = {}
        for key, text in [("timer", "大字计时"), ("back", "「恢复到正常模式」按钮"),
                          ("clock", "当前时间"), ("today", "今日已学习时长")]:
            var = tk.BooleanVar(value=bool(items.get(key, True)))
            item_vars[key] = var
            tk.Checkbutton(win, text=text, variable=var, font=("微软雅黑", 12),
                           cursor="hand2").pack(anchor="w", padx=40, pady=2)

        tk.Frame(win, height=1, bg="#ecf0f1").pack(fill=tk.X, padx=30, pady=10)
        custom_var = tk.BooleanVar(value=bool(cfg.get("custom", False)))
        tk.Checkbutton(win, text="自定义大小（窗口可按住边框调整）",
                       variable=custom_var, font=("微软雅黑", 12),
                       cursor="hand2").pack(anchor="w", padx=40)

        row = tk.Frame(win)
        row.pack(pady=6)
        tk.Label(row, text="宽", font=("微软雅黑", 11)).pack(side=tk.LEFT)
        w_var = tk.StringVar(value=str(cfg.get("w", 360)))
        tk.Entry(row, textvariable=w_var, width=6, font=("微软雅黑", 11)).pack(side=tk.LEFT, padx=4)
        tk.Label(row, text="高", font=("微软雅黑", 11)).pack(side=tk.LEFT)
        h_var = tk.StringVar(value=str(cfg.get("h", 200)))
        tk.Entry(row, textvariable=h_var, width=6, font=("微软雅黑", 11)).pack(side=tk.LEFT, padx=4)
        tk.Label(row, text="字号", font=("微软雅黑", 11)).pack(side=tk.LEFT)
        f_var = tk.StringVar(value=str(cfg.get("font", 56)))
        tk.Entry(row, textvariable=f_var, width=6, font=("微软雅黑", 11)).pack(side=tk.LEFT, padx=4)

        def save_cfg():
            try:
                w, h, fs = int(w_var.get()), int(h_var.get()), int(f_var.get())
                if not (200 <= w <= 1200 and 120 <= h <= 900 and 20 <= fs <= 120):
                    raise ValueError
            except ValueError:
                messagebox.showerror("输入错误",
                                     "宽 200~1200，高 120~900，字号 20~120", parent=win)
                return
            cfg["items"] = {k: v.get() for k, v in item_vars.items()}
            cfg["custom"] = custom_var.get()
            cfg["w"], cfg["h"], cfg["font"] = w, h, fs
            STORE.save()
            self.dev_log(f"极简展示配置更新 {cfg}")
            messagebox.showinfo("完成", "已写入 Orbit3_data.json。\n下次进入极简展示时生效。",
                                parent=win)
            win.destroy()

        tk.Button(win, text="保存", command=save_cfg, font=("微软雅黑", 12),
                  bg=self.color_primary, fg="white", width=10, relief=tk.FLAT,
                  cursor="hand2").pack(pady=10)

    # ---------- 5. 崩溃日志自动传输 ----------
    def dev_crash_path(self):
        cfg = STORE.seg("orbit3")
        d = filedialog.askdirectory(
            initialdir=cfg.get("crash_log_dir") or os.path.join(os.path.expanduser("~"), "Desktop"),
            title="选择崩溃日志传输路径")
        if d:
            cfg["crash_log_dir"] = d
            STORE.save()
            self.dev_log("崩溃日志传输路径 -> " + d)
            messagebox.showinfo("完成", f"崩溃日志将传输到：\n{d}", parent=self._dev_parent())

    # ---------- 6. 崩溃日志读取与分析 ----------
    _CRASH_CN = [
        ("ZeroDivisionError", "除以零：有地方拿 0 当了除数"),
        ("KeyError", "字典里找不到这个键：多半是没做 setdefault 或键名写错"),
        ("IndexError", "下标越界：列表没这么长"),
        ("AttributeError", "对象上没有这个属性/方法：名字写错，或变量其实是 None"),
        ("TypeError", "类型不对：参数个数/类型和方法要的对不上"),
        ("ValueError", "值不合法：比如把非数字字符串塞进 int()"),
        ("FileNotFoundError", "文件不存在：路径错了或文件被移走"),
        ("PermissionError", "没有权限：文件被占用或只读"),
        ("JSONDecodeError", "JSON 解析失败：数据文件内容坏了"),
        ("TclError", "tkinter 界面错误：多半是操作了已销毁的控件"),
        ("NameError", "名字没定义：变量/函数名写错或没导入"),
        ("ImportError", "导入失败：模块不存在或路径不对"),
        ("MemoryError", "内存不足"),
        ("OverflowError", "数值溢出"),
        ("StopIteration", "迭代结束：next() 拿过头了"),
        ("RuntimeError", "运行时错误"),
        ("OSError", "操作系统层错误"),
    ]

    def dev_crash_analyze(self):
        path = filedialog.askopenfilename(
            title="选择崩溃日志",
            initialdir=ORBIT3_LOG_DIR,
            filetypes=[("日志文件", "*.log *.txt"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("读取失败", str(e), parent=self._dev_parent())
            return

        lines = ["崩溃日志分析报告", "=" * 40,
                 "源文件：" + path,
                 "分析时间：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""]
        found = False
        for en, cn in self._CRASH_CN:
            if en in content:
                lines.append(f"● 发现 {en}：{cn}")
                found = True
        if not found:
            lines.append("● 没认出具体错误类型，请看原文最后的异常行。")
        tb_lines = [ln for ln in content.splitlines()
                    if ln.strip().startswith(("File ", "Traceback"))]
        if tb_lines:
            lines.append("")
            lines.append("出错位置（从下往上看，最下面的是真正的出错行）：")
            for ln in tb_lines[-6:]:
                lines.append("  " + ln.strip())
        exc_lines = [ln for ln in content.splitlines()
                     if ln and not ln.startswith((" ", "-", "Tim", "Ver", "Pyt",
                                                  "Des", "OS", "Dat", "（"))
                     and ":" in ln]
        if exc_lines:
            lines.append("")
            lines.append("原始异常：" + exc_lines[-1])

        out = os.path.join(os.path.dirname(path),
                           "分析_" + os.path.basename(path).rsplit(".", 1)[0] + ".txt")
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.dev_log("分析崩溃日志 " + os.path.basename(path))
            messagebox.showinfo("分析完成",
                                "\n".join(lines[4:8]) + f"\n\n已导出：{out}",
                                parent=self._dev_parent())
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self._dev_parent())

    # ---------- 7. 数据与存档工具 ----------
    def dev_data_tools(self):
        win = tk.Toplevel(self._dev_win)
        win.title("数据与存档工具")
        win.geometry("480x420")
        win.resizable(False, False)
        win.transient(self._dev_win)
        txt = tk.Text(win, font=("Consolas", 10), wrap=tk.WORD,
                      bg="#f4f6f8", relief=tk.FLAT)
        txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 4))

        def w(s=""):
            txt.insert(tk.END, s + "\n")
            txt.see(tk.END)

        w("当前数据文件：" + STORE.path)
        try:
            w("大小：%d 字节" % os.path.getsize(STORE.path))
        except Exception:
            w("（文件还不存在）")
        w("")

        def check_main():
            txt.delete("1.0", tk.END)
            w("【校验 Orbit3_data.json】")
            d = _read_json_safe(STORE.path)
            if d is None:
                w("✗ JSON 读不了（可能损坏）")
                return
            w("✓ JSON 能正常解析")
            for seg in ("orbit2", "tasks", "mouse", "kuakua", "orbit3"):
                if seg in d:
                    w(f"✓ 段 {seg}：{len(d[seg])} 个键")
                else:
                    w(f"○ 段 {seg} 不存在（还没用过对应模块）")
            self.dev_log("校验 Orbit3_data.json")

        def check_sources():
            txt.delete("1.0", tk.END)
            w("【只读检查两个源 JSON】（不会写入；学习存档不读）")
            names = {"tasks": "任务管理器 tasks_v3.json",
                     "mouse": "鼠标检测器 data.json"}
            for key, path in SRC_JSONS.items():
                if not os.path.exists(path):
                    w(f"○ {names[key]}：不存在")
                    continue
                d = _read_json_safe(path)
                if d is None:
                    w(f"✗ {names[key]}：读不了")
                else:
                    w(f"✓ {names[key]}：{len(d)} 个键")
            self.dev_log("只读检查两个源 JSON")

        def do_merge():
            merged = STORE.merge_from_sources()
            if merged:
                messagebox.showinfo("合并完成",
                                    "已补入：\n" + "\n".join("  • " + m for m in merged)
                                    + "\n\n（只补缺失内容，源文件未动）",
                                    parent=win)
            else:
                messagebox.showinfo("无需合并",
                                    "Orbit3_data.json 里已有对应内容，或源文件不存在。",
                                    parent=win)
            self.dev_log("手动触发源 JSON 合并")

        bf = tk.Frame(win)
        bf.pack(pady=(4, 12))
        tk.Button(bf, text="校验数据", command=check_main, font=("微软雅黑", 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="只读检查源 JSON", command=check_sources,
                  font=("微软雅黑", 10), relief=tk.FLAT, bg="#ecf0f1",
                  cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="触发源→Orbit3 合并", command=do_merge,
                  font=("微软雅黑", 10), relief=tk.FLAT, bg="#ecf0f1",
                  cursor="hand2").pack(side=tk.LEFT, padx=4)

    # ---------- 8. 诊断面板 ----------
    def dev_diag(self):
        win = tk.Toplevel(self._dev_win)
        win.title("开发者诊断面板")
        win.geometry("480x400")
        win.resizable(False, False)
        win.transient(self._dev_win)
        txt = tk.Text(win, font=("Consolas", 10), wrap=tk.WORD,
                      bg="#f4f6f8", relief=tk.FLAT)
        txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        thr = getattr(self, "timer_thread", None)
        thr_state = "无计时线程"
        if thr is not None:
            try:
                thr_state = "运行中" if thr.is_alive() else "已结束"
            except Exception:
                thr_state = "状态未知"
        lines = [
            "版本：Orbit3 " + ORBIT3_VERSION + " " + ORBIT3_EDITION,
            "程序目录：" + ORBIT3_DIR,
            "数据文件：" + STORE.path,
            "log 目录：" + ORBIT3_LOG_DIR,
            "当前模式：" + str(self.mode),
            "计时线程：" + thr_state,
            "线程总数：" + str(threading.active_count()),
            "mod 加载：" + (", ".join(self.mod_files_loaded) if self.mod_files_loaded else "（无）"),
            "mod 值个数：" + str(len(self.mod_values)),
            "异常捕获：已开启（sys.excepthook + Tk 回调）",
            "崩溃日志输出：" + ("开" if STORE.seg("orbit3").get("crash_log_enabled", True) else "关"),
            "开发者日志：" + ("开" if STORE.seg("orbit3").get("log_enabled", True) else "关"),
            "",
            "最近错误摘要：",
        ] + (["  " + e for e in RECENT_ERRORS[-5:]] or ["  （无）"])
        txt.insert(tk.END, "\n".join(lines))
        txt.config(state=tk.DISABLED)
        self.dev_log("查看诊断面板")

    # ---------- 9. 界面调试工具 ----------
    def dev_ui_debug(self):
        win = tk.Toplevel(self._dev_win)
        win.title("界面调试工具")
        win.geometry("460x440")
        win.resizable(False, False)
        win.transient(self._dev_win)

        bf = tk.Frame(win)
        bf.pack(pady=8)
        txt = tk.Text(win, font=("Consolas", 9), wrap=tk.NONE,
                      bg="#f4f6f8", relief=tk.FLAT)
        txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        def show_tree():
            txt.config(state=tk.NORMAL)
            txt.delete("1.0", tk.END)
            def walk(wd, depth):
                try:
                    txt.insert(tk.END, "  " * depth + wd.winfo_class()
                               + ("  (text=" + str(wd.cget("text"))[:18] + ")"
                                  if wd.winfo_class() in ("Label", "Button",
                                                          "Radiobutton", "Checkbutton")
                                  else "") + "\n")
                    for ch in wd.winfo_children():
                        walk(ch, depth + 1)
                except Exception:
                    pass
            walk(self.root, 0)
            self.dev_log("查看控件树")

        def check_hidden():
            txt.config(state=tk.NORMAL)
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, "开发者模式按钮：" +
                       ("已显示" if getattr(self, "_dev_btn_shown", False) else "完全不可见") + "\n")
            txt.insert(tk.END, "dev_mode = " + str(self.dev_mode_on()) + "\n")
            for k in ("task_manager", "small_tools", "mod_fqm"):
                txt.insert(tk.END, f"feature {k} = {self.feature_on(k)}\n")
            self.dev_log("隐藏按钮可见性检查")

        def reload_ui():
            self.show_main_menu()
            self.dev_log("UI 重载")

        def apply_temp():
            try:
                w, h = int(w_var.get()), int(h_var.get())
                self.root.geometry(f"{w}x{h}")
            except ValueError:
                pass
            try:
                fs = int(f_var.get())
                self.root.option_add("*Font", ("微软雅黑", fs))
            except ValueError:
                pass
            self.dev_log("临时尺寸/字体调试")

        tk.Button(bf, text="控件树", command=show_tree, font=("微软雅黑", 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="隐藏按钮检查", command=check_hidden, font=("微软雅黑", 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="UI 重载", command=reload_ui, font=("微软雅黑", 10),
                  relief=tk.FLAT, bg="#ecf0f1", cursor="hand2").pack(side=tk.LEFT, padx=3)

        row = tk.Frame(win)
        row.pack(pady=4)
        tk.Label(row, text="临时调试 宽", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        w_var = tk.StringVar(value=str(self.win_w))
        tk.Entry(row, textvariable=w_var, width=5).pack(side=tk.LEFT, padx=2)
        tk.Label(row, text="高", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        h_var = tk.StringVar(value=str(self.win_h))
        tk.Entry(row, textvariable=h_var, width=5).pack(side=tk.LEFT, padx=2)
        tk.Label(row, text="字号", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        f_var = tk.StringVar(value="12")
        tk.Entry(row, textvariable=f_var, width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="应用（仅本次）", command=apply_temp,
                  font=("微软雅黑", 10), relief=tk.FLAT, bg="#ecf0f1",
                  cursor="hand2").pack(side=tk.LEFT, padx=4)

    # ---------- 日志开关 ----------
    def dev_log_toggle(self):
        cfg = STORE.seg("orbit3")
        cur = cfg.get("log_enabled", True)
        if cur:
            cfg["log_enabled"] = False
            if messagebox.askyesno("崩溃日志", "开发者日志已关闭。\n是否同时关闭崩溃日志输出？",
                                   parent=self._dev_parent()):
                cfg["crash_log_enabled"] = False
            STORE.save()
            messagebox.showinfo("完成", "日志已关闭。", parent=self._dev_parent())
        else:
            cfg["log_enabled"] = True
            cfg["crash_log_enabled"] = True
            STORE.save()
            self.dev_log("日志重新开启")
            messagebox.showinfo("完成", "日志已开启（崩溃日志一并开启）。", parent=self._dev_parent())

    # ---------- 内存占用显示（主界面实时刷新） ----------
    def dev_memory_display(self):
        cfg = STORE.seg("orbit3")
        cur = cfg.get("show_memory", False)
        cfg["show_memory"] = not cur
        STORE.save()
        self.dev_log("内存占用显示 -> " + str(not cur))
        messagebox.showinfo("完成",
                            ("已开启。主界面标题下方会显示当前内存占用（实时刷新）。"
                             if not cur else "已关闭。内存占用显示已隐藏。"),
                            parent=self._dev_parent())
        self.show_main_menu()

    def _memory_tick(self):
        """主界面内存占用 Label 的刷新回调"""
        lbl = getattr(self, "_mem_lbl", None)
        if lbl is None:
            return
        try:
            if not lbl.winfo_exists():
                return
            mb = self._get_memory_mb()
            if mb >= 0:
                lbl.config(text=f"内存占用：{mb:.1f} MB")
        except Exception:
            pass
        self.root.after(2000, self._memory_tick)

    # ---------- 定时自动内存优化（Ultra） ----------
    def dev_auto_gc(self):
        cfg = STORE.seg("orbit3")
        cur = cfg.get("auto_gc_enabled", False)
        cfg["auto_gc_enabled"] = not cur
        STORE.save()
        self.dev_log("定时自动内存优化 -> " + str(not cur))
        messagebox.showinfo("完成",
                            ("已开启。每 5 分钟静默回收一次内存。"
                             if not cur else "已关闭。"),
                            parent=self._dev_parent())

    # ---------- 更新日志显示方式（HTML / tk） ----------
    def dev_changelog_mode(self):
        cfg = STORE.seg("orbit3")
        cur = cfg.get("changelog_mode", "html")
        cfg["changelog_mode"] = "tk" if cur == "html" else "html"
        STORE.save()
        self.dev_log("更新日志显示方式 -> " + cfg["changelog_mode"])
        if cfg["changelog_mode"] == "html":
            messagebox.showinfo("已切换",
                                "更新日志现在用浏览器打开 README.html（更便于阅读）。",
                                parent=self._dev_parent())
        else:
            messagebox.showinfo("已切换",
                                "更新日志现在用原来的 tk 窗口显示。",
                                parent=self._dev_parent())

    # ---------- 10. 千万别点 ----------
    def dev_dont_click(self):
        box = tk.Toplevel(self._dev_win)
        box.title("最后警告")
        box.resizable(False, False)
        box.transient(self._dev_win)
        box.grab_set()
        win_w, win_h = 420, 170
        box.update_idletasks()
        x = (box.winfo_screenwidth() - win_w) // 2
        y = (box.winfo_screenheight() - win_h) // 2
        box.geometry(f"{win_w}x{win_h}+{x}+{y}")
        tk.Label(box, text="请不要点击「千万别点」，点后造成的作者概不负责",
                 font=("微软雅黑", 12, "bold"), fg="#e74c3c",
                 wraplength=380).pack(pady=(24, 14))
        row = tk.Frame(box)
        row.pack()
        tk.Button(row, text="是", font=("微软雅黑", 12, "bold"), width=8,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=lambda: (box.destroy(), self._dont_click_effects())
                  ).pack(side=tk.LEFT, padx=10)
        tk.Button(row, text="是", font=("微软雅黑", 12, "bold"), width=8,
                  bg="#e74c3c", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=lambda: (box.destroy(), self._dont_click_effects())
                  ).pack(side=tk.LEFT, padx=10)

    def _dont_click_effects(self):
        self.dev_log("点了「千万别点」")
        root = self.root
        colors = ["#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#3498db",
                  "#9b59b6", "#e67e22", "#1abc9c"]
        state = {"i": 0}

        def color_tick():
            state["i"] += 1
            if state["i"] > 60:
                try:
                    root.configure(bg="")
                except Exception:
                    pass
                return
            try:
                root.configure(bg=colors[state["i"] % len(colors)])
                x = root.winfo_x() + random.randint(-14, 14)
                y = root.winfo_y() + random.randint(-10, 10)
                root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
            except Exception:
                pass
            root.after(100, color_tick)

        color_tick()

        # 主菜单按钮会跑：鼠标一碰就跑
        try:
            for w in self.root.winfo_children():
                for b in w.winfo_children():
                    if b.winfo_class() == "Button":
                        b.bind("<Enter>", lambda e: e.widget.place(
                            relx=random.uniform(0.05, 0.75),
                            rely=random.uniform(0.15, 0.85)))
        except Exception:
            pass

        for i in range(1, 101):
            messagebox.showinfo("千万别点", f"说了别点。（{i}/100）")
        messagebox.showinfo("结束", "好了，玩够了吧。\n重启程序即可恢复正常。")

    # ==================================================================
    # 更新日志
    # ==================================================================
    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title("更新日志")
        win.geometry("560x680")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 280
        y = (win.winfo_screenheight() // 2) - 340
        win.geometry(f"560x680+{x}+{y}")

        header = tk.Frame(win, bg="#2c3e50")
        header.pack(fill=tk.X)
        tk.Label(header, text=APP_TITLE, font=("微软雅黑", 22, "bold"),
                 bg="#2c3e50", fg="white").pack(pady=(16, 0))
        tk.Label(header, text=APP_BETA, font=("微软雅黑", 11),
                 bg="#2c3e50", fg="#bdc3c7").pack(pady=(0, 12))

        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(14, 0))

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=500)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        author = self.get_mod_value("author", "CZY")
        desc = self.get_mod_value(
            "desc",
            "一款集学习计时、番茄钟、挑战、\n考试模拟与学习记录于一体的学习陪伴工具。")
        mod_name = self.get_mod_value("mod_name", "")
        mod_version = self.get_mod_value("mod_version", "")

        def section(title):
            tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, pady=(14, 0))
            tk.Label(inner, text=title, font=("微软雅黑", 14, "bold"),
                     fg=self.color_timer, anchor="w").pack(fill=tk.X, pady=(10, 4))

        def item(text, sub=None):
            tk.Label(inner, text="• " + text, font=("微软雅黑", 11),
                     fg="#2c3e50", anchor="w", justify="left",
                     wraplength=470).pack(fill=tk.X, anchor="w", pady=(2, 0))
            if sub:
                tk.Label(inner, text="    " + sub, font=("微软雅黑", 9),
                         fg="#95a5a6", anchor="w", justify="left",
                         wraplength=470).pack(fill=tk.X, anchor="w")

        tk.Label(inner, text=f"作者：{author}", font=("微软雅黑", 12, "bold"),
                 fg=self.color_primary).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text=desc, font=("微软雅黑", 10),
                 fg="#7f8c8d", justify="left").pack(anchor="w")

        if mod_name:
            tk.Label(inner, text=f"mod：{mod_name}  {mod_version}",
                     font=("微软雅黑", 10, "italic"),
                     fg=self.color_accent).pack(anchor="w", pady=(4, 0))

        # ---------- Orbit3（当前版本）----------
        section("🆕 Orbit3（当前版本）")
        item("三合一", "番茄钟4.2 + 任务管理器3.0 + 鼠标检测器")
        item("新增主菜单入口", "任务管理器 / 小功能 / 关闭窗口（mod 可改前两个按钮文字）")
        item("小功能", "鼠标检测器 / 音乐（可自定义网址）/ 倒计时纪念日 / 随机决定器")
        item("统一数据", "Orbit3_data.json；任务/鼠标数据首次启动只读合并，学习存档不读")
        item("任务标签", "正常学习 / 努力的我（创建即锁定，Pro 开发者模式可解锁删除）")
        item("预设新交互", "单击选中 / 双击直接应用 / 右键 修改·重命名·删除·复制")
        item("设置改名", "清理内存 → 清理程序垃圾（+ 更新日志记录 + log 日志）")
        item("mod 扩展", "8 个新 key（task_manager_btn_text 等）+ task / ui 类别")
        item("Pro 版", "连点大标题 8 下开启开发者模式，10 项特别设置")
        item("Ultra 版", "附件系统 / HTML 更新日志 / 内存优化 / 多开")
        item("版本号", "Orbit3 / Orbit 3（原番茄钟5.0）")

        # ---------- Orbit 2 ----------
        section("Orbit 2")
        item("版本号升级", "番茄钟 4.2 / Orbit 2")
        item("新增「教程」按钮", "主菜单位于「mod 使用方法」和「更新日志」之间")
        item("教程内容", "12 页图文引导，新手友好，可上一步/下一步/跳过")
        item("mod 使用方法新增按钮", "「生成示例 fqm 与 almfq 文件」")
        item("生成的示例文件", "example.fqm（全项含注释）+ example.almfq（全指令含注释）")
        item("新增 window_title 字段", "可单独设置窗口标题条上的文字，不影响主界面大字")
        item("数据文件升级", "study_dataV4.2.json（自动迁移 V4.0）")
        item("Orbit 1 移入老版本列表")

        # ---------- Orbit 1 ----------
        section("Orbit 1")
        item("版本号进入 4.0", "番茄钟 4.0 / Orbit 1")
        item("新增 loc 1 内置", "老版本列表补上最古老的一版（内置，不依赖文件）")
        item("学习模式置顶变色", "选择模式列表里加 ★ 标记，推荐使用")
        item("脑筋急转弯改造", "输入答案，答对休息 +1 分钟")
        item("新增 mod 系统", ".fqm 皮肤 + .almfq 冲突规则")
        item("新增主界面按钮", "mod 使用方法")
        item("原「简介」改名", "→ 更新日志")
        item("Nova 2 移入老版本列表")

        # ---------- Nova 2 ----------
        section("Nova 2")
        item("新增「现在时间」模式", "大字显示时:分:秒，配中文日期与星期")
        item("模式选择列表新增「现在时间，正计时」按钮")
        item("简介窗口 → 更新日志窗口", "改成可滚动的版本更新说明")
        item("因为效果不佳删除两个番茄模式", "番茄钟 · 自定义 / 番茄钟 · 连续")

        # ---------- Nova 1 ----------
        section("Nova 1")
        item("这是一个划时代的版本", "从 beta 的不成熟版本进入 nova 测试版本")
        item("全新主菜单界面", "标题 + 简介 + 设置三大入口")
        item("选择模式加入加载进度条", "0% → 100% 后弹出模式列表")
        item("学习模式新增「极简展示」按钮", "需先开启「学习模式自动」")
        item("新增两个番茄模式", "番茄钟 · 自定义 / 番茄钟 · 连续")
        item("极简模式可自定义窗口大小")
        item("学习模式统计区拆分", "今日学习时长 / 总学习时长")
        item("设置新增", "选择其他 JSON / 备份 JSON / 导出为 CSV / 生成 PNG 报告")
        item("设置新增", "新存档（红色，危险操作）")
        item("数据文件升级", "study_dataV3.2.json（自动迁移旧版本）")

        # ---------- beta 5 ----------
        section("beta 5")
        item("新增「我的学习记录」模式", "6 行表格 + 合计行，含挑战积分与自由时间")
        item("新增统计数据字段", "各模式的时长与次数分别统计")
        item("名言功能", "可自定义不超过 10 个字的名言")
        item("修复BUG", "修复了 beta 2 的 BUG")
        item("文件改为 PYW", "更加简洁")

        # ---------- beta 4 ----------
        section("beta 4")
        item("学习模式新增「设置名言」按钮")
        item("数据文件升级至 V3", "study_dataV3.json")
        item("挑战时间可选 1/10/100/200/300/500/1000/10000/100000/999999 秒")

        # ---------- beta 3 ----------
        section("beta 3")
        item("新增「极简模式」", "自定义时长，大字倒计时")
        item("新增「极简番茄模式」", "25 分钟一个番茄，自动计数")
        item("考试模式支持自定义时长")
        item("学习模式加入实时时钟")
        item("数据文件升级至 V2", "study_dataV2.json")

        # ---------- beta 2 ----------
        section("beta 2")
        item("扩充脑筋急转弯题库至 100 条")
        item("扩充励志名言至 100 条")
        item("挑战时间支持更长秒数")
        item("猜数字游戏加入调侃弹窗")

        # ---------- beta 1 ----------
        section("beta 1")
        item("加入模式选择", "学习 / 挑战 / 考试")
        item("加入 JSON 数据保存", "study_data.json")
        item("挑战模式：完成计时赢积分")
        item("积分兑换自由时间", "1 积分 = 1 分钟，版本 BUG，该功能暂未实现")
        item("考试模式：极简倒计时大字")

        # ---------- Alpha 1 ----------
        section("Alpha 1")
        item("番茄钟雏形", "25 分钟学习 + 5 分钟休息 + 每 4 个长休息")
        item("休息娱乐区", "脑筋急转弯 / 猜数字 / 励志名言")
        item("纯内存数据", "关闭程序即丢失")

        # ---------- loc 1 ----------
        section("loc 1")
        item("仅时钟，因版本古老无备份，无法选择", "在 Orbit 1 中以内置方式复活")

        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=(10, 14))

    # ==================================================================
    # mod 使用方法
    # ==================================================================
    def show_mod_help(self):
        win = tk.Toplevel(self.root)
        win.title("mod 使用方法")
        win.geometry("600x720")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 300
        y = (win.winfo_screenheight() // 2) - 360
        win.geometry(f"600x720+{x}+{y}")

        header = tk.Frame(win, bg=self.color_primary)
        header.pack(fill=tk.X)
        tk.Label(header, text="📖 mod 使用方法",
                 font=("微软雅黑", 20, "bold"),
                 bg=self.color_primary, fg="white").pack(pady=14)

        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(14, 0))

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=540)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        def sec(t):
            tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, pady=(14, 0))
            tk.Label(inner, text=t, font=("微软雅黑", 14, "bold"),
                     fg=self.color_timer, anchor="w").pack(fill=tk.X, pady=(10, 4))

        def para(t):
            tk.Label(inner, text=t, font=("微软雅黑", 10),
                     fg="#2c3e50", anchor="w", justify="left",
                     wraplength=520).pack(fill=tk.X, anchor="w", pady=(2, 0))

        def code(t):
            box = tk.Frame(inner, bg="#f4f6f8", bd=1, relief=tk.SOLID)
            box.pack(fill=tk.X, pady=(4, 4))
            tk.Label(box, text=t, font=("Consolas", 10),
                     bg="#f4f6f8", fg="#2c3e50", anchor="w",
                     justify="left").pack(fill=tk.X, padx=8, pady=6)

        sec("一、mod 是什么")
        para("mod 让你在不修改程序的情况下，改掉界面标题、副标题、作者、")
        para("学习时长、各种颜色、窗口大小……")
        para("")
        para("mod 只改外观和行为，不碰成绩。json 存档里的数据（番茄数、")
        para("总时长、积分……）永远不受 mod 影响。")

        sec("二、.fqm 文件（皮肤包）")
        para("位置：主程序同目录下的 mods/ 文件夹")
        para("格式：纯文本，每行一条，key:值")
        para("")
        para("示例：")
        code('title:"我的番茄钟"\n'
             'window_title:"学习时间"\n'
             'beta:"特别版"\n'
             'author:"张三"\n'
             'study_time:30\n'
             'break_time:10\n'
             'color_primary:"#e74c3c"\n'
             'challenge_times:100,200,300\n'
             'window_width:800\n'
             'window_height:700')

        sec("三、.fqm 能改哪些东西（共 20 项）")
        para("📝 文字类：")
        para("    title / window_title / beta / author / desc / motto /")
        para("    mod_name / mod_version")
        para("")
        para("⏱ 时长类：")
        para("    study_time / break_time / long_break_time /")
        para("    simple_pomodoro_time")
        para("")
        para("🎨 颜色类：")
        para("    color_primary / color_timer / color_bg / color_accent")
        para("")
        para("⚙ 行为类：")
        para("    challenge_times / default_mode /")
        para("    window_width / window_height")
        para("")
        para("【title 与 window_title 的区别】")
        para("    title         →  主菜单上的大字")
        para("    window_title  →  窗口标题条上的字")
        para("    两个互不影响，可以只写一个")

        sec("四、多个 .fqm 怎么办？")
        para("如果你只放了一个 .fqm → 直接生效，不需要别的。")
        para("")
        para("如果放了多个 .fqm → 必须提供 .almfq 文件，")
        para("否则所有 .fqm 全部失效。")
        para("")
        para("按「设置 → 选择 almfq 文件」手动指定 .almfq 的位置。")

        sec("五、.almfq 文件（冲突规则）")
        para("三种指令：let / class / kill")

        para("")
        para("【let】决定加载顺序")
        code('let modA.fqm modB.fqm modC.fqm\n'
             '    ← 直接列文件名\n'
             '\n'
             'let f,a,m\n'
             '    ← 先读 f 开头，再读 a 开头，再读 m 开头\n'
             '\n'
             'let no modX.fqm\n'
             '    ← 彻底不读 modX（modX 等于不存在）\n'
             '\n'
             'let no modA.fqm,modB.fqm\n'
             '    ← 排除多个\n'
             '\n'
             'let no all\n'
             '    ← 排除全部（等于关掉 mod）')

        para("")
        para("【class】同 key 冲突时的取值策略")
        code('class number big,middle\n'
             '    ← number 类：1~2 个 mod 写时取最大，\n'
             '      3 个以上时取中间\n'
             '\n'
             'class number big,middle &\n'
             '    ← 行尾加 " &"，禁用这条\n'
             '\n'
             'class & class string first,last\n'
             '    ← 禁用上一条 class，同时定义 string 类')

        para("可用策略：")
        para("    big      → 取最大值")
        para("    small    → 取最小值")
        para("    middle   → 取中间值")
        para("    first    → 第一个加载的 mod 的值")
        para("    last     → 最后一个加载的 mod 的值")
        para("    数字 N   → 取第 N 个加载的 mod 的值")

        para("")
        para("【kill】禁用某个 mod 的某个 key")
        code('kill modA.fqm-title\n'
             '    ← 禁掉 modA 的 title\n'
             '\n'
             'kill modA.fqm,modB.fqm-title\n'
             '    ← 禁掉两个 mod 的 title\n'
             '\n'
             'kill all-title\n'
             '    ← 禁掉所有 mod 的 title\n'
             '\n'
             'kill all-title@modA.fqm\n'
             '    ← 禁掉所有，唯独 modA 保留\n'
             '\n'
             'kill all-title@modA.fqm,modB.fqm\n'
             '    ← 例外名单可以有多个\n'
             '\n'
             'kill all-title@all\n'
             '    ← 全部豁免 = 等于没写')

        sec("六、常见问题")
        para("Q: 成绩会丢吗？")
        para("A: 不会。mod 只改外观和参数，绝不碰 json 成绩数据。")
        para("")
        para("Q: 忘了 almfq 会怎样？")
        para("A: 多个 .fqm 会全部失效，但程序不会崩。")
        para("")
        para("Q: 没有 class 规则时同 key 谁赢？")
        para("A: 按 let 排出的顺序，最后一个定义该 key 的 fqm 赢。")
        para("")
        para("Q: almfq 必须放哪？")
        para("A: 位置任意，在「设置 → 选择 almfq 文件」里手动指定即可。")
        para("")
        para("Q: 只放一个 .fqm 需要 almfq 吗？")
        para("A: 不需要，1 个 .fqm 直接生效。")

        bottom = tk.Frame(win)
        bottom.pack(pady=(10, 14))

        tk.Button(bottom, text="📄 生成示例 fqm 与 almfq 文件",
                  command=self.generate_example_files,
                  font=("微软雅黑", 11),
                  bg=self.color_primary, fg="white",
                  relief=tk.FLAT, cursor="hand2",
                  width=26).pack(side=tk.LEFT, padx=6)

        tk.Button(bottom, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(side=tk.LEFT, padx=6)

    # ==================================================================
    # 教程（新手引导）
    # ==================================================================
    def show_tutorial(self):
        pages = [
            {
                "title": "👋 欢迎使用 " + APP_TITLE,
                "content": (
                    "你好！这是「番茄钟」的新手教程。\n\n"
                    "「番茄钟」是一个学习陪伴工具，可以帮助你：\n\n"
                    "  •  用番茄工作法专注学习\n"
                    "  •  记录每天的学习时长\n"
                    "  •  通过挑战赚积分，兑换休息时间\n"
                    "  •  用 mod 定制界面外观\n\n"
                    "下面会用 12 页带你过一遍所有功能。\n"
                    "点「下一步」开始，或点「跳过」直接使用。"
                ),
            },
            {
                "title": "📌 选择模式",
                "content": (
                    "主菜单 → 选择模式。\n\n"
                    "进入后会看到 8 个模式的列表：\n\n"
                    "  ★ 学习模式        推荐，番茄工作法\n"
                    "  现在时间          单纯的时钟\n"
                    "  挑战模式          完成计时赢积分\n"
                    "  极简模式          自定义倒计时\n"
                    "  考试模式          模拟考试倒计时\n"
                    "  极简番茄          简化的番茄钟\n"
                    "  正计时模式        从 0 往上累计\n"
                    "  我的学习记录      数据统计\n\n"
                    "选好后点「确认选择」。"
                ),
            },
            {
                "title": "★ 学习模式（推荐）",
                "content": (
                    "这是最核心的功能，番茄工作法：\n\n"
                    "  25 分钟专注学习 → 5 分钟休息\n"
                    "  每完成 4 个番茄 → 15 分钟长休息\n\n"
                    "操作：\n"
                    "  1. 点「开始学习」开始倒计时\n"
                    "  2. 中途可点「暂停」/「重置」\n"
                    "  3. 时间到后自动进入休息\n\n"
                    "底部还有：\n"
                    "  •  统计区（今日番茄数 / 今日时长 / 总时长）\n"
                    "  •  娱乐区（休息时开放，猜谜 / 猜数字 / 名言）\n"
                    "  •  积分兑换（用挑战积分换休息时间）"
                ),
            },
            {
                "title": "🎮 学习模式的娱乐区",
                "content": (
                    "只有「休息时间」才能玩娱乐区，\n"
                    "这是为了防止你学习时摸鱼。\n\n"
                    "🎯 猜个脑筋急转弯\n"
                    "  输入答案 → 答对休息 +1 分钟\n"
                    "  答错会公布正确答案\n\n"
                    "🔢 玩猜数字游戏\n"
                    "  猜 1-100 之间的数字\n\n"
                    "✨ 看句励志名言\n"
                    "  随机抽一句名言鼓励你\n\n"
                    "💎 积分兑换自由时间\n"
                    "  用挑战模式赚的积分换休息时长\n"
                    "  1 积分 = 1 分钟"
                ),
            },
            {
                "title": "🔥 挑战模式",
                "content": (
                    "选择挑战时长后开始倒计时。\n\n"
                    "规则：\n"
                    "  完成计时（不暂停、不重置）即可获得积分\n\n"
                    "  100 秒  =  1 积分\n"
                    "  200 秒  =  2 积分\n"
                    "  300 秒  =  3 积分\n"
                    "  …\n\n"
                    "积分可以在学习模式里兑换休息时间。\n"
                    "（挑战也计入今日学习时长）"
                ),
            },
            {
                "title": "⏱ 极简模式 / 考试模式",
                "content": (
                    "【极简模式】\n"
                    "  输入分钟数 → 大字倒计时\n"
                    "  窗口可以自由调整大小\n\n"
                    "【考试模式】\n"
                    "  输入考试时长 → 大字倒计时\n"
                    "  到时间会提示交卷\n"
                    "  中途也可以手动点「交卷」\n\n"
                    "两个模式都很清爽，只显示时间。"
                ),
            },
            {
                "title": "🍅 极简番茄 / 正计时",
                "content": (
                    "【极简番茄】\n"
                    "  25 分钟一个番茄，自动计数\n"
                    "  比学习模式更简单，没有休息\n"
                    "  记录本次完成的番茄个数\n\n"
                    "【正计时】\n"
                    "  从 0 开始累计\n"
                    "  随时点「结束并保存」记入学习记录\n"
                    "  适合自由学习，不限时长"
                ),
            },
            {
                "title": "🕰 现在时间 / 我的学习记录",
                "content": (
                    "【现在时间】\n"
                    "  只显示当前的 时:分:秒 + 日期 + 星期\n"
                    "  不带任何计时功能，纯时钟\n\n"
                    "【我的学习记录】\n"
                    "  汇总所有模式的数据：\n"
                    "    •  每个模式的完成次数\n"
                    "    •  每个模式的累计时长\n"
                    "    •  总学习时长\n"
                    "    •  挑战积分、可用自由时间\n"
                    "  也可以在这里一键清空记录"
                ),
            },
            {
                "title": "⚙ 设置",
                "content": (
                    "主菜单 → 设置。所有设置都在这：\n\n"
                    "  ☐  学习模式自动\n"
                    "      开启后学习模式自动跑番茄，不用手点\n\n"
                    "  ☐  开启自定义大小\n"
                    "      开启后所有模式窗口都能拖拽调整大小\n\n"
                    "  [选择其他 JSON]  切换存档\n"
                    "  [备份 JSON]      备份当前存档\n"
                    "  [导出为 CSV]     导出统计表\n"
                    "  [生成 PNG 报告]  生成图表报告\n"
                    "  [清理内存]       清掉旧的时间记录\n"
                    "  [老版本]         启动历史版本"
                ),
            },
            {
                "title": "🎨 mod 相关（一）",
                "content": (
                    "「设置」里有一块「mod 相关」：\n\n"
                    "  [选择 almfq 文件]\n"
                    "    多个 .fqm 冲突时的规则文件\n"
                    "    （只放 1 个 fqm 时不需要）\n\n"
                    "  [重新扫描 mods]\n"
                    "    改完 mods/ 文件夹后点这个生效\n\n"
                    "  [当前 mod 状态]\n"
                    "    查看当前加载了哪些 mod、\n"
                    "    每个 key 最终取了什么值\n\n"
                    "详细的 .fqm / .almfq 语法请看\n"
                    "主菜单 → mod 使用方法。"
                ),
            },
            {
                "title": "🎨 mod 相关（二）",
                "content": (
                    "简单来说：\n\n"
                    "  .fqm  =  皮肤包\n"
                    "    放在 mods/ 文件夹里\n"
                    "    可以改：标题、副标题、作者、\n"
                    "    时长、颜色、窗口大小……\n"
                    "    但绝对不能改成绩（番茄数、积分等）\n\n"
                    "  .almfq  =  冲突规则\n"
                    "    只在有多个 .fqm 时用\n"
                    "    位置任意，在设置里手动指定\n\n"
                    "不会写？\n"
                    "→ 打开「mod 使用方法」→ 点底部\n"
                    "  「生成示例 fqm 与 almfq 文件」\n"
                    "会自动生成一份带注释的示例，\n"
                    "照着改就行。"
                ),
            },
            {
                "title": "❓ 常见问题",
                "content": (
                    "Q：数据保存在哪？\n"
                    "A：同目录下的 study_dataV4.2.json。\n\n"
                    "Q：换电脑了怎么办？\n"
                    "A：把整个文件夹拷过去即可。\n\n"
                    "Q：想清空重来？\n"
                    "A：设置 → 新存档（红色按钮）。\n\n"
                    "Q：老版本还能玩吗？\n"
                    "A：设置 → 老版本，可以启动历史版本。\n\n"
                    "Q：遇到了 bug？\n"
                    "A：备份 JSON 后重启程序。\n"
                    "   bug 不影响 json 存档。\n\n"
                    "祝你学习愉快！🎉"
                ),
            },
        ]

        win = tk.Toplevel(self.root)
        win.title("教程")
        win.geometry("620x520")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 310
        y = (win.winfo_screenheight() // 2) - 260
        win.geometry(f"620x520+{x}+{y}")

        header = tk.Frame(win, bg=self.color_primary)
        header.pack(fill=tk.X)

        title_var = tk.StringVar(value="")
        tk.Label(header, textvariable=title_var,
                 font=("微软雅黑", 16, "bold"),
                 bg=self.color_primary, fg="white",
                 anchor="w", padx=18, pady=12).pack(fill=tk.X)

        body_frame = tk.Frame(win)
        body_frame.pack(fill=tk.BOTH, expand=True, padx=22, pady=(16, 8))

        content_label = tk.Label(body_frame, text="",
                                 font=("微软雅黑", 11),
                                 fg="#2c3e50", justify="left",
                                 anchor="nw", wraplength=560)
        content_label.pack(fill=tk.BOTH, expand=True, anchor="nw")

        footer = tk.Frame(win)
        footer.pack(fill=tk.X, padx=22, pady=(0, 14))

        page_var = tk.StringVar(value="")
        tk.Label(footer, textvariable=page_var,
                 font=("微软雅黑", 10), fg="#95a5a6").pack(side=tk.LEFT)

        state = {"idx": 0}

        btn_next = tk.Button(footer, text="下一步",
                             font=("微软雅黑", 11), width=10,
                             bg=self.color_primary, fg="white",
                             relief=tk.FLAT, cursor="hand2")
        btn_next.pack(side=tk.RIGHT, padx=4)

        btn_prev = tk.Button(footer, text="上一步",
                             font=("微软雅黑", 11), width=10,
                             relief=tk.FLAT, cursor="hand2")
        btn_prev.pack(side=tk.RIGHT, padx=4)

        tk.Button(footer, text="跳过",
                  command=win.destroy,
                  font=("微软雅黑", 10), width=8,
                  relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)

        def render():
            i = state["idx"]
            p = pages[i]
            title_var.set(p["title"])
            content_label.config(text=p["content"])
            page_var.set(f"{i + 1} / {len(pages)}")

            btn_prev.config(state=(tk.NORMAL if i > 0 else tk.DISABLED))
            if i == len(pages) - 1:
                btn_next.config(text="完成")
            else:
                btn_next.config(text="下一步")

        def go_prev():
            if state["idx"] > 0:
                state["idx"] -= 1
                render()

        def go_next():
            if state["idx"] < len(pages) - 1:
                state["idx"] += 1
                render()
            else:
                win.destroy()

        btn_prev.config(command=go_prev)
        btn_next.config(command=go_next)

        render()

    # ==================================================================
    # 生成示例 fqm / almfq 文件
    # ==================================================================
    def generate_example_files(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()

        mods_dir = os.path.join(base_dir, "mods")
        fqm_path = os.path.join(mods_dir, "example.fqm")
        almfq_path = os.path.join(base_dir, "example.almfq")

        existing = []
        if os.path.exists(fqm_path):
            existing.append(fqm_path)
        if os.path.exists(almfq_path):
            existing.append(almfq_path)
        if existing:
            msg = "以下文件已存在：\n" + "\n".join("  • " + p for p in existing)
            msg += "\n\n是否覆盖？"
            if not messagebox.askyesno("文件已存在", msg):
                return

        if not os.path.isdir(mods_dir):
            try:
                os.makedirs(mods_dir)
            except Exception as e:
                messagebox.showerror("失败", f"无法创建 mods 文件夹：\n{e}")
                return

        fqm_content = '''# ============================================
# 示例 .fqm 文件（自动生成）
# 位置：mods/example.fqm
# 说明：这是皮肤包，放在 mods/ 文件夹里即可生效
#       下面所有 key 都写出来了，你可以删掉不需要的
# ============================================

# ---------- 文字类 ----------
# 主标题（显示在窗口顶部、报告、CSV 里）
title:"我的番茄钟"

# 窗口标题条上的字（仅影响任务栏/标题栏，不影响主菜单大字）
window_title:"学习时间"

# 副标题（主菜单下面的小字）
beta:"MyMod"

# 作者（显示在更新日志里）
author:"你的名字"

# 一句话简介（显示在更新日志里）
desc:"这是我定制的学习助手。"

# 学习模式的默认名言（不超过 10 个字）
motto:"静能生慧"

# mod 自己的名字（会显示在更新日志里）
mod_name:"示例 Mod"

# mod 自己的版本号
mod_version:"1.0"

# ---------- 时长类（单位：分钟）----------
# 学习模式：学习时长
study_time:25

# 学习模式：短休息时长
break_time:5

# 学习模式：长休息时长（每 4 个番茄后）
long_break_time:15

# 极简番茄：单次番茄时长
simple_pomodoro_time:25

# ---------- 颜色类（十六进制 #RRGGBB）----------
# 主色（开始按钮、★ 标记等）
color_primary:"#2ecc71"

# 计时数字颜色（主菜单标题、大计时字）
color_timer:"#2c3e50"

# 主背景色（暂未全面应用，保留）
color_bg:"#ffffff"

# 强调色（部分文字、图表颜色）
color_accent:"#e67e22"

# ---------- 行为类 ----------
# 挑战模式可选的秒数列表（逗号分隔）
challenge_times:1,10,100,200,300,500,1000,10000,100000,999999

# 启动后默认进入的模式
# 可选值：main（主菜单）/ clock / learning / challenge /
#         simple / exam / simple_pomodoro / count_up / records
default_mode:"main"

# 默认窗口宽度（像素）
window_width:640

# 默认窗口高度（像素）
window_height:820

# ---------- Orbit3 新增 ----------
# 主菜单「任务管理器」按钮文字
task_manager_btn_text:"任务管理器"

# 主菜单「小功能」按钮文字
small_tools_btn_text:"小功能"

# 任务标签文字（普通）
tag_normal_text:"正常学习"

# 任务标签文字（锁定）
tag_effort_text:"努力的我"

# 锁定标签颜色
tag_effort_color:"#e74c3c"

# 新建任务默认分类
task_default_category:"学习"

# 新建任务默认标签
task_default_tag:"正常学习"

# ============================================
# 注意：
#   •  title 管主界面大字
#   •  window_title 管窗口标题条
#   •  两个独立，可以只写一个
#   •  .fqm 只能改"外观"和"行为参数"
#   •  不能改成绩（番茄数、总时长、积分等），写了也无效
#   •  只有 1 个 .fqm 时直接生效
#   •  有多个 .fqm 时必须提供 .almfq 文件
# ============================================
'''

        almfq_content = '''# ============================================
# 示例 .almfq 文件（自动生成）
# 位置：example.almfq（主程序同目录，位置可自选）
# 说明：这是冲突规则文件
#       只在 mods/ 里有多个 .fqm 时才需要
#       在「设置 → 选择 almfq 文件」里手动指定它
# ============================================

# ============================================
# 指令一：let —— 决定加载顺序
# ============================================

# 写法 A：直接列文件名（不区分大小写）
# 让 f1.fqm 先读，再读 f2.fqm，再读 f3.fqm
# let f1.fqm f2.fqm f3.fqm

# 写法 B：按首字母分组（不区分大小写）
# 先读所有 a 开头的 fqm（组内按字母表顺序）
# 再读 b 开头的，再读 c 开头的
# let a,b,c

# 彻底不读某些 fqm（等于这些文件不存在）
# let no modX.fqm
# let no modA.fqm,modB.fqm
# let no all          ← 全部不读（等于关掉 mod 系统）

# 【示例】只加载 example.fqm
let example.fqm


# ============================================
# 指令二：class —— 同 key 冲突时的取值策略
# ============================================

# 语法：class <类别> <1~2个mod定义该key时的策略>,<3个及以上时的策略>
#
# 类别（自动识别，无需自己写）：
#   string  →  title / window_title / beta / author / desc / motto / ...
#   number  →  study_time / break_time / window_width / ...
#   color   →  color_primary / color_timer / ...
#   list    →  challenge_times
#   task    →  tag_normal_text / tag_effort_text / task_default_*（Orbit3）
#   ui      →  task_manager_btn_text / small_tools_*（Orbit3）
#
# 策略：
#   big      取最大值（仅 number）
#   small    取最小值（仅 number）
#   middle   取中间值（仅 number）
#   first    取第一个加载的 mod 的值
#   last     取最后一个加载的 mod 的值
#   数字 N   取第 N 个加载的 mod 的值（1 表示第 1 个）

# 【示例】
class string last,last
class number big,middle
class color last,last
class task last,last
class ui last,last

# 禁用某条 class 规则的两种写法：
#   class number big,middle &        ← 行尾加 " &"（前面有空格），禁用自己
#   class & class number big,middle  ← 禁用上面那一条 class


# ============================================
# 指令三：kill —— 禁用某 mod 的某个 key
# ============================================

# 语法：kill <范围>-<key>@<例外>
#   范围：单个 fqm / 多个用逗号分隔 / all（全部）
#   例外：单个 fqm / 多个用逗号分隔 / all（全部豁免）
#   @ 前面的 "-" 必须有

# 【示例】
# kill example.fqm-title                禁掉 example 的 title
# kill modA.fqm,modB.fqm-title          禁掉两个 mod 的 title
# kill all-title                        禁掉所有 mod 的 title
# kill all-title@example.fqm            禁掉所有，唯独 example 保留
# kill all-title@modA.fqm,modB.fqm      例外名单可以有多个
# kill all-title@all                    全部豁免 = 等于没写


# ============================================
# 完整示例：如何同时使用多个 mod
# ============================================
#
# 假设 mods/ 里有：
#   dark.fqm    暗色调主题
#   boost.fqm   增强学习
#
# 期望结果：
#   - boost 的时长覆盖 dark
#   - dark 的底色保留
#   - 主标题用 boost 的
#
# almfq 写：
#   let dark.fqm boost.fqm
#   class number last,last
#   class string last,last
#   class color first,last
#   kill dark.fqm-title        ← 不要 dark 的标题
#
# ============================================
'''

        errors = []
        try:
            with open(fqm_path, "w", encoding="utf-8") as f:
                f.write(fqm_content)
        except Exception as e:
            errors.append(f"写入 fqm 失败：{e}")

        try:
            with open(almfq_path, "w", encoding="utf-8") as f:
                f.write(almfq_content)
        except Exception as e:
            errors.append(f"写入 almfq 失败：{e}")

        if errors:
            messagebox.showerror("部分失败", "\n".join(errors))
            return

        messagebox.showinfo(
            "生成完成",
            f"已生成 2 个示例文件：\n\n"
            f"  📄  {fqm_path}\n"
            f"  📄  {almfq_path}\n\n"
            f"提示：\n"
            f"  •  example.fqm 已放在 mods/ 里，重启程序即可生效\n"
            f"  •  example.almfq 在「设置 → 选择 almfq 文件」里指定\n"
            f"  •  两个文件都带详细注释，照着改就行")

    # ==================================================================
    # 进度条 → 选择模式
    # ==================================================================
    def open_mode_selection_with_progress(self):
        prog_win = tk.Toplevel(self.root)
        prog_win.title("加载中")
        prog_win.geometry("420x130")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        prog_win.transient(self.root)
        prog_win.update_idletasks()
        x = (prog_win.winfo_screenwidth() // 2) - 210
        y = (prog_win.winfo_screenheight() // 2) - 65
        prog_win.geometry(f"420x130+{x}+{y}")

        tk.Label(prog_win, text="正在加载模式选择…",
                 font=("微软雅黑", 12)).pack(pady=(18, 8))
        bar = ttk.Progressbar(prog_win, orient="horizontal", length=340,
                              mode="determinate", maximum=100)
        bar.pack(pady=8)
        pct_label = tk.Label(prog_win, text="0%",
                             font=("微软雅黑", 10), fg="#7f8c8d")
        pct_label.pack()

        def step(val=0):
            if val > 100:
                try:
                    prog_win.grab_release()
                except Exception:
                    pass
                prog_win.destroy()
                self.show_mode_selection()
                return
            bar["value"] = val
            pct_label.config(text=f"{val}%")
            prog_win.after(12, lambda: step(val + 2))

        step(0)

    def show_mode_selection(self):
        self.clear_root()
        self.root.title(f"{APP_WINDOW_TITLE} - 选择模式")
        self.apply_window_resizable(False)
        self.root.geometry(f"{self.win_w}x{self.win_h}")

        tk.Label(self.root, text="📌 选择使用模式",
                 font=("微软雅黑", 20, "bold")).pack(pady=15)

        self.mode_var = tk.StringVar(value="")

        if self.feature_on("mode_learning"):
            tk.Radiobutton(self.root, text="★ 学习模式", variable=self.mode_var,
                           value="learning", font=("微软雅黑", 13, "bold"),
                           fg="#27ae60", activeforeground="#27ae60",
                           selectcolor="#eafaf1",
                           cursor="hand2").pack(pady=5)

        options = [
            ("现在时间", "clock"),
            ("挑战模式", "challenge"),
            ("极简模式", "simple"),
            ("考试模式", "exam"),
            ("极简番茄", "simple_pomodoro"),
            ("正计时模式", "count_up"),
            ("我的学习记录", "records"),
        ]
        for text, value in options:
            if not self.feature_on("mode_" + value):
                continue
            tk.Radiobutton(self.root, text=text, variable=self.mode_var,
                           value=value, font=("微软雅黑", 12),
                           cursor="hand2").pack(pady=4)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=18)
        tk.Button(btn_frame, text="确认选择", command=self.confirm_mode,
                  font=("微软雅黑", 12), bg=self.color_primary, fg="white",
                  width=12, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="返回主菜单", command=self.back_to_main_menu,
                  font=("微软雅黑", 12), width=12,
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

    def confirm_mode(self):
        selected = self.mode_var.get()
        if not selected:
            messagebox.showwarning("提示", "请选择一个模式！")
            return
        self.mode = selected
        self.mode_locked = True
        self.init_mode_ui()

    def back_to_mode_selection(self):
        self._settle_unfinished_study()
        self.is_running = False
        self.mode_locked = False
        self.mode = None
        self.compact_view = False
        self.show_mode_selection()

    def init_mode_ui(self):
        if self.mode == "clock":
            self.init_clock_mode()
        elif self.mode == "learning":
            self.init_learning_mode()
        elif self.mode == "challenge":
            self.init_challenge_mode()
        elif self.mode == "simple":
            self.init_simple_mode()
        elif self.mode == "exam":
            self.init_exam_mode()
        elif self.mode == "simple_pomodoro":
            self.init_simple_pomodoro_mode()
        elif self.mode == "count_up":
            self.init_count_up_mode()
        elif self.mode == "records":
            self.init_records_mode()

    # ==================================================================
    # 设置
    # ==================================================================
    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("460x600")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 230
        y = (win.winfo_screenheight() // 2) - 300
        win.geometry(f"460x600+{x}+{y}")

        tk.Label(win, text="⚙ 设置",
                 font=("微软雅黑", 18, "bold"),
                 fg=self.color_timer).pack(pady=(14, 6))

        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=430)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        auto_frame = tk.Frame(inner)
        auto_frame.pack(fill=tk.X, padx=30, pady=(10, 0))
        auto_var = tk.BooleanVar(value=self.auto_learning)

        def toggle_auto():
            self.auto_learning = auto_var.get()
            self.save_data()

        tk.Checkbutton(auto_frame, text="学习模式自动", variable=auto_var,
                       command=toggle_auto, font=("微软雅黑", 12),
                       cursor="hand2").pack(anchor="w")
        tk.Label(inner, text="开启后，学习模式和极简番茄将全部自动进行",
                 font=("微软雅黑", 9), fg="#95a5a6",
                 wraplength=380, justify="left").pack(anchor="w", padx=50, pady=(0, 6))

        size_frame = tk.Frame(inner)
        size_frame.pack(fill=tk.X, padx=30, pady=(6, 0))
        size_var = tk.BooleanVar(value=self.custom_size)

        def toggle_size():
            self.custom_size = size_var.get()
            self.save_data()
            self.apply_window_resizable(False)

        tk.Checkbutton(size_frame, text="开启自定义大小", variable=size_var,
                       command=toggle_size, font=("微软雅黑", 12),
                       cursor="hand2").pack(anchor="w")
        tk.Label(inner, text="开启后，所有模式的窗口大小均可自由调整",
                 font=("微软雅黑", 9), fg="#95a5a6",
                 wraplength=380, justify="left").pack(anchor="w", padx=50, pady=(0, 6))

        def mk_btn(text, cmd, desc=None, fg="#2c3e50", hover="#dfe6e9"):
            b = tk.Button(inner, text=text, command=cmd,
                          font=("微软雅黑", 12),
                          width=24, relief=tk.FLAT, bg="#ecf0f1", fg=fg,
                          cursor="hand2", activebackground=hover)
            b.pack(pady=(12, 0), ipady=4)
            if desc:
                tk.Label(inner, text=desc, font=("微软雅黑", 9),
                         fg="#95a5a6", wraplength=380,
                         justify="left").pack(anchor="w", padx=50, pady=(0, 2))
            return b

        mk_btn("选择其他 JSON", self.choose_json)
        mk_btn("备份 JSON", self.backup_json, "自选保存位置")
        mk_btn("导出为 CSV", self.export_csv)
        mk_btn("生成 PNG 报告", self.generate_png_report)
        mk_btn("清理程序垃圾", self.clean_garbage,
               "时间记录 + 更新日志 + log 里的崩溃/开发者日志")
        as_row = tk.Frame(inner)
        as_row.pack(pady=(12, 0))
        tk.Label(as_row, text="自动保存间隔（分钟，0=关闭）",
                 font=("微软雅黑", 12)).pack(side=tk.LEFT)
        as_var = tk.StringVar(value=str(self.data.get("auto_save_min", 1)))
        tk.Entry(as_row, textvariable=as_var, width=5,
                 font=("微软雅黑", 12)).pack(side=tk.LEFT, padx=6)
        def apply_auto_save():
            try:
                v = int(as_var.get())
                if v < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("输入错误", "请输入 ≥ 0 的整数")
                return
            self.data["auto_save_min"] = v
            self._auto_save_counter = 0
            self.save_data()
        tk.Button(as_row, text="应用", command=apply_auto_save,
                  font=("微软雅黑", 10), bg="#ecf0f1", fg="#2c3e50",
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)
        tk.Label(inner, text="关闭程序时也会自动保存",
                 font=("微软雅黑", 9), fg="#95a5a6").pack(anchor="w", padx=50)

        mem_row = tk.Frame(inner)
        mem_row.pack(pady=(10, 0))
        tk.Label(mem_row, text="内存优化", font=("微软雅黑", 12)).pack(side=tk.LEFT)
        tk.Button(mem_row, text="一键优化", command=self.optimize_memory,
                  font=("微软雅黑", 10), bg="#ecf0f1", fg="#2c3e50",
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=8)
        tk.Label(inner, text="回收垃圾对象、清空工作集（不清理学习数据）",
                 font=("微软雅黑", 9), fg="#95a5a6").pack(anchor="w", padx=50)

        tk.Label(inner, text="多开关闭后主界面操作", font=("微软雅黑", 12, "bold"),
                 fg=self.color_timer).pack(anchor="w", padx=50, pady=(12, 0))
        mc_var = tk.StringVar(value=STORE.seg("orbit3").get("close_behavior", "open"))
        def apply_close_beh():
            STORE.seg("orbit3")["close_behavior"] = mc_var.get()
            STORE.save()
        tk.Radiobutton(inner, text="打开（重新出现）", variable=mc_var, value="open",
                       command=apply_close_beh, font=("微软雅黑", 11),
                       cursor="hand2").pack(anchor="w", padx=70)
        tk.Radiobutton(inner, text="不出现（保持隐藏）", variable=mc_var, value="hide",
                       command=apply_close_beh, font=("微软雅黑", 11),
                       cursor="hand2").pack(anchor="w", padx=70)
        def more_settings():
            if not self.dev_mode_on():
                messagebox.showerror("提示", "没有开启开发者模式，请打开后再试")
                return
            self.open_dev_settings()
        tk.Button(inner, text="更多设置（打开开发者功能开关）", command=more_settings,
                  font=("微软雅黑", 10), bg="#ecf0f1", fg="#2c3e50",
                  relief=tk.FLAT, cursor="hand2").pack(anchor="w", padx=70, pady=(4, 0))

        mk_btn("old", self.show_old_versions,
               "启动 loc 1 / Alpha 1 / beta 1~5 / Nova 1/2 / Orbit 1/2")

        tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, padx=30, pady=(20, 0))
        tk.Label(inner, text="🎨 mod 相关",
                 font=("微软雅黑", 12, "bold"),
                 fg=self.color_accent).pack(pady=(12, 0))

        mk_btn("选择 almfq 文件", self.choose_almfq_file,
               "多个 .fqm 冲突时必需")
        mk_btn("重新扫描 mods", self.rescan_mods,
               "改动 mods/ 后手动触发")
        mk_btn("当前 mod 状态", self.show_mod_status)

        tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, padx=30, pady=(20, 0))
        new_btn = tk.Button(inner, text="新存档", command=self.new_archive,
                            font=("微软雅黑", 12), width=24, relief=tk.FLAT,
                            bg="#fdecea", fg="#e74c3c", cursor="hand2",
                            activebackground="#f8d7da",
                            activeforeground="#c0392b")
        new_btn.pack(pady=(14, 0), ipady=4)
        tk.Label(inner, text="这将会删除你现在的存档，小心开启，建议先备份",
                 font=("微软雅黑", 9), fg="#e74c3c",
                 wraplength=380, justify="left").pack(anchor="w",
                                                      padx=50, pady=(0, 20))

    def choose_almfq_file(self):
        path = filedialog.askopenfilename(
            title="选择 .almfq 文件",
            filetypes=[("almfq 文件", "*.almfq"), ("所有文件", "*.*")])
        if not path:
            return
        self.almfq_path = path
        self.save_data()
        messagebox.showinfo("完成", f"已指定 almfq：\n{path}\n\n请前往「重新扫描 mods」应用规则。")

    def rescan_mods(self):
        self.scan_and_load_mods()
        self.apply_mod_values()
        self.study_time = self.get_mod_value("study_time", 25) * 60
        self.break_time = self.get_mod_value("break_time", 5) * 60
        self.long_break_time = self.get_mod_value("long_break_time", 15) * 60
        self.pomodoro_simple_time = self.get_mod_value("simple_pomodoro_time", 25) * 60
        self.color_primary = self.get_mod_value("color_primary", "#2ecc71")
        self.color_timer = self.get_mod_value("color_timer", "#2c3e50")
        self.color_bg = self.get_mod_value("color_bg", "#ffffff")
        self.color_accent = self.get_mod_value("color_accent", "#e67e22")
        self.challenge_times = self.get_mod_value(
            "challenge_times", [1, 10, 100, 200, 300, 500, 1000, 10000, 100000, 999999])
        self.win_w = self.get_mod_value("window_width", 640)
        self.win_h = self.get_mod_value("window_height", 820)
        try:
            self.root.title(APP_WINDOW_TITLE)
        except Exception:
            pass
        messagebox.showinfo("完成", "已重新扫描 mods 文件夹。")

    def show_mod_status(self):
        win = tk.Toplevel(self.root)
        win.title("当前 mod 状态")
        win.geometry("500x480")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 250
        y = (win.winfo_screenheight() // 2) - 240
        win.geometry(f"500x480+{x}+{y}")

        tk.Label(win, text="🎨 当前 mod 状态",
                 font=("微软雅黑", 16, "bold"),
                 fg=self.color_timer).pack(pady=(14, 8))

        tk.Label(win, text="已加载的 .fqm：",
                 font=("微软雅黑", 12, "bold"), anchor="w").pack(
            fill=tk.X, padx=20)
        if self.mod_files_loaded:
            for fn in self.mod_files_loaded:
                tk.Label(win, text="  • " + fn,
                         font=("微软雅黑", 10),
                         fg="#27ae60", anchor="w").pack(fill=tk.X, padx=30)
        else:
            tk.Label(win, text="  （无）",
                     font=("微软雅黑", 10),
                     fg="#bdc3c7", anchor="w").pack(fill=tk.X, padx=30)

        tk.Label(win, text="已指定的 .almfq：",
                 font=("微软雅黑", 12, "bold"), anchor="w").pack(
            fill=tk.X, padx=20, pady=(12, 0))
        tk.Label(win, text="  " + (self.almfq_path or "（未指定）"),
                 font=("微软雅黑", 10),
                 fg="#3498db" if self.almfq_path else "#bdc3c7",
                 anchor="w", wraplength=440,
                 justify="left").pack(fill=tk.X, padx=30)

        tk.Label(win, text="当前生效的 mod 值：",
                 font=("微软雅黑", 12, "bold"), anchor="w").pack(
            fill=tk.X, padx=20, pady=(12, 0))
        txt_frame = tk.Frame(win)
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=6)
        txt = tk.Text(txt_frame, font=("Consolas", 10), wrap=tk.WORD,
                      bg="#f4f6f8", relief=tk.FLAT)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(txt_frame, command=txt.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.config(yscrollcommand=sb.set)
        if self.mod_values:
            for k, v in sorted(self.mod_values.items()):
                txt.insert(tk.END, f"{k} = {v}\n")
        else:
            txt.insert(tk.END, "（无 mod 生效）\n")
        txt.config(state=tk.DISABLED)

        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=10)

    # ==================================================================
    # 原有设置按钮
    # ==================================================================
    def choose_json(self):
        path = filedialog.askopenfilename(
            title="选择其他 JSON 数据文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("文件格式不正确")
        except Exception as e:
            messagebox.showerror("错误", f"读取失败：{e}")
            return

        if not messagebox.askyesno("确认",
                                   "将载入该数据文件并替换当前内存中的数据，\n是否继续？"):
            return

        self.data_file = path
        self.data = data
        for k, v in self.get_default_data().items():
            self.data.setdefault(k, v)
        self.apply_data_to_state()
        self.save_data()
        messagebox.showinfo("完成", f"已切换到：\n{path}")

    def backup_json(self):
        path = filedialog.asksaveasfilename(
            title="备份 JSON（自选保存位置）",
            defaultextension=".json",
            initialfile=f"study_backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.json",
            filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            self.save_data()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("完成", f"备份成功：\n{path}")
        except Exception as e:
            messagebox.showerror("错误", f"备份失败：{e}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="导出为 CSV",
            defaultextension=".csv",
            initialfile=f"study_report_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        try:
            rows = self.get_record_rows()
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([f"{APP_TITLE} 学习报告"])
                w.writerow(["导出时间",
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                w.writerow([])
                w.writerow(["模式", "完成情况", "累计时长（秒）", "累计时长"])
                for name, count, secs in rows:
                    w.writerow([name, count, secs, self.format_duration(secs)])
                total = sum(r[2] for r in rows)
                w.writerow([])
                w.writerow(["合计", "", total, self.format_duration(total)])
                w.writerow([])
                w.writerow(["日期", "学习时长（秒）"])
                for k in sorted(self.daily_study.keys()):
                    w.writerow([k, self.daily_study[k]])
                w.writerow([])
                w.writerow(["挑战积分", self.challenge_score])
                w.writerow(["可用自由时间（分钟）", self.free_time // 60])
                w.writerow(["我的名言", self.motto])
            messagebox.showinfo("完成", f"已导出：\n{path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败：{e}")

    def _pil_font(self, size):
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def generate_png_report(self):
        if not PIL_AVAILABLE:
            messagebox.showwarning("提示",
                                   "未检测到 Pillow，无法生成 PNG 报告。\n\n请先安装：\npip install Pillow")
            return
        path = filedialog.asksaveasfilename(
            title="保存 PNG 报告",
            defaultextension=".png",
            initialfile=f"study_report_{datetime.datetime.now():%Y%m%d_%H%M%S}.png",
            filetypes=[("PNG 图片", "*.png")])
        if not path:
            return
        try:
            W, H = 960, 820
            img = Image.new("RGB", (W, H), "white")
            d = ImageDraw.Draw(img)

            f_title = self._pil_font(36)
            f_sub = self._pil_font(18)
            f_label = self._pil_font(20)
            f_small = self._pil_font(15)
            f_total = self._pil_font(28)

            d.rectangle([0, 0, W, 92], fill="#2c3e50")
            d.text((36, 26), f"{APP_TITLE}  学习报告",
                   font=f_title, fill="white")
            d.text((W - 300, 40),
                   datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                   font=f_sub, fill="#bdc3c7")

            rows = self.get_record_rows()
            max_sec = max([r[2] for r in rows] + [1])

            y = 140
            colors = ["#3498db", "#e74c3c", "#e67e22", "#9b59b6",
                      "#f39c12", "#1abc9c", "#2ecc71"]
            for i, (name, count, secs) in enumerate(rows):
                d.text((36, y), name, font=f_label, fill="#2c3e50")
                d.text((36, y + 28), f"{count} ｜ {self.format_duration(secs)}",
                       font=f_small, fill="#7f8c8d")

                bar_x, bar_y = 360, y + 6
                bar_max_w = W - bar_x - 60
                w = int(bar_max_w * secs / max_sec)
                d.rectangle([bar_x, bar_y, bar_x + bar_max_w, bar_y + 30],
                            fill="#f0f2f4")
                if w > 0:
                    d.rectangle([bar_x, bar_y, bar_x + max(w, 8), bar_y + 30],
                                fill=colors[i % len(colors)])
                y += 82

            total = sum(r[2] for r in rows)
            d.rectangle([0, H - 100, W, H], fill="#ecf0f1")
            d.text((36, H - 74), f"累计学习时长：{self.format_duration(total)}",
                   font=f_total, fill="#e67e22")
            d.text((36, H - 30),
                   f"挑战积分：{self.challenge_score}   ｜   可用自由时间：{self.free_time // 60} 分钟"
                   f"   ｜   今日学习：{self.format_duration(self.daily_study.get(self.today_key(), 0))}",
                   font=f_small, fill="#7f8c8d")

            img.save(path, "PNG")
            messagebox.showinfo("完成", f"PNG 报告已生成：\n{path}")
        except Exception as e:
            messagebox.showerror("错误", f"生成失败：{e}")

    def new_archive(self):
        if not messagebox.askyesno("⚠ 危险操作",
                                   "这将会删除你现在的存档！\n建议先备份。\n\n确定要新建存档吗？"):
            return
        if not messagebox.askyesno("再次确认",
                                   "真的要清空所有数据吗？\n此操作不可恢复！"):
            return
        self.data = self.get_default_data()
        self.apply_data_to_state()
        self.save_data()
        messagebox.showinfo("完成", "已创建新存档，所有数据已清空。")

    def clean_memory(self):
        if not messagebox.askyesno(
                "确认清理",
                "将要清理以下内容：\n\n"
                "  • 保存历史记录（save_history）\n"
                "  • 30 天前的每日学习记录（daily_study）\n\n"
                "此操作不可恢复，确定继续吗？"):
            return

        removed_items = []
        hist = self.data.get("save_history", [])
        if hist:
            removed_items.append(f"保存历史记录 {len(hist)} 条")
            self.data["save_history"] = []

        if self.daily_study:
            today = datetime.date.today()
            cutoff = today - datetime.timedelta(days=30)
            kept = {}
            removed_days = 0
            for k, v in self.daily_study.items():
                try:
                    d = datetime.datetime.strptime(k, "%Y-%m-%d").date()
                    if d >= cutoff:
                        kept[k] = v
                    else:
                        removed_days += 1
                except Exception:
                    kept[k] = v
            if removed_days:
                removed_items.append(f"30 天前的每日学习记录 {removed_days} 天")
                self.daily_study = kept
                self.data["daily_study"] = kept

        self.save_data()

        if removed_items:
            messagebox.showinfo("清理完成",
                                "已清理：\n" + "\n".join("  • " + i for i in removed_items))
        else:
            messagebox.showinfo("清理完成", "没有需要清理的记录，内存已经很干净啦。")

    def clean_garbage(self):
        if not messagebox.askyesno(
                "确认清理",
                "将要清理以下内容：\n\n"
                "  • 保存历史记录（save_history）\n"
                "  • 30 天前的每日学习记录（daily_study）\n"
                "  • 更新日志记录（last_save_time 等）\n"
                "  • log 文件夹中的崩溃日志 / 开发者日志\n\n"
                "此操作不可恢复，确定继续吗？"):
            return

        removed_items = []
        hist = self.data.get("save_history", [])
        if hist:
            removed_items.append(f"保存历史记录 {len(hist)} 条")
            self.data["save_history"] = []
        if self.data.get("last_save_time"):
            self.data["last_save_time"] = ""
            removed_items.append("更新日志记录")

        if self.daily_study:
            today = datetime.date.today()
            cutoff = today - datetime.timedelta(days=30)
            kept = {}
            removed_days = 0
            for k, v in self.daily_study.items():
                try:
                    d = datetime.datetime.strptime(k, "%Y-%m-%d").date()
                    if d >= cutoff:
                        kept[k] = v
                    else:
                        removed_days += 1
                except Exception:
                    kept[k] = v
            if removed_days:
                removed_items.append(f"30 天前的每日学习记录 {removed_days} 天")
                self.daily_study = kept
                self.data["daily_study"] = kept

        if os.path.isdir(ORBIT3_LOG_DIR):
            n = 0
            for fn in os.listdir(ORBIT3_LOG_DIR):
                if fn.startswith(("crash_", "dev_")) and fn.endswith((".log", ".txt")):
                    try:
                        os.remove(os.path.join(ORBIT3_LOG_DIR, fn))
                        n += 1
                    except OSError:
                        pass
            if n:
                removed_items.append(f"log 日志 {n} 个")

        self.save_data()

        if removed_items:
            messagebox.showinfo("清理完成",
                                "已清理：\n" + "\n".join("  • " + i for i in removed_items))
        else:
            messagebox.showinfo("清理完成", "没有需要清理的内容，已经很干净啦。")

    # ==================================================================
    # 老版本启动器
    # 顺序：loc 1 → Alpha 1 → beta 1~5 → Nova 1 → Nova 2 → Orbit 1
    # ==================================================================
    def show_old_versions(self):
        win = tk.Toplevel(self.root)
        win.title("old")
        win.geometry("420x600")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 210
        y = (win.winfo_screenheight() // 2) - 300
        win.geometry(f"420x600+{x}+{y}")

        tk.Label(win, text="🕰 老版本", font=("微软雅黑", 18, "bold"),
                 fg=self.color_timer).pack(pady=(15, 5))
        tk.Label(win, text="点击启动对应版本（会打开新窗口）",
                 font=("微软雅黑", 10), fg="#95a5a6").pack(pady=(0, 8))

        # 可滚动区（设置同款 Canvas + Scrollbar，版本多了也能滑）
        _body = tk.Frame(win)
        _body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 4))
        _canvas = tk.Canvas(_body, highlightthickness=0)
        _sb = tk.Scrollbar(_body, orient="vertical", command=_canvas.yview)
        _inner = tk.Frame(_canvas)
        _inner.bind("<Configure>",
                    lambda e: _canvas.configure(scrollregion=_canvas.bbox("all")))
        _canvas.create_window((0, 0), window=_inner, anchor="nw", width=360)
        _canvas.configure(yscrollcommand=_sb.set)
        _canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _sb.pack(side=tk.RIGHT, fill=tk.Y)
        _binder = getattr(self, "_bind_scroll_canvas", None)
        if _binder is not None:
            _binder(_canvas, win)
        else:
            def _wheely(e):
                try:
                    _canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass
            _canvas.bind_all("<MouseWheel>", _wheely)
            win.bind("<Destroy>", lambda e: _canvas.unbind_all("<MouseWheel>"))

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()
        search_dirs = [
            base_dir,
            os.path.join(base_dir, "versions"),
            os.path.join(base_dir, "old"),
            os.path.join(base_dir, "old"),
        ]

        version_files = [
            ("loc 1", "LOC1_BUILTIN"),
            ("1.0", ["v1_0.pyw", "v1_0.py"]),
            ("2.0", ["v2_0.pyw", "v2_0.py"]),
            ("2.7", ["v2_7.pyw", "v2_7.py"]),
            ("2.9", ["v2_9.pyw", "v2_9.py"]),
            ("3.0", ["v3_0.pyw", "v3_0.py"]),
            ("3.1", ["v3_1.pyw", "v3_1.py"]),
            ("3.2", ["v3_2.pyw", "v3_2.py"]),
            ("3.3", ["v3_3.pyw", "v3_3.py"]),
            ("4.0", ["v4_0.pyw", "v4_0.py"]),
            ("4.2", ["v4_2.pyw", "v4_2.py", "orbit2.pyw"]),
        ]

        def find_version_file(candidates):
            for d in search_dirs:
                if not os.path.isdir(d):
                    continue
                try:
                    files = os.listdir(d)
                except Exception:
                    continue
                lower_map = {f.lower(): f for f in files}
                for cand in candidates:
                    if cand.lower() in lower_map:
                        return os.path.join(d, lower_map[cand.lower()])
                for cand in candidates:
                    key = cand.lower().replace(".pyw", "").replace(".py", "")
                    for f_lower, f_orig in lower_map.items():
                        if not (f_lower.endswith(".py") or f_lower.endswith(".pyw")):
                            continue
                        if key in f_lower:
                            return os.path.join(d, f_orig)
            return None

        def launch(path):
            try:
                import subprocess
                import sys as _sys
                exe = _sys.executable
                if path.lower().endswith(".pyw"):
                    if exe.lower().endswith("python.exe"):
                        cand = exe[:-4] + "w.exe"
                        if os.path.exists(cand):
                            exe = cand
                else:
                    if exe.lower().endswith("pythonw.exe"):
                        cand = exe[:-5] + ".exe"
                        if os.path.exists(cand):
                            exe = cand
                subprocess.Popen([exe, path], cwd=os.path.dirname(path))
            except Exception as e:
                try:
                    os.startfile(path)
                except Exception as e2:
                    messagebox.showerror("启动失败",
                                         f"无法启动：\n{path}\n\n{e}\n{e2}")

        for name, candidates in version_files:
            if candidates == "LOC1_BUILTIN":
                tk.Button(_inner, text=name, font=("微软雅黑", 12),
                          width=22, relief=tk.FLAT, bg="#d5f5e3",
                          fg="#1e8449", cursor="hand2",
                          command=self.init_loc1_builtin).pack(pady=4, ipady=3)
                continue

            path = find_version_file(candidates)
            if path:
                tk.Button(_inner, text=name, font=("微软雅黑", 12),
                          width=22, relief=tk.FLAT, bg="#ecf0f1",
                          cursor="hand2",
                          command=lambda p=path: launch(p)).pack(pady=4, ipady=3)
            else:
                tk.Button(_inner, text=f"{name}（未找到）", font=("微软雅黑", 12),
                          width=22, relief=tk.FLAT, bg="#f8f9fa",
                          fg="#bdc3c7",
                          state=tk.DISABLED).pack(pady=4, ipady=3)

        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=(15, 10))

    # ---------- loc 1 内置 ----------
    def init_loc1_builtin(self):
        minutes = simpledialog.askinteger(
            "loc 1", "请输入分钟数：",
            minvalue=1, maxvalue=9999, parent=self.root)
        if minutes is None:
            return

        total_seconds = minutes * 60
        win = tk.Toplevel(self.root)
        win.title("计时器")
        win.geometry("520x320")
        win.resizable(False, False)
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 260
        y = (win.winfo_screenheight() // 2) - 160
        win.geometry(f"520x320+{x}+{y}")

        tk.Label(win, text="计时器",
                 font=("微软雅黑", 16, "bold"),
                 fg="#7f8c8d").pack(pady=(14, 0))

        time_label = tk.Label(win, text=self.format_time(total_seconds),
                              font=("微软雅黑", 80, "bold"),
                              fg=self.color_timer)
        time_label.pack(expand=True)

        state = {"remaining": total_seconds, "running": True}

        def tick():
            if not state["running"]:
                return
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return
            state["remaining"] -= 1
            if state["remaining"] <= 0:
                time_label.config(text="00:00")
                state["running"] = False
                messagebox.showinfo("时间到！",
                                    f"计时 {minutes} 分钟结束！",
                                    parent=win)
                return
            time_label.config(text=self.format_time(state["remaining"]))
            win.after(1000, tick)

        def on_close():
            state["running"] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        tick()

    # ==================================================================
    # 现在时间模式
    # ==================================================================
    def init_clock_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 现在时间")
        self.root.geometry(f"{self.win_w}x{self.win_h}")
        self.apply_window_resizable(False)
        self.clear_root()
        self.create_clock_widgets()
        self.update_clock()

    def create_clock_widgets(self):
        self.clear_root()

        tk.Label(self.root, text="🕰 现在时间",
                 font=("微软雅黑", 18, "bold"),
                 fg=self.color_timer).pack(pady=(18, 0))

        wrap = tk.Frame(self.root)
        wrap.place(relx=0.5, rely=0.45, anchor="center")

        self.clock_time_label = tk.Label(
            wrap, text="00:00:00",
            font=("微软雅黑", 72, "bold"), fg=self.color_timer)
        self.clock_time_label.pack()

        self.clock_date_label = tk.Label(
            wrap, text="", font=("微软雅黑", 20), fg="#7f8c8d")
        self.clock_date_label.pack(pady=(14, 0))

        self.clock_week_label = tk.Label(
            wrap, text="", font=("微软雅黑", 16), fg="#95a5a6")
        self.clock_week_label.pack(pady=(4, 0))

        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10),
                  relief=tk.FLAT).pack(side=tk.BOTTOM, pady=12)

    def update_clock(self):
        if self.mode not in ("learning", "clock"):
            return
        now = datetime.datetime.now()

        if self.mode == "learning":
            time_str = now.strftime("%Y/%m/%d %H:%M:%S")
            try:
                if hasattr(self, 'clock_label') and self.clock_label.winfo_exists():
                    self.clock_label.config(text=time_str)
            except tk.TclError:
                return

        elif self.mode == "clock":
            try:
                if hasattr(self, 'clock_time_label') and self.clock_time_label.winfo_exists():
                    self.clock_time_label.config(text=now.strftime("%H:%M:%S"))
                if hasattr(self, 'clock_date_label') and self.clock_date_label.winfo_exists():
                    self.clock_date_label.config(text=now.strftime("%Y 年 %m 月 %d 日"))
                if hasattr(self, 'clock_week_label') and self.clock_week_label.winfo_exists():
                    weekdays = ["星期一", "星期二", "星期三", "星期四",
                                "星期五", "星期六", "星期日"]
                    self.clock_week_label.config(text=weekdays[now.weekday()])
            except tk.TclError:
                return

        self.root.after(1000, self.update_clock)

    # ==================================================================
    # 学习模式
    # ==================================================================
    def init_learning_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 学习模式")
        self.root.geometry(f"{self.win_w}x{self.win_h}")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = self.study_time
        self.is_break = False
        self.fun_used_time = 0
        self.compact_view = False
        self.used_riddles_this_break = set()
        self.create_learning_widgets()
        self.refresh_study_labels()
        if not self.auto_learning:
            self.show_random_quote()
        self.update_clock()
        if self.auto_learning:
            self.root.after(400, self.start_timer)

    def create_learning_widgets(self):
        title_label = tk.Label(self.root, text="📚 学习陪伴助手",
                               font=("微软雅黑", 20, "bold"))
        title_label.pack(pady=(10, 0))

        motto_frame = tk.Frame(self.root)
        motto_frame.pack(pady=(2, 5))
        self.motto_label = tk.Label(
            motto_frame,
            text=f"我的名言：{self.motto if self.motto else '（未设置）'}",
            font=("微软雅黑", 12, "italic"), fg=self.color_timer)
        self.motto_label.pack(side=tk.LEFT, padx=(0, 10))
        self.set_motto_btn = tk.Button(motto_frame, text="设置名言",
                                       command=self.set_motto,
                                       font=("微软雅黑", 10), width=8)
        self.set_motto_btn.pack(side=tk.LEFT)

        self.clock_label = tk.Label(self.root, text="",
                                    font=("微软雅黑", 12), fg="#555")
        self.clock_label.pack(pady=2)

        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0",
                                    bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)
        self.timer_label = tk.Label(self.timer_frame,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(pady=20)
        self.status_label = tk.Label(self.timer_frame, text="准备开始学习",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)
        self.start_btn = tk.Button(self.button_frame, text="开始学习",
                                   command=self.start_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停",
                                   command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置",
                                   command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        self.compact_btn = tk.Button(self.button_frame, text="极简展示",
                                     command=self.enter_compact_view,
                                     font=("微软雅黑", 12), width=10,
                                     bg="#9b59b6", fg="white")
        self.compact_btn.grid(row=0, column=3, padx=5)

        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(self.progress_frame, text="今日完成番茄数：",
                 font=("微软雅黑", 12)).grid(row=0, column=0, sticky=tk.W)
        self.pomodoro_label = tk.Label(self.progress_frame,
                                       text=str(self.pomodoro_count),
                                       font=("微软雅黑", 12, "bold"),
                                       fg="#27ae60")
        self.pomodoro_label.grid(row=0, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="今日学习时长：",
                 font=("微软雅黑", 12)).grid(row=1, column=0, sticky=tk.W)
        self.today_time_label = tk.Label(self.progress_frame, text="0 分钟",
                                         font=("微软雅黑", 12, "bold"),
                                         fg="#27ae60")
        self.today_time_label.grid(row=1, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="总学习时长：",
                 font=("微软雅黑", 12)).grid(row=2, column=0, sticky=tk.W)
        self.total_time_label = tk.Label(self.progress_frame, text="0 分钟",
                                         font=("微软雅黑", 12, "bold"),
                                         fg="#16a085")
        self.total_time_label.grid(row=2, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="可用自由时间：",
                 font=("微软雅黑", 12)).grid(row=3, column=0, sticky=tk.W)
        self.free_time_label = tk.Label(self.progress_frame,
                                        text=f"{self.free_time // 60}分钟",
                                        font=("微软雅黑", 12, "bold"),
                                        fg="#3498db")
        self.free_time_label.grid(row=3, column=1, sticky=tk.W)

        self.fun_frame = tk.LabelFrame(self.root,
                                       text="休息娱乐区（仅休息时间可用）",
                                       font=("微软雅黑", 12))
        self.fun_frame.pack(pady=10, padx=20, fill=tk.X)

        self.riddle_btn = tk.Button(self.fun_frame, text="猜个脑筋急转弯",
                                    command=self.show_riddle,
                                    font=("微软雅黑", 10), state=tk.DISABLED)
        self.riddle_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.number_guess_btn = tk.Button(self.fun_frame, text="玩猜数字游戏",
                                          command=self.pd_tf,
                                          font=("微软雅黑", 10),
                                          state=tk.DISABLED)
        self.number_guess_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.quote_btn = tk.Button(self.fun_frame, text="看句励志名言",
                                   command=self.show_random_quote,
                                   font=("微软雅黑", 10))
        self.quote_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.exchange_btn = tk.Button(self.fun_frame, text="积分兑换自由时间",
                                      command=self.exchange_score,
                                      font=("微软雅黑", 10))
        self.exchange_btn.grid(row=1, column=0, columnspan=3,
                               padx=5, pady=5, sticky="ew")
        self.update_exchange_btn_state()

        self.use_free_btn = tk.Button(self.fun_frame,
                                      text="使用自由时间（延长休息）",
                                      command=self.use_free_time,
                                      font=("微软雅黑", 10),
                                      state=tk.DISABLED)
        self.use_free_btn.grid(row=2, column=0, columnspan=3,
                               padx=5, pady=5, sticky="ew")

        self.fun_time_label = tk.Label(self.fun_frame, text="",
                                       font=("微软雅黑", 10), fg="#e74c3c")
        self.fun_time_label.grid(row=3, column=0, columnspan=3, pady=2)

        self.fun_frame.columnconfigure(0, weight=1)
        self.fun_frame.columnconfigure(1, weight=1)
        self.fun_frame.columnconfigure(2, weight=1)

    def refresh_study_labels(self):
        try:
            if hasattr(self, 'today_time_label') and self.today_time_label.winfo_exists():
                today = self.daily_study.get(self.today_key(), 0)
                self.today_time_label.config(text=self.format_duration(today))
            if hasattr(self, 'total_time_label') and self.total_time_label.winfo_exists():
                self.total_time_label.config(
                    text=self.format_duration(self.calc_total_study_all()))
            if hasattr(self, 'pomodoro_label') and self.pomodoro_label.winfo_exists():
                self.pomodoro_label.config(text=str(self.pomodoro_count))
            if hasattr(self, 'free_time_label') and self.free_time_label.winfo_exists():
                self.free_time_label.config(text=f"{self.free_time // 60}分钟")
        except Exception:
            pass

    def set_motto(self):
        current = self.motto if self.motto else ""
        new_motto = simpledialog.askstring(
            "设置我的名言", "请输入你的励志名言（不超过10个字）：",
            initialvalue=current, parent=self.root)
        if new_motto is None:
            return
        if len(new_motto) > 10:
            messagebox.showwarning("提示", "名言不能超过10个字！")
            return
        self.motto = new_motto.strip()
        self.motto_label.config(
            text=f"我的名言：{self.motto if self.motto else '（未设置）'}")
        self.save_data()

    def enter_compact_view(self):
        if not self.auto_learning:
            messagebox.showwarning(
                "提示",
                "极简展示需要先开启「学习模式自动」。\n\n"
                "请前往：主菜单 → 设置 → 勾选「学习模式自动」。",
                parent=self.root)
            return

        self.compact_view = True
        self.clear_root()
        cfg = self._compact_cfg()
        items = cfg.get("items", {})
        custom = bool(cfg.get("custom", False))
        w = int(cfg.get("w", 360))
        h = int(cfg.get("h", 200))
        fs = int(cfg.get("font", 56))
        self.root.geometry(f"{w}x{h}")
        self.root.resizable(custom, custom)

        # 控件始终创建（计时回调要用），只是按配置决定显不显示
        self._compact_clock_lbl = tk.Label(self.root, text="",
                                           font=("微软雅黑", 12), fg="#95a5a6")
        if items.get("clock"):
            self._compact_clock_lbl.pack(pady=(8, 0))

        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", fs, "bold"),
                                    fg=self.color_timer)
        if items.get("timer", True):
            self.timer_label.pack(expand=True)

        self._compact_today_lbl = tk.Label(self.root,
                                           text="今日已学习：" + self.format_duration(
                                               self.daily_study.get(self.today_key(), 0)),
                                           font=("微软雅黑", 11), fg=self.color_primary)
        if items.get("today"):
            self._compact_today_lbl.pack(pady=4)

        self._compact_back_btn = tk.Button(self.root, text="恢复到正常模式",
                  command=self.exit_compact_view,
                  font=("微软雅黑", 11), relief=tk.FLAT, cursor="hand2",
                  bg="#ecf0f1")
        if items.get("back", True):
            self._compact_back_btn.pack(pady=10, ipadx=10)

        self._compact_clock_tick()

    def _compact_clock_tick(self):
        if not self.compact_view:
            return
        try:
            if (getattr(self, "_compact_clock_lbl", None) is not None
                    and self._compact_clock_lbl.winfo_exists()):
                self._compact_clock_lbl.config(
                    text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass
        self.root.after(1000, self._compact_clock_tick)

    def exit_compact_view(self):
        self.compact_view = False
        self.root.geometry(f"{self.win_w}x{self.win_h}")
        self.apply_window_resizable(False)
        self.clear_root()
        self.create_learning_widgets()
        self.refresh_study_labels()

        try:
            self.timer_label.config(text=self.format_time(self.current_seconds))
        except Exception:
            pass

        if self.is_running:
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            self.status_label.config(
                text="专注学习中..." if not self.is_break else "休息时间，放松一下~")
            if self.is_break:
                self.enable_fun_buttons()
        else:
            self.start_btn.config(state=tk.NORMAL, text="开始学习")

    # ==================================================================
    # 挑战模式
    # ==================================================================
    def init_challenge_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 挑战模式")
        self.apply_window_resizable(False)
        self.clear_root()

        challenge_win = tk.Toplevel(self.root)
        challenge_win.title("选择挑战时间")
        challenge_win.geometry("1200x200")
        challenge_win.resizable(False, False)
        challenge_win.grab_set()
        challenge_win.transient(self.root)
        challenge_win.update_idletasks()
        x = (challenge_win.winfo_screenwidth() // 2) - 600
        y = (challenge_win.winfo_screenheight() // 2) - 100
        challenge_win.geometry(f"1200x200+{x}+{y}")

        tk.Label(challenge_win, text="选择挑战时长（秒）",
                 font=("微软雅黑", 14)).pack(pady=15)

        def select_time(seconds):
            self.challenge_selected = seconds
            self.current_seconds = seconds
            challenge_win.destroy()
            self.create_challenge_widgets()

        def cancel():
            challenge_win.destroy()
            self.mode_locked = False
            self.mode = None
            self.show_mode_selection()

        challenge_win.protocol("WM_DELETE_WINDOW", cancel)

        frame = tk.Frame(challenge_win)
        frame.pack(pady=10)
        for t in self.challenge_times:
            tk.Button(frame, text=f"{t}秒",
                      command=lambda x=t: select_time(x),
                      font=("微软雅黑", 12), width=8).grid(
                row=0, column=self.challenge_times.index(t), padx=5)

    def create_challenge_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="🔥 挑战模式",
                 font=("微软雅黑", 20, "bold")).pack(pady=10)
        self.score_label = tk.Label(self.root,
                                    text=f"当前积分：{self.challenge_score}",
                                    font=("微软雅黑", 14), fg=self.color_accent)
        self.score_label.pack(pady=5)
        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0",
                                    bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)
        self.timer_label = tk.Label(self.timer_frame,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(pady=20)
        self.status_label = tk.Label(self.timer_frame,
                                     text=f"挑战时长：{self.challenge_selected}秒",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)
        self.start_btn = tk.Button(self.button_frame, text="开始挑战",
                                   command=self.start_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停",
                                   command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置挑战",
                                   command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        tk.Label(self.root,
                 text="✅ 挑战规则：完成计时不暂停/重置即可获得对应积分\n"
                      "100秒=1积分 | 200秒=2积分 | 300秒=3积分",
                 font=("微软雅黑", 10), fg="#7f8c8d").pack(pady=10)
        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 极简模式
    # ==================================================================
    def init_simple_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 极简模式")
        self.apply_window_resizable(True)
        self.clear_root()
        minutes = simpledialog.askinteger("自定义时间",
                                          "请输入极简模式时长（分钟）：",
                                          minvalue=1, maxvalue=100000,
                                          parent=self.root)
        if minutes is None:
            self.mode_locked = False
            self.mode = None
            self.show_mode_selection()
            return
        self.custom_time = minutes * 60
        self.current_seconds = self.custom_time
        self.create_simple_widgets()

    def create_simple_widgets(self):
        self.clear_root()
        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 80, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(expand=True)
        self.start_btn = tk.Button(self.root, text="开始",
                                   command=self.start_timer,
                                   font=("微软雅黑", 14), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.pack(pady=30)
        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 考试模式
    # ==================================================================
    def init_exam_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 考试模式")
        self.apply_window_resizable(False)
        self.clear_root()
        minutes = simpledialog.askinteger("考试时间",
                                          "请输入考试时长（分钟）：",
                                          minvalue=1, maxvalue=999,
                                          parent=self.root)
        if minutes is None:
            self.mode_locked = False
            self.mode = None
            self.show_mode_selection()
            return
        self.exam_time = minutes * 60
        self.current_seconds = self.exam_time
        self.exam_start_timestamp = None
        self.exam_recorded = False
        self.create_exam_widgets()

    def create_exam_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="📝 考试模式",
                 font=("微软雅黑", 20, "bold")).pack(pady=10)
        tk.Label(self.root,
                 text=f"考试时长：{self.exam_time // 60} 分钟",
                 font=("微软雅黑", 12)).pack(pady=5)
        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 60, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(expand=True)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        self.start_btn = tk.Button(self.button_frame, text="开始考试",
                                   command=self.start_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停",
                                   command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置",
                                   command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        self.submit_btn = tk.Button(self.button_frame, text="交卷",
                                    command=self.submit_exam,
                                    font=("微软雅黑", 12), width=10,
                                    bg="#3498db", fg="white", state=tk.DISABLED)
        self.submit_btn.grid(row=0, column=3, padx=5)
        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    def submit_exam(self):
        if not self.is_running and self.current_seconds == self.exam_time:
            messagebox.showwarning("提示", "考试尚未开始！")
            return
        if self.is_running:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL, text="继续")
            self.pause_btn.config(state=tk.DISABLED)

        used_seconds = self.exam_time - self.current_seconds

        if not self.exam_recorded and used_seconds > 0:
            self.exam_mode_seconds += used_seconds
            self.exam_mode_count += 1
            self.add_study_time(used_seconds)
            self.exam_recorded = True
            self.save_data()

        used_min = used_seconds // 60
        used_sec = used_seconds % 60
        messagebox.showinfo("交卷成功",
                            f"考试结束，您用时 {used_min}分{used_sec}秒。\n"
                            f"剩余时间 {self.format_time(self.current_seconds)}")
        self.submit_btn.config(state=tk.DISABLED)

    # ==================================================================
    # 极简番茄
    # ==================================================================
    def init_simple_pomodoro_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 极简番茄")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = self.pomodoro_simple_time
        self.create_simple_pomodoro_widgets()
        if self.auto_learning:
            self.root.after(400, self.start_timer)

    def create_simple_pomodoro_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="🍅 极简番茄",
                 font=("微软雅黑", 20, "bold")).pack(pady=10)
        self.count_label = tk.Label(self.root,
                                    text=f"本次已完成番茄：{self.pomodoro_simple_count} 个",
                                    font=("微软雅黑", 14), fg="#27ae60")
        self.count_label.pack(pady=5)
        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 60, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(expand=True)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        self.start_btn = tk.Button(self.button_frame, text="开始",
                                   command=self.start_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停",
                                   command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置",
                                   command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 正计时模式
    # ==================================================================
    def init_count_up_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 正计时")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = 0
        self.create_count_up_widgets()

    def create_count_up_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="⏳ 正计时",
                 font=("微软雅黑", 22, "bold")).pack(pady=(15, 0))
        tk.Label(self.root,
                 text="从 0 开始累计，随时点击「结束并保存」记入学习记录",
                 font=("微软雅黑", 10), fg="#7f8c8d").pack()

        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 72, "bold"),
                                    fg=self.color_timer)
        self.timer_label.pack(expand=True)

        self.today_label = tk.Label(
            self.root,
            text=f"今日学习时长：{self.format_duration(self.daily_study.get(self.today_key(), 0))}",
            font=("微软雅黑", 12), fg="#27ae60")
        self.today_label.pack(pady=5)

        self.total_label = tk.Label(
            self.root,
            text=f"总学习时长：{self.format_duration(self.calc_total_study_all())}",
            font=("微软雅黑", 12), fg="#16a085")
        self.total_label.pack(pady=2)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        self.start_btn = tk.Button(self.button_frame, text="开始",
                                   command=self.start_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg=self.color_primary, fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停",
                                   command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10,
                                   bg="#f39c12", fg="white", state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.stop_btn = tk.Button(self.button_frame, text="结束并保存",
                                  command=self.stop_count_up,
                                  font=("微软雅黑", 12), width=12,
                                  bg="#3498db", fg="white")
        self.stop_btn.grid(row=0, column=2, padx=5)
        tk.Button(self.root, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    def refresh_count_up_labels(self):
        try:
            if hasattr(self, 'today_label') and self.today_label.winfo_exists():
                self.today_label.config(
                    text=f"今日学习时长：{self.format_duration(self.daily_study.get(self.today_key(), 0))}")
            if hasattr(self, 'total_label') and self.total_label.winfo_exists():
                self.total_label.config(
                    text=f"总学习时长：{self.format_duration(self.calc_total_study_all())}")
        except Exception:
            pass

    def stop_count_up(self):
        self.is_running = False
        secs = self.current_seconds
        if secs > 0:
            self.count_up_seconds += secs
            self.count_up_count += 1
            self.add_study_time(secs)
            self.save_data()
            self.refresh_count_up_labels()
            messagebox.showinfo("已保存",
                                f"本次正计时：{self.format_duration(secs)}\n已记入学习记录。")
        self.current_seconds = 0
        try:
            self.timer_label.config(text=self.format_time(0))
            self.start_btn.config(state=tk.NORMAL, text="开始")
            self.pause_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    # ==================================================================
    # 我的学习记录
    # ==================================================================
    def init_records_mode(self):
        self.root.title(f"{APP_WINDOW_TITLE} - 我的学习记录")
        self.apply_window_resizable(False)
        self.clear_root()
        self.create_records_widgets()

    def create_records_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="📊 我的学习记录",
                 font=("微软雅黑", 20, "bold")).pack(pady=(15, 10))

        total_seconds = self.calc_total_study_all()

        summary_frame = tk.Frame(self.root, bg="#ecf0f1",
                                 bd=2, relief=tk.GROOVE)
        summary_frame.pack(pady=5, padx=30, fill=tk.X)
        tk.Label(summary_frame, text="累计学习时长",
                 font=("微软雅黑", 12),
                 bg="#ecf0f1", fg="#7f8c8d").pack(pady=(8, 0))
        tk.Label(summary_frame, text=self.format_duration(total_seconds),
                 font=("微软雅黑", 20, "bold"),
                 bg="#ecf0f1", fg=self.color_accent).pack(pady=(0, 10))

        table = tk.Frame(self.root)
        table.pack(pady=10, padx=30, fill=tk.BOTH, expand=True)

        headers = ["模式", "完成情况", "累计时长"]
        for col, h in enumerate(headers):
            tk.Label(table, text=h, font=("微软雅黑", 12, "bold"),
                     bg="#3498db", fg="white", pady=6).grid(
                row=0, column=col, sticky="nsew", padx=1, pady=1)

        rows = self.get_record_rows()
        for i, (mode, count, dur) in enumerate(rows, start=1):
            bg = "#ffffff" if i % 2 else "#f8f9fa"
            tk.Label(table, text=mode, font=("微软雅黑", 11),
                     bg=bg, pady=6).grid(row=i, column=0, sticky="nsew",
                                         padx=1, pady=1)
            tk.Label(table, text=count, font=("微软雅黑", 11),
                     bg=bg, pady=6).grid(row=i, column=1, sticky="nsew",
                                         padx=1, pady=1)
            tk.Label(table, text=self.format_duration(dur),
                     font=("微软雅黑", 11), bg=bg, pady=6).grid(
                row=i, column=2, sticky="nsew", padx=1, pady=1)

        n = len(rows) + 1
        tk.Label(table, text="合计", font=("微软雅黑", 12, "bold"),
                 bg=self.color_accent, fg="white", pady=6).grid(
            row=n, column=0, sticky="nsew", padx=1, pady=1)
        tk.Label(table, text="", bg=self.color_accent).grid(
            row=n, column=1, sticky="nsew", padx=1, pady=1)
        tk.Label(table, text=self.format_duration(total_seconds),
                 font=("微软雅黑", 12, "bold"),
                 bg=self.color_accent, fg="white", pady=6).grid(
            row=n, column=2, sticky="nsew", padx=1, pady=1)

        for c in range(3):
            table.columnconfigure(c, weight=1)

        extra_frame = tk.Frame(self.root)
        extra_frame.pack(pady=10)
        tk.Label(extra_frame, text=f"💎 挑战积分：{self.challenge_score}",
                 font=("微软雅黑", 12), fg="#9b59b6").pack(side=tk.LEFT, padx=15)
        tk.Label(extra_frame, text=f"🎁 可用自由时间：{self.free_time // 60} 分钟",
                 font=("微软雅黑", 12), fg="#3498db").pack(side=tk.LEFT, padx=15)

        if self.motto:
            tk.Label(self.root, text=f"我的名言：{self.motto}",
                     font=("微软雅黑", 11, "italic"),
                     fg="#7f8c8d").pack(pady=5)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="返回模式选择",
                  command=self.back_to_mode_selection,
                  font=("微软雅黑", 12), width=14,
                  bg=self.color_primary, fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="清空记录",
                  command=self.reset_records,
                  font=("微软雅黑", 12), width=14,
                  bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)

    def reset_records(self):
        if not messagebox.askyesno("确认",
                                   "确定要清空所有学习记录吗？此操作不可恢复！"):
            return
        self.pomodoro_count = 0
        self.total_study_seconds = 0
        self.simple_mode_seconds = 0
        self.simple_mode_count = 0
        self.exam_mode_seconds = 0
        self.exam_mode_count = 0
        self.challenge_total_seconds = 0
        self.challenge_count = 0
        self.simple_pomodoro_seconds = 0
        self.simple_pomodoro_total_count = 0
        self.count_up_seconds = 0
        self.count_up_count = 0
        self.pomodoro_simple_count = 0
        self.daily_study = {}
        self.save_data()
        self.create_records_widgets()
        messagebox.showinfo("完成", "学习记录已清空。")

    # ==================================================================
    # 通用计时器
    # ==================================================================
    def start_timer(self):
        if not self.is_running and self.mode_locked:
            self.is_running = True
            try:
                self.start_btn.config(state=tk.DISABLED)
            except Exception:
                pass

            if self.mode == "simple":
                try:
                    self.start_btn.pack_forget()
                except Exception:
                    pass
            else:
                if self.mode in ["learning", "challenge", "simple_pomodoro",
                                 "exam", "count_up"]:
                    if hasattr(self, 'pause_btn'):
                        try:
                            self.pause_btn.config(state=tk.NORMAL)
                        except Exception:
                            pass
                if self.mode == "exam":
                    try:
                        self.submit_btn.config(state=tk.NORMAL)
                    except Exception:
                        pass
                    if self.exam_start_timestamp is None:
                        self.exam_start_timestamp = time.time()

                if self.mode == "learning" and not self.compact_view:
                    try:
                        self.status_label.config(
                            text="专注学习中..." if not self.is_break
                            else "休息时间，放松一下~")
                    except Exception:
                        pass
                    if self.is_break:
                        self.enable_fun_buttons()
                elif self.mode == "challenge":
                    try:
                        self.status_label.config(text="挑战进行中...")
                    except Exception:
                        pass

            self.timer_thread = threading.Thread(target=self.update_timer,
                                                 daemon=True)
            self.timer_thread.start()

    def update_timer(self):
        if self.mode == "count_up":
            while self.is_running:
                time.sleep(1)
                if not self.is_running:
                    break
                self.current_seconds += 1
                self.root.after(0, lambda: self.set_timer_text(
                    self.format_time(self.current_seconds)))
            return

        while self.is_running and self.current_seconds > 0:
            time.sleep(1)
            self.current_seconds -= 1
            self.root.after(0, lambda: self.set_timer_text(
                self.format_time(self.current_seconds)))

            if self.mode == "learning" and self.is_break:
                self.fun_used_time += 1
                remaining_fun = self.max_fun_time - self.fun_used_time
                if remaining_fun < 0:
                    remaining_fun = 0

                def _upd_fun(rem=remaining_fun):
                    try:
                        if hasattr(self, 'fun_time_label') and self.fun_time_label.winfo_exists():
                            self.fun_time_label.config(
                                text=f"剩余娱乐时间：{self.format_time(rem)}")
                    except Exception:
                        pass

                self.root.after(0, _upd_fun)

                if not self.auto_learning and not self.compact_view:
                    if remaining_fun == 60:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "提醒", "休息时间还有1分钟结束！"))
                    elif remaining_fun == 10:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "提醒", "休息时间还有10秒结束！"))

        if self.current_seconds == 0:
            self.is_running = False
            self.root.after(0, self.timer_finished)

    def timer_finished(self):
        if self.mode == "learning":
            self.handle_learning_finish()
        elif self.mode == "challenge":
            self.handle_challenge_finish()
        elif self.mode == "simple":
            self.handle_simple_finish()
        elif self.mode == "exam":
            self.handle_exam_finish()
        elif self.mode == "simple_pomodoro":
            self.handle_simple_pomodoro_finish()

    # ==================================================================
    # 各模式完成处理
    # ==================================================================
    def handle_learning_finish(self):
        compact = getattr(self, 'compact_view', False)
        if not self.is_break:
            self.pomodoro_count += 1
            self.total_study_seconds += self.study_time
            self.add_study_time(self.study_time)
            self.refresh_study_labels()
            self.save_data()

            self.used_riddles_this_break = set()

            if self.pomodoro_count % 4 == 0:
                self.current_seconds = self.long_break_time
                self.max_fun_time = self.long_break_time
                if not self.auto_learning:
                    messagebox.showinfo(
                        "太棒了！",
                        f"你已经完成了{self.pomodoro_count}个番茄钟！\n"
                        f"奖励你一个{self.long_break_time // 60}分钟的长休息！")
            else:
                self.current_seconds = self.break_time
                self.max_fun_time = self.break_time
                if not self.auto_learning:
                    messagebox.showinfo(
                        "学习时间结束",
                        f"干得漂亮！休息{self.break_time // 60}分钟再继续吧~")

            self.is_break = True
            self.fun_used_time = 0
            if not compact:
                self.enable_fun_buttons()
        else:
            self.current_seconds = self.study_time
            self.is_break = False
            if not compact:
                self.disable_fun_buttons()
            if not self.auto_learning:
                messagebox.showinfo("休息结束", "休息好了吗？让我们继续学习吧！")
            if not compact:
                try:
                    self.status_label.config(text="准备开始学习")
                except Exception:
                    pass

        try:
            self.timer_label.config(text=self.format_time(self.current_seconds))
        except Exception:
            pass

        if not compact:
            try:
                self.start_btn.config(state=tk.NORMAL, text="开始学习")
            except Exception:
                pass
            if hasattr(self, 'pause_btn'):
                try:
                    self.pause_btn.config(state=tk.DISABLED)
                except Exception:
                    pass

        if self.auto_learning:
            self.root.after(300, self.start_timer)

    def handle_challenge_finish(self):
        score_gain = self.challenge_selected // 100
        self.challenge_score += score_gain
        self.challenge_total_seconds += self.challenge_selected
        self.challenge_count += 1
        self.add_study_time(self.challenge_selected)
        self.score_label.config(text=f"当前积分：{self.challenge_score}")
        self.save_data()
        messagebox.showinfo(
            "挑战成功！",
            f"恭喜你完成{self.challenge_selected}秒挑战！\n"
            f"获得{score_gain}积分，当前总积分：{self.challenge_score}")
        self.current_seconds = self.challenge_selected
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        if hasattr(self, 'pause_btn'):
            self.pause_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f"挑战时长：{self.challenge_selected}秒")

    def handle_simple_finish(self):
        self.simple_mode_seconds += self.custom_time
        self.simple_mode_count += 1
        self.add_study_time(self.custom_time)
        self.save_data()
        messagebox.showinfo("计时结束", "时间到！")
        self.current_seconds = self.custom_time
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        self.start_btn.pack(pady=30)

    def handle_exam_finish(self):
        if not self.exam_recorded:
            self.exam_mode_seconds += self.exam_time
            self.exam_mode_count += 1
            self.add_study_time(self.exam_time)
            self.exam_recorded = True
            self.save_data()
        messagebox.showinfo("考试结束", "时间到！请停止作答，准备交卷。")
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL, text="继续")
        if hasattr(self, 'pause_btn'):
            self.pause_btn.config(state=tk.DISABLED)
        if hasattr(self, 'submit_btn'):
            self.submit_btn.config(state=tk.DISABLED)

    def handle_simple_pomodoro_finish(self):
        self.pomodoro_simple_count += 1
        self.simple_pomodoro_total_count += 1
        self.simple_pomodoro_seconds += self.pomodoro_simple_time
        self.add_study_time(self.pomodoro_simple_time)
        self.count_label.config(text=f"本次已完成番茄：{self.pomodoro_simple_count} 个")
        self.save_data()
        if not self.auto_learning:
            messagebox.showinfo(
                "番茄完成",
                f"🎉 完成一个番茄！\n本次已完成 {self.pomodoro_simple_count} 个。")
        self.current_seconds = self.pomodoro_simple_time
        self.timer_label.config(text=self.format_time(self.current_seconds))
        self.start_btn.config(state=tk.NORMAL)
        if hasattr(self, 'pause_btn'):
            self.pause_btn.config(state=tk.DISABLED)
        if self.auto_learning:
            self.root.after(300, self.start_timer)

    # ==================================================================
    # 暂停 / 重置
    # ==================================================================
    def pause_timer(self):
        if self.is_running and self.mode in ["learning", "challenge", "exam",
                                              "simple_pomodoro", "count_up"]:
            self.is_running = False
            try:
                self.start_btn.config(state=tk.NORMAL, text="继续")
            except Exception:
                pass
            if hasattr(self, 'pause_btn'):
                try:
                    self.pause_btn.config(state=tk.DISABLED)
                except Exception:
                    pass
            if self.mode == "learning" and not self.compact_view:
                try:
                    self.status_label.config(text="已暂停")
                except Exception:
                    pass
            elif self.mode == "challenge":
                try:
                    self.status_label.config(text="挑战已暂停")
                except Exception:
                    pass
            if self.mode == "exam":
                try:
                    self.submit_btn.config(state=tk.NORMAL)
                except Exception:
                    pass

    def reset_timer(self):
        self.is_running = False
        self.is_break = False
        self.fun_used_time = 0

        if self.mode == "learning":
            self.current_seconds = self.study_time
            try:
                self.status_label.config(text="准备开始学习")
                self.start_btn.config(state=tk.NORMAL, text="开始学习")
            except Exception:
                pass
            if not self.compact_view:
                self.disable_fun_buttons()
                try:
                    self.fun_time_label.config(text="")
                except Exception:
                    pass
        elif self.mode == "challenge":
            self.current_seconds = self.challenge_selected
            self.status_label.config(text=f"挑战时长：{self.challenge_selected}秒")
            self.start_btn.config(state=tk.NORMAL)
        elif self.mode == "simple":
            self.current_seconds = self.custom_time
            self.timer_label.config(text=self.format_time(self.current_seconds))
            self.start_btn.config(state=tk.NORMAL)
            self.start_btn.pack(pady=30)
        elif self.mode == "exam":
            self.current_seconds = self.exam_time
            self.exam_start_timestamp = None
            self.exam_recorded = False
            self.start_btn.config(state=tk.NORMAL)
            self.submit_btn.config(state=tk.DISABLED)
        elif self.mode == "simple_pomodoro":
            self.current_seconds = self.pomodoro_simple_time
            self.pomodoro_simple_count = 0
            self.count_label.config(
                text=f"本次已完成番茄：{self.pomodoro_simple_count} 个")
            self.start_btn.config(state=tk.NORMAL)
            self.save_data()
        elif self.mode == "count_up":
            self.current_seconds = 0
            self.start_btn.config(state=tk.NORMAL, text="开始")

        try:
            self.timer_label.config(text=self.format_time(self.current_seconds))
        except Exception:
            pass
        if hasattr(self, 'pause_btn'):
            try:
                self.pause_btn.config(state=tk.DISABLED)
            except Exception:
                pass

    # ==================================================================
    # 学习模式娱乐功能
    # ==================================================================
    def enable_fun_buttons(self):
        try:
            self.riddle_btn.config(state=tk.NORMAL)
            self.number_guess_btn.config(state=tk.NORMAL)
            if self.free_time > 0:
                self.use_free_btn.config(state=tk.NORMAL)
            else:
                self.use_free_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    def disable_fun_buttons(self):
        try:
            self.riddle_btn.config(state=tk.DISABLED)
            self.number_guess_btn.config(state=tk.DISABLED)
            self.use_free_btn.config(state=tk.DISABLED)
            self.fun_time_label.config(text="")
        except Exception:
            pass

    # ==================================================================
    # 脑筋急转弯（改造版：输入答案）
    # ==================================================================
    @staticmethod
    def _normalize_text(s):
        return re.sub(r"[^\w\u4e00-\u9fff]", "", s).lower()

    def show_riddle(self):
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩脑筋急转弯哦！")
            return

        if len(self.used_riddles_this_break) >= len(self.riddles):
            self.used_riddles_this_break = set()

        candidates = [i for i in range(len(self.riddles))
                      if i not in self.used_riddles_this_break]
        if not candidates:
            candidates = list(range(len(self.riddles)))
        idx = random.choice(candidates)
        self.used_riddles_this_break.add(idx)
        riddle = self.riddles[idx]

        user_answer = simpledialog.askstring(
            "脑筋急转弯",
            f"{riddle['question']}\n\n请输入你的答案：",
            parent=self.root)
        if user_answer is None:
            return

        user_norm = self._normalize_text(user_answer)
        correct_norm = self._normalize_text(riddle["answer"])

        if not user_norm:
            messagebox.showinfo("答案", f"答案是：{riddle['answer']}",
                                parent=self.root)
            return

        if user_norm in correct_norm or correct_norm in user_norm:
            self.max_fun_time += 60
            self.current_seconds += 60
            try:
                if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
                    self.timer_label.config(
                        text=self.format_time(self.current_seconds))
            except Exception:
                pass
            messagebox.showinfo(
                "✓ 正确！",
                f"✓ 正确！休息时间 +1 分钟。\n"
                f"（正确答案：{riddle['answer']}）",
                parent=self.root)
        else:
            messagebox.showinfo("答案",
                                f"答案是：{riddle['answer']}",
                                parent=self.root)

    # ==================================================================
    # 猜数字游戏
    # ==================================================================
    def pd_tf(self, show_game="猜数字"):
        back = messagebox.askyesno(
            "警告⚠",
            f"这是一个学习软件！！！你确定要玩{show_game}？",
            parent=self.root)
        if back:
            messagebox.showinfo("提示", "我已经写了功能代码在下面，但是，嘿嘿..")
            time.sleep(random.randint(1, 5))
            self.start_number_guess()
        else:
            messagebox.showinfo("提示", "我不喜欢违心的人")
            return

    def start_number_guess(self):
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩猜数字游戏哦！")
            return
        game_window = tk.Toplevel(self.root)
        game_window.title("猜数字游戏")
        game_window.geometry("300x220")
        game_window.resizable(False, False)
        game_window.transient(self.root)
        game_window.grab_set()
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
                    result_label.config(
                        text=f"恭喜你猜对了！用了{attempts}次", fg="#27ae60")
                    guess_entry.config(state=tk.DISABLED)
                    check_btn.config(state=tk.DISABLED)
                guess_entry.delete(0, tk.END)
            except ValueError:
                result_label.config(text="请输入一个有效的数字！", fg="#e74c3c")

        tk.Label(game_window, text="我想了一个1-100之间的数字",
                 font=("微软雅黑", 12)).pack(pady=10)
        guess_entry = tk.Entry(game_window, font=("微软雅黑", 12), width=10)
        guess_entry.pack(pady=5)
        guess_entry.focus()
        check_btn = tk.Button(game_window, text="猜一下", command=check_guess,
                              font=("微软雅黑", 12))
        check_btn.pack(pady=5)
        result_label = tk.Label(game_window, text="", font=("微软雅黑", 12))
        result_label.pack(pady=10)
        game_window.bind('<Return>', lambda event: check_guess())

    # ==================================================================
    # 名言 / 积分兑换 / 自由时间
    # ==================================================================
    def show_random_quote(self):
        quote = random.choice(self.quotes)
        messagebox.showinfo("✨ 励志名言", quote)

    def exchange_score(self):
        if self.challenge_score <= 0:
            messagebox.showwarning("提示", "当前没有可兑换的积分！")
            return

        def confirm_exchange():
            try:
                exchange_num = int(entry.get())
                if exchange_num <= 0 or exchange_num > self.challenge_score:
                    messagebox.showwarning(
                        "提示",
                        f"请输入1-{self.challenge_score}之间的数字！")
                    return
                self.challenge_score -= exchange_num
                self.free_time += exchange_num * 60
                if hasattr(self, 'score_label'):
                    self.score_label.config(
                        text=f"当前积分：{self.challenge_score}")
                if hasattr(self, 'free_time_label'):
                    self.free_time_label.config(
                        text=f"{self.free_time // 60}分钟")
                self.save_data()
                if hasattr(self, 'use_free_btn'):
                    if self.free_time > 0:
                        self.use_free_btn.config(
                            state=tk.NORMAL if self.is_break else tk.DISABLED)
                messagebox.showinfo("兑换成功",
                                    f"成功兑换{exchange_num}分钟自由时间！")
                win.destroy()
            except ValueError:
                messagebox.showwarning("提示", "请输入有效的数字！")

        win = tk.Toplevel(self.root)
        win.title("积分兑换")
        win.geometry("300x150")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win,
                 text=f"当前可兑换积分：{self.challenge_score}\n1积分=1分钟自由时间",
                 font=("微软雅黑", 12)).pack(pady=10)
        entry = tk.Entry(win, font=("微软雅黑", 12), width=10)
        entry.pack(pady=5)
        entry.insert(0, "1")
        tk.Button(win, text="确认兑换", command=confirm_exchange,
                  font=("微软雅黑", 12), bg="#3498db",
                  fg="white").pack(pady=5)

    def use_free_time(self):
        if not self.is_break:
            messagebox.showwarning("提示", "只能在休息时间使用自由时间！")
            return
        if self.free_time <= 0:
            messagebox.showwarning("提示", "当前没有可用的自由时间！")
            return

        minutes = simpledialog.askinteger(
            "使用自由时间",
            f"当前拥有 {self.free_time // 60} 分钟自由时间\n"
            f"请输入要使用的分钟数：",
            minvalue=1, maxvalue=self.free_time // 60,
            parent=self.root)
        if minutes is None or minutes <= 0:
            return

        use_seconds = minutes * 60
        self.free_time -= use_seconds
        self.max_fun_time += use_seconds
        if self.is_running:
            self.current_seconds += use_seconds
            self.root.after(0, lambda: self.timer_label.config(
                text=self.format_time(self.current_seconds)))
        self.free_time_label.config(text=f"{self.free_time // 60}分钟")
        self.save_data()
        if self.free_time <= 0:
            self.use_free_btn.config(state=tk.DISABLED)
        messagebox.showinfo("使用成功",
                            f"已使用 {minutes} 分钟自由时间，当前休息时间已延长。")

    def update_exchange_btn_state(self):
        try:
            if self.challenge_score <= 0:
                self.exchange_btn.config(state=tk.DISABLED)
            else:
                self.exchange_btn.config(state=tk.NORMAL)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CZY.Orbit3.5")
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.2)
    except tk.TclError:
        pass
    try:
        root.iconbitmap(default=os.path.join(ORBIT3_DIR, "icon.ico"))
    except Exception:
        pass
    orbit3_install_crash_hooks(root)
    app = StudyCompanion(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)   # 点 X 也自动保存
    root.mainloop()