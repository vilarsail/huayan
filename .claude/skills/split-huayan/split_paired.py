#!/usr/bin/env python3
"""把 docs/{N}.md 中过长的 原文/译文 配对段重新划分为更短的配对块（华严经项目适配版）。

设计：
- 脚本做确定性工作：解析原文/译文配对、识别偈颂（永不分割）、按标点切句、
  校验 splits.json（拼接一致性、块数对齐、长度硬上限）、重组文件、字符流校验
- LLM 只做语义决策：原文在哪里分（选句子分组）、译文对应怎么分（直接写出译文块）
- 三步流程：prepare → LLM 写 splits.json → apply

用法:
    python3 split_paired.py prepare <start> <end> [--split-dir DIR] [--work-dir DIR] [--max-len N]
    python3 split_paired.py apply    <start> <end> [--split-dir DIR] [--work-dir DIR] [--max-out N]

docs/{N}.md 格式（现行：译文为 quote 引用行；兼容旧斜体，与 check-huayan 一致）:
    - 译文行：以 `> ` 开头的引用行（现行格式）；旧斜体行（`*译文*`，可带 　　前缀）仍兼容
    - 标题行：以 # 开头
    - 原文行：其余所有非空行（可能带 　　前缀，也可能顶格）
    - 原文段 = 连续原文行（多行颂偈为同一段，永不分割）
    - 译文内容 = 引用行去 `> ` 前缀 / 旧斜体去 * 包裹；旧斜体未闭合时可跨行续行
    - 页脚杂行（大方广佛华严经卷第… / 大正新修大藏经… / 孤立的 . 或 。）：跳过
    - 重组时统一格式：去 　　前缀、块间空行分隔（字符内容不变）

splits.json 格式（LLM 写，每个长配对一个键）:
    {
      "P3": [
        {"o": ["P3S1-P3S2"], "t": "译文第一块……"},
        {"o": ["P3S3"],      "t": "译文第二块……"}
      ]
    }
    - o 为原文句子编号（单个或区间），按顺序拼接为原文块
    - t 为译文块原文（LLM 从原文译文复制切分，不增删改任何字符）
    - o 组数必须等于 t 块数；两组拼接必须与原原文段/原译文段完全一致

退出码:
    0 - 全部通过
    1 - 校验失败或文件缺失
    2 - 参数错误
"""

import argparse
import json
import os
import re
import sys

MAX_LEN_DEFAULT = 200    # 超过此长度的原文段进入待切分列表
MAX_OUT_DEFAULT = 300    # 切分后原文块的硬上限
INDENT_CHARS = '　'      # 全角空格：段首缩进（剥离），偈颂行内分隔（识别用）

SENT_END = '。？！；'  # 华严经大量用分号连接并列长句，；也作为切分点

NOISE_PATTERNS = (
    re.compile(r'^大正新修大藏经'),
    re.compile(r'^大[方广佛华严经]+卷第'),
)


# ============================================================
# 解析
# ============================================================

def read_file(path):
    """读取文件，返回 (text, had_bom)。"""
    with open(path, 'rb') as f:
        raw = f.read()
    had_bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    return text, had_bom


def write_file(path, text, had_bom):
    with open(path, 'w', encoding='utf-8-sig' if had_bom else 'utf-8') as f:
        f.write(text)


def clean_line(line):
    """去除行首尾空白（含全角空格）。"""
    return line.strip().strip(INDENT_CHARS).strip()


def is_noise(line):
    """页脚杂行：不算原文也不算译文。"""
    s = line.strip()
    if s.startswith('>'):
        s = s.lstrip('> ').strip()
    s = s.lstrip('*').strip()
    if s in ('.', '。'):
        return True
    return any(p.match(s) for p in NOISE_PATTERNS)


def is_trans_line(line):
    s = clean_line(line)
    return s.startswith('> ') or s.startswith('*')


def trans_inner(line):
    """取一行译文的内容：剥掉 `> ` 前缀与行首尾的 * 包裹和空白。"""
    s = clean_line(line)
    if s.startswith('>'):
        s = s.lstrip('> ').strip()
    if s.startswith('*'):
        s = s[1:]
    if s.endswith('*'):
        s = s[:-1]
    return s.strip()


def clean_orig_block(lines):
    """原文块：逐行清理后用换行连接（多行颂偈保持行结构）。"""
    cleaned = [clean_line(l) for l in lines]
    return '\n'.join(l for l in cleaned if l)


