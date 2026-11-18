#!/usr/bin/env python3
"""
prepare_reading.py - 从 docs/{N}.md 提取「原文-only 紧凑文本」供 LLM 生成导读与注释。

提取内容：
- 标题行（# 原样保留；无 # 标题时取首段首行为标题）
- 原文段落（任意非 #、非译文、非空行；多行连续合并为一段，段号 P{n} 标注首行）
- 跳过译文行（`> ` 引用行，兼容旧 `*` 斜体行）、空行

全量重跑第一步：所有行先剥离旧标注（旧版圈号 ①-㊿ 与旧〔n〕编号），幂等。

docs/ 格式说明（现行：译文为 quote 引用；兼容旧斜体）：
- 以 `> ` 开头的引用行是译文；旧格式以 * 或 　　* 开头的行也是译文（兼容）
- 以 # 开头的是标题，空行是分隔，其余行都是原文
- 部分卷原文段以 　　（双全角空格）开头，部分卷无前缀；均按原文处理
- docs/80.md 无 # 标题，首行直接为卷名

用法：
    python3 prepare_reading.py <N>            # 单卷
    python3 prepare_reading.py <s> <e>        # 区间
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

DOCS_DIR = Path('docs')
TMP_PREFIX = 'reading_{n}_orig.txt'

# 标注样式与 build_reading.py 保持一致：统一〔n〕；圈号表仅用于剥离历史遗留
CIRCLED = ('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
           '㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚'
           '㉛㉜㉝㉞㉟'
           '㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿')
MARKER_RE = re.compile(r'〔\d+〕|[' + ''.join(CIRCLED) + ']')


def is_translation(line: str) -> bool:
    """译文行：`> ` 引用行（现行）；兼容旧斜体（* 或 　　* 开头）"""
    s = line.lstrip('　 \t')
    return s.startswith('> ') or s.startswith('*')


def is_heading(line: str) -> bool:
    """标题行：以 # 开头"""
    return line.lstrip('　 \t').startswith('#')


def is_blank(line: str) -> bool:
    """空白行"""
    return not line.strip()


def strip_markers(line: str) -> str:
    """剥离旧标注（幂等：清除历史圈号与〔n〕，避免 LLM 把标记当原文）"""
    if '〔' not in line and not any(ch in line for ch in CIRCLED):
        return line
    return MARKER_RE.sub('', line)


def parse_md(n: int):
    """返回 (title, headings, paragraphs)。
    paragraphs 为多行字符串列表（含原行格式，多行段合并）。
    识别规则：# 行→标题；* 或 　　* 行→译文（跳过）；空行→分隔；其余→原文。
    """
    path = DOCS_DIR / f'{n}.md'
    if not path.exists():
        print(f'[ERROR] {path} 不存在')
        return None
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    title = ''
    headings = []
    paragraphs = []
    cur = None
    for line in lines:
        line = strip_markers(line)
        if is_heading(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
            stripped = line.lstrip('　 \t').lstrip('#').strip()
            if stripped and not title:
                title = stripped
            headings.append(line)
        elif is_translation(line) or is_blank(line):
            if cur is not None:
                paragraphs.append('\n'.join(cur))
                cur = None
        else:
            # 原文行
            if cur is None:
                cur = [line]
            else:
                cur.append(line)
    if cur is not None:
        paragraphs.append('\n'.join(cur))

    # 无 # 标题时（如 docs/80.md），取首段首行作标题
    if not title and paragraphs:
        first_line = paragraphs[0].split('\n')[0]
        title = first_line.lstrip('　 \t').strip()
    return title, headings, paragraphs


def build_extract(title: str, headings: list[str], paragraphs: list[str]) -> str:
    out = [f'# {title}']
    for h in headings:
        s = h.lstrip('　 \t').lstrip('#').strip()
        if s != title:
            out.append(h)
    out.append('')
    for i, para in enumerate(paragraphs, 1):
        lines = para.split('\n')
        out.append(f'P{i}' + lines[0])
        out.extend(lines[1:])
    return '\n'.join(out) + '\n'


def main():
    args = sys.argv[1:]
    if not args:
        print('用法: python3 prepare_reading.py <N> | <s> <e>')
        return 2
    if len(args) == 2:
        s, e = int(args[0]), int(args[1])
        ns = list(range(s, e + 1))
    else:
        ns = [int(a) for a in args]

    print('=' * 60)
    print(f'prepare_reading: 共 {len(ns)} 章')
    print('=' * 60)
    for n in ns:
        parsed = parse_md(n)
        if parsed is None:
            return 1
        title, headings, paragraphs = parsed
        out_path = DOCS_DIR / TMP_PREFIX.format(n=n)
        out_path.write_text(build_extract(title, headings, paragraphs), encoding='utf-8')
        print(f'  [{n}] ✓ {title}: 标题={len(headings)}, 段={len(paragraphs)}'
              f' -> {out_path.name}')
    print('')
    print('LLM 输入文件: docs/reading_{N}_orig.txt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
