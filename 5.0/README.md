# 5.0 / Orbit3

> 版本存在BUG，不建议作为主要应用，建议使用4.2-Orbit2

以番茄钟 4.2（Orbit2）为主体，合并任务管理器 3.0、鼠标检测器、小功能等。仅作功能预览，不建议日常主用。

## 目录

```
source/
  normal/   orbit3.pyw + orbit3_tm.py + orbit3_mouse.py
  pro/      同上 + 开发者模式
  ultra/    同上 + 附件系统 + HTML 更新日志
  se/       orbit3_se.pyw + task_manager.pyw（精简版）
  每个变体含 icon.ico / README.html / mods / almfq / presets / old
exe/
  orbit3_se.exe   SE 主程序（绿色版）
  icon.ico, README.html, presets/
```

## 为什么没有安装/卸载 exe

GitHub 不允许仓库里的文件 >25MB。原安装程序 `orbit3_installer.exe` 为 52MB，
`orbit3_se_installer.exe` 为 30MB，均超过限制，因此连同 `uninstall.exe` 一并移除。
5.0 只保留可直接运行的 `orbit3_se.exe`（约 10MB）。

## 运行

- 源码：进入任一变体目录，双击主 `.pyw`（Windows + Python 3.8+）。
- 应用：运行 `exe/orbit3_se.exe`。
- 在用安装目录 `其他与使用的exe/Orbit3` 已排除。

## 历史版本（各变体 old/）

| 文件 | 版本 | 旧名 |
| --- | --- | --- |
| v1_0.py / v1_0.pyw | 1.0 | ggame.py / alpha1 |
| v2_0.py / v2_0.pyw | 2.0 | ggame2.0.py / beta1 |
| v2_7.py / v2_7.pyw | 2.7 | ggame2.7.py / beta2 |
| v2_9.py / v2_9.pyw | 2.9 | ggame2.9.py / beta3 |
| v3_0.py / v3_0.pyw | 3.0 | ggame3.0.py / beta4 |
| v3_1.py / v3_1.pyw | 3.1 | ggame3.1.pyw / beta5 |
| v3_2.py / v3_2.pyw | 3.2 | ggame3.2.pyw / nova1 |
| v3_3.py / v3_3.pyw | 3.3 | nova2 |
| v4_0.pyw | 4.0 | Orbit1 |
| v4_2.pyw | 4.2 | Orbit2 |

源码内老版本启动列表与图标路径已同步更新。

## 数据

- 不含个人存档：`Orbit3_data.json`、`study_data*.json`、备份、`save/` 均未纳入。
- `questions.json` 为题库资源，保留在 normal / pro / ultra 源码中。
- 首次运行会生成新数据；不会读取个人学习存档。
