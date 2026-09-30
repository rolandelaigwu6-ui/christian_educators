"""Generate sitemap.xml after the actual public HTTPS domain has been confirmed."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'sitemap.xml')
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        parser.error('Use the confirmed HTTPS origin only, e.g. https://your-confirmed-domain.org')
    origin = args.base_url.rstrip('/')
    ET.register_namespace('', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    sitemap = ET.Element(ns + 'urlset')
    files = [ROOT / 'index.html', *sorted((ROOT / 'pages').glob('*.html'))]
    for page in files:
        if 'content="noindex"' in page.read_text():
            continue
        entry = ET.SubElement(sitemap, ns + 'url')
        path = '/' if page.name == 'index.html' else '/' + page.relative_to(ROOT).as_posix()
        ET.SubElement(entry, ns + 'loc').text = origin + path
    ET.indent(sitemap)
    ET.ElementTree(sitemap).write(args.output, encoding='utf-8', xml_declaration=True)
    print(f'Wrote {len(sitemap)} URLs to {args.output}')


if __name__ == '__main__':
    main()
