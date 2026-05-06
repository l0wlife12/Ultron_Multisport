# Fix syntax errors in ultron_bot_fixed.py
import re

with open('ultron_bot_fixed.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix all literal \n patterns that break syntax
# Pattern: ends with \n followed by whitespace and code
content = re.sub(r'\\n\s+', '\n    ', content)
content = content.replace('\\n    ', '\n    ')
content = content.replace('\\n', '\n')

# Write back
with open('ultron_bot_fixed.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ File syntax fixed')
