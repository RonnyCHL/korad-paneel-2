"""Handboek naar PDF met Microsoft Edge zonder venster (A4).

    .venv\\Scripts\\python docs\\handboek\\maak_pdf.py   ->  docs\\handboek\\Korad-paneel-2-handboek.pdf
"""
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

edge = next((p for p in EDGE if p.exists()), None)
if edge is None:
    sys.exit("Microsoft Edge niet gevonden")
pdf = HIER / "Korad-paneel-2-handboek.pdf"
subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                (HIER / "handboek.html").as_uri()], check=True, capture_output=True, timeout=180)
print("geschreven:", pdf, f"{pdf.stat().st_size // 1024} kB")
