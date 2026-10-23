"""De telefoon als afstandsbediening: een kleine webserver op het thuisnetwerk met één pagina.

Vanaf de telefoon kun je kijken (spanning, stroom, de grafiek van de laatste vijf minuten, alarm, lopende proef),
een markering plaatsen en de uitgang UIT zetten. Aanzetten of de spanning veranderen kan alleen aan de laptop.
De code in de link werkt als wachtwoord (hmac.compare_digest); alles zonder de juiste code wordt geweigerd.

De server praat nooit zelf met het paneel: hij leest een momentopname (dict) die het paneel elke seconde ververst,
en zet opdrachten in een wachtrij die het paneel op zijn tikker leegt. Zo blijft alles in de schermthread.
"""

from __future__ import annotations

import hmac
import json
import queue
import secrets
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"


def lokaal_ip() -> str:
    """IP-adres van deze pc op het thuisnetwerk (er gaat niets het netwerk op)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


def nieuwe_code() -> str:
    return secrets.token_urlsafe(9)


PAGINA = r"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0F1115">
<title>Korad paneel</title>
<style>
  :root { --bg:#0F1115; --card:#171A21; --card2:#21262E; --line:#262B36; --text:#F2F3F5; --muted:#9AA3B2;
          --red:#FF6B6B; --amber:#F5B544; --green:#3DDC97; --btnred:#B23B3B; --blue:#3D7BF2; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:16px/1.4 "Segoe UI", system-ui, sans-serif;
         padding:16px 16px 28px; }
  header { display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; margin-bottom:12px; }
  header b { font-size:20px; letter-spacing:.02em; } header span.m { color:var(--muted); font-size:20px; }
  .pill { margin-left:auto; display:flex; align-items:center; gap:6px; font-size:13px; color:var(--muted); }
  .dot { width:10px; height:10px; border-radius:50%; background:#3A4150; }
  .alarm { background:#3A1A18; border:1px solid var(--btnred); color:#FFB3AD; border-radius:10px; padding:10px 12px;
           margin-bottom:12px; font-weight:600; }
  .tiles { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:8px; }
  .tile { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:10px 10px 8px; }
  .tile span { display:block; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
  .tile b { display:block; font-size:clamp(20px, 6.4vw, 26px); font-variant-numeric:tabular-nums; margin-top:2px; }
  .tile small { color:var(--muted); font-size:12px; }
  .row { display:flex; align-items:center; gap:8px; margin:12px 0 8px; flex-wrap:wrap; }
  .chip { padding:3px 10px; border-radius:20px; background:var(--card2); font-size:13px; font-weight:600; }
  .muted { color:var(--muted); font-size:13px; margin:4px 0; overflow-wrap:anywhere; }
  canvas { width:100%; height:170px; display:block; background:#12161B; border:1px solid var(--line); border-radius:12px; }
  button { font:inherit; border:0; border-radius:12px; cursor:pointer; }
  #off { width:100%; margin:16px 0 12px; padding:16px; background:var(--btnred); color:#fff; font-size:18px;
         font-weight:700; letter-spacing:.02em; }
  #off:active { filter:brightness(1.15); }
  .mark { display:flex; gap:8px; }
  .mark input { flex:1; min-width:0; font:inherit; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
                background:var(--card2); color:var(--text); }
  .mark button { padding:0 16px; background:var(--card2); color:var(--text); border:1px solid var(--line); }
  .foot { color:var(--muted); font-size:12px; margin-top:16px; }
  :focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
</style></head>
<body>
<header><b>KORAD</b><span class="m">paneel 2</span>
  <span class="pill"><span class="dot" id="dot"></span><span id="st">verbinden...</span></span></header>
<div class="alarm" id="alarm" hidden></div>
<div class="tiles">
  <div class="tile"><span>Spanning</span><b id="v" style="color:var(--red)">--</b><small id="vs"></small></div>
  <div class="tile"><span>Stroom</span><b id="i" style="color:var(--amber)">--</b><small id="is"></small></div>
  <div class="tile"><span>Vermogen</span><b id="w" style="color:var(--green)">--</b><small>W</small></div>
</div>
<div class="row"><span class="chip" id="mode">--</span><span class="chip" id="out">--</span>
  <span class="muted" id="grens"></span></div>
<canvas id="c" width="700" height="340" aria-label="Spanning en stroom, laatste vijf minuten"></canvas>
<p class="muted" id="prog"></p>
<button id="off">Uitgang uit</button>
<div class="mark"><input id="txt" maxlength="60" placeholder="Notitie als markering" aria-label="Notitie">
  <button id="mk">Plaatsen</button></div>
<p class="foot">Vanaf de telefoon kun je kijken, een markering plaatsen en de uitgang uitzetten. Aanzetten of de
  spanning veranderen kan alleen aan de laptop.</p>
<script>
const K = "__CODE__";
const $ = (id) => document.getElementById(id);
const nl = (x, d) => (x === null || x === undefined) ? "--" : x.toFixed(d).replace(".", ",");
function draw(pts) {
  const c = $("c"), g = c.getContext("2d"), W = c.width, H = c.height;
  g.clearRect(0, 0, W, H);
  g.strokeStyle = "#262B36"; g.lineWidth = 1;
  for (let k = 1; k < 4; k++) { g.beginPath(); g.moveTo(0, H * k / 4); g.lineTo(W, H * k / 4); g.stroke(); }
  if (!pts || pts.length < 2) return;
  let vmax = 1, imax = 0.01;
  for (const p of pts) { vmax = Math.max(vmax, p[1]); imax = Math.max(imax, p[2]); }
  vmax *= 1.15; imax *= 1.25;
  const X = (a) => W - (a / 300) * W;
  for (const [idx, max, col] of [[2, imax, "#F5B544"], [1, vmax, "#FF6B6B"]]) {
    g.beginPath(); g.strokeStyle = col; g.lineWidth = 3;
    pts.forEach((p, n) => { const x = X(p[0]), y = H - 8 - (H - 16) * p[idx] / max; n ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke();
  }
  g.fillStyle = "#9AA3B2"; g.font = "22px Segoe UI, sans-serif"; g.fillText("laatste 5 minuten", 12, 30);
}
async function poll() {
  try {
    const r = await fetch("/api/stand?k=" + K, {cache: "no-store"});
    if (!r.ok) throw new Error(r.status);
    const s = await r.json();
    $("dot").style.background = s.verbonden ? "#3DDC97" : "#FF6B6B";
    $("st").textContent = s.verbonden ? "verbonden" : "voeding niet verbonden";
    $("v").textContent = nl(s.v, 2); $("i").textContent = nl(s.i, 3);
    $("w").textContent = (s.v === null || s.i === null) ? "--" : nl(s.v * s.i, 2);
    $("vs").textContent = s.vset === null ? "" : "ingesteld " + nl(s.vset, 2) + " V";
    $("is").textContent = s.iset === null ? "" : "grens " + nl(s.iset, 3) + " A";
    $("mode").textContent = !s.uit ? "uitgang uit" : (s.cc ? "CC begrensd" : "CV");
    $("mode").style.color = s.uit && s.cc ? "#FF6B6B" : "";
    $("out").textContent = s.uit ? "uitgang aan" : "uitgang uit";
    $("out").style.color = s.uit ? "#3DDC97" : "";
    $("grens").textContent = "Project: " + s.grens;
    $("alarm").hidden = !s.alarm; $("alarm").textContent = s.alarm;
    $("prog").textContent = s.programma || "";
    draw(s.punten);
  } catch (e) {
    $("dot").style.background = "#FF6B6B";
    $("st").textContent = "geen verbinding met het paneel";
  }
}
$("off").onclick = async () => {
  if (!confirm("Uitgang van de voeding uitzetten?")) return;
  try { await fetch("/api/uit?k=" + K, {method: "POST"}); } catch (e) {}
  poll();
};
$("mk").onclick = async () => {
  const t = $("txt").value.trim(); if (!t) return;
  try { await fetch("/api/markering?k=" + K, {method: "POST", body: t}); $("txt").value = ""; } catch (e) {}
};
$("txt").addEventListener("keydown", (e) => { if (e.key === "Enter") $("mk").click(); });
poll(); setInterval(poll, 1000);
</script>
</body></html>
"""


