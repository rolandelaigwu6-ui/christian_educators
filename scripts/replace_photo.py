"""Replace one illustrative photo everywhere, using prepared 640px/1200px WebP files."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'assets/img/photos/manifest.json'


def webp_file(value):
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f'File not found: {path}')
    header = path.read_bytes()[:12]
    if header[:4] != b'RIFF' or header[8:12] != b'WEBP':
        raise argparse.ArgumentTypeError('Use an exported WebP image, not a renamed JPEG.')
    return path


def main():
    manifest = json.loads(MANIFEST.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('photo', choices=sorted(manifest))
    parser.add_argument('--small', required=True, type=webp_file, help='640 × 427 WebP')
    parser.add_argument('--large', required=True, type=webp_file, help='1200 × 800 WebP')
    parser.add_argument('--alt', required=True, help='Accurate description of the real photo')
    parser.add_argument('--caption', required=True, help='Accurate caption and credit, with permission')
    args = parser.parse_args()
    if not args.alt.strip() or not args.caption.strip():
        parser.error('Alt text and caption must not be blank.')
    entry = manifest[args.photo]
    updates = []
    pattern = re.compile(r'(<figure\b[^>]*\bdata-photo="' + re.escape(args.photo) + r'"[^>]*>)(.*?)(</figure>)', re.S)
    for file in entry['pages']:
        page = ROOT / file
        def replace(match):
            body = re.sub(r'\balt="[^"]*"', lambda _: 'alt="' + html.escape(args.alt.strip(), quote=True) + '"', match[2], count=1)
            body = re.sub(r'<figcaption>.*?</figcaption>', lambda _: '<figcaption>' + html.escape(args.caption.strip()) + '</figcaption>', body, count=1, flags=re.S)
            return match[1] + body + match[3]
        text, count = pattern.subn(replace, page.read_text())
        if not count:
            raise SystemExit(f'No matching photo found in {file}; no changes made.')
        updates.append((page, text))
    for source, target in [(args.small, entry['files'][0]), (args.large, entry['files'][1])]:
        target = ROOT / target
        if source != target.resolve():
            shutil.copyfile(source, target)
    for page, text in updates:
        page.write_text(text)
    entry.update(illustrative=False, alt=args.alt.strip(), caption=args.caption.strip())
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Replaced {args.photo} across {len(updates)} pages. Review the photo framing in your browser.')


if __name__ == '__main__':
    main()
