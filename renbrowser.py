import os
import sys
import shutil
import json
import urllib.request
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QDialog, QLabel, QMessageBox,
    QScrollArea, QFrame, QProgressBar, QFileDialog, QRadioButton,
    QButtonGroup
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage

APP_NAME = "renbrowser"
VERSION = "0.100.3"

# Paths
HOME_DIR = os.path.expanduser("~")
PROFILE_DIR = os.path.join(HOME_DIR, f".{APP_NAME}")
CONFIG_PATH = os.path.join(PROFILE_DIR, "settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "search_engine": "google",  # google | duckduckgo | bing | custom
    # Use %s where the query goes
    "custom_template": "https://example.com/search?q=%s"
}

SEARCH_TEMPLATES = {
    "google": "https://www.google.com/search?q=%s",
    "duckduckgo": "https://duckduckgo.com/?q=%s",
    "bing": "https://www.bing.com/search?q=%s"
}

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
    def __init__(self, profile_path, settings, save_settings_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(380, 260)
        self.profile_path = profile_path
        self.settings = settings
        self.save_settings_callback = save_settings_callback

        layout = QVBoxLayout()

        # Version
        self.version_label = QLabel(f"Version: {VERSION}")

        # Search engine group
        layout.addWidget(QLabel("Search engine:"))
        self.engine_group = QButtonGroup(self)
        self.rb_google = QRadioButton("Google")
        self.rb_ddg = QRadioButton("DuckDuckGo")
        self.rb_bing = QRadioButton("Bing")
        self.rb_custom = QRadioButton("Custom")
        for rb in (self.rb_google, self.rb_ddg, self.rb_bing, self.rb_custom):
            self.engine_group.addButton(rb)
            layout.addWidget(rb)

        # Custom template input
        self.custom_label = QLabel("Custom search template (use %s for query):")
        self.custom_edit = QLineEdit()
        self.custom_confirm = QPushButton("Confirm custom engine")
        layout.addWidget(self.custom_label)
        layout.addWidget(self.custom_edit)
        layout.addWidget(self.custom_confirm)

        # Buttons
        self.clear_btn = QPushButton("Clear ALL browser data")
        self.update_btn = QPushButton("Check for Updates")
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.update_btn)
        layout.addStretch()
        layout.addWidget(self.version_label)
        self.setLayout(layout)

        # Restore settings
        self._apply_settings_to_ui()

        # Events
        self.clear_btn.clicked.connect(self.clear_data)
        self.update_btn.clicked.connect(self.check_update)
        self.custom_confirm.clicked.connect(self.confirm_custom)
        self.rb_google.toggled.connect(self._engine_changed)
        self.rb_ddg.toggled.connect(self._engine_changed)
        self.rb_bing.toggled.connect(self._engine_changed)
        self.rb_custom.toggled.connect(self._engine_changed)

        # Show/hide custom controls initially
        self._update_custom_visibility()

    def _apply_settings_to_ui(self):
        engine = self.settings.get("search_engine", DEFAULT_SETTINGS["search_engine"])
        self.custom_edit.setText(self.settings.get("custom_template", DEFAULT_SETTINGS["custom_template"]))
        if engine == "google":
            self.rb_google.setChecked(True)
        elif engine == "duckduckgo":
            self.rb_ddg.setChecked(True)
        elif engine == "bing":
            self.rb_bing.setChecked(True)
        else:
            self.rb_custom.setChecked(True)

    def _engine_changed(self):
        # Update settings based on which radio is selected
        if self.rb_google.isChecked():
            self.settings["search_engine"] = "google"
        elif self.rb_ddg.isChecked():
            self.settings["search_engine"] = "duckduckgo"
        elif self.rb_bing.isChecked():
            self.settings["search_engine"] = "bing"
        elif self.rb_custom.isChecked():
            self.settings["search_engine"] = "custom"
        self.save_settings_callback(self.settings)
        self._update_custom_visibility()

    def _update_custom_visibility(self):
        is_custom = self.rb_custom.isChecked()
        self.custom_label.setVisible(is_custom)
        self.custom_edit.setVisible(is_custom)
        self.custom_confirm.setVisible(is_custom)

    def confirm_custom(self):
        tpl = self.custom_edit.text().strip()
        if "%s" not in tpl:
            QMessageBox.warning(self, "Invalid template", "Template must include %s where the query goes.")
            return
        self.settings["custom_template"] = tpl
        self.settings["search_engine"] = "custom"
        self.save_settings_callback(self.settings)
        QMessageBox.information(self, "Saved", "Custom search engine saved.")

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

