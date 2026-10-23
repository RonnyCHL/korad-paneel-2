"""Twee logs vergelijken: allebei vanaf hun eigen begin, de reeks van stroom, spanning of vermogen, en een tabel
met de verschillen (B min A, ook in procenten). Overgenomen uit het oude paneel (logs vergelijken)."""

from __future__ import annotations

import html
from datetime import datetime

from .geschiedenis import Meting, Venster, venster_uit
from .rapport import datum, nl

WAT = {"stroom": "mA", "spanning": "V", "vermogen": "W"}


def duur_tekst(s: float) -> str:
    s = int(round(s))
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def reeks(pts: list[Meting], wat: str) -> list[tuple[float, float]]:
    """(seconden sinds het begin, waarde) per meting."""
    if not pts:
        return []
    t0 = pts[0].t
    if wat == "stroom":
        return [(p.t - t0, p.i * 1000) for p in pts]
    if wat == "spanning":
        return [(p.t - t0, p.v) for p in pts]
    return [(p.t - t0, p.w) for p in pts]


def _w_gem(v: Venster | None, pts: list[Meting]) -> float | None:
    if not pts:
        return None
    return sum(p.w for p in pts) / len(pts)


def rijen(a: list[Meting] | None, b: list[Meting] | None) -> list[tuple[str, str, str, str]]:
    """De tabel: (label, A, B, verschil B - A)."""
    va = venster_uit(a) if a and len(a) >= 2 else None
    vb = venster_uit(b) if b and len(b) >= 2 else None
    ma = lambda x: f"{nl(x * 1000, 0)} mA"
    velden = [("Duur", lambda v, p: v.duur, duur_tekst),
              ("Gemiddelde stroom", lambda v, p: v.i_gem, ma),
              ("Hoogste stroom", lambda v, p: v.i_max, ma),
              ("Laagste stroom", lambda v, p: v.i_min, ma),
              ("Gemiddelde spanning", lambda v, p: v.v_gem, lambda x: f"{nl(x, 2)} V"),
              ("Gemiddeld vermogen", lambda v, p: _w_gem(v, p), lambda x: f"{nl(x, 2)} W"),
              ("Lading", lambda v, p: v.mah, lambda x: f"{nl(x, 1)} mAh"),
              ("Energie", lambda v, p: v.wh, lambda x: f"{nl(x, 3)} Wh")]
    uit = []
    for label, haal, f in velden:
        xa = haal(va, a) if va else None
        xb = haal(vb, b) if vb else None
        verschil = ""
        if xa is not None and xb is not None and label != "Duur":
            d = xb - xa
            pct = f" ({'+' if d >= 0 else ''}{nl(d / xa * 100, 1)} %)" if abs(xa) > 1e-9 else ""
            verschil = ("+" if d >= 0 else "-") + f(abs(d)) + pct
        uit.append((label, f(xa) if xa is not None else "-", f(xb) if xb is not None else "-", verschil))
    return uit


def _svg(reeksen: list[tuple[list[tuple[float, float]], str]], eenheid: str) -> str:
    W, H, L, R, T, B = 900, 300, 56, 16, 14, 30
    pw, ph = W - L - R, H - T - B
    xmax = max((r[-1][0] for r, _ in reeksen if r), default=1.0) or 1.0
    ymax = max((max(y for _, y in r) for r, _ in reeksen if r), default=1.0) * 1.15 or 1.0
    X = lambda x: L + pw * x / xmax
    Y = lambda y: T + ph * (1 - min(y / ymax, 1.0))
    uit = [f"<svg viewBox='0 0 {W} {H}' xmlns='http://www.w3.org/2000/svg'>"]
    for k in range(5):
        y = T + ph * k / 4
        uit.append(f"<line x1='{L}' y1='{y:.1f}' x2='{L + pw}' y2='{y:.1f}' stroke='#E6E0D0'/>")
        uit.append(f"<text x='{L - 6}' y='{y + 4:.1f}' text-anchor='end' class='t'>{nl(ymax * (1 - k / 4), 1)}</text>")
    for k in range(7):
        x = L + pw * k / 6
        uit.append(f"<text x='{x:.1f}' y='{T + ph + 18}' text-anchor='middle' class='t'>{duur_tekst(xmax * k / 6)}</text>")
    uit.append(f"<text x='4' y='{T + 10}' class='t'>{eenheid}</text>")
    for r, kleur in reeksen:
        if len(r) < 2:
            continue
        stap = max(1, len(r) // 1500)
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in r[::stap])
        uit.append(f"<polyline points='{pts}' fill='none' stroke='{kleur}' stroke-width='1.8'/>")
    uit.append("</svg>")
    return "".join(uit)


def rapport_html(naam_a: str, a: list[Meting], naam_b: str, b: list[Meting], wat: str = "stroom") -> str:
    esc = html.escape
    reeksen = [(reeks(a, wat), "#C98400"), (reeks(b, wat), "#2F6FD0")]
    tabel = "".join(f"<tr><td>{esc(l)}</td><td>{esc(x)}</td><td>{esc(y)}</td><td>{esc(d)}</td></tr>"
                    for l, x, y, d in rijen(a, b))
    nu = datetime.now()
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>Vergelijking</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; background: #F3EFE4; color: #1F2430; margin: 0; }}
  .page {{ max-width: 980px; margin: 24px auto; background: white; padding: 28px 36px; border: 1px solid #DDD5C1; }}
  h1 {{ font-size: 22px; margin: 4px 0 8px; }} .meta {{ color: #6B7280; font-size: 13px; margin: 2px 0; }}
  .legenda i {{ display: inline-block; width: 22px; height: 3px; vertical-align: middle; margin: 0 6px 0 14px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 14px; }}
  th, td {{ border-bottom: 1px solid #E6E0D0; padding: 6px 8px; text-align: left; }} th {{ color: #6B7280; }}
  svg {{ width: 100%; height: auto; }} .t {{ font-size: 10px; fill: #6B7280; }}
  @media print {{ body {{ background: white; }} .page {{ margin: 0; border: none; padding: 0; }} }}
</style></head><body><div class="page">
  <p class="meta">Korad paneel 2 · vergelijking · {esc(wat)}</p>
  <h1>{esc(naam_a)} en {esc(naam_b)}</h1>
  <p class="legenda"><i style="background:#C98400;margin-left:0"></i>Meting A: {esc(naam_a)}
    <i style="background:#2F6FD0"></i>Meting B: {esc(naam_b)}</p>
  {_svg(reeksen, WAT.get(wat, ""))}
  <table><tr><th></th><th>Meting A</th><th>Meting B</th><th>Verschil B - A</th></tr>{tabel}</table>
  <p class="meta" style="margin-top:20px">Allebei vanaf hun eigen begin. Gemaakt met Korad paneel 2 op
    {datum(nu.timestamp())} om {nu:%H:%M}.</p>
</div></body></html>
"""
