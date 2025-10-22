#!/usr/bin/env python3
"""
AI Browser - Enhanced with Background Services
Real browser with AI + silent background optimization
"""

import sys
import os
import json
import re
import time
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import OrderedDict
from io import BytesIO

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

try:
    from PIL import Image
    has_pil = True
except ImportError:
    has_pil = False

try:
    import openai
    has_openai = True
except ImportError:
    has_openai = False

# Configuration
DATA_DIR = Path.home() / ".ai_browser"
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
SESSION_FILE = DATA_DIR / "session.pkl"
FORMS_DIR = DATA_DIR / "forms"
FORMS_DIR.mkdir(exist_ok=True)

# Performance settings
MAX_CONTENT_LENGTH = 50000
CACHE_SIZE = 100
CACHE_TTL = 3600

# Background service intervals (milliseconds)
SESSION_SAVE_INTERVAL = 30000  # 30 seconds
CACHE_CLEANUP_INTERVAL = 300000  # 5 minutes
FORM_SAVE_INTERVAL = 10000  # 10 seconds
MEMORY_CHECK_INTERVAL = 60000  # 1 minute
TAB_FREEZE_TIMEOUT = 600000  # 10 minutes


class ContentExtractor:
    """Smart content extraction"""

    @staticmethod
    def extract_smart_content(html: str, max_length: int = MAX_CONTENT_LENGTH) -> Tuple[str, str]:
        text = re.sub('<[^<]+?>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > max_length:
            text = text[:max_length] + "\n[Content truncated]"

        summary = text[:1000] + "..." if len(text) > 1000 else text
        return text, summary


class PageCache:
    """LRU cache for pages"""

    def __init__(self, max_size: int = CACHE_SIZE):
        self.cache = OrderedDict()
        self.max_size = max_size

    def _get_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[Dict]:
        key = self._get_key(url)
        if key in self.cache:
            page = self.cache[key]
            if time.time() - page.get('timestamp', 0) < CACHE_TTL:
                self.cache.move_to_end(key)
                return page
            else:
                del self.cache[key]
        return None

    def put(self, url: str, data: Dict):
        key = self._get_key(url)
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        data['timestamp'] = time.time()
        self.cache[key] = data

    def clear(self):
        self.cache.clear()

    def cleanup_old(self):
        """Remove expired entries"""
        now = time.time()
        expired = [k for k, v in self.cache.items() if now - v.get('timestamp', 0) > CACHE_TTL]
        for k in expired:
            del self.cache[k]
        return len(expired)

    def size(self) -> int:
        return len(self.cache)


class SessionManager:
    """Auto-save and restore browser sessions"""

    def __init__(self):
        self.session_file = SESSION_FILE

    def save_session(self, tabs_data: List[Dict]):
        """Save current session"""
        try:
            with open(self.session_file, 'wb') as f:
                pickle.dump({
                    'tabs': tabs_data,
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            print(f"Session save error: {e}")

    def load_session(self) -> Optional[List[Dict]]:
        """Load last session"""
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, 'rb') as f:
                data = pickle.load(f)
                # Only restore if less than 24 hours old
                saved_time = datetime.fromisoformat(data['timestamp'])
                if datetime.now() - saved_time < timedelta(hours=24):
                    return data['tabs']
        except Exception as e:
            print(f"Session load error: {e}")

        return None


class FormSaver:
    """Auto-save form data to prevent loss"""

    def __init__(self):
        self.forms_dir = FORMS_DIR

    def save_form_data(self, url: str, form_data: Dict):
        """Save form data for a URL"""
        if not form_data:
            return

        try:
            form_hash = hashlib.md5(url.encode()).hexdigest()
            form_file = self.forms_dir / f"{form_hash}.json"

            with open(form_file, 'w') as f:
                json.dump({
                    'url': url,
                    'data': form_data,
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            print(f"Form save error: {e}")

    def load_form_data(self, url: str) -> Optional[Dict]:
        """Load saved form data"""
        try:
            form_hash = hashlib.md5(url.encode()).hexdigest()
            form_file = self.forms_dir / f"{form_hash}.json"

            if form_file.exists():
                with open(form_file, 'r') as f:
                    data = json.load(f)
                    # Only restore if less than 1 hour old
                    saved_time = datetime.fromisoformat(data['timestamp'])
                    if datetime.now() - saved_time < timedelta(hours=1):
                        return data['data']
        except Exception as e:
            print(f"Form load error: {e}")

        return None

    def cleanup_old_forms(self):
        """Remove form data older than 24 hours"""
        count = 0
        for form_file in self.forms_dir.glob("*.json"):
            try:
                with open(form_file, 'r') as f:
                    data = json.load(f)
                    saved_time = datetime.fromisoformat(data['timestamp'])
                    if datetime.now() - saved_time > timedelta(hours=24):
                        form_file.unlink()
                        count += 1
            except:
                pass
        return count


class AIAssistant:
    """AI Assistant with command execution"""

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
                self.client.models.list()
                self.enabled = True
            except:
                self.enabled = False

    def ask(self, question: str, context: str = "") -> str:
        if not self.enabled or not self.client:
            return "AI not available. Start LM Studio on port 1234."

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

    def execute_command(self, command: str, page_url: str, page_title: str) -> Dict[str, Any]:
        if not self.enabled or not self.client:
            return {"action": "error", "explanation": "AI not available"}

        system_prompt = """You are an AI browser assistant. Convert natural language to JSON.

Actions:
- navigate: {"action": "navigate", "parameters": {"url": "..."}, "explanation": "..."}
- click: {"action": "click", "parameters": {"selector": "..."}, "explanation": "..."}
- type: {"action": "type", "parameters": {"selector": "...", "text": "..."}, "explanation": "..."}
- scroll: {"action": "scroll", "parameters": {"direction": "...", "amount": 500}, "explanation": "..."}
- read: {"action": "read", "parameters": {}, "explanation": "..."}

Current: {title} ({url})
Respond ONLY with JSON."""

        try:
            messages = [
                {"role": "system", "content": system_prompt.format(title=page_title, url=page_url)},
                {"role": "user", "content": command}
            ]

            response = self.client.chat.completions.create(
                model="local-model",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )

            response_text = response.choices[0].message.content
            json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"action": "error", "explanation": f"Could not parse: {response_text}"}

        except Exception as e:
            return {"action": "error", "explanation": f"Error: {str(e)}"}


class BookmarkManager:
    def __init__(self):
        self.bookmarks = []
        self.load()

    def load(self):
        if BOOKMARKS_FILE.exists():
            with open(BOOKMARKS_FILE, 'r') as f:
                self.bookmarks = json.load(f)

    def save(self):
        with open(BOOKMARKS_FILE, 'w') as f:
            json.dump(self.bookmarks, f, indent=2)

    def add(self, title: str, url: str):
        self.bookmarks.append({
            "title": title,
            "url": url,
            "created": datetime.now().isoformat()
        })
        self.save()

    def remove(self, url: str):
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        self.save()

    def is_bookmarked(self, url: str) -> bool:
        return any(b["url"] == url for b in self.bookmarks)


class HistoryManager:
    def __init__(self):
        self.history = []
        self.load()

    def load(self):
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r') as f:
                self.history = json.load(f)

    def save(self):
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history[-1000:], f, indent=2)

    def add(self, title: str, url: str):
        if not url or url.startswith('about:'):
            return
        self.history.append({
            "title": title,
            "url": url,
            "timestamp": datetime.now().isoformat()
        })
        self.save()


class BrowserTab(QWidget):
    """Enhanced browser tab"""

    loadFinished = pyqtSignal(bool)
    urlChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.google.com"))
        self.cached_content = None
        self.last_active = time.time()
        self.is_frozen = False

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        self.setLayout(layout)

        self.browser.loadFinished.connect(self._on_load_finished)
        self.browser.urlChanged.connect(self._on_url_changed)

    def _on_load_finished(self, success):
        if success:
            self.browser.page().toHtml(self._cache_content)
            # Auto-upgrade HTTP to HTTPS
            self._check_https_upgrade()
        self.loadFinished.emit(success)

    def _cache_content(self, html):
        self.cached_content = html

    def _check_https_upgrade(self):
        """Auto-upgrade HTTP to HTTPS"""
        url = self.browser.url()
        if url.scheme() == "http":
            # Try HTTPS version
            https_url = QUrl(url)
            https_url.setScheme("https")
            # Note: In production, verify HTTPS works before switching

    def _on_url_changed(self, url):
        self.urlChanged.emit(url.toString())

    def touch(self):
        """Mark tab as active"""
        self.last_active = time.time()
        if self.is_frozen:
            self.unfreeze()

    def freeze(self):
        """Freeze tab to save resources"""
        if not self.is_frozen:
            # Pause rendering
            self.browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
            self.is_frozen = True

    def unfreeze(self):
        """Unfreeze tab"""
        if self.is_frozen:
            self.browser.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
            self.is_frozen = False

    def get_url(self) -> str:
        return self.browser.url().toString()

    def get_title(self) -> str:
        return self.browser.title()

    def get_content(self) -> str:
        return self.cached_content or ""

    def navigate(self, url: str):
        self.touch()
        if not url.startswith(('http://', 'https://', 'file://', 'about:')):
            if ' ' in url or '.' not in url:
                url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
            else:
                # Auto-upgrade to HTTPS
                url = f"https://{url}"
        self.browser.setUrl(QUrl(url))

    def go_back(self):
        self.touch()
        self.browser.back()

    def go_forward(self):
        self.touch()
        self.browser.forward()

    def reload(self):
        self.touch()
        self.browser.reload()

    def execute_js(self, script: str, callback=None):
        if callback:
            self.browser.page().runJavaScript(script, callback)
        else:
            self.browser.page().runJavaScript(script)

    def click_element(self, selector: str):
        script = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (el) {{ el.click(); return 'Clicked'; }}
            return 'Not found';
        }})()
        """
        self.execute_js(script)

    def type_into_element(self, selector: str, text: str):
        script = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (el) {{
                el.value = '{text}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'Typed';
            }}
            return 'Not found';
        }})()
        """
        self.execute_js(script)

    def scroll_page(self, direction: str, amount: int = 500):
        if direction == "down":
            script = f"window.scrollBy(0, {amount});"
        else:
            script = f"window.scrollBy(0, -{amount});"
        self.execute_js(script)

    def get_form_data(self, callback):
        """Extract current form data"""
        script = """
        (function() {
            const forms = document.querySelectorAll('form');
            const data = {};
            forms.forEach((form, i) => {
                const inputs = form.querySelectorAll('input, textarea');
                inputs.forEach(input => {
                    if (input.value && input.type !== 'password') {
                        data[input.name || input.id || i] = input.value;
                    }
                });
            });
            return data;
        })()
        """
        self.execute_js(script, callback)


