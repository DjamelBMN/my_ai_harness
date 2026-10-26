# scripts/refine_ribbon.py
from pathlib import Path
import re

server_path = Path("ui/server.py")
content = server_path.read_text(encoding="utf-8")

old_style = """.word-top-ribbon {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: linear-gradient(90deg, #0F6CBD 0%, #115EA3 100%);
    color: #FFFFFF;
    padding: 0 16px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08);
  }}"""

new_style = """.word-top-ribbon {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: #0f1c2e;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    color: #FFFFFF;
    padding: 0 18px;
    height: 46px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  }}
  .word-ribbon-left {{
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }}
  .word-brand-pill {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(255,255,255,0.08);
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.1);
  }}
  .word-app-badge {{
    background: #185ABD;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 11px;
    width: 20px;
    height: 20px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    flex-shrink: 0;
  }}
  .word-brand-name {{
    font-weight: 600;
    font-size: 12px;
    color: #FFFFFF;
    letter-spacing: -0.2px;
  }}
  .word-brand-sep {{
    color: rgba(255,255,255,0.3);
    font-size: 14px;
  }}
  .word-doc-title {{
    font-weight: 600;
    font-size: 13px;
    color: #E2E8F0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 320px;
    letter-spacing: -0.1px;
  }}
  .word-status-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 12px;
    background: rgba(46, 204, 113, 0.15);
    border: 1px solid rgba(46, 204, 113, 0.3);
    color: #68D391;
    white-space: nowrap;
  }}
  .word-status-badge::before {{
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #48BB78;
    box-shadow: 0 0 6px #48BB78;
  }}
  .word-ribbon-actions {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }}
  .word-action-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #185ABD;
    color: #FFFFFF;
    padding: 6px 14px;
    border-radius: 6px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    border: 1px solid rgba(255,255,255,0.18);
    box-shadow: 0 2px 6px rgba(24, 90, 189, 0.35);
    transition: all 0.15s ease;
  }}
  .word-action-btn:hover {{
    background: #1a66d4;
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(24, 90, 189, 0.45);
  }}
  .word-action-btn.secondary {{
    background: rgba(255,255,255,0.06);
    color: #CBD5E0;
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: none;
  }}
  .word-action-btn.secondary:hover {{
    background: rgba(255,255,255,0.12);
    color: #FFFFFF;
    border-color: rgba(255,255,255,0.25);
  }}"""

# Match old CSS block
old_css_full = re.search(r'\.word-top-ribbon\s*\{\{[\s\S]*?\.word-action-btn\.secondary:hover\s*\{\{[\s\S]*?\}\}', content)
if old_css_full:
    content = content[:old_css_full.start()] + new_style + content[old_css_full.end():]
    print("Replaced Word ribbon CSS with premium Fluent styling")
else:
    print("old_css_full not matched")

# Update ribbon HTML
old_html = """  <div class="word-top-ribbon">
    <div class="word-ribbon-left">
      <span class="word-app-badge">W</span>
      <span class="word-doc-title" title="{filename}">{filename}</span>
      <span class="word-status-badge">Document vérifié</span>
    </div>"""

new_html = """  <div class="word-top-ribbon">
    <div class="word-ribbon-left">
      <div class="word-brand-pill">
        <span class="word-app-badge">W</span>
        <span class="word-brand-name">Word</span>
      </div>
      <span class="word-brand-sep">·</span>
      <span class="word-doc-title" title="{filename}">{filename}</span>
      <span class="word-status-badge">Document vérifié (.docx)</span>
    </div>"""

if old_html in content:
    content = content.replace(old_html, new_html, 1)
    print("Replaced ribbon HTML markup")
else:
    print("old_html not matched")

server_path.write_text(content, encoding="utf-8")
print("Done updating ui/server.py")

