#!/usr/bin/env python3
"""校验 study/pages/{N}-study.html 的结构完整性与内容规范（华严经版）。

额外校验：所有 .quote 块中的引文必须是 docs/{N}.md 原文的精确子串
（比对前剥离标签、圈号与空白）。

用法: python3 .claude/skills/study-huayan/check_study.py <N> [<M> ...]
exit 0 = 全部通过; exit 1 = 有失败项（逐条打印）。
"""
import sys
import re
import os

REQUIRED = [
    ('class="hero"', "hero 头部"),
    ('path-box', "学习路径区块"),
    ('id="toc"', "导航"),
    ('hui-map', "九会定位条"),
    ('<script>', "脚本"),
    ('renderPath();', "进度初始化调用"),
]
FORBIDDEN = [
    ('{{', "未替换的占位符"),
    ('quiz', "测验区块"),
]

DOCS_DIR = 'docs'

CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')


def _strip_circled_ws(s: str) -> str:
    return ''.join(ch for ch in s if ch not in CIRCLED and not ch.isspace())


def load_original(n: int) -> str:
    """docs/{N}.md 的原文流（跳过译文 `> ` 引用行、旧斜体 * 行、标题 # 行、空行），剥圈号与空白。"""
    path = os.path.join(DOCS_DIR, f'{n}.md')
    if not os.path.exists(path):
        return ''
    lines = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.lstrip('　 \t')
            if s.startswith('> ') or s.startswith('*') or s.startswith('#'):
                continue
            lines.append(line)
    return _strip_circled_ws(''.join(lines))


def extract_quotes(s: str):
    """提取所有 .quote 块的纯文本（去掉 src 来源行与标签）。"""
    quotes = []
    for m in re.finditer(r'<div class="quote">(.*?)</div>', s, re.S):
        body = re.sub(r'<span class="src">.*?</span>', '', m.group(1), flags=re.S)
        body = re.sub(r'<[^>]+>', '', body)
        quotes.append(body.strip())
    return quotes


def check(n: int) -> list:
    path = f"study/pages/{n}-study.html"
    errs = []
    if not os.path.exists(path):
        return [f"文件不存在: {path}"]

    with open(path, encoding="utf-8") as f:
        s = f.read()

    for needle, desc in REQUIRED:
        if needle == 'hui-map':
            if 'class="hui-map"' not in s:
                errs.append(f"缺少组件: {desc} (hui-map)")
        elif needle not in s:
            errs.append(f"缺少组件: {desc} ({needle})")

    for needle, desc in FORBIDDEN:
        if needle in s:
            errs.append(f"不应出现: {desc} ({needle})")

    # 定制 JS 占位符应已替换
    if '@@CUSTOM_JS@@' in s:
        errs.append("占位符未替换: @@CUSTOM_JS@@")

    # 导航锚点与章节 id 对应
    for m in re.finditer(r'href="#(s\d+)"', s):
        if f'id="{m.group(1)}"' not in s:
            errs.append(f"导航锚点 #{m.group(1)} 无对应章节")

    # 学习路径步骤的 data-target 有效
    for m in re.finditer(r'data-target="#(s\d+)"', s):
        if f'id="{m.group(1)}"' not in s:
            errs.append(f"路径步骤 data-target #{m.group(1)} 无对应章节")

    # 交互组件初始化
    calls = len(re.findall(r'initStepper\(|initSorter\(', s))
    if calls < 2:  # 模板自带函数定义各 1 处，至少还要有 1 次实际调用
        errs.append("定制交互未初始化（无 initStepper/initSorter 调用）")

    # hui-map chips：应含全部八会且本卷会高亮
    chips = re.findall(r'<span class="hui[^"]*">([^<]+)</span>', s)
    if len(chips) < 8:
        errs.append(f"hui-map 会次 chip 仅 {len(chips)} 个，应有八会")
    if 'class="hui cur"' not in s:
        errs.append("hui-map 无本卷所在会的高亮（class=\"hui cur\"）")

    # 落点块数量
    touches = s.count('class="touch"')
    if touches < 8:
        errs.append(f"落点块仅 {touches} 个，要求 ≥8")

    # 每章 ≥1 个落点块
    sections = re.split(r'<section class="chapter"', s)[1:]
    for i, sec in enumerate(sections, 1):
        if 'class="touch"' not in sec:
            errs.append(f"第 {i} 章缺少落点块（.touch）")

    # 章节数
    chapters = len(sections)
    if chapters < 4:
        errs.append(f"章节数仅 {chapters} 个，要求 ≥4")

    # localStorage key
    if f"huayan{n}-study-progress" not in s:
        errs.append("localStorage key 与卷号不符")

    # 引文精确子串校验
    orig = load_original(n)
    if not orig:
        errs.append(f"无法读取原文 docs/{n}.md（引文校验跳过）")
    else:
        quotes = extract_quotes(s)
        if not quotes:
            errs.append("没有任何 .quote 原文引用块")
        for q in quotes:
            qs = _strip_circled_ws(q)
            if not qs:
                errs.append("存在空的 .quote 块")
            elif qs not in orig:
                head = q.strip().replace('\n', ' ')[:30]
                errs.append(f"引文非原文精确子串: 「{head}…」")

    kb = len(s.encode("utf-8")) / 1024
    if kb < 20:
        errs.append(f"篇幅过短（{kb:.0f} KB < 20 KB）")

    if not errs:
        print(f"[{n}] ✓ {path} ({kb:.0f} KB, 章节 {chapters}, 落点 {touches}, "
              f"引文 {len(extract_quotes(s))} 条全部核对通过)")
    else:
        print(f"[{n}] ✗ {path}")
        for e in errs:
            print(f"   - {e}")
    return errs


def main():
    ns = sys.argv[1:]
    if not ns:
        print(__doc__)
        sys.exit(1)
    failed = False
    for n in ns:
        if check(int(n)):
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
