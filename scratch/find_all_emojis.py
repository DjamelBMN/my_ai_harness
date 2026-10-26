import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

for root, dirs, files in os.walk('.'):
    if any(p in root for p in ('.git', '.venv', '__pycache__', 'node_modules', 'scratch', '.system_generated', 'brain')):
        continue
    for file in files:
        if file.endswith(('.py', '.html', '.js', '.css', '.json', '.yaml', '.yml')):
            fp = os.path.join(root, file)
            try:
                with open(fp, encoding='utf-8') as f:
                    for lno, line in enumerate(f, 1):
                        for c in line:
                            code = ord(c)
                            if (0x1F000 <= code <= 0x1FFFF) or (0x2600 <= code <= 0x27BF) or (code in (0x23F3, 0x2318)):
                                print(f"{fp}:L{lno}: U+{code:04X} ({repr(c)}) -> {line.strip()[:60]}")
            except Exception as e:
                pass

