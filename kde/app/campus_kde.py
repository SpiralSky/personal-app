"""
Personal App — KDE desktop integration.

System tray icon with:
- Quick popup showing upcoming deadlines
- Open main UI (QWebEngineView window)
- Trigger sync
- KDE/freedesktop notifications on new items

Run with:  python3 kde/app/campus_kde.py
Or via the .desktop file after `bash kde/install.sh`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QSize,
    QTimer,
    Qt,
    Signal,
    QObject,
    QUrl,
)
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtNetwork import (
    QLocalServer,
    QLocalSocket,
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

API_BASE = "http://localhost:8765"
POLL_INTERVAL_MS = 120_000  # 2 min
APP_NAME = "Personal App"
ICON_NAME = "user-home"
_SOCKET_NAME = "campus-assistant-kde"

# ── Embedded server management ────────────────────────────────────────────────

_server_proc: subprocess.Popen | None = None


def _server_alive() -> bool:
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=0.5):
            return True
    except Exception:
        return False


def _find_repo_root() -> Path:
    """Walk up from this file's location to find the project root (has pyproject.toml)."""
    here = Path(__file__).resolve().parent
    for candidate in [here, here.parent, here.parent.parent]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here.parent.parent  # best guess


def start_embedded_server() -> bool:
    """Start the campus serve backend if not already running. Returns True when ready."""
    global _server_proc
    if _server_alive():
        return True  # systemd service or another instance already running

    repo = _find_repo_root()
    # Try uv run (dev checkout) first, then fall back to campus on PATH.
    uv = repo / ".venv" / "bin" / "campus"
    if uv.exists():
        cmd = [str(uv), "serve", "--no-schedule"]
    elif (repo / "pyproject.toml").exists():
        cmd = ["uv", "--directory", str(repo), "run", "campus", "serve", "--no-schedule"]
    else:
        cmd = ["campus", "serve", "--no-schedule"]

    try:
        _server_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # detach from our process group
        )
    except FileNotFoundError:
        return False

    # Wait up to 15 s for the server to become ready.
    for _ in range(30):
        time.sleep(0.5)
        if _server_proc.poll() is not None:
            return False  # crashed
        if _server_alive():
            return True
    return False


def stop_embedded_server() -> None:
    """Terminate the server we started (no-op if we didn't start one)."""
    global _server_proc
    if _server_proc is not None and _server_proc.poll() is None:
        _server_proc.terminate()
        try:
            _server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server_proc.kill()
    _server_proc = None


# ── Notification helper (freedesktop D-Bus, works on KDE/GNOME/etc.) ─────────