class Telefoon:
    """De webserver. momentopname: dict dat het paneel ververst; opdrachten: wachtrij met ('uit',) en
    ('markering', tekst) die het paneel leegt."""

    def __init__(self, poort: int = 8085, code: str = ""):
        self.poort = int(poort)
        self.code = code or nieuwe_code()
        self.momentopname: dict = {}
        self.opdrachten: queue.Queue = queue.Queue()
        self._srv: ThreadingHTTPServer | None = None

    @property
    def loopt(self) -> bool:
        return self._srv is not None

    @property
    def echte_poort(self) -> int:
        return self._srv.server_address[1] if self._srv else self.poort

    def url(self) -> str:
        return f"http://{lokaal_ip()}:{self.echte_poort}/?k={self.code}"

    def start(self) -> None:
        if self._srv is not None:
            return
        srv = ThreadingHTTPServer((HOST, self.poort), self._handler())
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True, name="telefoon").start()
        self._srv = srv

    def stop(self) -> None:
        srv, self._srv = self._srv, None
        if srv is not None:
            threading.Thread(target=lambda: (srv.shutdown(), srv.server_close()), daemon=True).start()

    def _handler(self):
        tel = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "KoradPaneel2"

            def log_message(self, *a):  # noqa: D102
                pass

            def _check(self):
                u = urllib.parse.urlparse(self.path)
                gegeven = urllib.parse.parse_qs(u.query).get("k", [""])[0]
                return u.path, bool(tel.code) and hmac.compare_digest(gegeven.encode(), tel.code.encode())

            def _stuur(self, status, body, ctype):
                data = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _weiger(self):
                self._stuur(403, "Geen toegang. Open de link of QR-code uit het Korad paneel.", "text/plain; charset=utf-8")

            def do_GET(self):  # noqa: N802
                pad, ok = self._check()
                if not ok:
                    return self._weiger()
                if pad == "/":
                    return self._stuur(200, PAGINA.replace("__CODE__", tel.code), "text/html; charset=utf-8")
                if pad == "/api/stand":
                    return self._stuur(200, json.dumps(tel.momentopname), "application/json")
                self._stuur(404, "Niet gevonden", "text/plain; charset=utf-8")

            def do_POST(self):  # noqa: N802
                pad, ok = self._check()
                if not ok:
                    return self._weiger()
                n = min(int(self.headers.get("Content-Length") or 0), 2000)
                body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                if pad == "/api/uit":
                    tel.opdrachten.put(("uit",))
                    return self._stuur(200, '{"ok":1}', "application/json")
                if pad == "/api/markering":
                    tekst = " ".join(body.split())[:60]
                    if tekst:
                        tel.opdrachten.put(("markering", tekst))
                    return self._stuur(200, '{"ok":1}', "application/json")
                self._stuur(404, "Niet gevonden", "text/plain; charset=utf-8")

        return Handler