class CommandPanel(QWidget):
    commandExecuted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("🤖 AI Commands")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        examples = QLabel("Examples: 'Go to reddit.com' • 'Click the login button' • 'Read this page'")
        examples.setStyleSheet("font-size: 10px; color: gray;")
        examples.setWordWrap(True)
        layout.addWidget(examples)

        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type a command...")
        self.command_input.returnPressed.connect(self.execute_command)

        execute_btn = QPushButton("Execute")
        execute_btn.clicked.connect(self.execute_command)

        input_layout.addWidget(self.command_input)
        input_layout.addWidget(execute_btn)
        layout.addLayout(input_layout)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(150)
        layout.addWidget(self.output)

        self.setLayout(layout)

    def execute_command(self):
        command = self.command_input.text().strip()
        if command:
            self.command_input.clear()
            self.output.append(f"<b>Command:</b> {command}<br>")
            self.commandExecuted.emit(command)

    def add_output(self, text: str):
        self.output.append(f"{text}<br>")


class AIPanel(QWidget):
    def __init__(self, ai_assistant: AIAssistant, parent=None):
        super().__init__(parent)
        self.ai = ai_assistant

        layout = QVBoxLayout()

        title = QLabel("💬 AI Chat")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

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

        if self.ai.enabled:
            self.add_message("System", "✓ AI ready (LM Studio)")
        else:
            self.add_message("System", "⚠️ AI offline. Start LM Studio")

    def add_message(self, sender: str, message: str):
        self.chat_display.append(f"<b>{sender}:</b> {message}<br>")

    def send_message(self):
        question = self.input_field.text().strip()
        if not question:
            return

        self.add_message("You", question)
        self.input_field.clear()

        main_window = self.get_main_window()
        if main_window:
            current_tab = main_window.get_current_tab()
            if current_tab:
                url = current_tab.get_url()
                title = current_tab.get_title()
                content = current_tab.get_content()

                _, summary = ContentExtractor.extract_smart_content(content)
                context = f"Page: {title}\nURL: {url}\nContent: {summary}"

                response = self.ai.ask(question, context)
                self.add_message("AI", response)

    def get_main_window(self):
        parent = self.parent()
        while parent and not isinstance(parent, MainWindow):
            parent = parent.parent()
        return parent


