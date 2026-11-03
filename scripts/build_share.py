"""Build a fresh sharing URL from the current app; keep behavior in sync."""
from pathlib import Path

base = 'https://kibbutz-entrance.github.io/bloomfield-parking/'
source = Path('dist/index.html').read_text()
for attribute in ('content', 'href'):
    source = source.replace(f'{attribute}="{base}"', f'{attribute}="{base}share.html"')
Path('dist/share.html').write_text(source)
