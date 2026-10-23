"""Meldingen (ntfy, gesproken tekst) en de telefoon-webserver, zonder echte telefoon: een lokale server."""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from koradpaneel.kern import meldingen as md
from koradpaneel.kern.telefoon import Telefoon


def test_gesproken_eenheden():
    assert md.gesproken("13,8 V en 230 mA, 1.5KE18A") == "13,8 volt en 230 milliampère, 1.5KE18A"
    assert md.gesproken("lading 44,6 mAh (95 %)") == "lading 44,6 milliampère-uur (95 procent)"


class _Vang(BaseHTTPRequestHandler):
    ontvangen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        _Vang.ontvangen.append(json.loads(self.rfile.read(n)))
        self.send_response(200)
        self.end_headers()


def test_ntfy_stuurt_json_naar_de_server():
    srv = HTTPServer(("127.0.0.1", 0), _Vang)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    uit = {}
    md.ntfy_stuur(f"http://127.0.0.1:{srv.server_address[1]}", "korad-test", "Korad: test", "hallo", 4, ("x",),
                  lambda ok, fout: uit.update(ok=ok, fout=fout), wacht=True)
    srv.shutdown()
    assert uit == {"ok": True, "fout": ""}
    assert _Vang.ontvangen[-1] == {"topic": "korad-test", "title": "Korad: test", "message": "hallo", "priority": 4, "tags": ["x"]}


def test_meldingen_kijken_in_de_instellingen():
    inst = {"spraak": False, "geluid_cc": False, "ntfy": {"server": "", "onderwerp": "", "aan": False}}
    m = md.Meldingen(inst)
    assert m.ntfy("x", "y") is False and m.laatste_ntfy == ""
    inst["ntfy"] = {"server": "http://127.0.0.1:1", "onderwerp": "t", "aan": True}
    assert m.ntfy("alarm", "stroom te hoog") is True and m.laatste_ntfy == "alarm: stroom te hoog"


def test_telefoon_pagina_stand_en_opdrachten():
    tel = Telefoon(0, "geheim")
    tel.start()
    try:
        basis = f"http://127.0.0.1:{tel.echte_poort}"
        tel.momentopname = {"verbonden": True, "v": 5.0, "i": 0.08, "punten": []}
        with urllib.request.urlopen(f"{basis}/?k=geheim") as r:
            html = r.read().decode()
        assert 'const K = "geheim"' in html and "Uitgang uit" in html
        with urllib.request.urlopen(f"{basis}/api/stand?k=geheim") as r:
            assert json.loads(r.read())["v"] == 5.0
        try:
            urllib.request.urlopen(f"{basis}/api/stand?k=fout")
            raise AssertionError("verkeerde code moet geweigerd worden")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        req = urllib.request.Request(f"{basis}/api/markering?k=geheim", data="hallo  daar".encode(), method="POST")
        urllib.request.urlopen(req).read()
        req = urllib.request.Request(f"{basis}/api/uit?k=geheim", data=b"", method="POST")
        urllib.request.urlopen(req).read()
        assert tel.opdrachten.get(timeout=2) == ("markering", "hallo daar")
        assert tel.opdrachten.get(timeout=2) == ("uit",)
        assert tel.url().startswith("http://") and tel.url().endswith("?k=geheim")
    finally:
        tel.stop()