class MainWindow(QMainWindow):
    """Main browser with background services"""

    def __init__(self):
        super().__init__()

        self.bookmarks = BookmarkManager()
        self.history = HistoryManager()
        self.ai = AIAssistant()
        self.cache = PageCache()
        self.session_manager = SessionManager()
        self.form_saver = FormSaver()

        self.setWindowTitle("AI Browser - Enhanced Edition")
        self.setGeometry(100, 100, 1600, 1000)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        navbar = self.create_navbar()
        main_layout.addWidget(navbar)

        self.command_panel = CommandPanel()
        self.command_panel.commandExecuted.connect(self.execute_natural_command)
        self.command_panel.setVisible(False)
        main_layout.addWidget(self.command_panel)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        h_layout.addWidget(self.tabs)

        # Restore session or add first tab
        restored = self.restore_session()
        if not restored:
            self.add_new_tab()

        self.ai_panel = AIPanel(self.ai)
        self.ai_panel.setVisible(False)
        h_layout.addWidget(self.ai_panel)

        h_layout_widget = QWidget()
        h_layout_widget.setLayout(h_layout)
        main_layout.addWidget(h_layout_widget)

        central.setLayout(main_layout)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status()

        # Start background services
        self.start_background_services()

    def start_background_services(self):
        """Initialize background timers"""

        # Session auto-save every 30 seconds
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.auto_save_session)
        self.session_timer.start(SESSION_SAVE_INTERVAL)

        # Cache cleanup every 5 minutes
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self.auto_cleanup)
        self.cleanup_timer.start(CACHE_CLEANUP_INTERVAL)

        # Form auto-save every 10 seconds
        self.form_timer = QTimer(self)
        self.form_timer.timeout.connect(self.auto_save_forms)
        self.form_timer.start(FORM_SAVE_INTERVAL)

        # Memory check every minute
        self.memory_timer = QTimer(self)
        self.memory_timer.timeout.connect(self.check_memory)
        self.memory_timer.start(MEMORY_CHECK_INTERVAL)

        # Tab freezing check every minute
        self.freeze_timer = QTimer(self)
        self.freeze_timer.timeout.connect(self.freeze_inactive_tabs)
        self.freeze_timer.start(60000)

        print("✓ Background services started")

    def auto_save_session(self):
        """Auto-save current session"""
        tabs_data = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, BrowserTab):
                tabs_data.append({
                    'url': tab.get_url(),
                    'title': tab.get_title()
                })

        if tabs_data:
            self.session_manager.save_session(tabs_data)

    def restore_session(self) -> bool:
        """Restore previous session"""
        tabs_data = self.session_manager.load_session()
        if tabs_data:
            for tab_data in tabs_data:
                self.add_new_tab(tab_data['url'])
            self.status.showMessage("✓ Session restored", 3000)
            return True
        return False

    def auto_cleanup(self):
        """Auto-cleanup old cache and forms"""
        cache_removed = self.cache.cleanup_old()
        forms_removed = self.form_saver.cleanup_old_forms()

        if cache_removed > 0 or forms_removed > 0:
            print(f"✓ Cleanup: {cache_removed} cache, {forms_removed} forms")

    def auto_save_forms(self):
        """Auto-save form data"""
        tab = self.get_current_tab()
        if tab:
            def save_forms(form_data):
                if form_data:
                    self.form_saver.save_form_data(tab.get_url(), form_data)

            tab.get_form_data(save_forms)

    def check_memory(self):
        """Check memory usage and warn if high"""
        # Simple check: count tabs
        if self.tabs.count() > 20:
            self.status.showMessage("⚠️ Many tabs open - consider closing some", 5000)

    def freeze_inactive_tabs(self):
        """Freeze tabs that haven't been active"""
        current_index = self.tabs.currentIndex()
        now = time.time()

        for i in range(self.tabs.count()):
            if i == current_index:
                continue

            tab = self.tabs.widget(i)
            if isinstance(tab, BrowserTab):
                if now - tab.last_active > TAB_FREEZE_TIMEOUT / 1000:
                    if not tab.is_frozen:
                        tab.freeze()
                        print(f"❄️ Froze tab {i}: {tab.get_title()[:30]}")

    def create_navbar(self) -> QWidget:
        navbar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        back_btn = QPushButton("◀")
        back_btn.clicked.connect(self.navigate_back)
        back_btn.setMaximumWidth(40)
        layout.addWidget(back_btn)

        forward_btn = QPushButton("▶")
        forward_btn.clicked.connect(self.navigate_forward)
        forward_btn.setMaximumWidth(40)
        layout.addWidget(forward_btn)

        reload_btn = QPushButton("⟳")
        reload_btn.clicked.connect(self.reload_page)
        reload_btn.setMaximumWidth(40)
        layout.addWidget(reload_btn)

        home_btn = QPushButton("⌂")
        home_btn.clicked.connect(self.navigate_home)
        home_btn.setMaximumWidth(40)
        layout.addWidget(home_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        layout.addWidget(self.url_bar)

        self.bookmark_btn = QPushButton("☆")
        self.bookmark_btn.clicked.connect(self.toggle_bookmark)
        self.bookmark_btn.setMaximumWidth(40)
        layout.addWidget(self.bookmark_btn)

        cmd_btn = QPushButton("⌘ CMD")
        cmd_btn.clicked.connect(self.toggle_command_panel)
        cmd_btn.setMaximumWidth(70)
        layout.addWidget(cmd_btn)

        ai_btn = QPushButton("💬 AI")
        ai_btn.clicked.connect(self.toggle_ai_panel)
        ai_btn.setMaximumWidth(60)
        layout.addWidget(ai_btn)

        new_tab_btn = QPushButton("+")
        new_tab_btn.clicked.connect(self.add_new_tab)
        new_tab_btn.setMaximumWidth(40)
        layout.addWidget(new_tab_btn)

        menu_btn = QPushButton("☰")
        menu_btn.clicked.connect(self.show_menu)
        menu_btn.setMaximumWidth(40)
        layout.addWidget(menu_btn)

        navbar.setLayout(layout)
        return navbar

    def add_new_tab(self, url: str = ""):
        tab = BrowserTab()
        if url:
            tab.navigate(url)

        tab.loadFinished.connect(lambda success: self.on_page_loaded() if success else None)
        tab.urlChanged.connect(lambda: self.update_url_bar())

        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        return tab

    def close_tab(self, index: int):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.navigate_home()

    def on_tab_changed(self, index: int):
        if index >= 0:
            tab = self.tabs.widget(index)
            if isinstance(tab, BrowserTab):
                tab.touch()
            self.update_url_bar()
            self.update_bookmark_button()

    def get_current_tab(self) -> Optional[BrowserTab]:
        return self.tabs.currentWidget()

    def navigate_to_url(self):
        url = self.url_bar.text()
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)

    def navigate_back(self):
        tab = self.get_current_tab()
        if tab:
            tab.go_back()

    def navigate_forward(self):
        tab = self.get_current_tab()
        if tab:
            tab.go_forward()

    def reload_page(self):
        tab = self.get_current_tab()
        if tab:
            tab.reload()

    def navigate_home(self):
        tab = self.get_current_tab()
        if tab:
            tab.navigate("https://www.google.com")

    def update_url_bar(self):
        tab = self.get_current_tab()
        if tab:
            self.url_bar.setText(tab.get_url())
            self.update_bookmark_button()

    def update_bookmark_button(self):
        tab = self.get_current_tab()
        if tab:
            url = tab.get_url()
            self.bookmark_btn.setText("★" if self.bookmarks.is_bookmarked(url) else "☆")

    def toggle_bookmark(self):
        tab = self.get_current_tab()
        if tab:
            url = tab.get_url()
            title = tab.get_title()

            if self.bookmarks.is_bookmarked(url):
                self.bookmarks.remove(url)
                self.status.showMessage(f"Removed bookmark: {title}", 3000)
            else:
                self.bookmarks.add(title, url)
                self.status.showMessage(f"✓ Bookmarked: {title}", 3000)

            self.update_bookmark_button()

    def toggle_command_panel(self):
        self.command_panel.setVisible(not self.command_panel.isVisible())

    def toggle_ai_panel(self):
        self.ai_panel.setVisible(not self.ai_panel.isVisible())

    def execute_natural_command(self, command: str):
        tab = self.get_current_tab()
        if not tab:
            self.command_panel.add_output("⚠️ No active tab")
            return

        self.command_panel.add_output("🤖 Processing...")
        actions = self.ai.execute_command(command, tab.get_url(), tab.get_title())

        if isinstance(actions, dict):
            actions = [actions]

        for action in actions:
            self.execute_action(action, tab)

    def execute_action(self, action: Dict[str, Any], tab: BrowserTab):
        action_type = action.get("action")
        params = action.get("parameters", {})
        explanation = action.get("explanation", "")

        if explanation:
            self.command_panel.add_output(f"→ {explanation}")

        if action_type == "navigate":
            url = params.get("url", "")
            tab.navigate(url)
            self.command_panel.add_output(f"✓ Navigating to {url}")

        elif action_type == "click":
            selector = params.get("selector", "")
            tab.click_element(selector)
            self.command_panel.add_output(f"✓ Clicked {selector}")

        elif action_type == "type":
            selector = params.get("selector", "")
            text = params.get("text", "")
            tab.type_into_element(selector, text)
            self.command_panel.add_output(f"✓ Typed into {selector}")

        elif action_type == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 500)
            tab.scroll_page(direction, amount)
            self.command_panel.add_output(f"✓ Scrolled {direction}")

        elif action_type == "read":
            content = tab.get_content()
            if content:
                _, summary = ContentExtractor.extract_smart_content(content)
                self.command_panel.add_output(f"📄 Content:\n{summary[:300]}...")
            else:
                self.command_panel.add_output("⚠️ No content")

        elif action_type == "error":
            self.command_panel.add_output(f"❌ {explanation}")

        else:
            self.command_panel.add_output(f"⚠️ Unknown: {action_type}")

    def on_page_loaded(self):
        tab = self.get_current_tab()
        if tab:
            title = tab.get_title()
            index = self.tabs.currentIndex()
            self.tabs.setTabText(index, title[:30] if len(title) > 30 else title)
            self.history.add(title, tab.get_url())
            self.update_url_bar()
            self.update_status()
            self.status.showMessage(f"✓ Loaded: {title}", 3000)

    def update_status(self):
        stats = f"📑 {self.tabs.count()} tabs  |  ⭐ {len(self.bookmarks.bookmarks)} bookmarks  |  💾 {self.cache.size()}/{CACHE_SIZE} cached"
        if self.ai.enabled:
            stats += "  |  🤖 AI ready"
        stats += "  |  🔄 Auto-save on"
        self.status.showMessage(stats)

    def show_menu(self):
        menu = QMenu(self)

        bookmarks_menu = menu.addMenu("⭐ Bookmarks")
        for bookmark in self.bookmarks.bookmarks:
            action = bookmarks_menu.addAction(bookmark["title"])
            action.triggered.connect(lambda checked, url=bookmark["url"]: self.navigate_to_bookmark(url))
        if not self.bookmarks.bookmarks:
            bookmarks_menu.addAction("No bookmarks").setEnabled(False)

        menu.addSeparator()

        history_action = menu.addAction("📜 History")
        history_action.triggered.connect(self.show_history)

        cache_action = menu.addAction(f"💾 Clear Cache ({self.cache.size()})")
        cache_action.triggered.connect(self.clear_cache)

        menu.addSeparator()

        about_action = menu.addAction("ℹ️ About")
        about_action.triggered.connect(self.show_about)

        quit_action = menu.addAction("❌ Quit")
        quit_action.triggered.connect(self.close)

        menu.exec_(QCursor.pos())

    def navigate_to_bookmark(self, url: str):
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)

    def clear_cache(self):
        self.cache.clear()
        self.status.showMessage("✓ Cache cleared", 3000)
        self.update_status()

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("History")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()
        history_list = QListWidget()

        for item in reversed(self.history.history[-100:]):
            timestamp = datetime.fromisoformat(item["timestamp"]).strftime("%Y-%m-%d %H:%M")
            list_item = QListWidgetItem(f"{timestamp} - {item['title']}")
            list_item.setData(Qt.UserRole, item["url"])
            history_list.addItem(list_item)

        history_list.itemDoubleClicked.connect(lambda item: self.navigate_to_history_item(item, dialog))
        layout.addWidget(history_list)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def navigate_to_history_item(self, item, dialog):
        url = item.data(Qt.UserRole)
        tab = self.get_current_tab()
        if tab:
            tab.navigate(url)
        dialog.close()

    def show_about(self):
        QMessageBox.about(self, "About AI Browser",
                         "AI Browser - Enhanced with Background Services v3.0\n\n"
                         "Real browser + AI automation + silent optimization\n\n"
                         "Features:\n"
                         "• Visual browsing with tabs\n"
                         "• Natural language commands\n"
                         "• AI chat assistant\n"
                         "• Auto-save sessions (every 30s)\n"
                         "• Auto-cleanup cache (every 5min)\n"
                         "• Form auto-save (every 10s)\n"
                         "• Auto HTTPS upgrade\n"
                         "• Tab auto-freeze (inactive 10min)\n"
                         "• Memory monitoring\n\n"
                         "Built with PyQt5, QtWebEngine, and LM Studio\n"
                         "All background services run automatically!")

    def closeEvent(self, event):
        """Save session on close"""
        self.auto_save_session()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Browser - Enhanced")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
