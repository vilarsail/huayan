# 新会话续跑指令（复制以下全文即可）

我在 /Users/zhangwei/work/huayan 做《华严经》教学网站（study/ 目录，单文件离线 HTML，藏青+金视觉体系）。这是分多次进行的长期任务。

先读两个文件：
1. study/_notes/ROADMAP.md —— 模块清单与进度账本（✅ 为已完成；从第一个 ⬜ 继续）
2. .claude/skills/huayan-module/SKILL.md —— 完整流程：数据抽取格式、视觉体系、测试基线、收账方式

然后按 SKILL 五步流程做 ROADMAP 中第一个未完成模块，做完一个更新一次 ROADMAP（⬜→✅ + 一行备注），并在 study/_templates/_index_t.html 加学习页卡片与 pilot 角标后重新注入生成 index.html，最后浏览器断言测试（条目计数、1280 与 390 宽无横向溢出、交互各点一遍）。

关键约束：
- 内容必须来自 docs/N.md、N.notes.md、N.guide.md 的实际文本，引用名号/法门/处所要先 grep 核实，禁止凭佛学常识编造；
- 经文已按大正藏通行本校订（卷71末含守护一切城夜神、卷73为大愿精进力夜神），网页中不得出现「缺参/重复/待校」旧表述；
- docs 段落解析必须按空行分段（译文段只有首行带 * 前缀）；解析后做刚性计数断言；
- 数据放 study/data/*_data.json，模板 study/_templates/_*_t.html 占位符注入生成 study/pages/*.html（总览页仍生成到 study/index.html），不改生成物。

一个模块测过即收账；有余力按 ROADMAP 顺序继续。跑不完就停，务必保证 ROADMAP 状态与实际文件一致。
