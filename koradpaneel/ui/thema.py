"""Thema's: de kleuren uit het goedgekeurde ontwerp (22-10-2026), als tokens en als Qt-stylesheet.

Spanning koraal, stroom amber, vermogen groen; accent blauw. Status wordt nooit alleen met kleur getoond.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thema:
    naam: str
    grond: str          # achtergrond van het venster
    kop: str            # kop- en voetbalk
    kaart: str
    kaart_rand: str
    inkt: str
    inkt_zacht: str     # labels
    inkt_vaag: str      # schaalgetallen
    lijn: str
    veld: str           # invoervelden
    spoor: str          # de lege ring van een meter
    spanning: str
    stroom: str
    vermogen: str
    accent: str
    gevaar: str
    goed: str
    uit: str            # lampje uit
    letters: str = "Inter, 'Segoe UI', system-ui, sans-serif"
    cijfers: str = "'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"


DONKER = Thema("donker", grond="#0F1115", kop="#13161C", kaart="#171A21", kaart_rand="#262B36",
               inkt="#F2F3F5", inkt_zacht="#9AA3B2", inkt_vaag="#6E7787", lijn="#262B36", veld="#0F1115",
               spoor="#262B36", spanning="#FF6B6B", stroom="#F5B544", vermogen="#3DDC97",
               accent="#3D7BF2", gevaar="#B23B3B", goed="#3DDC97", uit="#3A4150")

LICHT = Thema("licht", grond="#F4F5F7", kop="#FFFFFF", kaart="#FFFFFF", kaart_rand="#DDE1E8",
              inkt="#161A22", inkt_zacht="#5B6472", inkt_vaag="#8A93A2", lijn="#DDE1E8", veld="#FFFFFF",
              spoor="#E8EBF0", spanning="#D9484A", stroom="#C7791A", vermogen="#1E9E5A",
              accent="#2F6FE4", gevaar="#B8302F", goed="#1E9E5A", uit="#C9CFD8")

THEMAS = {"donker": DONKER, "licht": LICHT}


def qss(t: Thema) -> str:
    return f"""
QMainWindow, QWidget#grond {{ background: {t.grond}; color: {t.inkt}; }}
QWidget {{ color: {t.inkt}; font-family: {t.letters}; font-size: 14px; }}
QWidget#kop, QWidget#voet {{ background: {t.kop}; }}
QWidget#kop {{ border-bottom: 1px solid {t.lijn}; }}
QWidget#voet {{ border-top: 1px solid {t.lijn}; }}
QFrame#kaart {{ background: {t.kaart}; border: 1px solid {t.kaart_rand}; border-radius: 18px; }}
QLabel#titel {{ font-size: 20px; font-weight: 700; letter-spacing: 1px; }}
QLabel#zacht {{ color: {t.inkt_zacht}; }}
QLabel#kopje {{ color: {t.inkt_zacht}; font-size: 12px; font-weight: 600; letter-spacing: 2px; }}
QLabel#cijfer {{ font-family: {t.cijfers}; }}
QLabel#chip {{ background: {t.kaart}; border: 1px solid {t.kaart_rand}; border-radius: 12px; padding: 8px 12px; }}
QPushButton {{ background: {t.kaart}; color: {t.inkt}; border: 1px solid {t.kaart_rand}; border-radius: 10px;
               padding: 10px 14px; }}
QPushButton:hover {{ border-color: {t.inkt_zacht}; }}
QPushButton:pressed {{ background: {t.spoor}; }}
QPushButton:disabled {{ color: {t.inkt_vaag}; }}
QPushButton#primair {{ background: {t.accent}; color: #FFFFFF; border: 0; font-weight: 600; padding: 12px 20px; }}
QPushButton#gevaar {{ background: {t.gevaar}; color: #FFFFFF; border: 0; font-weight: 600; padding: 12px 20px; }}
QPushButton#geheugen {{ padding: 8px 12px; font-size: 13px; }}
QPushButton#menu {{ background: transparent; border: 0; padding: 8px 12px; }}
QPushButton#menu:hover {{ background: {t.kaart}; }}
QLineEdit {{ background: {t.veld}; color: {t.inkt}; border: 1px solid {t.kaart_rand}; border-radius: 10px;
             padding: 10px 12px; font-family: {t.cijfers}; font-size: 18px; selection-background-color: {t.accent}; }}
QLineEdit:focus {{ border-color: {t.accent}; }}
QComboBox {{ background: {t.kaart}; color: {t.inkt}; border: 1px solid {t.kaart_rand}; border-radius: 8px;
             padding: 7px 12px; }}
QComboBox QAbstractItemView {{ background: {t.kaart}; color: {t.inkt}; selection-background-color: {t.accent}; }}
QMenuBar {{ background: transparent; }}
QMenuBar::item {{ padding: 8px 12px; border-radius: 8px; }}
QMenuBar::item:selected {{ background: {t.kaart}; }}
QMenu {{ background: {t.kaart}; color: {t.inkt}; border: 1px solid {t.kaart_rand}; }}
QMenu::item {{ padding: 8px 20px; }}
QMenu::item:selected {{ background: {t.accent}; color: #FFFFFF; }}
QToolTip {{ background: {t.kaart}; color: {t.inkt}; border: 1px solid {t.kaart_rand}; }}
QStatusBar {{ background: {t.kop}; color: {t.inkt_zacht}; }}
"""
