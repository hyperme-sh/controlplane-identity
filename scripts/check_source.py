"""Verify relocated runtime and historical contract bytes against the import receipt."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'SOURCE-MANIFEST.json').read_text())
for entry in manifest['files']:
    if entry['unchanged']:
        actual = hashlib.sha256((root / entry['destination']).read_bytes()).hexdigest()
        if actual != entry['sha256']:
            raise SystemExit(f"Changed imported file: {entry['destination']}")
expected = {entry['destination'] for entry in manifest['files'] if entry['destination'].startswith('src/')}
actual = {path.relative_to(root).as_posix() for path in (root / 'src').rglob('*.py')}
if actual != expected:
    raise SystemExit('Runtime source inventory differs from the imported package')
print('Imported runtime, tests, and historical contract bytes verified')
