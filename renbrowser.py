import os
import sys
import shutil
import urllib.request
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QDialog, QLabel, QMessageBox,
    QScrollArea, QFrame, QProgressBar, QFileDialog
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage

APP_NAME = "renbrowser"
VERSION = "0.100.2"

class DownloadItemWidget(QFrame):
    def __init__(self, download_item, parent=None):
        super().__init__(parent)
        self.download_item = download_item
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout()
        self.label = QLabel(download_item.suggestedFileName())
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.cancel_btn = QPushButton("Cancel")
        layout.addWidget(self.label, stretch=2)
        layout.addWidget(self.progress, stretch=3)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)
        self.cancel_btn.clicked.connect(self.cancel)
        download_item.downloadProgress.connect(self.update_progress)
        download_item.finished.connect(self.finished)

    def update_progress(self, received, total):
        if total > 0:
            self.progress.setValue(int(received * 100 / total))

    def cancel(self):
        self.download_item.cancel()
        self.progress.setFormat("Cancelled")
        self.cancel_btn.setEnabled(False)

    def finished(self):
        if self.download_item.state() == self.download_item.DownloadCompleted:
            self.progress.setValue(100)
            self.progress.setFormat("Completed")
        else:
            self.progress.setFormat("Failed")
        self.cancel_btn.setEnabled(False)

class DownloadsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setMinimumSize(600, 400)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.vbox = QVBoxLayout()
        self.container.setLayout(self.vbox)
        self.scroll.setWidget(self.container)
        layout = QVBoxLayout()
        layout.addWidget(self.scroll)
        self.setLayout(layout)

    def add_download(self, widget):
        self.vbox.addWidget(widget)

class SettingsWindow(QDialog):
    def __init__(self, profile_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(300, 180)
        self.profile_path = profile_path
        layout = QVBoxLayout()
        self.clear_btn = QPushButton("Clear ALL browser data")
        self.clear_btn.clicked.connect(self.clear_data)
        self.version_label = QLabel(f"Version: {VERSION}")
        self.update_btn = QPushButton("Check for Updates")
        self.update_btn.clicked.connect(self.check_update)
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.update_btn)
        layout.addStretch()
        layout.addWidget(self.version_label)
        self.setLayout(layout)

    def clear_data(self):
        try:
            shutil.rmtree(self.profile_path, ignore_errors=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to clear data: {e}")
            return
        QMessageBox.information(
            self, "Data Cleared",
            "All browser data has been erased. The browser will now restart."
        )
        QApplication.quit()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def check_update(self):
        check_for_update()

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)
        self.profile_path = os.path.join(os.path.expanduser("~"), f".{APP_NAME}")
        os.makedirs(self.profile_path, exist_ok=True)
        self.profile = QWebEngineProfile(self.profile_path)
        try:
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        except Exception:
            pass
        self.profile.setCachePath(os.path.join(self.profile_path, "cache"))
        self.profile.setPersistentStoragePath(os.path.join(self.profile_path, "storage"))
        self.page = QWebEnginePage(self.profile)
        self.view = QWebEngineView()
        self.view.setPage(self.page)
        self.address_bar = QLineEdit()
        self.address_bar.returnPressed.connect(self.load_address)
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.view.back)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.view.reload)
        self.downloads_btn = QPushButton("Downloads")
        self.downloads_btn.clicked.connect(self.show_downloads)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        topbar = QHBoxLayout()
        topbar.addWidget(QLabel("URL:"))
        topbar.addWidget(self.address_bar, stretch=3)
        topbar.addWidget(self.back_btn)
        topbar.addWidget(self.refresh_btn)
        topbar.addWidget(self.downloads_btn)
        topbar.addWidget(self.settings_btn)
        central = QWidget()
        layout = QVBoxLayout()
        layout.addLayout(topbar)
        layout.addWidget(self.view, stretch=1)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.downloads_window = DownloadsWindow(self)
        self.view.page().profile().downloadRequested.connect(self.handle_download)
        self.view.urlChanged.connect(self.sync_address_bar)
        self.view.load(QUrl("https://www.google.com"))

    def sync_address_bar(self, url: QUrl):
        self.address_bar.setText(url.toDisplayString())

    def normalize_url(self, text: str) -> QUrl:
        t = text.strip()
        if not t:
            return QUrl()
        if "://" not in t and "." in t:
            return QUrl(f"https://{t}")
        return QUrl(t)

    def load_address(self):
        url = self.normalize_url(self.address_bar.text())
        if url.isValid():
            self.view.load(url)

    def show_downloads(self):
        self.downloads_window.show()
        self.downloads_window.raise_()
        self.downloads_window.activateWindow()

    def show_settings(self):
        win = SettingsWindow(self.profile_path, self)
        win.exec_()

    def handle_download(self, download_item):
        suggested_name = download_item.suggestedFileName()
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(default_dir, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", os.path.join(default_dir, suggested_name))
        if not save_path:
            download_item.cancel()
            return
        download_item.setPath(save_path)
        download_item.accept()
        widget = DownloadItemWidget(download_item)
        self.downloads_window.add_download(widget)

def check_for_update():
    try:
        url_ver = "https://raw.githubusercontent.com/renatus777rr/renbrowser/main/verupdate.txt?nocache=1"
        with urllib.request.urlopen(url_ver, timeout=5) as resp:
            latest_version = resp.read().decode("utf-8").strip()
        if latest_version != VERSION:
            reply = QMessageBox.question(
                None,
                "Update Available",
                f"Do you want to update to new version: {latest_version}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                url_code = "https://raw.githubusercontent.com/renatus777rr/renbrowser/refs/heads/main/renbrowser.py"
                with urllib.request.urlopen(url_code, timeout=10) as resp:
                    new_code = resp.read().decode("utf-8")
                current_file = os.path.realpath(sys.argv[0])
                with open(current_file, "w", encoding="utf-8") as f:
                    f.write(new_code)
                QMessageBox.information(None, "Updated", "RenBrowser has been updated. Restarting now...")
                QApplication.quit()
                os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        print("Update check failed:", e)

def main():
    if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # check for updates on startup
    check_for_update()
    window = Browser()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
