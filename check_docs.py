import re
import os
import json
from collections import defaultdict

def classify_char(ch):
    code = ord(ch)

    # Unicode Private Use Area (PUA)
    if 0xE000 <= code <= 0xF8FF:
        return "PUA(私有区-疑似CBETA缺字)"
    
    # Unicode Extension blocks (common in Buddhist texts for rare characters)
    elif 0x20000 <= code <= 0x2A6DF:
        return "Unicode扩展区B"
    elif 0x2A700 <= code <= 0x2B73F:
        return "Unicode扩展区C"
    elif 0x2B740 <= code <= 0x2B81F:
        return "Unicode扩展区D"
    elif 0x2B820 <= code <= 0x2CEAF:
        return "Unicode扩展区E"
    elif 0x2CEB0 <= code <= 0x2EBEF:
        return "Unicode扩展区F"
    elif 0x30000 <= code <= 0x3134F:
        return "Unicode扩展区G"
    elif 0x31350 <= code <= 0x323AF:
        return "Unicode扩展区H"
    elif code >= 0x20000:
        return "Unicode扩展区(其他)"
    
    # Specials and problematic characters
    elif ch == "\uFFFD":
        return "乱码替换符"
    elif code < 32 and ch not in ['\n', '\t', '\r']:
        return "不可见控制字符"
    elif 127 <= code <= 159:
        return "C1控制字符"
    elif '\u2FF0' <= ch <= '\u2FFF':
        return "组合字结构符(IDS)"
    elif ch == '\u3000':
        return None
    elif ch.isspace() and ch not in [' ', '\n', '\r', '\t']:
        return "其他空白字符"
    
    return None

def analyze_directory(directory_path, context_window=15):
    stats = {}

    # Target .md files, exclude 0.md
    files = sorted([f for f in os.listdir(directory_path) if f.endswith('.md') and f != '0.md' and not f.startswith('.')], 
                   key=lambda x: (0, int(x.split('.')[0])) if x.split('.')[0].isdigit() else (1, x))

    for filename in files:
        filepath = os.path.join(directory_path, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        for i, ch in enumerate(text):
            category = classify_char(ch)
            if category:
                hex_code = f"U+{ord(ch):04X}"
                key = f"{ch} ({hex_code})"

                if key not in stats:
                    stats[key] = {
                        "char": ch,
                        "hex": hex_code,
                        "type": category,
                        "count": 0,
                        "replacement": "",
                        "occurrences": []
                    }

                stats[key]["count"] += 1

                if len(stats[key]["occurrences"]) < 10:
                    start = max(0, i - context_window)
                    end = min(len(text), i + context_window + 1)
                    snippet = text[start:end].replace("\n", "\\n").replace("\r", "\\r")
                    stats[key]["occurrences"].append({
                        "file": filename,
                        "index": i,
                        "context": snippet
                    })

    return stats

if __name__ == "__main__":
    docs_dir = 'docs/'
    output_json = 'docs-check.json'

    if not os.path.exists(docs_dir):
        print(f"Error: Directory {docs_dir} does not exist.")
    else:
        print(f"Analyzing files in {docs_dir}...")
        results = analyze_directory(docs_dir)

        sorted_results = dict(sorted(results.items(), key=lambda x: (x[1]['type'], x[1]['hex'])))

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(sorted_results, f, ensure_ascii=False, indent=2)

        print(f"Analysis complete. Results saved to {output_json}")
        print(f"Found {len(results)} unique problematic characters.")
