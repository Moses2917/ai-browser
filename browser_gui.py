#!/usr/bin/env python3
"""
AI Browser - Real browser with GUI using QtWebEngine
Full-featured browser with AI integration, tabs, bookmarks, and more
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
    from PyQt5.QtGui import *
    from PyQt5.QtWebEngineWidgets import *
    from PyQt5.QtWebEngineCore import *
except ImportError:
    print("Missing PyQt5. Install with:")
    print("pip install PyQt5 PyQtWebEngine")
    sys.exit(1)

# Import our AI components
try:
    import openai
    has_openai = True
except ImportError:
    has_openai = False

# Configuration
DATA_DIR = Path.home() / ".ai_browser"
DATA_DIR.mkdir(exist_ok=True)
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


class AIAssistant:
    """AI Assistant for browser - supports LM Studio"""

    def __init__(self):
        self.enabled = False
        self.base_url = "http://localhost:1234/v1"
        self.client = None

        if has_openai:
            try:
                self.client = openai.OpenAI(
                    base_url=self.base_url,
                    api_key="lm-studio"
                )
                # Test connection
                self.client.models.list()
                self.enabled = True
            except:
                self.enabled = False

    def ask(self, question: str, context: str = "") -> str:
        """Ask AI a question"""
        if not self.enabled or not self.client:
            return "AI not available. Start LM Studio first."

        try:
            messages = [
                {"role": "system", "content": "You are a helpful browser assistant. Be concise."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
            ]

            response = self.client.chat.completions.create(
                model="local-model",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )

            return response.choices[0].message.content
        except Exception as e:
            return f"AI Error: {str(e)}"


class BookmarkManager:
    """Manage bookmarks"""

    def __init__(self):
        self.bookmarks = []
        self.load()

    def load(self):
        """Load bookmarks"""
        if BOOKMARKS_FILE.exists():
            with open(BOOKMARKS_FILE, 'r') as f:
                self.bookmarks = json.load(f)

    def save(self):
        """Save bookmarks"""
        with open(BOOKMARKS_FILE, 'w') as f:
            json.dump(self.bookmarks, f, indent=2)

    def add(self, title: str, url: str):
        """Add bookmark"""
        self.bookmarks.append({
            "title": title,
            "url": url,
            "created": datetime.now().isoformat()
        })
        self.save()

    def remove(self, url: str):
        """Remove bookmark"""
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        self.save()

    def is_bookmarked(self, url: str) -> bool:
        """Check if URL is bookmarked"""
        return any(b["url"] == url for b in self.bookmarks)


class HistoryManager:
    """Manage browsing history"""

    def __init__(self):
        self.history = []
        self.load()

    def load(self):
        """Load history"""
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r') as f:
                self.history = json.load(f)

    def save(self):
        """Save history"""
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history[-1000:], f, indent=2)  # Keep last 1000

    def add(self, title: str, url: str):
        """Add to history"""
        if not url or url.startswith('about:'):
            return

        self.history.append({
            "title": title,
            "url": url,
            "timestamp": datetime.now().isoformat()
        })
        self.save()


class BrowserTab(QWidget):
    """A single browser tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.google.com"))

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        self.setLayout(layout)

        # Connect signals
        self.browser.loadFinished.connect(self.on_load_finished)
        self.browser.urlChanged.connect(self.on_url_changed)

    def on_load_finished(self, success):
        """Called when page finishes loading"""
        if success:
            # Notify parent (main window)
            parent = self.parent()
            while parent and not isinstance(parent, MainWindow):
                parent = parent.parent()
            if parent:
                parent.on_page_loaded()

    def on_url_changed(self, url):
        """Called when URL changes"""
        parent = self.parent()
        while parent and not isinstance(parent, MainWindow):
            parent = parent.parent()
        if parent:
            parent.update_url_bar()

    def get_url(self) -> str:
        """Get current URL"""
        return self.browser.url().toString()

    def get_title(self) -> str:
        """Get current title"""
        return self.browser.title()

    def navigate(self, url: str):
        """Navigate to URL"""
        if not url.startswith(('http://', 'https://', 'file://', 'about:')):
            if ' ' in url or '.' not in url:
                # It's a search query
                url = f"https://www.google.com/search?q={url}"
            else:
                url = f"https://{url}"

        self.browser.setUrl(QUrl(url))

    def go_back(self):
        """Go back"""
        self.browser.back()

    def go_forward(self):
        """Go forward"""
        self.browser.forward()

    def reload(self):
        """Reload page"""
        self.browser.reload()

    def stop(self):
        """Stop loading"""
        self.browser.stop()


