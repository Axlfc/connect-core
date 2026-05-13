import os

def check_siblings():
    md_files = []
    for root, dirs, files in os.walk('.'):
        if '.git' in dirs: dirs.remove('.git')
        for f in files:
            if f.endswith('.md') and not any(x in f for x in ['.en.md', '.ca.md', '.zh-cn.md']):
                md_files.append(os.path.join(root, f))

    missing = []
    for f in md_files:
        for lang in ['en', 'ca', 'zh-cn']:
            sibling = f.replace('.md', f'.{lang}.md')
            if not os.path.exists(sibling):
                missing.append(sibling)

    with open('verification_results.txt', 'w') as out:
        if missing:
            out.write(f"Missing {len(missing)} sibling files:\n")
            for m in missing[:10]: out.write(f"  {m}\n")
        else:
            out.write("All siblings present.\n")

def check_variants():
    langs = {'': '## 🔄 Variantes', 'en': '## 🔄 Variants', 'ca': '## 🔄 Variants', 'zh-cn': '## 🔄 变体版本'}
    with open('verification_results.txt', 'a') as out:
        for lang, expected in langs.items():
            fname = f"README.{lang}.md" if lang else "README.md"
            if os.path.exists(fname):
                with open(fname, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if expected in content:
                        out.write(f"✓ {fname} has correct variants header\n")
                    else:
                        out.write(f"✗ {fname} missing variants header\n")

def check_badges_random():
    import random
    files = []
    for root, dirs, f_list in os.walk('.'):
        if '.git' in dirs: dirs.remove('.git')
        for f in f_list:
            if f.endswith('.md'): files.append(os.path.join(root, f))

    sample = random.sample(files, min(10, len(files)))
    with open('verification_results.txt', 'a') as out:
        for s in sample:
            with open(s, 'r', encoding='utf-8') as f:
                content = f.read(500)
                if 'img.shields.io/badge/lang' in content:
                    out.write(f"✓ {s} has badges\n")
                else:
                    out.write(f"✗ {s} missing badges\n")

check_siblings()
check_variants()
check_badges_random()
