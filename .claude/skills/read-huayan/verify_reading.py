#!/usr/bin/env python3
"""verify_reading.py - 独立复核 docs/{N}.md / {N}.notes.md 的完整性（导读不在检查范围）。

检查项：
- docs/{N}.md 与 {N}.notes.md 存在且非空（导读 {N}.guide.md 不在检查范围）
- 旧版圈号 ①-㊿ 已全部清除（正文/标题/译文任何位置残留即报错）
- 标注只出现在原文行（标题/译文行含〔n〕即报错）
- 正文〔n〕编号连续递增：〔1〕..〔k〕
- notes.md 注释表与正文编号 1:1、顺序一致
- 每个标注的左邻字符与注释表词条精确匹配

用法：
    python3 verify_reading.py <start> <end>
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

DOCS_DIR = Path('docs')

CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
CIRCLED_SET = set(CIRCLED)
MARKER_RE = re.compile(r'〔(\d+)〕')
NUM_RE = re.compile(r'〔(\d+)〕')

def ws_strip(s: str) -> str:
    return ''.join(ch for ch in s if not ch.isspace())


def is_translation(line: str) -> bool:
    return line.lstrip('　 \t').startswith('*')


def is_heading(line: str) -> bool:
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    return not line.strip()


def parse_md(n: int):
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    title = ''
    paragraphs = []
    cur = None
    for line in text.split('\n'):
        if is_heading(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
            stripped = line.lstrip('　 \t').lstrip('#').strip()
            if stripped and not title:
                title = stripped
        elif is_translation(line) or is_blank(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
        else:
            if cur is None:
                cur = [line]
            else:
                cur.append(line)
    if cur is not None:
        paragraphs.append('\n'.join(cur))
    if not title and paragraphs:
        title = paragraphs[0].split('\n')[0].lstrip('　 \t').strip()
    return title, paragraphs, text


def parse_notes_md(n: int):
    path = DOCS_DIR / f'{n}.notes.md'
    if not path.exists():
        return None
    items = []
    for line in path.read_text(encoding='utf-8').split('\n'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = re.match(r'^〔(\d+)〕\s*(\S.*?)　(.*)$', line.strip())
        if not m:
            m = re.match(r'^〔(\d+)〕\s+(\S.*?)\s+(.*)$', line.strip())
            if not m:
                continue
        items.append((int(m.group(1)), m.group(2), m.group(3)))
    return items


def verify_volume(n: int) -> tuple[list[str], list[str]]:
    """返回 (problems, warnings)。problems 阻断（退出码 1），warnings 仅提示。"""
    problems = []
    warnings = []

    for fname in (f'{n}.md', f'{n}.notes.md'):
        p = DOCS_DIR / fname
        if not p.exists():
            problems.append(f'缺少文件 {fname}')
            return problems, warnings
        if not p.read_text(encoding='utf-8').strip():
            problems.append(f'空文件 {fname}')

    parsed = parse_md(n)
    if parsed is None:
        problems.append(f'无法解析 {n}.md')
        return problems, warnings
    title, paragraphs, full_text = parsed

    # 1) 旧版圈号必须已全部清除（全文任何位置）
    stray = sorted({ch for ch in full_text if ch in CIRCLED_SET})
    if stray:
        problems.append(f'旧版圈号残留: {"".join(stray)}（应重跑 build_reading.py 清除）')

    # 2) 标注只允许出现在原文行
    for line in full_text.split('\n'):
        if (is_heading(line) or is_translation(line)) and MARKER_RE.search(line):
            problems.append(f'标注越界（标题/译文行含〔n〕）: {line[:40]}')
            break

    # 3) 正文编号连续递增
    seq = [int(m.group(1)) for m in MARKER_RE.finditer(''.join(paragraphs))]
    expect = list(range(1, len(seq) + 1))
    if seq != expect:
        first_break = next((i for i, (a, b) in enumerate(zip(seq, expect)) if a != b),
                           len(seq))
        problems.append(
            f'正文编号不连续: 共 {len(seq)} 个，首个断点在第 {first_break + 1} 个'
            f'（期望〔{expect[first_break] if first_break < len(expect) else "?"}〕'
            f' 实际〔{seq[first_break] if first_break < len(seq) else "?"}〕）')

    # 4) 注释表
    notes_items = parse_notes_md(n)
    if notes_items is None:
        problems.append(f'无法解析 {n}.notes.md')
        return problems, warnings

    notes_nums = [num for num, _, _ in notes_items]
    if notes_nums != expect:
        problems.append(f'注释表编号与正文不一致: 表 {len(notes_nums)} 条 / 正文 {len(seq)} 个，'
                        f'或顺序不符')

    # 5) 标注位置与词条左邻匹配
    marker_to_term = {}
    for num, term, _ in notes_items:
        if num in marker_to_term:
            problems.append(f'注释表重复编号: 〔{num}〕')
            continue
        marker_to_term[num] = term

    for pi, para in enumerate(paragraphs):
        for ci, m in enumerate(MARKER_RE.finditer(para)):
            num = int(m.group(1))
            term = marker_to_term.get(num)
            if term is None:
                continue
            left = ws_strip(para[:m.start()])
            if not left.endswith(ws_strip(term)):
                tail = left[-min(len(ws_strip(term)) + 5, len(left)):]
                problems.append(
                    f'位置不匹配: 第 {pi + 1} 段〔{num}〕左邻应为「{term}」，'
                    f'实际「…{tail}」')

    return problems, warnings


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        print('用法: python3 verify_reading.py <start> <end>')
        return 2
    s, e = int(args[0]), int(args[1])
    ns = list(range(s, e + 1))
    print('=' * 60)
    print(f'verify_reading: 共 {len(ns)} 章（{s}-{e}）')
    print('=' * 60)
    total_ok = total_issues = total_warns = 0
    for n in ns:
        problems, warnings = verify_volume(n)
        if not problems:
            tag = '✓ 全部通过'
            if warnings:
                tag += f'（{len(warnings)} 条提示）'
            print(f'  [{n}] {tag}')
            for w in warnings:
                print(f'       - {w}')
            total_ok += 1
            total_warns += len(warnings)
        else:
            print(f'  [{n}] ✗ {len(problems)} 个问题:')
            for p in problems:
                print(f'       - {p}')
            for w in warnings:
                print(f'       - {w}')
            total_issues += len(problems)
            total_warns += len(warnings)
    print('=' * 60)
    print(f'汇总: {total_ok}/{len(ns)} 章通过，{total_issues} 项阻断，{total_warns} 条提示')
    return 0 if total_issues == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
