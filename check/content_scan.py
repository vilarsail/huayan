#!/usr/bin/env python3
"""docs/N.md 原文 ↔ origin/N.txt 内容级校验工具（修复方案的验收门禁）。

用法:
  python3 check/content_scan.py 71 72 73     # 检查指定卷
  python3 check/content_scan.py --all        # 检查全部 80 卷, 输出汇总

判定:
  覆盖率   = md 原文中真正匹配到 origin 的字符比例（<99.5% = 有内容缺失/错乱）
  纯净度   = 匹配字符占 md 原文提取的比例（低 = 译文行漏斜体/混入白话）
  真缺失   = 缺失块在 md 全文（含译文行）中也搜不到 → 实际丢内容
  文言多出 = md 原文层多出的非白话块（重复/串卷/虚构内容）
"""
import re, sys, difflib

W = __file__.rsplit('/check/', 1)[0]
FOOT = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿]')
PUNCT = re.compile(r'[，。：；？！、「」『』“”‘’…—·《》〈〉（）\[\]〔〕\*]')
BAIHUA = set('的了着是在和跟这个那哪些呢吧会被把对于从到吗非常十分真正')


def norm(t):
    t = FOOT.sub('', t)
    t = PUNCT.sub('', t)
    return re.sub(r'\s+', '', t)


def md_extract(p):
    out = []
    for line in open(p, encoding='utf-8'):
        s = line.rstrip('\n').strip()
        if not s or s.startswith(('#', '*', '---', '|', '>')):
            continue
        if re.match(r'^(\[\^|[①-㊿]|\d+[\.、\)])', s):
            continue
        out.append(s)
    t = norm(''.join(out))
    t = re.sub(r'大方广佛华严经卷第.{1,4}$', '', t)
    t = re.sub(r'大正新修大藏经第10册No0279大方广佛华严经$', '', t)
    return t


def origin_extract(p):
    t = norm(open(p, encoding='utf-8').read())
    t = re.sub(r'^大方广佛华严经卷第.{1,4}', '', t)
    t = re.sub(r'大方广佛华严经卷第.{1,4}大正新修大藏经第10册No0279大方广佛华严经$', '', t)
    return t


def baihua_score(s):
    return sum(1 for c in s if c in BAIHUA) / len(s) if len(s) > 40 else 0


def scan(n, verbose=True):
    md_p, o_p = f'{W}/docs/{n}.md', f'{W}/origin/{n}.txt'
    try:
        m, o = md_extract(md_p), origin_extract(o_p)
        raw = norm(open(md_p, encoding='utf-8').read())
    except FileNotFoundError as e:
        return ('缺文件', 0, 0, [], [])
    sm = difflib.SequenceMatcher(None, o, m, autojunk=False)
    eq = sum(i2 - i1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag == 'equal')
    cov, pur = eq / len(o), eq / len(m) if m else 0
    missing, extras = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if i2 - i1 >= 15:
            blk = o[i1:i2]
            if blk[:12] not in raw:  # 原文+译文层都搜不到 = 真缺失
                missing.append((i2 - i1, blk, o[max(0, i1 - 12):i1], o[i2:i2 + 12]))
        if j2 - j1 >= 50:
            extras.append((j2 - j1, m[j1:j2]))
    return ('ok', cov, pur, missing, extras)


def main():
    args = sys.argv[1:]
    vols = range(1, 81) if (not args or args[0] == '--all') else [int(a) for a in args]
    bad = []
    for n in vols:
        st, cov, pur, missing, extras = scan(n)
        if st != 'ok':
            print(f'卷{n}: {st}'); bad.append(n); continue
        flag = ''
        if cov < 0.995 or missing: flag += ' ⚠️内容'
        wenyan = [(sz, b) for sz, b in extras if baihua_score(b) <= 0.10]
        if wenyan: flag += ' ⚠️多出文言'
        if pur < 0.90: flag += ' ⚠️格式'
        if flag: bad.append(n)
        print(f'卷{n}: 覆盖率{cov*100:5.1f}% 纯净度{pur*100:5.1f}% 缺失{len(missing)}处/{sum(x[0] for x in missing)}字{flag}')
        for sz, blk, before, after in missing[:5]:
            print(f'    [真缺失{sz}字] 插入点前文…{before} ⟵ {blk[:40]}…')
        for sz, b in wenyan[:3]:
            print(f'    [文言多出{sz}字] {b[:40]}…')
    print()
    ok = [n for n in vols if n not in bad]
    print(f'通过 {len(ok)} 卷: {ok}')
    print(f'未通过 {len(bad)} 卷: {bad}')


if __name__ == '__main__':
    main()
