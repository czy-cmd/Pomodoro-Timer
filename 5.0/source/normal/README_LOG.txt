版本存在BUG，不建议作为主要应用，建议使用4.2-Orbit2

番茄钟5.0（Orbit 3）· 崩溃日志解读说明
============================================

一、崩溃日志在哪
程序崩溃时，会在程序目录下的 log 文件夹里生成一个 crash_*.log 文件，
文件名格式：crash_年-月-日_时-分-秒.log
（Ultra 版的崩溃日志比普通版 / Pro 版更详细）

二、日志里有什么
  Time        ：崩溃发生的时间
  Version     ：程序版本（normal / pro / ultra）
  Python      ：Python 版本
  Description ：错误类型和原因（最关键的一行）
  调用栈      ：出错时程序跑到哪一行（从下往上看，最下面的是真正出错处）

三、怎么自己看
先看 "Description" 那行，认一下错误类型：
  ZeroDivisionError  → 除以零
  KeyError           → 字典里找不到某个键
  IndexError         → 列表下标越界
  AttributeError     → 对象没有这个属性 / 方法
  TypeError          → 参数类型或个数不对
  ValueError         → 值不合法（比如把非数字塞进 int()）
  FileNotFoundError  → 文件不存在，路径错了或文件被移走
  PermissionError    → 没有权限，文件被占用或只读
  JSONDecodeError    → 数据文件（Orbit3_data.json）内容损坏

再看 "调用栈" 最下面那几行 "File ..." —— 那就是真正出错的位置。

四、怎么让 AI 帮你分析
把这份 README_LOG.txt 和崩溃日志（crash_*.log）一起发给 AI 助手，
让它帮你解读报错原因、给出解决办法。
