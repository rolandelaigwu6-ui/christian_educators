"""Check public static pages, local links, accessibility hooks and photo references."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, file):
        super().__init__()
        self.file, self.ids, self.links, self.inputs, self.labels = file, [], [], [], []
        self.h1 = 0
        self.missing_alt = 0
        self.description = False
        self.title = False
        self.feed(file.read_text())

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'): self.ids.append(a['id'])
        if tag == 'h1': self.h1 += 1
        if tag == 'title': self.title = True
        if tag == 'meta' and a.get('name') == 'description': self.description = bool(a.get('content'))
        if tag == 'img' and 'alt' not in a: self.missing_alt += 1
        if tag in ('input', 'textarea', 'select') and a.get('type') != 'hidden': self.inputs.append(a.get('id'))
        if tag == 'label': self.labels.append(a.get('for'))
        for key in ('src', 'href'):
            if a.get(key): self.links.append(a[key])
        if a.get('srcset'):
            self.links += [part.strip().split()[0] for part in a['srcset'].split(',')]


def main():
    files = [ROOT / 'index.html', ROOT / '404.html', *sorted((ROOT / 'pages').glob('*.html'))]
    pages = {p.resolve(): Page(p) for p in files}
    errors = []
    for path, page in pages.items():
        name = path.relative_to(ROOT)
        if page.h1 != 1: errors.append(f'{name}: expected one h1, found {page.h1}')
        if not page.description or not page.title: errors.append(f'{name}: missing title/description')
        if page.missing_alt: errors.append(f'{name}: missing image alt text')
        if any(n > 1 for n in Counter(page.ids).values()): errors.append(f'{name}: duplicate ids')
        for id in page.inputs:
            if not id or id not in page.labels: errors.append(f'{name}: unlabelled input {id}')
        for ref in page.links:
            url = urlsplit(ref)
            if url.scheme or url.netloc: continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not target.exists(): errors.append(f'{name}: missing {ref}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f'{name}: missing fragment {ref}')
        if re.search(r'\[X\]|\[amount\]|sample testimonial|demonstration form|65,700|266,700|Spiritual@COCEGN', path.read_text()):
            errors.append(f'{name}: stale placeholder/sample copy')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(pages)} pages; local links, anchors, metadata, headings, labels, image references and stale-copy checks.')


if __name__ == '__main__':
    main()