def parse_text(text):
    """按行解析为条目列表。

    条目类型:
      heading  - '# ' 标题
      pair     - (o, t) 原文/译文配对；o 为清理后的原文块（可多行），
                 t 为译文内容（无 * 包裹）；raw_o/raw_t 为原始行（重组时原样保留）
      solo     - 无译文的原文件段或无原文的译文段，原样保留
    """
    lines = text.split('\n')
    items = []
    pending_o = None  # list[str] 等待译文的原文行（原始行）
    i = 0
    n = len(lines)

    def flush_pending():
        nonlocal pending_o
        if pending_o is None:
            return
        block = clean_orig_block(pending_o)
        if block:
            items.append({'type': 'solo', 'raw': '\n'.join(pending_o)})
        pending_o = None

    while i < n:
        line = lines[i]
        if line.strip() == '':
            # 空行不断开待配对的原文段（原文与译文间可能隔空行）
            i += 1
            continue
        if is_noise(line):
            flush_pending()
            i += 1
            continue
        if clean_line(line).startswith('#'):
            flush_pending()
            items.append({'type': 'heading', 'raw': line})
            i += 1
            continue
        if is_trans_line(line):
            # 收集译文块：`> ` 引用行逐行自识别；旧斜体 * 行可跨行续行
            t_lines = [line]
            i += 1
            while i < n:
                l = lines[i]
                if is_noise(l):
                    i += 1
                    continue
                if is_trans_line(l):
                    t_lines.append(l)
                    i += 1
                    continue
                if l.strip() == '':
                    j = i
                    while j < n and (lines[j].strip() == '' or is_noise(lines[j])):
                        j += 1
                    if j < n and is_trans_line(lines[j]):
                        i = j
                        continue
                    break
                # 旧斜体块未闭合（最近译文行非引用行且未以 * 结尾）→ 硬换行续行
                if not clean_line(t_lines[-1]).startswith('> ') \
                        and not clean_line(t_lines[-1]).endswith('*'):
                    t_lines.append(l)
                    i += 1
                    continue
                break
            inner = ''.join(trans_inner(l) for l in t_lines)
            if pending_o is not None:
                items.append({'type': 'pair', 'o': clean_orig_block(pending_o),
                              't': inner, 'raw_o': '\n'.join(pending_o),
                              'raw_t': '\n'.join(t_lines)})
                pending_o = None
            else:
                items.append({'type': 'solo', 'raw': '\n'.join(t_lines)})
            continue
        # 原文行
        if pending_o is None:
            pending_o = [line]
        else:
            pending_o.append(line)
        i += 1

    flush_pending()
    return items


def parse_file(path):
    """读取并解析文件，返回 (items, had_bom)。"""
    text, had_bom = read_file(path)
    return parse_text(text), had_bom


# ============================================================
# 切句
# ============================================================

def split_sentences(text):
    """按标点切成候选句子，保留标点。

    分割点：引号外层的 。？！；以及引号闭口 ” 紧跟在 。？！ 之后时。
    引号按栈匹配，支持 ‘……’ 内嵌 ‘……’ 的嵌套。
    不保证每个候选都是好边界，LLM 只在这些点里挑。
    """
    sents = []
    cur = ''
    stack = []
    prev = ''
    for ch in text:
        cur += ch
        if ch == '“':
            stack.append(ch)
        elif ch == '”':
            if stack:
                stack.pop()
            if not stack and prev in SENT_END and cur.strip():
                sents.append(cur)
                cur = ''
        elif ch in SENT_END and not stack:
            sents.append(cur)
            cur = ''
        prev = ch
    if cur:
        sents.append(cur)
    return sents


def strip_ws(text):
    """去除所有空白（含全角空格、换行），用于字符流比较。"""
    return ''.join(ch for ch in text if not ch.isspace() and ch not in INDENT_CHARS)


def is_verse(o_block):
    """偈颂判定：多行段落，或含行内全角空格。永不分割。"""
    if '\n' in o_block:
        return True
    if INDENT_CHARS in o_block:
        return True
    return False


def annotate_items(items, max_len):
    """为配对编号（P1, P2...）、标记偈颂/待切分。prepare 和 apply 共用，保证编号一致。"""
    stats = {'pairs': 0, 'verses': 0, 'solos': 0, 'long': 0}
    long_pairs = []
    pair_idx = 0
    for it in items:
        if it['type'] == 'solo':
            stats['solos'] += 1
        if it['type'] != 'pair':
            continue
        pair_idx += 1
        it['pid'] = f'P{pair_idx}'
        stats['pairs'] += 1
        if is_verse(it['o']):
            stats['verses'] += 1
            it['splittable'] = False
        elif len(it['o']) > max_len:
            stats['long'] += 1
            it['splittable'] = True
            long_pairs.append(it)
        else:
            it['splittable'] = False
    return stats, long_pairs


