import os
import re
import json

def is_allowed(ch):
    code = ord(ch)
    # ASCII
    if 0 <= code <= 127:
        return True
    # CJK Unified Ideographs
    if 0x4E00 <= code <= 0x9FFF:
        return True
    # CJK Symbols and Punctuation (e.g., 、 。 〈 〉)
    if 0x3000 <= code <= 0x303F:
        return True
    # Full-width forms (e.g., ！ ， ： ； ？)
    if 0xFF00 <= code <= 0xFFEF:
        return True
    # CJK Unified Ideographs Extension A
    if 0x3400 <= code <= 0x4DBF:
        return True
    # General Punctuation (e.g., — …)
    if 0x2000 <= code <= 0x206F:
        return True
    
    # You might want to add more extensions if they are legitimate rare characters
    # But for now, let's flag everything else to be safe.
    return False

def analyze_foreign_chars(directory_path, context_window=20):
    stats = {}
    files = sorted([f for f in os.listdir(directory_path) if f.endswith('.md') and f != '0.md' and not f.startswith('.')], 
                   key=lambda x: (0, int(x.split('.')[0])) if x.split('.')[0].isdigit() else (1, x))

    for filename in files:
        filepath = os.path.join(directory_path, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        for i, ch in enumerate(text):
            if not is_allowed(ch):
                hex_code = f"U+{ord(ch):04X}"
                key = f"{ch} ({hex_code})"

                if key not in stats:
                    stats[key] = {
                        "char": ch,
                        "hex": hex_code,
                        "count": 0,
                        "occurrences": []
                    }

                stats[key]["count"] += 1

                if len(stats[key]["occurrences"]) < 5:
                    start = max(0, i - context_window)
                    end = min(len(text), i + context_window + 1)
                    snippet = text[start:end].replace("\n", "\\n").replace("\r", "\\r")
                    stats[key]["occurrences"].append({
                        "file": filename,
                        "context": snippet
                    })

    return stats

if __name__ == "__main__":
    docs_dir = 'docs/'
    output_json = 'foreign-chars-check.json'

    if not os.path.exists(docs_dir):
        print(f"Error: Directory {docs_dir} does not exist.")
    else:
        print(f"Searching for foreign/non-standard characters in {docs_dir}...")
        results = analyze_foreign_chars(docs_dir)

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Search complete. Results saved to {output_json}")
        print(f"Found {len(results)} unique non-standard characters.")
