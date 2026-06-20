import sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\benji\OneDrive\Desktop\MineForgeAI Omniverse\python-backend')
from mineforgeai.cli.interactive import InteractiveApp

workspace = Path('.').resolve()
# Ensure permissions allow file edits for generation tests
state_dir = workspace / '.mineforgeai'
state_dir.mkdir(parents=True, exist_ok=True)
(state_dir / 'permissions.json').write_text('{"mode": "full_access", "initialized": true}', encoding='utf-8')

app = InteractiveApp(workspace, 'local model', False)

print(app.respond('/model'))
print(app.respond('/model set mock'))
print('\n-- model diagnostics --')
print(app.respond('/model status'))

queries = [
    'Hello, how are you?',
    'Describe the workspace',
    'Read README.md',
    'How to make a paper plugin?'
]
for q in queries:
    print('> ', q)
    resp = app.respond(q)
    print(resp)
    print('-' * 60)

print(app.respond('/theme'))
print(app.respond('/theme set classic'))
print(app.respond('/theme'))