# ============================================================
# prepare
# ============================================================

def prepare_one(n, split_dir, work_dir, max_len):
    path = os.path.join(split_dir, f'{n}.md')
    if not os.path.exists(path):
        return None, f'缺失 {path}'

    items, had_bom = parse_file(path)

    # 备份原文件到 work 目录（apply 时做字符流校验的基准）
    os.makedirs(work_dir, exist_ok=True)
    orig_text, _ = read_file(path)
    backup = os.path.join(work_dir, f'{n}.orig.md')
    write_file(backup, orig_text, had_bom)

    stats, long_pairs = annotate_items(items, max_len)

    out = [f'== 文件 {n}.md ==']
    for pid_it in long_pairs:
        pid = pid_it['pid']
        sents = split_sentences(pid_it['o'])
        if len(sents) < 2:
            pid_it['splittable'] = False
            stats['long'] -= 1
            continue
        out.append('')
        out.append(f'== {pid} (原文{len(pid_it["o"])}字, 译文{len(pid_it["t"])}字) ==')
        out.append('--- 原文句子 ---')
        for i, s in enumerate(sents, 1):
            out.append(f'{pid}S{i} {s}')
        out.append('--- 译文全文 ---')
        out.append(pid_it['t'])
        pid_it['sent_count'] = len(sents)

    pairs_path = os.path.join(work_dir, f'{n}.pairs.txt')
    with open(pairs_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

    meta_path = os.path.join(work_dir, f'{n}.meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({'max_len': max_len}, f)

    return stats, None


def cmd_prepare(args):
    if args.start > args.end:
        print(f'错误: start ({args.start}) 不能大于 end ({args.end})', file=sys.stderr)
        sys.exit(2)

    print('=' * 60)
    print(f'prepare: 文件 {args.start} ~ {args.end}, 长段阈值 {args.max_len} 字')
    print('=' * 60)

    has_err = False
    for n in range(args.start, args.end + 1):
        stats, err = prepare_one(n, args.split_dir, args.work_dir, args.max_len)
        if err or stats is None:
            print(f'  [{n}] ✗ {err or "unknown error"}')
            has_err = True
            continue
        print(f'  [{n}] ✓ 配对={stats["pairs"]}, 偈颂={stats["verses"]}, '
              f'solo={stats["solos"]}, 待切分长段={stats["long"]}')

    print()
    print(f'pairs 文件: {args.work_dir}/{{{args.start}}}.pairs.txt ~ {args.work_dir}/{{{args.end}}}.pairs.txt')
    print('下一步：读取 pairs.txt，写 splits.json（每对给出 o 句子分组和 t 译文块），')
    print(f'放到 {args.work_dir}/{{N}}.splits.json，然后运行 apply。')
    sys.exit(1 if has_err else 0)


# ============================================================
# apply
# ============================================================

def parse_oid(oid):
    """解析句子编号 'P3S2' 或区间 'P3S1-P3S5'，返回 (pid, [句号...]) 或 None。"""
    oid = oid.strip()

    def one(s):
        m = re.fullmatch(r'P(\d+)S(\d+)', s.strip())
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))

    if '-' in oid:
        parts = oid.split('-', 1)
        a, b = one(parts[0]), one(parts[1])
        if a is None or b is None or a[0] != b[0] or a[1] > b[1]:
            return None
        return a[0], list(range(a[1], b[1] + 1))
    r = one(oid)
    if r is None:
        return None
    return r[0], [r[1]]


