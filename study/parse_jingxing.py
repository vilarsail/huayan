#!/usr/bin/env python3
"""解析《净行品》一百四十愿：原文/译文对齐 + 注释挂接 + 场景分组"""
import re, json

SRC = "/Users/zhangwei/work/huayan/docs/14.md"
NOTES = "/Users/zhangwei/work/huayan/docs/14.notes.md"
OUT = "/Users/zhangwei/work/huayan/study/jingxing_data.json"

CIRCLED = re.compile(r'[\u2460-\u2473\u3251-\u325F\u32B1-\u32BF]')
def circled_val(ch):
    o = ord(ch)
    if 0x2460 <= o <= 0x2473: return o - 0x2460 + 1
    if 0x3251 <= o <= 0x325F: return o - 0x3251 + 21
    if 0x32B1 <= o <= 0x32BF: return o - 0x32B1 + 36
    return None

text = open(SRC, encoding="utf-8").read()
lines = text.split("\n")

# 原文偈段：从含「菩萨在家」的非斜体行起，到「周顾十方」行止
verse_src = []
started = False
for i, ln in enumerate(lines):
    if not started and not ln.startswith("*") and "菩萨在家" in ln and "当愿众生" in ln:
        started = True
    if started:
        if ln.startswith("*"):
            break
        verse_src.append(ln)
orig = "".join(verse_src)

# 译文偈段：段首行带 *，其余为同段续行，读到空行为止
verse_tr = []
tr_started = False
for ln in lines:
    if not tr_started and ln.startswith("*") and "菩萨在家" in ln:
        tr_started = True
    if tr_started:
        if ln.strip() == "":
            break
        verse_tr.append(ln)
trans = "".join(verse_tr).strip("*")

# 注释表
notes_raw = open(NOTES, encoding="utf-8").read()
notes = {}
for m in re.finditer(r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺])\s*([^\n①-㊺]+)', notes_raw):
    body = m.group(2).strip()
    # 词条 = 第一个空格/全角空格前
    parts = re.split(r'[ 　]', body, 1)
    term = parts[0]
    notes[circled_val(m.group(1))] = {"term": term, "text": body}

def split_wishes(blob):
    """按句号切愿，返回每愿原文（保留内部分隔符）"""
    s = blob.replace("\u3000", "")          # 去全角空格
    s = re.sub(r'[""\"]', '', s)             # 去引号
    parts = [p.strip() for p in s.split("。") if p.strip()]
    return parts

o_parts = split_wishes(orig)
t_parts = split_wishes(trans)
print("原文愿数:", len(o_parts), " 译文愿数:", len(t_parts))
print("原文『当愿众生』数:", orig.count("当愿众生"), " 译文:", trans.count("当愿众生"))

wishes = []
for idx, (o, t) in enumerate(zip(o_parts, t_parts), 1):
    markers = [circled_val(c) for c in CIRCLED.findall(o)]
    clean = CIRCLED.sub("", o)
    segs = re.split(r'[，,：:；;]', clean)
    segs = [x for x in segs if x]
    wishes.append({
        "no": idx,
        "scene": segs[0] if segs else clean[:4],
        "orig": "，".join(segs),
        "trans": t.rstrip("。，"),
        "notes": [notes[m] for m in markers if m in notes],
        "marker_ids": markers,
    })

json.dump(wishes, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已写", OUT)

# 场景分组（依据愿文内容自然分段，用于页面筛选）
GROUPS = [
    (1, 11, "在家生活", "居家处世，随事发愿"),
    (12, 26, "出家受戒", "辞亲割爱，剃度受具"),
    (27, 33, "坐禅修观", "入堂敷座，止观双运"),
    (34, 39, "著衣威仪", "下足整衣，动静有仪"),
    (40, 46, "盥洗清洁", "杨枝净水，涤形去秽"),
    (47, 58, "出行持钵", "执锡持器，升道涉路"),
    (59, 77, "所见·山河草木", "林泉池井，触目菩提"),
    (78, 101, "所见·各色人等", "美丑恩怨，皆是老师"),
    (102, 104, "所见·城郭林野", "王都广漠，人间聚落"),
    (105, 111, "乞食", "入里乞食，空满平等"),
    (112, 115, "毁誉得失", "恭敬毁辱，惭愧为服"),
    (116, 122, "饭食", "粗软美恶，禅悦为食"),
    (123, 128, "说法洗浴", "说法度人，浴身除热"),
    (129, 138, "诵经礼塔", "讽诵观佛，绕塔赞叹"),
    (139, 141, "睡眠醒寤", "洗足寝息，智觉周顾"),
]
data = {"wishes": wishes, "groups": [
    {"id": i, "start": s, "end": e, "name": n, "note": t} for i, (s, e, n, t) in enumerate(GROUPS)]}
total = sum(e - s + 1 for s, e, n, t in GROUPS)
print("分组覆盖愿数:", total)
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已写(含分组)", OUT)
for w in wishes[:3] + wishes[-2:]:
    print(w["no"], w["scene"], "|", w["orig"][:22], "|", w["trans"][:18])
missing = [w["no"] for w in wishes if "当愿众生" not in w["orig"]]
print("缺『当愿众生』的愿:", missing)