class BrowserTab:
    def __init__(self, profile, on_title_change):
        self.page = QWebEnginePage(profile)
        self.view = QWebEngineView()
        self.view.setPage(self.page)
        self.button = QPushButton("New Tab")
        self.button.setCheckable(True)
        self.button.setStyleSheet("QPushButton { background: white; } QPushButton:checked { background: #d0d0d0; }")
        self.page.titleChanged.connect(lambda title: self._update_title(title, on_title_change))

    def _update_title(self, title, on_title_change):
        self.button.setText(title if title else "New Tab")
        if callable(on_title_change):
            on_title_change(self, title)

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        # Profile
        os.makedirs(PROFILE_DIR, exist_ok=True)
        self.profile = QWebEngineProfile(PROFILE_DIR)
        try:
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        except Exception:
            pass
        self.profile.setCachePath(os.path.join(PROFILE_DIR, "cache"))
        self.profile.setPersistentStoragePath(os.path.join(PROFILE_DIR, "storage"))

        # Settings persistence
        self.settings = self._load_settings()

        # UI: Tabs bar
        self.tabs_bar = QHBoxLayout()
        self.tabs_bar.setSpacing(6)
        self.tabs_bar.setContentsMargins(6, 6, 6, 6)

        # New tab button
        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.setFixedWidth(28)
        self.new_tab_btn.clicked.connect(self.add_tab)
        self.tabs_bar.addWidget(self.new_tab_btn)
        self.tabs_bar.addStretch()

        # Top bar (address + controls)
        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Enter URL or search")
        self.address_bar.returnPressed.connect(self.load_address)
        self.back_btn = QPushButton("Back")
        self.refresh_btn = QPushButton("Refresh")
        self.downloads_btn = QPushButton("Downloads")
        self.settings_btn = QPushButton("Settings")
        self.back_btn.clicked.connect(self._go_back)
        self.refresh_btn.clicked.connect(self._reload)
        self.downloads_btn.clicked.connect(self.show_downloads)
        self.settings_btn.clicked.connect(self.show_settings)

        topbar = QHBoxLayout()
        topbar.addWidget(QLabel("URL:"))
        topbar.addWidget(self.address_bar, stretch=3)
        topbar.addWidget(self.back_btn)
        topbar.addWidget(self.refresh_btn)
        topbar.addWidget(self.downloads_btn)
        topbar.addWidget(self.settings_btn)

        # Central layout
        central = QWidget()
        layout = QVBoxLayout()
        # Tabs bar goes ABOVE topbar (as requested)
        layout.addLayout(self.tabs_bar)
        layout.addLayout(topbar)
        # View container
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout()
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_container.setLayout(self.view_layout)
        layout.addWidget(self.view_container, stretch=1)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Downloads window
        self.downloads_window = DownloadsWindow(self)

        # Tabs management
        self.tabs = []
        self.current_tab = None
        self.add_tab()  # Start with one tab
        self.load_url_in_current(QUrl("https://www.google.com"))

        # Signals for downloads from profile
        self.profile.downloadRequested.connect(self.handle_download)

    def _load_settings(self):
        if not os.path.exists(CONFIG_PATH):
            return DEFAULT_SETTINGS.copy()
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge defaults to ensure keys exist
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data or {})
            return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()

    def _save_settings(self, settings):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print("Failed to save settings:", e)

    def add_tab(self):
        tab = BrowserTab(self.profile, on_title_change=self._tab_title_changed)
        tab.button.clicked.connect(lambda checked, t=tab: self.activate_tab(t))
        self.tabs_bar.insertWidget(self.tabs_bar.count() - 1, tab.button)
        self.tabs.append(tab)
        self.activate_tab(tab)

    def activate_tab(self, tab):
        # Uncheck all, check selected
        for t in self.tabs:
            t.button.setChecked(False)
        tab.button.setChecked(True)

        # Swap view
        if self.current_tab is not None:
            # Remove old view from layout
            for i in reversed(range(self.view_layout.count())):
                item = self.view_layout.itemAt(i)
                w = item.widget()
                if w:
                    self.view_layout.removeWidget(w)
                    w.setParent(None)
        self.view_layout.addWidget(tab.view)
        self.current_tab = tab

        # Update address bar with current URL
        url = tab.view.url().toDisplayString()
        self.address_bar.setText(url)

        # Connect URL change to address bar
        tab.view.urlChanged.connect(self.sync_address_bar)
        # Make sure Back/Refresh work on current tab
        self.back_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

    def _tab_title_changed(self, tab, title):
        # No extra actions needed here, button text is already updated
        pass

    def sync_address_bar(self, url: QUrl):
        self.address_bar.setText(url.toDisplayString())

    def _go_back(self):
        if self.current_tab:
            self.current_tab.view.back()

    def _reload(self):
        if self.current_tab:
            self.current_tab.view.reload()

    def show_downloads(self):
        self.downloads_window.show()
        self.downloads_window.raise_()
        self.downloads_window.activateWindow()

    def show_settings(self):
        win = SettingsWindow(PROFILE_DIR, self.settings, self._save_settings, self)
        win.exec_()

    def normalize_url_or_search(self, text: str) -> QUrl:
        t = text.strip()
        if not t:
            return QUrl()
        # If looks like a URL (has scheme or a dot and no spaces), treat as URL.
        if "://" in t or ("." in t and " " not in t):
            return QUrl(t if "://" in t else f"https://{t}")

        # Otherwise, use search engine
        engine = self.settings.get("search_engine", "google")
        if engine in SEARCH_TEMPLATES:
            template = SEARCH_TEMPLATES[engine]
        else:
            template = self.settings.get("custom_template", DEFAULT_SETTINGS["custom_template"])
        return QUrl(template.replace("%s", urllib.parse.quote(t)))

    def load_address(self):
        if not self.current_tab:
            return
        url = self.normalize_url_or_search(self.address_bar.text())
        if url.isValid():
            self.current_tab.view.load(url)

    def load_url_in_current(self, url: QUrl):
        if self.current_tab and url.isValid():
            self.current_tab.view.load(url)

    def handle_download(self, download_item):
        suggested_name = download_item.suggestedFileName()
        default_dir = os.path.join(HOME_DIR, "Downloads")
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
        url_ver = "https://raw.githubusercontent.com/renatus777rr/renbrowser/main/verupdate.txt"
        with urllib.request.urlopen(url_ver, timeout=5) as resp:
            latest_version = resp.read().decode("utf-8").strip()
        current_version = VERSION.strip()
        if latest_version == current_version:
            return
        reply = QMessageBox.question(
            None,
            "Update Available",
            f"Do you want to update to new version: {latest_version}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            url_code = "https://raw.githubusercontent.com/renatus777rr/renbrowser/main/renbrowser.py"
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
    # Wayland compatibility
    if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    # Ensure profile directory exists
    os.makedirs(PROFILE_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Check for updates on startup
    check_for_update()

    window = Browser()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    # urllib.parse for query encoding
    import urllib.parse
    main()