def validate_splits(items, splits, max_out):
    """校验 splits.json。返回 (errors, o_items_by_pid, missing)。"""
    o_items = {it['pid']: it for it in items if it['type'] == 'pair' and it.get('splittable')}
    errors = []

    for pid, groups in splits.items():
        if pid not in o_items:
            errors.append(f'{pid}: 不存在或不是待切分长段')
            continue
        it = o_items[pid]
        sents = split_sentences(it['o'])

        o_chunks = []
        for g in groups:
            if 'o' not in g or 't' not in g:
                errors.append(f'{pid}: 组缺少 o 或 t 字段')
                continue
            idxs = []
            for oid in g['o']:
                r = parse_oid(oid)
                if r is None or r[0] != int(pid[1:]):
                    errors.append(f'{pid}: 编号格式错误 {oid!r}')
                    continue
                for s in r[1]:
                    if s < 1 or s > len(sents):
                        errors.append(f'{pid}: 句号越界 {oid!r} (共{len(sents)}句)')
                        continue
                    idxs.append(s)
            o_chunks.append(''.join(sents[s - 1] for s in idxs))

        t_chunks = [g['t'] for g in groups if 't' in g]
        for gi, g in enumerate(groups, 1):
            if 't' in g and not g['t'].strip():
                errors.append(f'{pid}: 译文块{gi}为空')
        if len(o_chunks) != len(t_chunks):
            errors.append(f'{pid}: 原文块 {len(o_chunks)} 个 vs 译文块 {len(t_chunks)} 个，数量不一致')
            continue
        if len(o_chunks) < 2:
            errors.append(f'{pid}: 至少要切成 2 块')
            continue

        if strip_ws(''.join(o_chunks)) != strip_ws(it['o']):
            errors.append(f'{pid}: 原文块拼接与原原文段不一致')
        if strip_ws(''.join(t_chunks)) != strip_ws(it['t']):
            errors.append(f'{pid}: 译文块拼接与原译文段不一致（漏字/多字/改字）')

        for i, oc in enumerate(o_chunks, 1):
            if len(oc) > max_out:
                errors.append(f'{pid}: 原文块{i} {len(oc)} 字，超过硬上限 {max_out} 字')

    missing = [pid for pid in o_items if pid not in splits]
    return errors, o_items, missing


def rebuild_file(items, splits):
    """按 splits 重组文件内容。

    未切分的条目按原始行原样保留（引用行/偈颂逐行译文结构不变）；
    只有被切分的配对用规整格式输出（o_chunk / `> ` 引用译文块，块间空行）。
    """
    out = []
    for it in items:
        if it['type'] == 'pair' and it.get('splittable'):
            pid = it['pid']
            if pid in splits:
                sents = split_sentences(it['o'])
                for g in splits[pid]:
                    idxs = []
                    for oid in g['o']:
                        r = parse_oid(oid)
                        if r is not None:
                            idxs.extend(r[1])
                    o_chunk = ''.join(sents[s - 1] for s in idxs)
                    t_chunk = g['t'].strip()
                    out.append(o_chunk)
                    out.append('')
                    out.append('\n'.join(f'> {ln.strip()}'
                                         for ln in t_chunk.split('\n') if ln.strip()))
                    out.append('')
                continue
        if it['type'] == 'heading':
            out.append(it['raw'])
        elif it['type'] == 'solo':
            out.append(it['raw'])
        else:
            out.append(it['raw_o'])
            out.append('')
            out.append(it['raw_t'])
        out.append('')
    # 规整：去掉多余空行，块间统一空行（保留块内原始行结构）
    blocks = []
    for b in out:
        b = b.strip('\n')
        if b.strip():
            blocks.append(b)
    return '\n\n'.join(blocks) + '\n'


def verify_rebuilt(orig_items, splits, new_text):
    """端到端校验：把重组后的文本重新解析，逐项与原始条目对照。

    - 非配对条目（heading/solo）必须原样出现且顺序不变
    - 未切分配对：原样出现
    - 切分配对：重组后变成 k 个连续配对，原文块拼接、译文块拼接都必须与原配对一致
    返回错误列表。
    """
    errors = []
    new_items = parse_text(new_text)
    j = 0
    for it in orig_items:
        if it['type'] != 'pair':
            if j >= len(new_items) or new_items[j]['type'] != it['type'] \
                    or strip_ws(new_items[j].get('raw', '')) != strip_ws(it.get('raw', '')):
                errors.append(f'结构不一致：{it["type"]} 条目丢失或被改动')
                return errors
            j += 1
            continue

        pid = it.get('pid')
        if it.get('splittable') and pid in splits:
            k = len(splits[pid])
            o_acc = ''
            t_acc = ''
            for _ in range(k):
                if j >= len(new_items) or new_items[j]['type'] != 'pair':
                    errors.append(f'{pid}: 重组后配对块不足（应有 {k} 块）')
                    return errors
                o_acc += new_items[j]['o']
                t_acc += new_items[j]['t']
                j += 1
            if strip_ws(o_acc) != strip_ws(it['o']):
                errors.append(f'{pid}: 重组后原文块拼接与原原文段不一致')
            if strip_ws(t_acc) != strip_ws(it['t']):
                errors.append(f'{pid}: 重组后译文块拼接与原译文段不一致')
        else:
            if j >= len(new_items) or new_items[j]['type'] != 'pair':
                errors.append(f'{pid or "?"}: 配对丢失')
                return errors
            if strip_ws(new_items[j]['o']) != strip_ws(it['o']) \
                    or strip_ws(new_items[j]['t']) != strip_ws(it['t']):
                errors.append(f'{pid or "?"}: 未切分配对内容被改动')
            j += 1

    if j != len(new_items):
        errors.append('重组后文件有多余内容')
    return errors


