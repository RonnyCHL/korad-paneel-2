"""Het HTML-rapport van een stuk meting: kop, getallen, een grafiekje als SVG en de markeringen.

Afdrukbaar als PDF vanuit de browser. Alleen stdlib; het rapport is een losse pagina zonder scripts.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .geschiedenis import Meting, venster_uit

from ..paden import BASIS

MAP = BASIS / "rapporten"
DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december"]


def nl(x: float, d: int) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def datum(t: float) -> str:
    d = datetime.fromtimestamp(t)
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month - 1]} {d.year}"


def _svg(pts: list[Meting], markers: list[tuple[float, str]], kleur_v: str, kleur_i: str) -> str:
    if len(pts) < 2:
        return ""
    W, H, L, R, T, B = 900, 220, 50, 60, 14, 26
    t0, t1 = pts[0].t, pts[-1].t
    span = max(1.0, t1 - t0)
    vmax = max(1.0, max(p.v for p in pts) * 1.15)
    imax = max(0.01, max(p.i for p in pts) * 1.15)
    X = lambda t: L + (W - L - R) * (t - t0) / span
    YV = lambda v: T + (H - T - B) * (1 - v / vmax)
    YI = lambda i: T + (H - T - B) * (1 - i / imax)
    lijn_v = " ".join(f"{X(p.t):.1f},{YV(p.v):.1f}" for p in pts)
    lijn_i = " ".join(f"{X(p.t):.1f},{YI(p.i):.1f}" for p in pts)
    raster = "".join(f"<line x1='{L}' y1='{T + (H - T - B) * k / 4:.1f}' x2='{W - R}' y2='{T + (H - T - B) * k / 4:.1f}' "
                     f"stroke='#E6E0D0'/>" for k in range(5))
    as_v = "".join(f"<text x='{L - 6}' y='{YV(vmax * k / 4) + 4:.1f}' text-anchor='end' class='t'>{nl(vmax * k / 4, 1)}</text>"
                   for k in range(5))
    as_i = "".join(f"<text x='{W - R + 6}' y='{YI(imax * k / 4) + 4:.1f}' class='t'>{nl(imax * k / 4 * 1000, 0)}</text>"
                   for k in range(5))
    mk = "".join(f"<line x1='{X(t):.1f}' y1='{T}' x2='{X(t):.1f}' y2='{H - B}' stroke='#8792A2' stroke-dasharray='4 3'/>"
                 f"<text x='{X(t) + 3:.1f}' y='{T + 10 + (k % 3) * 12}' class='m'>{html.escape(lab)}</text>"
                 for k, (t, lab) in enumerate(markers) if t0 <= t <= t1)
    tijden = "".join(f"<text x='{X(t0 + span * k / 4):.1f}' y='{H - 8}' text-anchor='middle' class='t'>"
                     f"{datetime.fromtimestamp(t0 + span * k / 4):%H:%M:%S}</text>" for k in range(5))
    return (f"<svg viewBox='0 0 {W} {H}'>{raster}{as_v}{as_i}{mk}"
            f"<polyline points='{lijn_v}' fill='none' stroke='{kleur_v}' stroke-width='1.6'/>"
            f"<polyline points='{lijn_i}' fill='none' stroke='{kleur_i}' stroke-width='1.6'/>"
            f"<text x='{L}' y='{T - 3}' class='t'>V</text><text x='{W - R + 6}' y='{T - 3}' class='t'>mA</text>{tijden}</svg>")


def maak(titel: str, pts: list[Meting], markers: list[tuple[float, str]], *, apparaat: str = "",
         project: str = "", v_set: float | None = None, i_set: float | None = None, oordeel: str = "",
         oordeel_klasse: str = "goed", toelichting: str = "", soort: str = "rapport",
         extra_html: str = "") -> str:
    esc = html.escape
    w = venster_uit(pts) if pts else None
    getallen = "" if not w else f"""
  <table><tr><th>Duur</th><th>Metingen</th><th>Spanning gem.</th><th>Stroom gem.</th><th>Stroom hoogste</th>
    <th>Stroom laagste</th><th>Lading</th><th>Energie</th></tr>
  <tr><td>{nl(w.duur, 1)} s</td><td>{w.n}</td><td>{nl(w.v_gem, 2)} V</td><td>{nl(w.i_gem * 1000, 0)} mA</td>
    <td>{nl(w.i_max * 1000, 0)} mA</td><td>{nl(w.i_min * 1000, 0)} mA</td><td>{nl(w.mah, 2)} mAh</td>
    <td>{nl(w.wh * 1000, 1)} mWh</td></tr></table>"""
    mk = "".join(f"<tr><td>{datetime.fromtimestamp(t):%H:%M:%S}</td><td>{esc(lab)}</td></tr>" for t, lab in markers)
    markering_tabel = f"<h2>Markeringen</h2><table><tr><th>Tijd</th><th>Markering</th></tr>{mk}</table>" if mk else ""
    t0 = pts[0].t if pts else datetime.now().timestamp()
    t1 = pts[-1].t if pts else t0
    inst = (f"; {nl(v_set, 2)} V, stroomgrens {nl(i_set, 3)} A" if v_set is not None and i_set is not None else "")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>{esc(titel)}</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; background: #F3EFE4; color: #1F2430; margin: 0; }}
  .page {{ max-width: 980px; margin: 24px auto; background: white; padding: 28px 36px; border: 1px solid #DDD5C1; }}
  h1 {{ font-size: 22px; margin: 4px 0 8px; }} h2 {{ font-size: 15px; margin: 22px 0 8px; }}
  .meta {{ color: #6B7280; font-size: 13px; margin: 2px 0; }}
  .verdict {{ font-size: 16px; font-weight: 600; margin: 14px 0; padding: 10px 14px; border-radius: 6px; }}
  .goed {{ background: #E3F4E1; color: #1E6B2E; }} .letop {{ background: #FFF2CC; color: #7A5A00; }}
  .fout {{ background: #FADDDA; color: #8E1B1B; }}
  td.goed, td.letop, td.fout {{ background: none; }} td.goed {{ color: #1E6B2E; }} td.letop {{ color: #7A5A00; }}
  td.fout {{ color: #8E1B1B; }} code {{ font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }} th, td {{ border-bottom: 1px solid #E6E0D0; padding: 6px 8px; text-align: left; }}
  svg {{ width: 100%; height: auto; }} .t {{ font-size: 10px; fill: #6B7280; }} .m {{ font-size: 10px; fill: #4B5563; }}
  @media print {{ body {{ background: white; }} .page {{ margin: 0; border: none; padding: 0; }} }}
</style></head><body><div class="page">
  <p class="meta">Korad paneel 2 · {esc(soort)}</p>
  <h1>{esc(titel)}</h1>
  <p class="meta">{datum(t0)}, {datetime.fromtimestamp(t0):%H:%M:%S} tot {datetime.fromtimestamp(t1):%H:%M:%S}{
    f", met {esc(apparaat)}" if apparaat else ""}{esc(inst)}{f"; project {esc(project)}" if project else ""}.</p>
  {f'<p class="verdict {oordeel_klasse}">{esc(oordeel)}</p>' if oordeel else ""}
  {f'<p>{esc(toelichting)}</p>' if toelichting else ""}
  {extra_html}
  {getallen}
  {"<h2>Spanning en stroom</h2>" + _svg(pts, markers, "#D9484A", "#C7791A") if len(pts) >= 2 else ""}
  {markering_tabel}
  <p class="meta" style="margin-top:20px">Gemaakt met Korad paneel 2 op {datum(datetime.now().timestamp())} om {datetime.now():%H:%M}.</p>
</div></body></html>
"""


def bewaar(pagina: str, stam: str, map_: Path = MAP) -> Path:
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / f"{stam}_{datetime.now():%Y%m%d_%H%M%S}.html"
    pad.write_text(pagina, encoding="utf-8")
    return pad