class AIPanel(QWidget):
    """AI Assistant side panel"""

    def __init__(self, ai_assistant: AIAssistant, parent=None):
        super().__init__(parent)
        self.ai = ai_assistant

        layout = QVBoxLayout()

        # Title
        title = QLabel("AI Assistant")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        # Input
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask AI about this page...")
        self.input_field.returnPressed.connect(self.send_message)

        send_btn = QPushButton("Ask")
        send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)

        self.setLayout(layout)
        self.setMaximumWidth(350)

        # Status
        if self.ai.enabled:
            self.add_message("System", "AI ready! (LM Studio connected)")
        else:
            self.add_message("System", "AI not available. Start LM Studio on port 1234.")

    def add_message(self, sender: str, message: str):
        """Add message to chat"""
        self.chat_display.append(f"<b>{sender}:</b> {message}<br>")

    def send_message(self):
        """Send message to AI"""
        question = self.input_field.text().strip()
        if not question:
            return

        self.add_message("You", question)
        self.input_field.clear()

        # Get page context
        main_window = self.get_main_window()
        if main_window:
            current_tab = main_window.get_current_tab()
            if current_tab:
                url = current_tab.get_url()
                title = current_tab.get_title()
                context = f"Page: {title}\nURL: {url}"

                # Ask AI
                response = self.ai.ask(question, context)
                self.add_message("AI", response)
            else:
                self.add_message("System", "No active tab")
        else:
            self.add_message("System", "Error getting context")

    def get_main_window(self):
        """Get main window"""
        parent = self.parent()
        while parent and not isinstance(parent, MainWindow):
            parent = parent.parent()
        return parent