def apply_one(n, split_dir, work_dir, max_out):
    path = os.path.join(split_dir, f'{n}.md')
    splits_path = os.path.join(work_dir, f'{n}.splits.json')
    backup = os.path.join(work_dir, f'{n}.orig.md')

    if not os.path.exists(splits_path):
        return False, '缺失 splits.json（尚无切分决策）'

    items, had_bom = parse_file(path)
    meta_path = os.path.join(work_dir, f'{n}.meta.json')
    max_len = MAX_LEN_DEFAULT
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            max_len = json.load(f).get('max_len', MAX_LEN_DEFAULT)
    annotate_items(items, max_len)  # 恢复 pid / splittable 标注，与 prepare 一致
    # 与 prepare 相同的排除：候选句 <2 的长段无法切分，不算待切分
    for it in items:
        if it.get('splittable') and len(split_sentences(it['o'])) < 2:
            it['splittable'] = False
    with open(splits_path, 'r', encoding='utf-8') as f:
        splits = json.load(f)

    errors, _, missing = validate_splits(items, splits, max_out)
    if missing:
        errors += [f'{pid}: 长配对未出现在 splits.json 中' for pid in missing]
    if errors:
        return False, 'splits.json 校验失败:\n' + '\n'.join(f'    - {e}' for e in errors[:20])

    if not os.path.exists(backup):
        return False, '缺失备份文件（请先运行 prepare）'

    new_text = rebuild_file(items, splits)

    errors = verify_rebuilt(items, splits, new_text)
    if errors:
        return False, '重组校验失败:\n' + '\n'.join(f'    - {e}' for e in errors[:10])

    write_file(path, new_text, had_bom)

    detail = []
    for pid in splits:
        detail.append(f'{pid}→{len(splits[pid])}块')
    return True, f'切分 {len(splits)} 对: {" ".join(detail)}'


def cmd_apply(args):
    if args.start > args.end:
        print(f'错误: start ({args.start}) 不能大于 end ({args.end})', file=sys.stderr)
        sys.exit(2)

    print('=' * 60)
    print(f'apply: 文件 {args.start} ~ {args.end}, 原文块硬上限 {args.max_out} 字')
    print('=' * 60)

    has_fail = False
    for n in range(args.start, args.end + 1):
        ok, msg = apply_one(n, args.split_dir, args.work_dir, args.max_out)
        mark = '✓' if ok else '✗'
        print(f'  [{n}] {mark} {msg}')
        if not ok:
            has_fail = True

    sys.exit(1 if has_fail else 0)


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='重新划分 docs/{N}.md 中过长的 原文/译文 配对段（华严经项目）'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    for name, help_text in (('prepare', '解析配对并生成 pairs.txt'),
                            ('apply', '应用 splits.json 并重组文件')):
        p = subparsers.add_parser(name, help=help_text)
        p.add_argument('start', type=int, help='起始文件号 (包含)')
        p.add_argument('end', type=int, help='结束文件号 (包含)')
        p.add_argument('--split-dir', default='docs', help='配对 md 所在目录 (默认 docs)')
        p.add_argument('--work-dir', default='.splitwork', help='中间文件目录 (默认 .splitwork)')
        if name == 'prepare':
            p.add_argument('--max-len', type=int, default=MAX_LEN_DEFAULT,
                           help=f'待切分原文段长度阈值 (默认 {MAX_LEN_DEFAULT})')
        else:
            p.add_argument('--max-out', type=int, default=MAX_OUT_DEFAULT,
                           help=f'切分后原文块硬上限 (默认 {MAX_OUT_DEFAULT})')
        p.set_defaults(cmd=name)

    args = parser.parse_args()
    if args.cmd == 'prepare':
        cmd_prepare(args)
    elif args.cmd == 'apply':
        cmd_apply(args)


if __name__ == '__main__':
    main()