def notify(summary: str, body: str = "", urgency: int = 1) -> None:
    """Send a desktop notification via notify-send (non-blocking)."""
    import subprocess
    levels = {0: "low", 1: "normal", 2: "critical"}
    try:
        subprocess.Popen(
            ["notify-send", "-a", APP_NAME,
             "-u", levels.get(urgency, "normal"),
             "-i", ICON_NAME,
             summary, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass  # notify-send not installed — silently skip


# ── Network helper ────────────────────────────────────────────────────────────

class ApiClient(QObject):
    upcoming_ready = Signal(list)
    status_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

    def get_upcoming(self, days: int = 7) -> None:
        req = QNetworkRequest(QUrl(f"{API_BASE}/upcoming?days={days}"))
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_upcoming(reply))

    def _on_upcoming(self, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.error.emit(reply.errorString())
            reply.deleteLater()
            return
        try:
            data = json.loads(bytes(reply.readAll()))
            self.upcoming_ready.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))
        reply.deleteLater()

    def get_status(self) -> None:
        req = QNetworkRequest(QUrl(f"{API_BASE}/status"))
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_status(reply))

    def _on_status(self, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            reply.deleteLater()
            return
        try:
            data = json.loads(bytes(reply.readAll()))
            self.status_ready.emit(data)
        except Exception:
            pass
        reply.deleteLater()

    def post_sync(self) -> None:
        req = QNetworkRequest(QUrl(f"{API_BASE}/sync/brightspace"))
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        reply = self._nam.post(req, b"")
        reply.finished.connect(reply.deleteLater)


# ── Tray icon ─────────────────────────────────────────────────────────────────

def _make_icon(count: int = 0) -> QIcon:
    """Return a tray icon, optionally with a red badge for deadline count."""
    icon = QIcon.fromTheme(ICON_NAME)
    if count <= 0 or icon.isNull():
        return icon if not icon.isNull() else QIcon.fromTheme("appointment-new")

    px = icon.pixmap(QSize(64, 64))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    badge_r = 18
    bx, by = px.width() - badge_r - 2, 2
    painter.setBrush(QColor("#e53935"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(bx, by, badge_r * 2, badge_r * 2)

    painter.setPen(QColor("white"))
    f = QFont()
    f.setPixelSize(18)
    f.setBold(True)
    painter.setFont(f)
    label = str(count) if count < 100 else "99+"
    painter.drawText(bx, by, badge_r * 2, badge_r * 2, Qt.AlignmentFlag.AlignCenter, label)
    painter.end()
    return QIcon(px)


class TrayApp(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._client = ApiClient(self)
        self._client.upcoming_ready.connect(self._on_upcoming)
        self._client.status_ready.connect(self._on_status)
        self._client.error.connect(self._on_error)

        self._upcoming: list[dict[str, Any]] = []
        self._last_ids: set[str] = set()
        self._status_text = ""
        self._main_win: MainWindow | None = None
        self._popup: QuickPopup | None = None

        self._tray = QSystemTrayIcon()
        self._tray.setIcon(_make_icon())
        self._tray.setToolTip(APP_NAME)
        self._tray.activated.connect(self._on_tray_activated)

        menu = QMenu()
        self._act_open = QAction(QIcon.fromTheme("internet-web-browser"), f"Open {APP_NAME}")
        self._act_open.triggered.connect(self._open_main)
        menu.addAction(self._act_open)

        self._act_sync = QAction(QIcon.fromTheme("view-refresh"), "Sync now")
        self._act_sync.triggered.connect(self._sync)
        menu.addAction(self._act_sync)

        menu.addSeparator()

        self._act_status = QAction("")
        self._act_status.setEnabled(False)
        menu.addAction(self._act_status)

        menu.addSeparator()

        quit_act = QAction(QIcon.fromTheme("application-exit"), "Quit")
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.show()

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._poll()

        # Open the main window on first launch so the user sees something.
        QTimer.singleShot(0, self._open_main)

    # ── Tray actions ──────────────────────────────────────────────────────────

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_popup()

    def _toggle_popup(self) -> None:
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return
        if self._popup is None:
            self._popup = QuickPopup(self._upcoming, self._open_main, self._sync)
        else:
            self._popup.update_items(self._upcoming)
        geo = self._tray.geometry()
        self._popup.move(geo.center().x() - self._popup.width() // 2,
                         geo.center().y() - self._popup.height() - 8)
        self._popup.show()
        self._popup.raise_()
        self._popup.activateWindow()

    def _open_main(self) -> None:
        if self._popup:
            self._popup.hide()
        if self._main_win is None:
            self._main_win = MainWindow()
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()

    def _sync(self) -> None:
        self._act_sync.setEnabled(False)
        self._act_status.setText("Syncing…")
        self._client.post_sync()
        QTimer.singleShot(5000, lambda: self._act_sync.setEnabled(True))
        QTimer.singleShot(10000, self._poll)

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self) -> None:
        self._client.get_upcoming()
        self._client.get_status()

    def _on_upcoming(self, items: list[dict[str, Any]]) -> None:
        new_ids = {i.get("id", "") for i in items}
        truly_new = new_ids - self._last_ids
        if self._last_ids and truly_new:
            notify(
                f"{len(truly_new)} new item(s)",
                "\n".join(
                    i.get("data", {}).get("title", "Untitled")
                    for i in items
                    if i.get("id") in truly_new
                )[:200],
            )
        self._last_ids = new_ids
        self._upcoming = items
        self._tray.setIcon(_make_icon(len(items)))
        tip = f"{APP_NAME} — {len(items)} upcoming"
        if self._status_text:
            tip += f"\n{self._status_text}"
        self._tray.setToolTip(tip)
        if self._popup and self._popup.isVisible():
            self._popup.update_items(items)

    def _on_status(self, s: dict[str, Any]) -> None:
        last = (s.get("sync") or {}).get("last") or {}
        fin = last.get("finished_at")
        if fin:
            try:
                dt = datetime.fromisoformat(fin.replace("Z", "+00:00"))
                diff = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
                self._status_text = f"Last sync: {diff}m ago" if diff < 60 else f"Last sync: {diff // 60}h ago"
            except Exception:
                self._status_text = ""
        self._act_status.setText(self._status_text or "Never synced")

    def _on_error(self, msg: str) -> None:
        self._act_status.setText("Service offline")
        self._tray.setToolTip(f"{APP_NAME} — offline")

    def _on_new_instance(self, server: QLocalServer) -> None:
        """Second-instance activation: drain the socket and raise the window."""
        conn = server.nextPendingConnection()
        if conn:
            conn.readAll()
            conn.deleteLater()
        self._open_main()


# ── Quick popup (click-on-tray) ───────────────────────────────────────────────

class QuickPopup(QWidget):
    def __init__(self, items: list, open_cb, sync_cb) -> None:
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(320)
        self.setStyleSheet("""
            QWidget { background: palette(window); border-radius: 8px; }
            QLabel { padding: 2px; }
        """)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 10, 12, 10)

        title = QLabel(f"<b>{APP_NAME}</b>")
        vbox.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep)

        self._list_layout = QVBoxLayout()
        scroll_widget = QWidget()
        scroll_widget.setLayout(self._list_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(220)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        vbox.addWidget(scroll)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        vbox.addWidget(sep2)

        btn_row = QHBoxLayout()
        open_btn = QPushButton(QIcon.fromTheme("internet-web-browser"), "Open")
        open_btn.clicked.connect(open_cb)
        sync_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Sync")
        sync_btn.clicked.connect(sync_cb)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(sync_btn)
        vbox.addLayout(btn_row)

        self.update_items(items)
        self.adjustSize()

    def update_items(self, items: list) -> None:
        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not items:
            self._list_layout.addWidget(QLabel("No upcoming deadlines in 7 days"))
            return

        now = datetime.now(timezone.utc)
        for item in items[:8]:
            data = item.get("data", {})
            title = data.get("title") or item.get("id", "Untitled")
            due_raw = data.get("due_date") or data.get("end_date")
            if due_raw:
                try:
                    due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
                    diff_d = (due - now).days
                    if diff_d < 0:
                        due_str = f"Overdue {abs(diff_d)}d"
                    elif diff_d == 0:
                        due_str = "Due today"
                    else:
                        due_str = f"Due in {diff_d}d"
                except Exception:
                    due_str = due_raw[:10]
            else:
                due_str = ""

            row = QHBoxLayout()
            name_lbl = QLabel(f"<b>{title[:40]}</b>")
            name_lbl.setWordWrap(False)
            due_lbl = QLabel(due_str)
            due_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name_lbl, 3)
            row.addWidget(due_lbl, 1)
            w = QWidget()
            w.setLayout(row)
            self._list_layout.addWidget(w)


# ── Main window (wraps the web UI) ────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon.fromTheme(ICON_NAME))
        self.resize(1200, 800)

        if HAS_WEBENGINE:
            self._view = QWebEngineView()
            if _server_alive():
                self._view.load(QUrl(f"{API_BASE}/ui/"))
            else:
                self._view.setHtml(
                    "<h2 style='font-family:sans-serif;text-align:center;margin-top:80px'>"
                    "Starting server…</h2>"
                )
                QTimer.singleShot(500, self._try_load)
            self.setCentralWidget(self._view)
        else:
            lbl = QLabel(
                f'<a href="{API_BASE}/ui/">Open in browser: {API_BASE}/ui/</a>'
            )
            lbl.setOpenExternalLinks(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCentralWidget(lbl)

    def _try_load(self) -> None:
        if _server_alive():
            self._view.load(QUrl(f"{API_BASE}/ui/"))
        else:
            QTimer.singleShot(500, self._try_load)

    def closeEvent(self, event):
        # Hide instead of quit — tray keeps running
        event.ignore()
        self.hide()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("personal-app")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available", file=sys.stderr)
        sys.exit(1)

    # Single-instance: if another copy is running, tell it to raise and exit.
    probe = QLocalSocket()
    probe.connectToServer(_SOCKET_NAME)
    if probe.waitForConnected(300):
        probe.write(b"raise\n")
        probe.flush()
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        sys.exit(0)
    probe.close()

    # Start the backend server if it isn't already running.
    if not _server_alive():
        threading.Thread(target=start_embedded_server, daemon=True).start()

    tray_app = TrayApp()  # noqa: F841 — kept alive by event loop

    # Start single-instance server for future activations.
    _server = QLocalServer()
    QLocalServer.removeServer(_SOCKET_NAME)
    _server.listen(_SOCKET_NAME)
    _server.newConnection.connect(lambda: tray_app._on_new_instance(_server))

    app.aboutToQuit.connect(stop_embedded_server)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
