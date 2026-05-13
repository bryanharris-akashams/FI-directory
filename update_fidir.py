"""
update_fidir.py
Downloads the four Intuit FIDIR files and regenerates the const PRODUCTS block in index.html.
Run locally or via GitHub Actions.
"""

import re
import sys
import json
try:
    import requests
except ImportError:
    import urllib.request as _urllib
    requests = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SOURCES = {
    'qbwin':  ('https://ofx-prod-filist.intuit.com/qb3400/data/fidir.txt',  0),
    'qbmac':  ('https://ofx-prod-filist.intuit.com/qbm3400/data/fidir.txt', 1),
    'qwwin':  ('https://ofx-prod-filist.intuit.com/qw2800/data/fidir.txt',  2),
    'qmmac':  ('https://ofx-prod-filist.intuit.com/qm2400/data/fidir.txt',  3),
}

SERVICE_MAP = {
    'BANKING':     'B',
    'CREDIT':      'C',
    'ACCOUNTINFO': 'A',
    'BILLPAY':     'P',
    'INVESTMENT':  'I',
    '401K':        'K',
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_text(url):
    if requests:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.text
    else:
        with _urllib.urlopen(url, timeout=30) as resp:
            return resp.read().decode('utf-8', errors='replace')


def parse_services(field):
    """'BANKING,CREDIT&WEB-CONNECT' → ['B', 'C']"""
    if not field or not field.strip():
        return []
    service_part = field.split('&')[0]
    codes = []
    for svc in service_part.split(','):
        svc = svc.strip()
        if svc in SERVICE_MAP:
            codes.append(SERVICE_MAP[svc])
    return codes


def parse_fidir(url, bid_col):
    print(f'  Downloading {url} ...', flush=True)
    text = fetch_text(url)
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line == 'FILIST' or line.isdigit():
            continue
        cols = line.split('\t')
        if len(cols) < 13:
            continue
        status = cols[8].strip() if len(cols) > 8 else ''
        if status != 'ACTIVE':
            continue

        bid      = cols[bid_col].strip()
        name     = cols[4].strip()
        homepage = cols[5].strip()
        phone    = cols[6].strip()
        enroll   = cols[7].strip()

        # Normalise NA → empty string
        phone    = '' if phone    in ('NA', 'N/A', 'na') else phone
        enroll   = '' if enroll   in ('NA', 'N/A', 'na') else enroll
        homepage = '' if homepage in ('NA', 'N/A', 'na') else homepage

        dc  = parse_services(cols[9]  if len(cols) >  9 else '')
        wc  = parse_services(cols[10] if len(cols) > 10 else '')
        ewc = parse_services(cols[12] if len(cols) > 12 else '')

        records.append([bid, name, homepage, phone, enroll, dc, wc, ewc])

    print(f'    → {len(records)} active records', flush=True)
    return records


def record_to_js(r):
    bid, name, homepage, phone, enroll, dc, wc, ewc = r

    def esc(s):
        return s.replace('\\', '\\\\').replace('"', '\\"')

    return (
        f'["{esc(bid)}","{esc(name)}","{esc(homepage)}",'
        f'"{esc(phone)}","{esc(enroll)}",'
        f'{json.dumps(dc)},{json.dumps(wc)},{json.dumps(ewc)}]'
    )


def build_products_js(all_products):
    lines = ['const PRODUCTS = {']
    keys = list(SOURCES.keys())
    for i, key in enumerate(keys):
        records_js = ','.join(record_to_js(r) for r in all_products[key])
        comma = ',' if i < len(keys) - 1 else ''
        lines.append(f'  {key}: [{records_js}]{comma}')
    lines.append('};')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('Fetching FIDIR files...', flush=True)
    all_products = {}
    for key, (url, bid_col) in SOURCES.items():
        all_products[key] = parse_fidir(url, bid_col)

    new_block = build_products_js(all_products)

    print('Updating index.html...', flush=True)
    with open('index.html', 'r', encoding='utf-8') as fh:
        content = fh.read()

    # Replace everything from "const PRODUCTS = {" up to and including the closing "};"
    pattern = r'const PRODUCTS = \{.*?\n\};'
    new_content, n = re.subn(pattern, new_block, content, flags=re.DOTALL)

    if n == 0:
        print('ERROR: Could not find "const PRODUCTS" block in index.html', file=sys.stderr)
        sys.exit(1)

    with open('index.html', 'w', encoding='utf-8') as fh:
        fh.write(new_content)

    totals = {k: len(v) for k, v in all_products.items()}
    print(f'Done. Counts: {totals}', flush=True)


if __name__ == '__main__':
    main()
