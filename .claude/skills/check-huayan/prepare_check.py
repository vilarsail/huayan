#!/usr/bin/env python3
"""
prepare_check.py — 校对前置：从 docs/{N}.md 提取「原文段 → 译文段」对，生成批次 chunk 文件。

仅做机械工作（段对提取、分批切块），不做任何质量判断。
质量判断全部由 LLM 在读取 chunk 全量信息后完成。

输出（临时文件放在 docs/ 下）：
- docs/pairs_{N}.json：所有段对 {"1": {"orig": "...", "trans": "..."}, ...}
- docs/check_{N}_batch{b}.json：每批最多 BATCH 个段对，含前 2 段上下文，供子 Agent 逐段判断

docs/{N}.md 格式（现行：译文为 quote 引用行；兼容旧斜体）：
- 译文行：以 `> ` 开头的引用行（现行格式）；旧斜体行（`*译文*`，可带 　　前缀）仍兼容
- 标题行：以 # 开头
- 原文行：其余所有非空行（可能带 　　 前缀，也可能顶格）
- 引用/斜体行均逐行自识别，无跨行续行（保留旧斜体未闭合续行兼容逻辑）
- 页脚杂行（大方广佛华严经卷第… / 大正新修大藏经… / 孤立的 .）：跳过，不算段落

trans 字段输出纯文本：剥离 `> ` 前缀与 `*` 包裹，多行用 \n 连接。
"""

import json, sys, os, re

BATCH = 20  # 每批段对数（含上下文）。校对需逐段对比原文与译文，认知负荷高，与 read-huayan 流水线对齐取 20

# 页脚/杂行（不算原文也不算译文）
NOISE_PATTERNS = (
    re.compile(r'^大正新修大藏经'),
    re.compile(r'^大[方广佛华严经]+卷第'),
)


def is_noise(line: str) -> bool:
    s = line.strip()
    if s.startswith('>'):
        s = s.lstrip('> ').strip()
    s = s.lstrip('*').strip()
    if s in ('.', '。'):
        return True
    return any(p.match(s) for p in NOISE_PATTERNS)


def is_trans_line(line: str) -> bool:
    s = line.lstrip(' \u3000\t')
    return s.startswith('> ') or s.startswith('*')


def trans_text(line: str) -> str:
    """取一行译文内容：剥掉 `> ` 前缀与 `*` 包裹。"""
    s = line.strip()
    if s.startswith('>'):
        s = s.lstrip('> ').strip()
    if s.startswith('*'):
        s = s[1:]
    if s.rstrip().endswith('*') and len(s.rstrip()) > 1:
        s = s.rstrip()[:-1]
    return s.strip()


def extract_pairs(filepath: str) -> dict[str, dict]:
    """从 docs/{N}.md 提取 原文段→译文段 对。

    原文段 = 连续的非译文、非标题、非空、非杂行（可多行颂偈，前缀有无均可）。
    译文段 = 紧随其后的译文块（`> ` 引用行；旧斜体 * 行 + 跨行续行兼容）。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')

    pairs = {}
    idx = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == '' or is_noise(line) or is_trans_line(line) or line.lstrip().startswith('#'):
            i += 1
            continue
        # 收集原文段（连续原文行，含多行颂偈）
        orig_lines = [line]
        i += 1
        while i < n:
            l = lines[i]
            if l.strip() == '' or is_noise(l) or is_trans_line(l) or l.lstrip().startswith('#'):
                break
            orig_lines.append(l)
            i += 1
        # 跳过空行与杂行
        while i < n and (lines[i].strip() == '' or is_noise(lines[i])):
            i += 1
        # 收集译文块。现行格式：每行 `> ` 引用，逐行自识别。
        # 旧斜体兼容两种多行格式：
        #   格式A：每行独立以 * 包裹（*行1* / *行2*）
        #   格式B：整块跨行包裹（首行 * 开头、末行 * 结尾，中间行无 *，含长段硬换行续行）
        # 旧斜体跨行续行判别：前一个已收集的译文行为未闭合 * 行（非引用行）→ 下一非空行为续行
        trans_lines = []
        last_raw = None  # 最近一个原始译文行（旧斜体未闭合判断用）
        while i < n:
            l = lines[i]
            if is_noise(l):
                i += 1
                continue
            if is_trans_line(l):
                trans_lines.append(trans_text(l))
                last_raw = l
                i += 1
                continue
            if l.strip() == '':
                j = i
                while j < n and (lines[j].strip() == '' or is_noise(lines[j])):
                    j += 1
                if j < n and is_trans_line(lines[j]):
                    i = j  # 空行后仍是译文，跳过空行继续
                    continue
                break
            # 非译文、非空行：仅当译文块为未闭合的旧斜体 * 行时视为续行
            if (last_raw is not None and not last_raw.lstrip().startswith('>')
                    and not last_raw.rstrip().endswith('*')):
                trans_lines.append(l)
                last_raw = l
                i += 1
                continue
            break
        idx += 1
        pairs[str(idx)] = {
            'orig': '\n'.join(orig_lines),
            'trans': '\n'.join(trans_lines) if trans_lines else '',
        }
    return pairs


def build_batches(pairs: dict[str, dict]) -> list[dict]:
    """按每批 BATCH 段切块，每批注入前 2 段作为上下文参考。"""
    keys = list(pairs.keys())
    total = len(keys)
    batches = []
    for start in range(0, total, BATCH):
        end = min(start + BATCH, total)
        batch_keys = keys[start:end]
        ctx_start = max(0, start - 2)
        ctx_keys = keys[ctx_start:start]
        batch = {
            '_batch_info': {
                'start': batch_keys[0] if batch_keys else '',
                'end': batch_keys[-1] if batch_keys else '',
                'count': len(batch_keys),
                'total': total,
            },
            '_context': {k: pairs[k] for k in ctx_keys},
            'paragraphs': {k: pairs[k] for k in batch_keys},
        }
        batches.append(batch)
    return batches


def main():
    if len(sys.argv) < 2:
        print("Usage: python prepare_check.py <N>", file=sys.stderr)
        sys.exit(1)
    n = int(sys.argv[1])
    src = f'docs/{n}.md'
    if not os.path.exists(src):
        print(f"Error: {src} not found", file=sys.stderr)
        sys.exit(1)

    pairs = extract_pairs(src)
    with open(f'docs/pairs_{n}.json', 'w', encoding='utf-8') as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)

    batches = build_batches(pairs)
    for b, batch in enumerate(batches, 1):
        with open(f'docs/check_{n}_batch{b}.json', 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(pairs)} pairs from {src} → docs/pairs_{n}.json, {len(batches)} batches")
    for b, batch in enumerate(batches, 1):
        info = batch['_batch_info']
        print(f"  Batch {b}: paragraphs {info['start']}-{info['end']} ({info['count']} pairs)")


if __name__ == '__main__':
    main()
