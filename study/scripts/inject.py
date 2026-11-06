#!/usr/bin/env python3
"""把 study/_templates/_*_t.html + study/data/*_data.json 注入生成正式页面：
- _index_t.html + atlas_data.json -> study/index.html（占位符 __ATLAS__）
- _<name>_t.html + <name>_data.json -> study/pages/<name>.html（占位符 __DATA__）
改数据或模板后重跑本脚本，不要直接改生成物。
"""
import json, pathlib

STUDY = pathlib.Path(__file__).resolve().parent.parent

def main():
    jobs = []
    for tpl in sorted((STUDY / "_templates").glob("_*_t.html")):
        name = tpl.stem[1:-2]  # _index_t -> index
        if name == "index":
            jobs.append((tpl, STUDY / "data" / "atlas_data.json", "__ATLAS__", STUDY / "index.html"))
        else:
            jobs.append((tpl, STUDY / "data" / f"{name}_data.json", "__DATA__", STUDY / "pages" / f"{name}.html"))
    for tpl, dataf, ph, out in jobs:
        text = tpl.read_text()
        if ph not in text:
            raise SystemExit(f"{tpl.name}: 未找到占位符 {ph}")
        data = json.dumps(json.loads(dataf.read_text()), ensure_ascii=False, separators=(",", ":"))
        out.write_text(text.replace(ph, data))
        print(f"{tpl.name} + {dataf.name} -> {out.relative_to(STUDY.parent)}")

if __name__ == "__main__":
    main()
