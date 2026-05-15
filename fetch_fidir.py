#!/usr/bin/env python3
"""
fetch_fidir.py — Intuit FI Directory refresh
Fetches all 4 OFX endpoints, parses active institutions,
generates a self-contained quicken-windows.html in ./dist/.
Exits with code 1 on any failure so GitHub Actions marks the run red.
"""

import urllib.request
import json
import time
import datetime
import os
import sys

ENDPOINTS = {
    "qbwin": "https://ofx-prod-filist.intuit.com/qb3400/data/fidir.txt",
    "qbmac": "https://ofx-prod-filist.intuit.com/qbm3400/data/fidir.txt",
    "qwwin": "https://ofx-prod-filist.intuit.com/qw2800/data/fidir.txt",
    "qmmac": "https://ofx-prod-filist.intuit.com/qm2400/data/fidir.txt",
}

SCHEMA = {
    "qbwin": dict(name=4, url=5, phone=6, ofx=7, status=8, dc=9,  wc=10, ewc=None, qbp=13),
    "qbmac": dict(name=4, url=5, phone=6, ofx=7, status=8, dc=9,  wc=10, ewc=None, qbp=13),
    "qwwin": dict(name=3, url=4, phone=5, ofx=6, status=7, dc=8,  wc=9,  ewc=11,   qbp=12),
    "qmmac": dict(name=3, url=4, phone=5, ofx=6, status=7, dc=8,  wc=9,  ewc=11,   qbp=12),
}

PRODUCT_LABELS = {
    "qwwin": "Quicken Windows",
    "qmmac": "Quicken Mac",
    "qbwin": "QuickBooks Win",
    "qbmac": "QuickBooks Mac",
}

# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------

def fetch_product(key, url, schema):
    s = schema
    with urllib.request.urlopen(url, timeout=30) as r:
        lines = r.read().decode("utf-8", errors="replace").splitlines()
    insts = []
    for line in lines[2:]:
        if not line.strip():
            continue
        c = line.split("\t")
        if len(c) <= s["status"]:
            continue
        if c[s["status"]].strip() != "ACTIVE":
            continue
        insts.append({
            "id":    c[0].strip(),
            "name":  c[s["name"]].strip()  if len(c) > s["name"]  else "",
            "url":   c[s["url"]].strip()   if len(c) > s["url"]   else "",
            "phone": c[s["phone"]].strip() if len(c) > s["phone"] else "",
            "ofx":   c[s["ofx"]].strip()   if len(c) > s["ofx"]   else "",
            "dc":    c[s["dc"]].strip()    if s["dc"]  and len(c) > s["dc"]  else "",
            "wc":    c[s["wc"]].strip()    if s["wc"]  and len(c) > s["wc"]  else "",
            "ewc":   c[s["ewc"]].strip()   if s["ewc"] and len(c) > s["ewc"] else "",
            "qbp":   c[s["qbp"]].strip()  if s["qbp"] and len(c) > s["qbp"] else "",
        })
    return insts


