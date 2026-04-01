import os

def final_fix():
    # Mapping of specific strings/chars to their correct Chinese equivalents
    replacements = {
        # 1.md
        " चारों": "四面",
        
        # 22.md, 47.md (Cyrillic)
        "菩са": "菩萨",
        "菩сса": "菩萨",
        
        # 44.md (Korean)
        "贪爱 즐거워할 뿐": "徒令众贪乐",
        
        # 62.md (Korean)
        "味光摩니宝": "味光摩尼宝",
        
        # 66.md (Korean)
        "행杀生": "行杀生",
        
        # 63.md (Vietnamese/Korean mix)
        " phá vỡ núi phiền não, dập tắt các pháp ác, mãi mãi không còn đấu tranh, vĩnh viễn hòa thuận và lương thiện. họ lại dùng huyễn lực để khai ngộ chúng sinh, khiến họ diệt trừ tội ác, khiến họ sợ hãi sinh tử, khiến họ thoát khỏi các nẻo轮回, khiến họ rời xa sự nhiễm ô và chấp trước, khiến họ an trụ vào tâm bồ đề vô thượng, khiến họ tu hành tất cả các hạnh nguyện của bồ tát, khiến họ an trụ vào tất cả các ba la mật, khiến họ tiến vào tất cả các quả vị của bồ tát, khiến họ quán chiếu tất cả các pháp môn vi diệu, khiến họ biết được tất cả các phương tiện của chư phật. những việc làm như vậy,": "破烦恼山，息众恶法，长无斗诤，永共和善；复以幻力，开悟众生，令灭罪恶，令怖生死，令出诸趣，令离染着，令住无上菩提之心，令修一切诸菩萨行，令住一切诸波罗蜜，令入一切诸菩萨地，令观一切微妙法门，令知一切诸佛方便。如是所作，",
        " phá vỡ ngọn núi nghi ngờ, tất cả các chướng ngại đều được trừ멸. những việc làm như vậy,": "破疑惑山，一切障碍悉皆除灭。如是所作，",
        " 항복 마귀의 서원, 흥립 정법의 수미산왕, 성취 중생의 모든 사업. 이와 같은 소작은 법계에 두루 퍼진다.": "发降魔愿，兴立正法须弥山王，成就众生一切事业。如是所作，周遍法界。",
        " 이와 같은 소작은 법계에 두루 퍼진다.": "如是所作，周遍法界。",
        " trừ멸": "除灭",
        
        # General cleanup found in 63.md or others
        "菩sà": "菩萨",
        "阿_多罗": "阿耨多罗",
        "菩-萨": "菩萨",
        "菩di树": "菩提树"
    }

    docs_dir = 'docs/'
    files = [f for f in os.listdir(docs_dir) if f.endswith('.md') and f != '0.md' and not f.startswith('.')]

    for filename in files:
        filepath = os.path.join(docs_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed foreign chars in {filename}")

if __name__ == "__main__":
    final_fix()
