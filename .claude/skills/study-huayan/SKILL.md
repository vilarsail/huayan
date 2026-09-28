---
name: study-huayan
description: 为《大方广佛华严经》某一卷（docs/{N}.md 原文译文对照版）生成单文件交互式学习网页 study/{N}-study.html。针对华严经「经」的特点设计——意象解码（原文引用+解码+落点三件套）、九会定位条、众类表法翻转卡、场景漫游/名数阶梯流程推演、偈颂导读，名录名单一律折叠不逐名罗列。结构与模板固定，仅内容随卷与卷型变化。无测验区。当用户输入 /study-huayan <start> <end> 或要求"生成第 X-Y 卷的交互学习网页/学习模块"时触发。
---

# 角色与目标

为 `docs/{N}.md`（原文+译文对照）生成**交互式学习网页** `study/{N}-study.html`：让没有佛学基础的读者不读文言也能弄懂这一卷在演什么、表什么法。华严是「经」不是「论」——不靠定义与论证，而靠场景、意象、名单、偈颂表法，所以本 skill 的重心是**解码**而非**讲解**。

# 架构

**结构与交互骨架 100% 固定，只有内容变化。**

```
template.html（CSS + 固定 JS + HTML 外壳，占位符）
        │  原样复制，替换占位符
        ▼
study/{N}-study.html
        │
        ▼
check_study.py（确定性校验：组件齐全、无占位符残留、落点≥8、引文为原文精确子串等）
```

- 骨架来源：`.claude/skills/study-huayan/template.html`——CSS、进度条 JS、initStepper、initSorter **一字不改**。
- 内容规范：`.claude/skills/study-huayan/AGENT_INSTRUCTIONS.md`——占位符表、四类卷型的章节划分、意象三件套（quote+decode+touch）、名录处理原则、交互组件选型、忠实性规则、自检清单。**写内容前必须先读它。**
- 校验：`.claude/skills/study-huayan/check_study.py`（含引文逐条比对原文）。

# 工作流

## 步骤一：准备

```
mkdir -p study
```

## 步骤二：生成（LLM 全文通读 docs/{N}.md 后撰写）

### 小范围（≤5 卷）：主代理直接处理

逐卷处理：Read `docs/{N}.md` 全文（可参考 `docs/{N}.guide.md`、`docs/{N}.notes.md`）→ Read `template.html` 与 `AGENT_INSTRUCTIONS.md` → Write `study/{N}-study.html`。

### 大范围（≥6 卷）：并行子 Agent

对每卷派发一个子 Agent（`subagent_type: general-purpose`），**所有子 Agent 在同一轮消息中并行派发**。prompt：

```
读取 .claude/skills/study-huayan/AGENT_INSTRUCTIONS.md 获取交互学习网页的内容撰写规范，严格按其要求执行。

输入：docs/{N}.md（通读全文；可参考 docs/{N}.guide.md 与 docs/{N}.notes.md）
模板：.claude/skills/study-huayan/template.html（骨架原样复制，替换占位符）
输出：study/{N}-study.html
```

子 Agent 只写 HTML，不跑校验——校验由步骤三完成。

## 步骤三：校验（确定性脚本）

```
python3 .claude/skills/study-huayan/check_study.py <start> <end>
```

校验项：文件存在、组件齐全（hero/path-box/toc/hui-map/脚本）、无占位符残留、导航锚点与章节对应、落点块 ≥8 且每章 ≥1、章节数 ≥4、交互已初始化、hui-map 八会 chip 齐全且本卷高亮、**每条 .quote 引文剥圈号去空白后是 docs/{N}.md 原文的精确子串**、localStorage key 卷号一致、篇幅 ≥20 KB。

## 步骤四：修正轮

校验 exit 1 时，按打印的错误逐条修复：
- 引文非子串 → 对照 `docs/{N}.md` 修正引文用字（注意异体字、圈号位置），或缩短到确定无歧义的片段；
- 缺组件 → 检查是否遗漏模板区块；
- 落点 <8 或某章缺落点 → 补 `.touch` 块；
- 交互未初始化 → 在 `{{CUSTOM_JS}}` 位置补调用；
- 锚点不对应 → 核对 `id="sK"` 与 nav/data-target。

修完重跑 `check_study.py`。同一文件最多两轮修正，仍失败则报告用户（列出失败项），不要无限重试。

## 步骤五：交付

- 报告：卷数、每卷文件路径、校验结果。
- 单卷时可 `open study/{N}-study.html` 在浏览器中打开（先询问或按用户习惯）。

# 注意事项

- **法义忠实**：所有解释以 `docs/{N}.md` 的原文与译文为准，可参考同流水线产出的 guide.md 与 notes.md；不引入本卷没有的教义；文言引文必须是原文精确子串（脚本强制校验）。
- **意象边界**：意象解读以经文自证为限，超出本卷的宗派诠释不用；比喻优先用经文自带的（因陀罗网、大海、镜像、梦幻），现代场景点明对应关系才用。
- **名录纪律**：长名单绝不逐名罗列——讲公式、分组与「皆」句，名单主体放 dict 折叠区。这是华严卷最容易踩的坑。
- **无测验**：不产出任何 quiz/自测区；测试类交互只有「归类练习」(initSorter) 这种嵌在章节内的练习。
- **重跑幂等**：整文件重写，不存在叠加问题；localStorage key 含卷号，互不干扰。
- 落点块（`.touch`）是本 skill 与其他产物的主要差异点：**全页 ≥8，每章 ≥1**；名录型卷的落点可以是「读名单的心法」，不硬编现代故事。