def fetch_all():
    start = time.time()
    products = {}
    errors = []
    for key, url in ENDPOINTS.items():
        try:
            insts = fetch_product(key, url, SCHEMA[key])
            products[key] = insts
            print(f"  {key}: {len(insts):,} active institutions")
            if len(insts) == 0:
                errors.append(
                    f"{key}: fetched OK but 0 active institutions "
                    f"(possible format change at {url})"
                )
        except Exception as e:
            products[key] = []
            errors.append(f"{key}: fetch failed — {type(e).__name__}: {e}")
            print(f"  ERROR {key}: {e}", file=sys.stderr)
    elapsed = round(time.time() - start, 1)
    return products, errors, elapsed


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def build_html(products, counts, updated):
    products_json = json.dumps(products, separators=(",", ":"))
    counts_json   = json.dumps(counts)
    labels_json   = json.dumps(PRODUCT_LABELS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Intuit FI Directory</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f6fa; color: #1a1a2e; }}
  header {{ background: #0b6ede; color: #fff; padding: 16px 24px;
            display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
  header h1 {{ font-size: 18px; font-weight: 700; letter-spacing: -.3px; flex: 1 1 auto; }}
  .updated {{ font-size: 12px; opacity: .8; white-space: nowrap; }}
  .container {{ padding: 20px 24px; }}
  .pills {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
  .pill {{ cursor: pointer; padding: 7px 16px; border-radius: 20px; border: 2px solid #d0d3e0;
           background: #fff; font-size: 13px; font-weight: 600; color: #555;
           transition: all .15s; user-select: none; }}
  .pill:hover {{ border-color: #0b6ede; color: #0b6ede; }}
  .pill.active {{ background: #0b6ede; border-color: #0b6ede; color: #fff; }}
  .pill .cnt {{ font-weight: 400; opacity: .85; margin-left: 4px; }}
  .filters {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }}
  .search-wrap {{ position: relative; flex: 1 1 280px; }}
  .search-wrap svg {{ position: absolute; left: 10px; top: 50%;
                      transform: translateY(-50%); opacity: .4; pointer-events: none; }}
  input[type=text] {{ width: 100%; padding: 8px 10px 8px 34px; border: 1.5px solid #d0d3e0;
                      border-radius: 8px; font-size: 13px; outline: none; background: #fff; }}
  input[type=text]:focus {{ border-color: #0b6ede; }}
  select {{ padding: 8px 10px; border: 1.5px solid #d0d3e0; border-radius: 8px;
            font-size: 13px; outline: none; background: #fff; cursor: pointer; }}
  select:focus {{ border-color: #0b6ede; }}
  .result-count {{ font-size: 12px; color: #888; margin-left: auto; white-space: nowrap; }}
  .table-wrap {{ background: #fff; border-radius: 10px;
                 box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ position: sticky; top: 0; background: #f0f2f8; padding: 10px 12px;
              text-align: left; font-weight: 600; font-size: 12px; color: #555;
              border-bottom: 1.5px solid #d8dbe8; cursor: pointer;
              user-select: none; white-space: nowrap; z-index: 2; }}
  thead th:hover {{ background: #e5e8f2; }}
  thead th .sort-icon {{ display: inline-block; margin-left: 4px; opacity: .4; }}
  thead th.asc  .sort-icon::after {{ content: '▲'; }}
  thead th.desc .sort-icon::after {{ content: '▼'; }}
  thead th:not(.asc):not(.desc) .sort-icon::after {{ content: '⇅'; }}
  tbody tr {{ border-bottom: 1px solid #f0f2f6; transition: background .1s; }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:hover {{ background: #f7f8fd; }}
  td {{ padding: 9px 12px; vertical-align: top; }}
  td.id   {{ font-family: monospace; color: #666; font-size: 12px; }}
  td.name {{ font-weight: 500; max-width: 260px; word-break: break-word; }}
  td.url a, td.ofx a {{ color: #0b6ede; text-decoration: none; font-size: 12px; }}
  td.url a:hover, td.ofx a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 4px;
            font-size: 11px; font-weight: 600; margin: 1px 2px; }}
  .badge-dc  {{ background: #e6f4ea; color: #1e7e34; }}
  .badge-wc  {{ background: #e8f0fe; color: #1a56c4; }}
  .badge-ewc {{ background: #fef3e2; color: #b45309; }}
  .badge-qbp {{ background: #f3e8ff; color: #7c3aed; }}
  .no-results {{ text-align: center; padding: 48px; color: #aaa; font-size: 14px; }}
  .sentinel   {{ height: 1px; }}
</style>
</head>
<body>
<header>
  <h1>&#127970; Intuit FI Directory</h1>
  <span class="updated">Updated: {updated}</span>
</header>
<div class="container">
  <div class="pills" id="pills"></div>
  <div class="filters">
    <div class="search-wrap">
      <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input type="text" id="search" placeholder="Search by name, FI ID, or OFX URL…" autocomplete="off">
    </div>
    <select id="conn-filter">
      <option value="">All connection types</option>
      <option value="dc">Direct Connect (DC)</option>
      <option value="wc">Web Connect (WC)</option>
      <option value="ewc">Express Web Connect (EWC)</option>
    </select>
    <select id="qbp-filter">
      <option value="">All QBP</option>
      <option value="qbp">QBP Only</option>
      <option value="not_qbp">Non-QBP</option>
    </select>
    <span class="result-count" id="result-count"></span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-col="id">FI ID<span class="sort-icon"></span></th>
          <th data-col="name" class="asc">Name<span class="sort-icon"></span></th>
          <th data-col="url">URL<span class="sort-icon"></span></th>
          <th data-col="ofx">OFX URL<span class="sort-icon"></span></th>
          <th data-col="phone">Phone<span class="sort-icon"></span></th>
          <th data-col="connections">Connections<span class="sort-icon"></span></th>
          <th data-col="qbp">QBP<span class="sort-icon"></span></th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="sentinel" id="sentinel"></div>
    <div class="no-results" id="no-results" style="display:none">
      No institutions match your filters.
    </div>
  </div>
</div>
<script>
const ALL_PRODUCTS = {products_json};
const COUNTS       = {counts_json};
const LABELS       = {labels_json};
let currentProduct = 'qwwin';
let sortCol = 'name', sortDir = 'asc';
let filtered = [], rendered = 0;
const PAGE = 80;
const pillsEl = document.getElementById('pills');
['qwwin','qmmac','qbwin','qbmac'].forEach(prod => {{
  const p = document.createElement('button');
  p.className = 'pill' + (prod === currentProduct ? ' active' : '');
  p.innerHTML = LABELS[prod] + ' <span class="cnt">(' + (COUNTS[prod]||0).toLocaleString() + ')</span>';
  p.onclick = () => {{
    currentProduct = prod;
    document.querySelectorAll('.pill').forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    applyFilters();
  }};
  pillsEl.appendChild(p);
}});
document.querySelectorAll('thead th').forEach(th => {{
  th.onclick = () => {{
    const col = th.dataset.col;
    sortDir = (sortCol === col && sortDir === 'asc') ? 'desc' : 'asc';
    sortCol = col;
    document.querySelectorAll('thead th').forEach(x => x.classList.remove('asc','desc'));
    th.classList.add(sortDir);
    applyFilters();
  }};
}});
['search','conn-filter','qbp-filter'].forEach(id =>
  document.getElementById(id).addEventListener('input', applyFilters)
);
function hasConn(inst, type) {{ const v = inst[type]; return v && v !== '0' && v !== ''; }}
function connSortKey(inst) {{
  return (hasConn(inst,'dc') ? 'dc' : '') + (hasConn(inst,'wc') ? 'wc' : '') + (hasConn(inst,'ewc') ? 'ewc' : '');
}}
function connBadges(inst) {{
  return (hasConn(inst,'dc')  ? '<span class="badge badge-dc">DC</span>'   : '') +
         (hasConn(inst,'wc')  ? '<span class="badge badge-wc">WC</span>'   : '') +
         (hasConn(inst,'ewc') ? '<span class="badge badge-ewc">EWC</span>' : '');
}}
function applyFilters() {{
  const q    = document.getElementById('search').value.trim().toLowerCase();
  const conn = document.getElementById('conn-filter').value;
  const qbp  = document.getElementById('qbp-filter').value;
  filtered = (ALL_PRODUCTS[currentProduct] || []).filter(inst => {{
    if (q && !inst.name.toLowerCase().includes(q) && !inst.id.includes(q) && !inst.ofx.toLowerCase().includes(q)) return false;
    if (conn && !hasConn(inst, conn)) return false;
    if (qbp === 'qbp'     && (!inst.qbp || inst.qbp === 'NOT_QBP')) return false;
    if (qbp === 'not_qbp' && inst.qbp && inst.qbp !== 'NOT_QBP')    return false;
    return true;
  }});
  filtered.sort((a, b) => {{
    let av = sortCol === 'connections' ? connSortKey(a) : (a[sortCol]||'').toLowerCase();
    let bv = sortCol === 'connections' ? connSortKey(b) : (b[sortCol]||'').toLowerCase();
    return av < bv ? (sortDir==='asc'?-1:1) : av > bv ? (sortDir==='asc'?1:-1) : 0;
  }});
  rendered = 0;
  document.getElementById('tbody').innerHTML = '';
  document.getElementById('no-results').style.display = filtered.length ? 'none' : '';
  document.getElementById('result-count').textContent = filtered.length.toLocaleString() + ' institutions';
  renderMore();
}}
function esc(s) {{
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}
function renderMore() {{
  const tbody = document.getElementById('tbody');
  const frag  = document.createDocumentFragment();
  filtered.slice(rendered, rendered + PAGE).forEach(inst => {{
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td class="id">${{esc(inst.id)}}</td>` +
      `<td class="name">${{esc(inst.name)}}</td>` +
      `<td class="url">${{inst.url ? `<a href="${{esc(inst.url)}}" target="_blank" rel="noopener">${{esc(inst.url)}}</a>` : ''}}</td>` +
      `<td class="ofx">${{inst.ofx ? `<a href="${{esc(inst.ofx)}}" target="_blank" rel="noopener">${{esc(inst.ofx)}}</a>` : ''}}</td>` +
      `<td>${{esc(inst.phone)}}</td>` +
      `<td>${{connBadges(inst)}}</td>` +
      `<td>${{inst.qbp && inst.qbp !== 'NOT_QBP' ? '<span class="badge badge-qbp">QBP</span>' : ''}}</td>`;
    frag.appendChild(tr);
  }});
  tbody.appendChild(frag);
  rendered += Math.min(PAGE, filtered.length - rendered);
}}
new IntersectionObserver(entries => {{
  if (entries[0].isIntersecting && rendered < filtered.length) renderMore();
}}, {{ rootMargin: '200px' }}).observe(document.getElementById('sentinel'));
applyFilters();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Fetching FI directory data...")
    products, errors, elapsed = fetch_all()
    counts = {k: len(v) for k, v in products.items()}
    total  = sum(counts.values())
    updated = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    print(f"\nCounts: {counts}")
    print(f"Total:  {total:,} | Elapsed: {elapsed}s")

    if total == 0:
        print("FATAL: zero institutions fetched.", file=sys.stderr)
        sys.exit(1)

    os.makedirs("dist", exist_ok=True)
    html = build_html(products, counts, updated)
    out  = os.path.join("dist", "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = os.path.getsize(out) / 1024
    print(f"\nHTML written -> {out}  ({size_kb:.0f} KB)")

    print("\n--- Summary ---")
    for k, n in counts.items():
        status = "OK" if n >= 1000 else "FAIL"
        print(f"  [{status}] {k}: {n:,}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  WARNING: {e}")

    if errors or any(n < 1000 for n in counts.values()):
        print("\nExiting with error code 1 (partial failure).", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll counts healthy. Done in {elapsed}s.")


if __name__ == "__main__":
    main()
