"""Check that no header/cell in the Early vote tables wraps, at given viewport widths; saves screenshots.
Usage: <venv>/bin/python pipeline/check_early_nowrap.py [base_url] [out_prefix]"""
import sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787/"
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "/workspace/election-tracker/shot_early_wide"
JS = """() => {
  const out = [];
  const probe = document.createElement('span'); probe.textContent = 'X';
  for (const id of ['evtable','evdtable']) {
    const t = document.getElementById(id);
    t.querySelector('td,th').appendChild(probe);
    const lh = probe.getBoundingClientRect().height; probe.remove();
    let wrapped = 0, cells = 0, ex = [];
    for (const c of t.querySelectorAll('th,td')) {
      cells++;
      // one text line = range client rects all on same top (ignores the bar's inline box)
      const r = document.createRange(); r.selectNodeContents(c);
      const tops = new Set([...r.getClientRects()].filter(x=>x.width>0&&x.height>0).map(x=>Math.round(x.top + x.height/2)));
      const lines = new Set(); for (const tp of tops) { if (![...lines].some(l=>Math.abs(l-tp)<lh*0.75)) lines.add(tp); }
      if (lines.size > 1) { wrapped++; if (ex.length<5) ex.push(c.textContent.trim().slice(0,50)); }
    }
    const w = t.parentElement; out.push({id, cells, wrapped, ex, lineHeight: lh, tableW: t.scrollWidth, wrapperW: w.clientWidth, scrolls: t.scrollWidth > w.clientWidth});
  }
  return out;
}"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    bad = 0
    for w in (1440, 1280):
        pg = b.new_page(viewport={"width": w, "height": 1100})
        pg.goto(BASE + "#early"); pg.wait_for_selector("#evtable tbody tr"); pg.wait_for_selector("#evdtable tbody tr")
        res = pg.evaluate(JS)
        for r in res:
            bad += r["wrapped"]; print(w, r)
        pg.screenshot(path=f"{PREFIX}_{w}.png", full_page=False)
        pg.close()
    b.close()
print("TOTAL wrapped cells:", bad); sys.exit(1 if bad else 0)