class MainWindow(QMainWindow):
    """Main browser window"""

    def __init__(self):
        super().__init__()

        self.bookmarks = BookmarkManager()
        self.history = HistoryManager()
        self.ai = AIAssistant()

        self.setWindowTitle("AI Browser")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout (horizontal: browser | AI panel)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Browser area (vertical: navbar | tabs)
        browser_area = QWidget()
        browser_layout = QVBoxLayout()
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        # Navigation bar
        navbar = self.create_navbar()
        browser_layout.addWidget(navbar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        browser_layout.addWidget(self.tabs)

        # Add first tab
        self.add_new_tab()

        browser_area.setLayout(browser_layout)
        main_layout.addWidget(browser_area)

        # AI Panel (collapsible)
        self.ai_panel = AIPanel(self.ai)
        self.ai_panel.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.ai_panel)

        central.setLayout(main_layout)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status.showMessage("Ready")

    def create_navbar(self) -> QWidget:
        """Create navigation bar"""
        navbar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Back button
        back_btn = QPushButton("◀")
        back_btn.clicked.connect(self.navigate_back)
        back_btn.setMaximumWidth(40)
        layout.addWidget(back_btn)

        # Forward button
        forward_btn = QPushButton("▶")
        forward_btn.clicked.connect(self.navigate_forward)
        forward_btn.setMaximumWidth(40)
        layout.addWidget(forward_btn)

        # Reload button
        reload_btn = QPushButton("⟳")
        reload_btn.clicked.connect(self.reload_page)
        reload_btn.setMaximumWidth(40)
        layout.addWidget(reload_btn)

        # Home button
        home_btn = QPushButton("⌂")
        home_btn.clicked.connect(self.navigate_home)
        home_btn.setMaximumWidth(40)
        layout.addWidget(home_btn)

        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        layout.addWidget(self.url_bar)

        # Bookmark button
        self.bookmark_btn = QPushButton("☆")
        self.bookmark_btn.clicked.connect(self.toggle_bookmark)
        self.bookmark_btn.setMaximumWidth(40)
        layout.addWidget(self.bookmark_btn)

        # AI button
        ai_btn = QPushButton("🤖 AI")
        ai_btn.clicked.connect(self.toggle_ai_panel)
        ai_btn.setMaximumWidth(60)
        layout.addWidget(ai_btn)

        # New tab button
        new_tab_btn = QPushButton("+")
        new_tab_btn.clicked.connect(self.add_new_tab)
        new_tab_btn.setMaximumWidth(40)
        layout.addWidget(new_tab_btn)

        # Menu button
        menu_btn = QPushButton("☰")
        menu_btn.clicked.connect(self.show_menu)
        menu_btn.setMaximumWidth(40)
        layout.addWidget(menu_btn)

        navbar.setLayout(layout)
        return navbar

    def add_new_tab(self, url: str = ""):
        """Add a new tab"""
        tab = BrowserTab()

        if url:
            tab.navigate(url)

        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)

        return tab

    def close_tab(self, index: int):
        """Close a tab"""
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            # Don't close last tab, just navigate home
            self.navigate_home()

    def on_tab_changed(self, index: int):
        """Called when tab changes"""
        if index >= 0:
            self.update_url_bar()
            self.update_bookmark_button()

    def get_current_tab(self) -> Optional[BrowserTab]:
        """Get current tab"""
        return self.tabs.currentWidget()

    def navigate_to_url(self):
        """Navigate to URL from address bar"""
        url = self.url_bar.text()
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)

    def navigate_back(self):
        """Go back"""
        tab = self.get_current_tab()
        if tab:
            tab.go_back()

    def navigate_forward(self):
        """Go forward"""
        tab = self.get_current_tab()
        if tab:
            tab.go_forward()

    def reload_page(self):
        """Reload page"""
        tab = self.get_current_tab()
        if tab:
            tab.reload()

    def navigate_home(self):
        """Go to home page"""
        tab = self.get_current_tab()
        if tab:
            tab.navigate("https://www.google.com")

    def update_url_bar(self):
        """Update URL bar with current URL"""
        tab = self.get_current_tab()
        if tab:
            url = tab.get_url()
            self.url_bar.setText(url)
            self.update_bookmark_button()

    def update_bookmark_button(self):
        """Update bookmark button state"""
        tab = self.get_current_tab()
        if tab:
            url = tab.get_url()
            if self.bookmarks.is_bookmarked(url):
                self.bookmark_btn.setText("★")
            else:
                self.bookmark_btn.setText("☆")

    def toggle_bookmark(self):
        """Toggle bookmark for current page"""
        tab = self.get_current_tab()
        if tab:
            url = tab.get_url()
            title = tab.get_title()

            if self.bookmarks.is_bookmarked(url):
                self.bookmarks.remove(url)
                self.status.showMessage(f"Removed bookmark: {title}", 3000)
            else:
                self.bookmarks.add(title, url)
                self.status.showMessage(f"Bookmarked: {title}", 3000)

            self.update_bookmark_button()

    def toggle_ai_panel(self):
        """Toggle AI panel visibility"""
        self.ai_panel.setVisible(not self.ai_panel.isVisible())

    def on_page_loaded(self):
        """Called when page loads"""
        tab = self.get_current_tab()
        if tab:
            # Update tab title
            title = tab.get_title()
            index = self.tabs.currentIndex()
            self.tabs.setTabText(index, title[:30] if len(title) > 30 else title)

            # Add to history
            self.history.add(title, tab.get_url())

            # Update UI
            self.update_url_bar()
            self.status.showMessage(f"Loaded: {title}", 3000)

    def show_menu(self):
        """Show menu"""
        menu = QMenu(self)

        # Bookmarks
        bookmarks_menu = menu.addMenu("Bookmarks")
        for bookmark in self.bookmarks.bookmarks:
            action = bookmarks_menu.addAction(bookmark["title"])
            action.triggered.connect(lambda checked, url=bookmark["url"]: self.navigate_to_bookmark(url))

        if not self.bookmarks.bookmarks:
            bookmarks_menu.addAction("No bookmarks").setEnabled(False)

        menu.addSeparator()

        # History
        history_action = menu.addAction("History")
        history_action.triggered.connect(self.show_history)

        # Downloads
        downloads_action = menu.addAction("Downloads")
        downloads_action.setEnabled(False)  # TODO

        menu.addSeparator()

        # Settings
        settings_action = menu.addAction("Settings")
        settings_action.setEnabled(False)  # TODO

        # About
        about_action = menu.addAction("About")
        about_action.triggered.connect(self.show_about)

        menu.addSeparator()

        # Quit
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        # Show menu at button position
        menu.exec_(QCursor.pos())

    def navigate_to_bookmark(self, url: str):
        """Navigate to bookmark"""
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)

    def show_history(self):
        """Show history dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("History")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()

        # History list
        history_list = QListWidget()
        for item in reversed(self.history.history[-100:]):  # Last 100
            timestamp = datetime.fromisoformat(item["timestamp"]).strftime("%Y-%m-%d %H:%M")
            list_item = QListWidgetItem(f"{timestamp} - {item['title']}")
            list_item.setData(Qt.UserRole, item["url"])
            history_list.addItem(list_item)

        history_list.itemDoubleClicked.connect(lambda item: self.navigate_to_history_item(item, dialog))
        layout.addWidget(history_list)

        # Buttons
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(lambda: self.clear_history(dialog))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)

        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def navigate_to_history_item(self, item, dialog):
        """Navigate to history item"""
        url = item.data(Qt.UserRole)
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)
        dialog.close()

    def clear_history(self, dialog):
        """Clear history"""
        reply = QMessageBox.question(self, "Clear History",
                                     "Are you sure you want to clear all history?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history.history = []
            self.history.save()
            dialog.close()
            self.status.showMessage("History cleared", 3000)

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About AI Browser",
                         "AI Browser v1.0\n\n"
                         "A modern browser with AI integration.\n\n"
                         "Features:\n"
                         "• Multiple tabs\n"
                         "• Bookmarks & History\n"
                         "• AI Assistant (LM Studio)\n"
                         "• Fast & Lightweight\n\n"
                         "Built with PyQt5 and QtWebEngine")


def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI Browser")

    # Set style
    app.setStyle("Fusion")

    # Create and show window
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
