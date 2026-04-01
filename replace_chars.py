import os
import json

def apply_replacements(docs_dir, mapping_file):
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    # Build a simple char -> replacement dict
    replacements = {}
    for key, info in mapping_data.items():
        char = info['char']
        rep = info['replacement']
        if rep:
            replacements[char] = rep

    if not replacements:
        print("No replacements found in mapping file.")
        return

    print(f"Applying replacements: {replacements}")

    # Process .md files in docs/, excluding 0.md
    files = [f for f in os.listdir(docs_dir) if f.endswith('.md') and f != '0.md' and not f.startswith('.')]
    
    for filename in files:
        filepath = os.path.join(docs_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for char, rep in replacements.items():
            content = content.replace(char, rep)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filename}")
        else:
            # print(f"No changes in {filename}")
            pass

if __name__ == "__main__":
    apply_replacements('docs/', 'check/encode-check.json')
