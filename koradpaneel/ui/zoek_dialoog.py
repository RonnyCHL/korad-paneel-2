"""Ctrl+K: een zoekvenster over alle menu-opdrachten. Typ een paar letters, Enter voert uit."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QMenuBar, QVBoxLayout


def alle_acties(menu: QMenuBar) -> list[tuple[str, QAction]]:
    uit = []
    for top in menu.actions():
        m = top.menu()
        if m is None:
            continue
        for a in m.actions():
            if a.isSeparator() or not a.isEnabled() or not a.text():
                continue
            uit.append((f"{top.text().replace('&', '')} › {a.text().replace('&', '').rstrip('…')}", a))
    return uit


class ZoekDialoog(QDialog):
    def __init__(self, menu: QMenuBar, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zoeken")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.acties = alle_acties(menu)
        root = QVBoxLayout(self)
        self.veld = QLineEdit()
        self.veld.setPlaceholderText("Typ wat je zoekt, bijvoorbeeld 'rapport' of 'thema'…")
        self.veld.setStyleSheet("font-family: inherit; font-size: 16px; padding: 10px 12px")
        self.veld.textChanged.connect(self._filter)
        self.veld.returnPressed.connect(self._doe)
        root.addWidget(self.veld)
        self.lijst = QListWidget()
        self.lijst.itemActivated.connect(lambda _it: self._doe())
        root.addWidget(self.lijst, 1)
        self.resize(560, 420)
        self._filter("")

    def _filter(self, tekst: str) -> None:
        t = tekst.lower().strip()
        self.lijst.clear()
        for naam, a in self.acties:
            if not t or all(deel in naam.lower() for deel in t.split()):
                it = QListWidgetItem(naam + (f"   ({a.shortcut().toString(QKeySequence.NativeText)})" if not a.shortcut().isEmpty() else ""))
                it.setData(Qt.UserRole, a)
                self.lijst.addItem(it)
        if self.lijst.count():
            self.lijst.setCurrentRow(0)

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if ev.key() in (Qt.Key_Down, Qt.Key_Up) and self.lijst.count():
            r = self.lijst.currentRow() + (1 if ev.key() == Qt.Key_Down else -1)
            self.lijst.setCurrentRow(max(0, min(self.lijst.count() - 1, r)))
            return
        super().keyPressEvent(ev)

    def _doe(self) -> None:
        it = self.lijst.currentItem()
        if it is None:
            return
        a = it.data(Qt.UserRole)
        self.accept()
        a.trigger()
