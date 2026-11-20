import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import random
import time
import threading
import json
import os
import csv
import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ===== V3.3 数据文件 =====
DATA_FILE = "study_dataV3.3.json"
V32_DATA_FILE = "study_dataV3.2.json"
V31_DATA_FILE = "study_dataV3.1.json"
V3_DATA_FILE = "study_dataV3.json"
OLD_DATA_FILE = "study_dataV2.json"
OLDER_DATA_FILE = "study_data.json"

APP_TITLE = "番茄钟3.3"
APP_BETA = "Nova 2"


class StudyCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("640x820")
        self.root.resizable(False, False)

        self.data_file = DATA_FILE
        self.mode = None
        self.mode_locked = False

        self.load_data()

        # ===== 基础参数 =====
        self.study_time = 25 * 60
        self.break_time = 5 * 60
        self.long_break_time = 15 * 60
        self.pomodoro_count = self.data.get("pomodoro_count", 0)
        self.total_study_seconds = self.data.get("total_study_seconds", 0)

        self.challenge_times = [1, 10, 100, 200, 300, 500, 1000, 10000, 100000, 999999]
        self.challenge_selected = None
        self.challenge_score = self.data.get("challenge_score", 0)
        self.free_time = self.data.get("free_time", 0)

        self.custom_time = 0
        self.exam_time = 0

        self.pomodoro_simple_count = self.data.get("simple_pomodoro_count", 0)
        self.pomodoro_simple_time = 25 * 60

        self.motto = self.data.get("motto", "")

        # ===== 统计字段 =====
        self.simple_mode_seconds = self.data.get("simple_mode_seconds", 0)
        self.simple_mode_count = self.data.get("simple_mode_count", 0)
        self.exam_mode_seconds = self.data.get("exam_mode_seconds", 0)
        self.exam_mode_count = self.data.get("exam_mode_count", 0)
        self.challenge_total_seconds = self.data.get("challenge_total_seconds", 0)
        self.challenge_count = self.data.get("challenge_count", 0)
        self.simple_pomodoro_seconds = self.data.get("simple_pomodoro_seconds", 0)
        self.simple_pomodoro_total_count = self.data.get("simple_pomodoro_total_count", 0)

        # V3.3 正计时模式
        self.count_up_seconds = self.data.get("count_up_seconds", 0)
        self.count_up_count = self.data.get("count_up_count", 0)

        self.auto_learning = self.data.get("auto_learning", False)
        self.custom_size = self.data.get("custom_size", False)

        self.daily_study = self.data.get("daily_study", {})
        if not isinstance(self.daily_study, dict):
            self.daily_study = {}

        # ===== 运行状态 =====
        self.is_running = False
        self.is_break = False
        self.current_seconds = 0
        self.timer_thread = None
        self.max_fun_time = self.break_time
        self.fun_used_time = 0
        self.exam_start_timestamp = None
        self.exam_recorded = False
        self.compact_view = False

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
            {"question": "有样东西你只能用左手拿，右手永远拿不到？", "answer": "右手"}
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
            "这句话看到了还不学习！1/101之一的概率都被你抽中了，不说明你是天选之子吗！！！"
        ]

        self.show_main_menu()

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
            # V3.3
            "count_up_seconds": 0,
            "count_up_count": 0,
            "auto_learning": False,
            "custom_size": False,
            "daily_study": {},
            "last_save_time": "",
            "save_history": [],
        }

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                for k, v in self.get_default_data().items():
                    self.data.setdefault(k, v)
                return
            except Exception:
                pass

        migrations = [
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
                f"检测到 {ver} 数据文件 ({path})，是否迁移到新版 ({DATA_FILE})？\n"
                "选择“是”将保留所有数据，选择“否”将从头开始。"
            )
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
                    messagebox.showinfo("迁移成功", f"数据已迁移至 {DATA_FILE}")
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
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
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
        self.root.title(APP_TITLE)
        self.root.geometry("640x820")
        self.apply_window_resizable(False)
        self.mode = None
        self.mode_locked = False
        self.compact_view = False

        frame = tk.Frame(self.root)
        frame.place(relx=0.5, rely=0.42, anchor="center")

        tk.Label(frame, text=APP_TITLE, font=("微软雅黑", 40, "bold"), fg="#2c3e50").pack()
        tk.Label(frame, text=APP_BETA, font=("微软雅黑", 13), fg="#95a5a6").pack(pady=(0, 45))

        tk.Button(frame, text="选择模式", command=self.open_mode_selection_with_progress,
                  font=("微软雅黑", 15), width=16, bg="#2ecc71", fg="white",
                  activebackground="#27ae60", relief=tk.FLAT, cursor="hand2").pack(pady=8)
        tk.Button(frame, text="简介", command=self.show_about,
                  font=("微软雅黑", 15), width=16, relief=tk.FLAT,
                  cursor="hand2").pack(pady=8)
        tk.Button(frame, text="设置", command=self.show_settings,
                  font=("微软雅黑", 15), width=16, relief=tk.FLAT,
                  cursor="hand2").pack(pady=8)

    def back_to_main_menu(self):
        self.is_running = False
        self.mode_locked = False
        self.mode = None
        self.compact_view = False
        self.show_main_menu()

    def show_about(self):
        """更新日志"""
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

        # 顶栏
        header = tk.Frame(win, bg="#2c3e50")
        header.pack(fill=tk.X)
        tk.Label(header, text=APP_TITLE, font=("微软雅黑", 22, "bold"),
                 bg="#2c3e50", fg="white").pack(pady=(16, 0))
        tk.Label(header, text=APP_BETA, font=("微软雅黑", 11),
                 bg="#2c3e50", fg="#bdc3c7").pack(pady=(0, 12))

        # 滚动区
        body = tk.Frame(win)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(14, 0))

        canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=500)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        def section(title):
            tk.Frame(inner, height=1, bg="#ecf0f1").pack(fill=tk.X, pady=(14, 0))
            tk.Label(inner, text=title, font=("微软雅黑", 14, "bold"),
                     fg="#2c3e50", anchor="w").pack(fill=tk.X, pady=(10, 4))

        def item(text, sub=None):
            row = tk.Frame(inner)
            row.pack(fill=tk.X, pady=(2, 0))
            tk.Label(row, text="• " + text, font=("微软雅黑", 11),
                     fg="#2c3e50", anchor="w", justify="left",
                     wraplength=470).pack(fill=tk.X, anchor="w")
            if sub:
                tk.Label(inner, text="    " + sub, font=("微软雅黑", 9),
                         fg="#95a5a6", anchor="w", justify="left",
                         wraplength=470).pack(fill=tk.X, anchor="w")

        # 作者信息
        tk.Label(inner, text="作者：CZY", font=("微软雅黑", 12, "bold"),
                 fg="#2ecc71").pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text="一款集学习计时、番茄钟、挑战、\n考试模拟与学习记录于一体的学习陪伴工具。",
                 font=("微软雅黑", 10), fg="#7f8c8d", justify="left").pack(anchor="w")

        # ===== Nova 2 =====
        section("🆕 Nova 2（当前版本）")
        item("新增「现在时间」模式", "大字显示时:分:秒，配中文日期与星期")
        item("模式选择列表新增「现在时间，正计时」按钮")
        item("简介窗口 → 更新日志窗口", "改成可滚动的版本更新说明")
        item("因为效果不佳删除两个番茄模式", "番茄钟 · 自定义 / 番茄钟 · 连续")

        # ===== Nova 1 =====
        section("Nova 1")
        item("这是一个划时代的版本，从beta的不成熟版本进入nova测试版本")
        item("全新主菜单界面", "标题 + 简介 + 设置三大入口")
        item("选择模式加入加载进度条", "0% → 100% 后弹出模式列表")
        item("学习模式新增「极简展示」按钮", "需先开启「学习模式自动」")
        item("新增两个番茄模式", "番茄钟 · 自定义 / 番茄钟 · 连续")
        item("极简模式可自定义窗口大小")
        item("学习模式统计区拆分", "今日学习时长 / 总学习时长")
        item("设置新增", "选择其他 JSON / 备份 JSON / 导出为 CSV / 生成 PNG 报告")
        item("设置新增", "新存档（红色，危险操作）")
        item("数据文件升级", "study_dataV3.2.json（自动迁移旧版本）")

        # ===== beta 5 =====
        section("beta 5")
        item("新增「我的学习记录」模式", "6 行表格 + 合计行，含挑战积分与自由时间")
        item("新增统计数据字段", "各模式的时长与次数分别统计")
        item("名言功能", "可自定义不超过 10 个字的名言")
        item("修复BUG","修复了beta 2的BUG")
        item("文件改为PYW，更加简洁")

        # ===== beta 4 =====
        section("beta 4")
        item("学习模式新增「设置名言」按钮")
        item("数据文件升级至 V3", "study_dataV3.json")
        item("挑战时间可选 1/10/100/200/300/500/1000/10000/100000/999999 秒")

        # ===== beta 3 =====
        section("beta 3")
        item("新增「极简模式」", "自定义时长，大字倒计时")
        item("新增「极简番茄模式」", "25 分钟一个番茄，自动计数")
        item("考试模式支持自定义时长")
        item("学习模式加入实时时钟")
        item("数据文件升级至 V2", "study_dataV2.json")

        # ===== beta 2 =====
        section("beta 2")
        item("扩充脑筋急转弯题库至 100 条")
        item("扩充励志名言至 100 条")
        item("挑战时间支持更长秒数")
        item("猜数字游戏加入调侃弹窗")

        # ===== beta 1 =====
        section("beta 1")
        item("加入模式选择", "学习 / 挑战 / 考试")
        item("加入 JSON 数据保存", "study_data.json")
        item("挑战模式：完成计时赢积分")
        item("积分兑换自由时间", "1 积分 = 1 分钟，版本BUG，该功能暂未实现")
        item("考试模式：极简倒计时大字")

        # ===== Alpha 1 =====
        section("Alpha 1")
        item("番茄钟雏形", "25 分钟学习 + 5 分钟休息 + 每 4 个长休息")
        item("休息娱乐区", "脑筋急转弯 / 猜数字 / 励志名言")
        item("纯内存数据", "关闭程序即丢失")

        section("loc 1")
        item("仅时钟，因版本古老无备份，无法选择")
        item("作者：CZY")


        # 底部按钮
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=(10, 14))

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

        tk.Label(prog_win, text="正在加载模式选择…", font=("微软雅黑", 12)).pack(pady=(18, 8))
        bar = ttk.Progressbar(prog_win, orient="horizontal", length=340,
                              mode="determinate", maximum=100)
        bar.pack(pady=8)
        pct_label = tk.Label(prog_win, text="0%", font=("微软雅黑", 10), fg="#7f8c8d")
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
        self.root.title(f"{APP_TITLE} - 选择模式")
        self.apply_window_resizable(False)
        self.root.geometry("640x820")

        tk.Label(self.root, text="📌 选择使用模式", font=("微软雅黑", 20, "bold")).pack(pady=15)

        self.mode_var = tk.StringVar(value="")
        options = [
            ("现在时间", "clock"),
            ("学习模式", "learning"),
            ("挑战模式", "challenge"),
            ("极简模式", "simple"),
            ("考试模式", "exam"),
            ("极简番茄", "simple_pomodoro"),
            ("正计时模式", "count_up"),
            ("我的学习记录", "records"),
        ]
        for text, value in options:
            tk.Radiobutton(self.root, text=text, variable=self.mode_var,
                           value=value, font=("微软雅黑", 12),
                           cursor="hand2").pack(pady=4)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=18)
        tk.Button(btn_frame, text="确认选择", command=self.confirm_mode,
                  font=("微软雅黑", 12), bg="#2ecc71", fg="white", width=12,
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="返回主菜单", command=self.back_to_main_menu,
                  font=("微软雅黑", 12), width=12, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

    def confirm_mode(self):
        selected = self.mode_var.get()
        if not selected:
            messagebox.showwarning("提示", "请选择一个模式！")
            return
        self.mode = selected
        self.mode_locked = True
        self.init_mode_ui()

    def back_to_mode_selection(self):
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
        win.geometry("480x880")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 240
        y = (win.winfo_screenheight() // 2) - 440
        win.geometry(f"480x880+{x}+{y}")

        tk.Label(win, text="⚙ 设置", font=("微软雅黑", 18, "bold"), fg="#2c3e50").pack(pady=(18, 5))

        # ---------- 学习模式自动 ----------
        auto_frame = tk.Frame(win)
        auto_frame.pack(fill=tk.X, padx=30, pady=(10, 0))
        auto_var = tk.BooleanVar(value=self.auto_learning)

        def toggle_auto():
            self.auto_learning = auto_var.get()
            self.save_data()

        tk.Checkbutton(auto_frame, text="学习模式自动", variable=auto_var,
                       command=toggle_auto, font=("微软雅黑", 12),
                       cursor="hand2").pack(anchor="w")
        tk.Label(win, text="开启此模式后，学习模式和极简番茄将全部自动进行，无需点击，也没有 messagebox",
                 font=("微软雅黑", 9), fg="#95a5a6", wraplength=410,
                 justify="left").pack(anchor="w", padx=50, pady=(0, 6))

        # ---------- 开启自定义大小 ----------
        size_frame = tk.Frame(win)
        size_frame.pack(fill=tk.X, padx=30, pady=(6, 0))
        size_var = tk.BooleanVar(value=self.custom_size)

        def toggle_size():
            self.custom_size = size_var.get()
            self.save_data()
            self.apply_window_resizable(False)

        tk.Checkbutton(size_frame, text="开启自定义大小", variable=size_var,
                       command=toggle_size, font=("微软雅黑", 12),
                       cursor="hand2").pack(anchor="w")
        tk.Label(win, text="开启后，所有模式的窗口大小均可自由调整",
                 font=("微软雅黑", 9), fg="#95a5a6", wraplength=410,
                 justify="left").pack(anchor="w", padx=50, pady=(0, 6))

        def mk_btn(text, cmd, desc=None, fg="#2c3e50", hover="#dfe6e9"):
            b = tk.Button(win, text=text, command=cmd, font=("微软雅黑", 12), width=24,
                          relief=tk.FLAT, bg="#ecf0f1", fg=fg, cursor="hand2",
                          activebackground=hover)
            b.pack(pady=(12, 0), ipady=4)
            if desc:
                tk.Label(win, text=desc, font=("微软雅黑", 9), fg="#95a5a6",
                         wraplength=410, justify="left").pack(anchor="w", padx=50, pady=(0, 2))
            return b

        mk_btn("选择其他 JSON", self.choose_json)
        mk_btn("备份 JSON", self.backup_json, "自选保存位置")
        mk_btn("导出为 CSV", self.export_csv)
        mk_btn("生成 PNG 报告", self.generate_png_report)
        mk_btn("清理内存", self.clean_memory, "删除用不上的时间记录")
        mk_btn("old", self.show_old_versions, "启动 Alpha 1 / beta 1~5")

        # ---------- 新存档（红色） ----------
        tk.Frame(win, height=1, bg="#ecf0f1").pack(fill=tk.X, padx=30, pady=(20, 0))
        new_btn = tk.Button(win, text="新存档", command=self.new_archive,
                            font=("微软雅黑", 12), width=24, relief=tk.FLAT,
                            bg="#fdecea", fg="#e74c3c", cursor="hand2",
                            activebackground="#f8d7da", activeforeground="#c0392b")
        new_btn.pack(pady=(14, 0), ipady=4)
        tk.Label(win, text="这将会删除你现在的存档，小心开启，建议先备份",
                 font=("微软雅黑", 9), fg="#e74c3c",
                 wraplength=410, justify="left").pack(anchor="w", padx=50, pady=(0, 2))

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

        if not messagebox.askyesno("确认", "将载入该数据文件并替换当前内存中的数据，\n是否继续？"):
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
                w.writerow(["导出时间", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
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
            d.text((36, 26), f"{APP_TITLE}  学习报告", font=f_title, fill="white")
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
                d.rectangle([bar_x, bar_y, bar_x + bar_max_w, bar_y + 30], fill="#f0f2f4")
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
        if not messagebox.askyesno("再次确认", "真的要清空所有数据吗？\n此操作不可恢复！"):
            return
        self.data = self.get_default_data()
        self.apply_data_to_state()
        self.save_data()
        messagebox.showinfo("完成", "已创建新存档，所有数据已清空。")

    # ---------- 清理内存 ----------
    def clean_memory(self):
        """清理用不上的时间记录：保存历史 + 30 天前的每日学习记录"""
        if not messagebox.askyesno(
                "确认清理",
                "将要清理以下内容：\n\n"
                "  • 保存历史记录（save_history）\n"
                "  • 30 天前的每日学习记录（daily_study）\n\n"
                "此操作不可恢复，确定继续吗？"):
            return

        removed_items = []

        # 1) 清空保存历史
        hist = self.data.get("save_history", [])
        if hist:
            removed_items.append(f"保存历史记录 {len(hist)} 条")
            self.data["save_history"] = []

        # 2) 删除 30 天前的每日学习记录
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
                    kept[k] = v  # 日期格式异常则保留
            if removed_days:
                removed_items.append(f"30 天前的每日学习记录 {removed_days} 天")
                self.daily_study = kept
                self.data["daily_study"] = kept

        # 3) 保存
        self.save_data()

        if removed_items:
            messagebox.showinfo("清理完成",
                                "已清理：\n" + "\n".join("  • " + i for i in removed_items))
        else:
            messagebox.showinfo("清理完成", "没有需要清理的记录，内存已经很干净啦。")

    # ---------- 老版本启动器 ----------
    def show_old_versions(self):
        """显示老版本选择窗口：Alpha 1 / beta 1~5 / Nova 1"""
        win = tk.Toplevel(self.root)
        win.title("old")
        win.geometry("380x560")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self.root)
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 190
        y = (win.winfo_screenheight() // 2) - 280
        win.geometry(f"380x560+{x}+{y}")

        tk.Label(win, text="🕰 老版本", font=("微软雅黑", 18, "bold"),
                 fg="#2c3e50").pack(pady=(15, 5))
        tk.Label(win, text="点击启动对应版本（会打开新窗口）",
                 font=("微软雅黑", 10), fg="#95a5a6").pack(pady=(0, 12))

        # 搜索目录：主程序所在目录 / versions / old / 老版本
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

        # 每个版本的候选文件名（不区分大小写），按优先顺序排列
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
            """先在 search_dirs 里精确匹配；失败则做一次关键字包含匹配兜底。"""
            for d in search_dirs:
                if not os.path.isdir(d):
                    continue
                try:
                    files = os.listdir(d)
                except Exception:
                    continue
                lower_map = {f.lower(): f for f in files}
                # 1) 精确匹配
                for cand in candidates:
                    if cand.lower() in lower_map:
                        return os.path.join(d, lower_map[cand.lower()])
                # 2) 关键字兜底（例如 “ggame_v2_0.pyw”）
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
                else:  # .py
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
            path = find_version_file(candidates)
            if path:
                tk.Button(win, text=name, font=("微软雅黑", 12),
                          width=20, relief=tk.FLAT, bg="#ecf0f1",
                          cursor="hand2",
                          command=lambda p=path: launch(p)).pack(pady=4, ipady=3)
            else:
                tk.Button(win, text=f"{name}（未找到）", font=("微软雅黑", 12),
                          width=20, relief=tk.FLAT, bg="#f8f9fa",
                          fg="#bdc3c7", state=tk.DISABLED).pack(pady=4, ipady=3)

        tk.Button(win, text="关闭", command=win.destroy,
                  font=("微软雅黑", 11), width=10).pack(pady=(15, 10))

    # ==================================================================
    # 现在时间模式（新增）
    # ==================================================================
    def init_clock_mode(self):
        self.root.title(f"{APP_TITLE} - 现在时间")
        self.root.geometry("640x820")
        self.apply_window_resizable(False)
        self.clear_root()
        self.create_clock_widgets()
        self.update_clock()

    def create_clock_widgets(self):
        self.clear_root()

        # 顶部提示
        tk.Label(self.root, text="🕰 现在时间", font=("微软雅黑", 18, "bold"),
                 fg="#2c3e50").pack(pady=(18, 0))

        # 主体：居中的时间 + 日期 + 星期
        wrap = tk.Frame(self.root)
        wrap.place(relx=0.5, rely=0.45, anchor="center")

        self.clock_time_label = tk.Label(
            wrap, text="00:00:00", font=("微软雅黑", 72, "bold"), fg="#2c3e50")
        self.clock_time_label.pack()

        self.clock_date_label = tk.Label(
            wrap, text="", font=("微软雅黑", 20), fg="#7f8c8d")
        self.clock_date_label.pack(pady=(14, 0))

        self.clock_week_label = tk.Label(
            wrap, text="", font=("微软雅黑", 16), fg="#95a5a6")
        self.clock_week_label.pack(pady=(4, 0))

        # 底部返回按钮
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(side=tk.BOTTOM, pady=12)

    # ==================================================================
    # 学习模式
    # ==================================================================
    def init_learning_mode(self):
        self.root.title(f"{APP_TITLE} - 学习模式")
        self.root.geometry("640x820")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = self.study_time
        self.is_break = False
        self.fun_used_time = 0
        self.compact_view = False
        self.create_learning_widgets()
        self.refresh_study_labels()
        if not self.auto_learning:
            self.show_random_quote()
        self.update_clock()
        if self.auto_learning:
            self.root.after(400, self.start_timer)

    def update_clock(self):
        # 现在时间模式 / 学习模式 都使用 update_clock
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
                    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                    self.clock_week_label.config(text=weekdays[now.weekday()])
            except tk.TclError:
                return

        self.root.after(1000, self.update_clock)

    def create_learning_widgets(self):
        title_label = tk.Label(self.root, text="📚 学习陪伴助手", font=("微软雅黑", 20, "bold"))
        title_label.pack(pady=(10, 0))

        motto_frame = tk.Frame(self.root)
        motto_frame.pack(pady=(2, 5))
        self.motto_label = tk.Label(motto_frame,
                                    text=f"我的名言：{self.motto if self.motto else '（未设置）'}",
                                    font=("微软雅黑", 12, "italic"), fg="#2c3e50")
        self.motto_label.pack(side=tk.LEFT, padx=(0, 10))
        self.set_motto_btn = tk.Button(motto_frame, text="设置名言", command=self.set_motto,
                                       font=("微软雅黑", 10), width=8)
        self.set_motto_btn.pack(side=tk.LEFT)

        self.clock_label = tk.Label(self.root, text="", font=("微软雅黑", 12), fg="#555")
        self.clock_label.pack(pady=2)

        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)
        self.timer_label = tk.Label(self.timer_frame, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"), fg="#2c3e50")
        self.timer_label.pack(pady=20)
        self.status_label = tk.Label(self.timer_frame, text="准备开始学习",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)
        self.start_btn = tk.Button(self.button_frame, text="开始学习", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white",
                                   state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        self.compact_btn = tk.Button(self.button_frame, text="极简展示",
                                     command=self.enter_compact_view,
                                     font=("微软雅黑", 12), width=10, bg="#9b59b6", fg="white")
        self.compact_btn.grid(row=0, column=3, padx=5)

        # ---------- 统计区 ----------
        self.progress_frame = tk.Frame(self.root)
        self.progress_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(self.progress_frame, text="今日完成番茄数：",
                 font=("微软雅黑", 12)).grid(row=0, column=0, sticky=tk.W)
        self.pomodoro_label = tk.Label(self.progress_frame, text=str(self.pomodoro_count),
                                       font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.pomodoro_label.grid(row=0, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="今日学习时长：",
                 font=("微软雅黑", 12)).grid(row=1, column=0, sticky=tk.W)
        self.today_time_label = tk.Label(self.progress_frame, text="0 分钟",
                                         font=("微软雅黑", 12, "bold"), fg="#27ae60")
        self.today_time_label.grid(row=1, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="总学习时长：",
                 font=("微软雅黑", 12)).grid(row=2, column=0, sticky=tk.W)
        self.total_time_label = tk.Label(self.progress_frame, text="0 分钟",
                                         font=("微软雅黑", 12, "bold"), fg="#16a085")
        self.total_time_label.grid(row=2, column=1, sticky=tk.W)

        tk.Label(self.progress_frame, text="可用自由时间：",
                 font=("微软雅黑", 12)).grid(row=3, column=0, sticky=tk.W)
        self.free_time_label = tk.Label(self.progress_frame, text=f"{self.free_time // 60}分钟",
                                        font=("微软雅黑", 12, "bold"), fg="#3498db")
        self.free_time_label.grid(row=3, column=1, sticky=tk.W)

        # ---------- 娱乐区 ----------
        self.fun_frame = tk.LabelFrame(self.root, text="休息娱乐区（仅休息时间可用）",
                                       font=("微软雅黑", 12))
        self.fun_frame.pack(pady=10, padx=20, fill=tk.X)

        self.riddle_btn = tk.Button(self.fun_frame, text="猜个脑筋急转弯", command=self.show_riddle,
                                    font=("微软雅黑", 10), state=tk.DISABLED)
        self.riddle_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.number_guess_btn = tk.Button(self.fun_frame, text="玩猜数字游戏", command=self.pd_tf,
                                          font=("微软雅黑", 10), state=tk.DISABLED)
        self.number_guess_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.quote_btn = tk.Button(self.fun_frame, text="看句励志名言", command=self.show_random_quote,
                                   font=("微软雅黑", 10))
        self.quote_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.exchange_btn = tk.Button(self.fun_frame, text="积分兑换自由时间", command=self.exchange_score,
                                      font=("微软雅黑", 10))
        self.exchange_btn.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.update_exchange_btn_state()

        self.use_free_btn = tk.Button(self.fun_frame, text="使用自由时间（延长休息）",
                                      command=self.use_free_time,
                                      font=("微软雅黑", 10), state=tk.DISABLED)
        self.use_free_btn.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        self.fun_time_label = tk.Label(self.fun_frame, text="", font=("微软雅黑", 10), fg="#e74c3c")
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
                self.total_time_label.config(text=self.format_duration(self.calc_total_study_all()))
            if hasattr(self, 'pomodoro_label') and self.pomodoro_label.winfo_exists():
                self.pomodoro_label.config(text=str(self.pomodoro_count))
            if hasattr(self, 'free_time_label') and self.free_time_label.winfo_exists():
                self.free_time_label.config(text=f"{self.free_time // 60}分钟")
        except Exception:
            pass

    def set_motto(self):
        current = self.motto if self.motto else ""
        new_motto = simpledialog.askstring("设置我的名言", "请输入你的励志名言（不超过10个字）：",
                                           initialvalue=current, parent=self.root)
        if new_motto is None:
            return
        if len(new_motto) > 10:
            messagebox.showwarning("提示", "名言不能超过10个字！")
            return
        self.motto = new_motto.strip()
        self.motto_label.config(text=f"我的名言：{self.motto if self.motto else '（未设置）'}")
        self.save_data()

    # ---------- 极简展示 ----------
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
        self.root.geometry("360x200")
        self.root.resizable(False, False)

        self.timer_label = tk.Label(self.root,
                                    text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 56, "bold"), fg="#2c3e50")
        self.timer_label.pack(expand=True)

        tk.Button(self.root, text="恢复到正常模式", command=self.exit_compact_view,
                  font=("微软雅黑", 11), relief=tk.FLAT, cursor="hand2",
                  bg="#ecf0f1").pack(pady=10, ipadx=10)

    def exit_compact_view(self):
        self.compact_view = False
        self.root.geometry("640x820")
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
        self.root.title(f"{APP_TITLE} - 挑战模式")
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

        tk.Label(challenge_win, text="选择挑战时长（秒）", font=("微软雅黑", 14)).pack(pady=15)

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
            tk.Button(frame, text=f"{t}秒", command=lambda x=t: select_time(x),
                      font=("微软雅黑", 12), width=8).grid(row=0, column=self.challenge_times.index(t), padx=5)

    def create_challenge_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="🔥 挑战模式", font=("微软雅黑", 20, "bold")).pack(pady=10)
        self.score_label = tk.Label(self.root, text=f"当前积分：{self.challenge_score}",
                                    font=("微软雅黑", 14), fg="#e67e22")
        self.score_label.pack(pady=5)
        self.timer_frame = tk.Frame(self.root, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        self.timer_frame.pack(pady=10, padx=20, fill=tk.X)
        self.timer_label = tk.Label(self.timer_frame, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 48, "bold"), fg="#2c3e50")
        self.timer_label.pack(pady=20)
        self.status_label = tk.Label(self.timer_frame, text=f"挑战时长：{self.challenge_selected}秒",
                                     font=("微软雅黑", 14), fg="#7f8c8d")
        self.status_label.pack(pady=5)
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)
        self.start_btn = tk.Button(self.button_frame, text="开始挑战", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white",
                                   state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置挑战", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        tk.Label(self.root,
                 text="✅ 挑战规则：完成计时不暂停/重置即可获得对应积分\n"
                      "100秒=1积分 | 200秒=2积分 | 300秒=3积分",
                 font=("微软雅黑", 10), fg="#7f8c8d").pack(pady=10)
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 极简模式
    # ==================================================================
    def init_simple_mode(self):
        self.root.title(f"{APP_TITLE} - 极简模式")
        self.apply_window_resizable(True)
        self.clear_root()
        minutes = simpledialog.askinteger("自定义时间", "请输入极简模式时长（分钟）：",
                                          minvalue=1, maxvalue=100000, parent=self.root)
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
        self.timer_label = tk.Label(self.root, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 80, "bold"), fg="#2c3e50")
        self.timer_label.pack(expand=True)
        self.start_btn = tk.Button(self.root, text="开始", command=self.start_timer,
                                   font=("微软雅黑", 14), width=10, bg="#2ecc71", fg="white")
        self.start_btn.pack(pady=30)
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 考试模式
    # ==================================================================
    def init_exam_mode(self):
        self.root.title(f"{APP_TITLE} - 考试模式")
        self.apply_window_resizable(False)
        self.clear_root()
        minutes = simpledialog.askinteger("考试时间", "请输入考试时长（分钟）：",
                                          minvalue=1, maxvalue=999, parent=self.root)
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
        tk.Label(self.root, text="📝 考试模式", font=("微软雅黑", 20, "bold")).pack(pady=10)
        tk.Label(self.root, text=f"考试时长：{self.exam_time // 60} 分钟",
                 font=("微软雅黑", 12)).pack(pady=5)
        self.timer_label = tk.Label(self.root, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 60, "bold"), fg="#2c3e50")
        self.timer_label.pack(expand=True)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        self.start_btn = tk.Button(self.button_frame, text="开始考试", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white",
                                   state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        self.submit_btn = tk.Button(self.button_frame, text="交卷", command=self.submit_exam,
                                    font=("微软雅黑", 12), width=10, bg="#3498db", fg="white",
                                    state=tk.DISABLED)
        self.submit_btn.grid(row=0, column=3, padx=5)
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
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
        self.root.title(f"{APP_TITLE} - 极简番茄")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = self.pomodoro_simple_time
        self.create_simple_pomodoro_widgets()
        if self.auto_learning:
            self.root.after(400, self.start_timer)

    def create_simple_pomodoro_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="🍅 极简番茄", font=("微软雅黑", 20, "bold")).pack(pady=10)
        self.count_label = tk.Label(self.root,
                                    text=f"本次已完成番茄：{self.pomodoro_simple_count} 个",
                                    font=("微软雅黑", 14), fg="#27ae60")
        self.count_label.pack(pady=5)
        self.timer_label = tk.Label(self.root, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 60, "bold"), fg="#2c3e50")
        self.timer_label.pack(expand=True)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=20)
        self.start_btn = tk.Button(self.button_frame, text="开始", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white",
                                   state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.reset_btn = tk.Button(self.button_frame, text="重置", command=self.reset_timer,
                                   font=("微软雅黑", 12), width=10, bg="#e74c3c", fg="white")
        self.reset_btn.grid(row=0, column=2, padx=5)
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
                  font=("微软雅黑", 10), relief=tk.FLAT).pack(pady=5)

    # ==================================================================
    # 正计时模式
    # ==================================================================
    def init_count_up_mode(self):
        self.root.title(f"{APP_TITLE} - 正计时")
        self.apply_window_resizable(False)
        self.clear_root()
        self.current_seconds = 0
        self.create_count_up_widgets()

    def create_count_up_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="⏳ 正计时", font=("微软雅黑", 22, "bold")).pack(pady=(15, 0))
        tk.Label(self.root, text="从 0 开始累计，随时点击「结束并保存」记入学习记录",
                 font=("微软雅黑", 10), fg="#7f8c8d").pack()

        self.timer_label = tk.Label(self.root, text=self.format_time(self.current_seconds),
                                    font=("微软雅黑", 72, "bold"), fg="#2c3e50")
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
        self.start_btn = tk.Button(self.button_frame, text="开始", command=self.start_timer,
                                   font=("微软雅黑", 12), width=10, bg="#2ecc71", fg="white")
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = tk.Button(self.button_frame, text="暂停", command=self.pause_timer,
                                   font=("微软雅黑", 12), width=10, bg="#f39c12", fg="white",
                                   state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.stop_btn = tk.Button(self.button_frame, text="结束并保存", command=self.stop_count_up,
                                  font=("微软雅黑", 12), width=12, bg="#3498db", fg="white")
        self.stop_btn.grid(row=0, column=2, padx=5)
        tk.Button(self.root, text="返回模式选择", command=self.back_to_mode_selection,
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
        self.root.title(f"{APP_TITLE} - 我的学习记录")
        self.apply_window_resizable(False)
        self.clear_root()
        self.create_records_widgets()

    def create_records_widgets(self):
        self.clear_root()
        tk.Label(self.root, text="📊 我的学习记录", font=("微软雅黑", 20, "bold")).pack(pady=(15, 10))

        total_seconds = self.calc_total_study_all()

        summary_frame = tk.Frame(self.root, bg="#ecf0f1", bd=2, relief=tk.GROOVE)
        summary_frame.pack(pady=5, padx=30, fill=tk.X)
        tk.Label(summary_frame, text="累计学习时长", font=("微软雅黑", 12),
                 bg="#ecf0f1", fg="#7f8c8d").pack(pady=(8, 0))
        tk.Label(summary_frame, text=self.format_duration(total_seconds),
                 font=("微软雅黑", 20, "bold"), bg="#ecf0f1", fg="#e67e22").pack(pady=(0, 10))

        table = tk.Frame(self.root)
        table.pack(pady=10, padx=30, fill=tk.BOTH, expand=True)

        headers = ["模式", "完成情况", "累计时长"]
        for col, h in enumerate(headers):
            tk.Label(table, text=h, font=("微软雅黑", 12, "bold"),
                     bg="#3498db", fg="white", pady=6).grid(row=0, column=col,
                                                            sticky="nsew", padx=1, pady=1)

        rows = self.get_record_rows()
        for i, (mode, count, dur) in enumerate(rows, start=1):
            bg = "#ffffff" if i % 2 else "#f8f9fa"
            tk.Label(table, text=mode, font=("微软雅黑", 11), bg=bg, pady=6).grid(
                row=i, column=0, sticky="nsew", padx=1, pady=1)
            tk.Label(table, text=count, font=("微软雅黑", 11), bg=bg, pady=6).grid(
                row=i, column=1, sticky="nsew", padx=1, pady=1)
            tk.Label(table, text=self.format_duration(dur), font=("微软雅黑", 11),
                     bg=bg, pady=6).grid(row=i, column=2, sticky="nsew", padx=1, pady=1)

        n = len(rows) + 1
        tk.Label(table, text="合计", font=("微软雅黑", 12, "bold"),
                 bg="#e67e22", fg="white", pady=6).grid(row=n, column=0,
                                                        sticky="nsew", padx=1, pady=1)
        tk.Label(table, text="", bg="#e67e22").grid(row=n, column=1,
                                                    sticky="nsew", padx=1, pady=1)
        tk.Label(table, text=self.format_duration(total_seconds),
                 font=("微软雅黑", 12, "bold"), bg="#e67e22", fg="white",
                 pady=6).grid(row=n, column=2, sticky="nsew", padx=1, pady=1)

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
                     font=("微软雅黑", 11, "italic"), fg="#7f8c8d").pack(pady=5)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="返回模式选择", command=self.back_to_mode_selection,
                  font=("微软雅黑", 12), width=14, bg="#2ecc71", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="清空记录", command=self.reset_records,
                  font=("微软雅黑", 12), width=14, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)

    def reset_records(self):
        if not messagebox.askyesno("确认", "确定要清空所有学习记录吗？此操作不可恢复！"):
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
                if self.mode in ["learning", "challenge", "simple_pomodoro", "exam",
                                 "count_up"]:
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
                            text="专注学习中..." if not self.is_break else "休息时间，放松一下~")
                    except Exception:
                        pass
                    if self.is_break:
                        self.enable_fun_buttons()
                elif self.mode == "challenge":
                    try:
                        self.status_label.config(text="挑战进行中...")
                    except Exception:
                        pass

            self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
            self.timer_thread.start()

    def update_timer(self):
        # 正计时：从 0 往上加
        if self.mode == "count_up":
            while self.is_running:
                time.sleep(1)
                if not self.is_running:
                    break
                self.current_seconds += 1
                self.root.after(0, lambda: self.set_timer_text(
                    self.format_time(self.current_seconds)))
            return

        # 倒计时
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

            if self.pomodoro_count % 4 == 0:
                self.current_seconds = self.long_break_time
                self.max_fun_time = self.long_break_time
                if not self.auto_learning:
                    messagebox.showinfo("太棒了！",
                                        f"你已经完成了{self.pomodoro_count}个番茄钟！\n"
                                        f"奖励你一个{self.long_break_time // 60}分钟的长休息！")
            else:
                self.current_seconds = self.break_time
                self.max_fun_time = self.break_time
                if not self.auto_learning:
                    messagebox.showinfo("学习时间结束",
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
        messagebox.showinfo("挑战成功！",
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
            messagebox.showinfo("番茄完成",
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
            self.count_label.config(text=f"本次已完成番茄：{self.pomodoro_simple_count} 个")
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

    def show_riddle(self):
        if not self.is_break:
            messagebox.showwarning("提示", "只有在休息时间才能玩脑筋急转弯哦！")
            return
        riddle = random.choice(self.riddles)
        answer = messagebox.askquestion("脑筋急转弯",
                                        f"{riddle['question']}\n\n点击'是'查看答案")
        if answer == 'yes':
            messagebox.showinfo("答案", f"答案是：{riddle['answer']}")

    def pd_tf(self, show_game="猜数字"):
        back = messagebox.askyesno("警告⚠",
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
        game_window.geometry("300x200")
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
                    result_label.config(text=f"恭喜你猜对了！用了{attempts}次", fg="#27ae60")
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
                    messagebox.showwarning("提示",
                                           f"请输入1-{self.challenge_score}之间的数字！")
                    return
                self.challenge_score -= exchange_num
                self.free_time += exchange_num * 60
                if hasattr(self, 'score_label'):
                    self.score_label.config(text=f"当前积分：{self.challenge_score}")
                if hasattr(self, 'free_time_label'):
                    self.free_time_label.config(text=f"{self.free_time // 60}分钟")
                self.save_data()
                if hasattr(self, 'use_free_btn'):
                    if self.free_time > 0:
                        self.use_free_btn.config(
                            state=tk.NORMAL if self.is_break else tk.DISABLED)
                messagebox.showinfo("兑换成功", f"成功兑换{exchange_num}分钟自由时间！")
                win.destroy()
            except ValueError:
                messagebox.showwarning("提示", "请输入有效的数字！")

        win = tk.Toplevel(self.root)
        win.title("积分兑换")
        win.geometry("300x150")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=f"当前可兑换积分：{self.challenge_score}\n1积分=1分钟自由时间",
                 font=("微软雅黑", 12)).pack(pady=10)
        entry = tk.Entry(win, font=("微软雅黑", 12), width=10)
        entry.pack(pady=5)
        entry.insert(0, "1")
        tk.Button(win, text="确认兑换", command=confirm_exchange,
                  font=("微软雅黑", 12), bg="#3498db", fg="white").pack(pady=5)

    def use_free_time(self):
        if not self.is_break:
            messagebox.showwarning("提示", "只能在休息时间使用自由时间！")
            return
        if self.free_time <= 0:
            messagebox.showwarning("提示", "当前没有可用的自由时间！")
            return

        minutes = simpledialog.askinteger(
            "使用自由时间",
            f"当前拥有 {self.free_time // 60} 分钟自由时间\n请输入要使用的分钟数：",
            minvalue=1, maxvalue=self.free_time // 60, parent=self.root)
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
        messagebox.showinfo("使用成功", f"已使用 {minutes} 分钟自由时间，当前休息时间已延长。")

    def update_exchange_btn_state(self):
        try:
            if self.challenge_score <= 0:
                self.exchange_btn.config(state=tk.DISABLED)
            else:
                self.exchange_btn.config(state=tk.NORMAL)
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = StudyCompanion(root)
    root.mainloop()