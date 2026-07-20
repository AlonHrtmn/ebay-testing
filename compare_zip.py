import zipfile
import os
import difflib

zip_path = r"C:\Users\Hp\Downloads\ebay_pages_rewritten.zip"
if not os.path.exists(zip_path):
    raise FileNotFoundError(zip_path)

with zipfile.ZipFile(zip_path) as z:
    entries = [n for n in z.namelist() if n.endswith('.py')]
    print('zip entries:', entries)
    for name in entries:
        print('\nFILE:', name)
        new_text = z.read(name).decode('utf-8').splitlines()
        old_path = os.path.join('pages', name)
        if not os.path.exists(old_path):
            print('  Existing file missing:', old_path)
            continue
        with open(old_path, 'r', encoding='utf-8') as f:
            old_text = f.read().splitlines()
        diff = list(difflib.unified_diff(old_text, new_text, fromfile=old_path, tofile='zip:'+name, n=3))
        added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
        hunks = sum(1 for line in diff if line.startswith('@@'))
        print('  old lines=', len(old_text), 'new lines=', len(new_text), 'added=', added, 'removed=', removed, 'hunks=', hunks)
        if not diff:
            print('  no content differences')
            continue
        print('  diff preview:')
        for line in diff[:40]:
            print('   ', line)
        if len(diff) > 40:
            print('   ... (truncated, total lines', len(diff), ')')
