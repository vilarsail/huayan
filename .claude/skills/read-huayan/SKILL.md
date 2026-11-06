---
name: read-huayan
description: 通读《大方广佛华严经》一卷原文（docs/{N}.md 的文言原文，不读译文），只产出重难点注释表 docs/{N}.notes.md（法相术语 + 非术语难解文言词 + 复杂文本难点，三类合一，数量不设上限）；编号标注〔1〕〔2〕…由脚本写入 docs/{N}.md 原文词语首次出现处。导读 docs/{N}.guide.md 已存在，本 skill 不生成、不改动。全量重跑模式：执行时自动剥离该卷全部旧标注（旧版圈号①-㊿与旧〔n〕，含误混入译文行的残留），注释与编号从〔1〕重新编排。序号定位与全部校验由确定性脚本完成。当用户输入 /read-huayan <start> <end> 或要求"生成第 X-Y 卷的注释"、"重新注释第 X-Y 卷"时触发。
---

# 《大方广佛华严经》导读与注释（合一版 · 全量重跑）

## 角色与目标

为 `docs/{N}.md`（N = 0..80，0 号卷为三篇古序）每卷产出**重难点注释** `docs/{N}.notes.md`——在原文词语**首次出现处**以〔1〕〔2〕…标注（脚本写入 `docs/{N}.md`）。**合一取词范围**（不再是仅术语）：
   - 法相术语与华严名相（海印三昧、因陀罗网、十地、波罗蜜、陀罗尼……）
   - 非术语的难解文言词（古今异义、生僻字、关键虚词句式——尔时、何以故、所谓、咸、悉 等）
   - **复杂文本难点**（必做）：偈颂/引文的背景、人物处所背景（摩竭提国、逝多林、菩提场……）、名数结构（十种 X 清单）的读法、疑难长句的句读

**只读原文文言文，不读译文**——译文是同一流水线的下游产物，不携带独立信息。

**导读不在本 skill 范围内**：`docs/{N}.guide.md` 已有可用导读，本 skill 不生成、不校验、不覆盖它。若导读文件不存在也不补写。

## 全量重跑（硬约定）

- **本 skill 无增量模式**。对某一卷执行时，脚本先剥离该卷 `docs/{N}.md` 中**全部旧标注**——旧版圈号 ①-㊿、旧〔n〕编号，以及误混入译文行的残留（如 31.md 译文中的 ㉟㊱）——然后按新注释表从〔1〕起重新编号，**全量重写** `docs/{N}.notes.md`。
- 旧注释表不参与新注释生成，直接覆盖；`{N}.guide.md` 全程不触碰。新编号由新取词结果按首次出现位置决定，与旧编号不同属正常。
- 剥离与重写均由脚本完成，天然幂等：同一卷重复执行结果一致，不会叠加标注。**不要在 LLM 层面做任何「保留旧注释」的合并逻辑。**

## 架构

```
prepare_reading.py → docs/reading_{N}_orig.txt
    → [LLM 通读] → docs/notes_{N}.json {"terms": [{term, note}, ...]}
    → build_reading.py → notes.md + 编号写入 docs/{N}.md + 全套校验（guide.md 不动）
```

LLM 只写一个 JSON；编号分配、标注插入、字符流/编号/对应校验全部由脚本完成。**原文永不进入 LLM 写入路径。**

## 执行工作流

### 步骤一：准备（脚本）

```bash
python3 .claude/skills/read-huayan/prepare_reading.py <N>      # 单卷；也支持 <s> <e> 区间
```

生成 `docs/reading_{N}_orig.txt`（原文-only 紧凑文本，段号 P{n}，已剥离旧标注，幂等）。

### 步骤二：LLM 生成 notes_{N}.json

- 小范围（≤5 卷）：主 Agent 逐卷 Read → Write，不需要子 Agent
- 大范围（≥6 卷）：每卷一个子 Agent（subagent_type: general-purpose）并行派发（同一轮消息内发出），prompt：

```
读取 .claude/skills/read-huayan/AGENT_INSTRUCTIONS.md 获取注释生成指令，按其要求撰写。

输入文件：docs/reading_{N}_orig.txt
输出文件：docs/notes_{N}.json
```

- **断点续传**：若 `docs/notes_{N}.json` 已存在（上轮中断遗留），该卷视为已完成，跳过不重新生成；状态由文件自身承载。

### 步骤三：构建 + 校验（脚本）

```bash
python3 .claude/skills/read-huayan/build_reading.py <N>        # 或 <s> <e>
```

- 自动剥离旧标注 → 校验词条（原文精确子串）→ 按首次出现位置分配〔1〕〔2〕… → 插入标注 → 生成 `docs/{N}.notes.md`
- 内置校验：字符流完整性、编号连续递增、注释表与正文编号 1:1
- `{N}.guide.md` 不读取、不写入
- exit 1 时按报错修 `notes_{N}.json`（term 改为原文精确子串或删除该条），最多两轮修正

### 步骤四：独立复核（可选）

```bash
python3 .claude/skills/read-huayan/verify_reading.py <s> <e>
```

复核已生成结果：无旧圈号残留、正文编号连续、注释表 1:1、标注位置与词条左邻匹配（不查导读）。

### 步骤五：清理

删除 `docs/reading_{N}_orig.txt`、`docs/notes_{N}.json`。

## 注意事项

- **华严 docs 原文与译文均不含〔〕字符**（已核查 0-80 全部卷文件），〔n〕编号标注无冲突
- **docs 格式混用**（脚本已统一处理，LLM 无需关心）：`*` 行（含 `　　*`）是译文，`#` 行是标题，空行是分隔，其余行都是原文；多行颂偈合并为一段。LLM 只读规整后的 `reading_{N}_orig.txt`
- 编号按全文首次出现位置分配；term 重叠时较长者优先、冲突自动顺延；找不到独立出现位的词脚本打印 ⚠ 丢弃，不阻断
- **顺序依赖**：read-huayan 在 translate/fix-huayan 之后跑（标注插入原文行）。check-huayan / fix-huayan 只动译文块，不影响标注；summarize-huayan 复用本 skill 的 prepare_reading.py
- 编号跳号、旧格式残留等问题一律**重跑 build_reading.py 解决**（全量重写即修复），无需手工修补脚本

## 交互反馈

- 启动时简要确认要处理的卷范围；≥6 卷时告知并行派发数量
- 处理中保持静默高效
- 结束后输出简明报告：卷数、每卷注释数、校验结果（全部 ✓ / 有 ✗ 需修正）
