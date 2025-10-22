#!/usr/bin/env python3
"""
AI Browser - Advanced browser with LM Studio support and modern browser features
Includes tabs, bookmarks, history, downloads, and AI-powered navigation
"""

import os
import sys
import json
import base64
import asyncio
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, quote_plus

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    from PIL import Image
    # Make optional - not everyone needs these
    try:
        import anthropic
    except ImportError:
        anthropic = None
    try:
        import openai
    except ImportError:
        openai = None
except ImportError as e:
    print(f"Missing dependencies. Install with:")
    print(f"pip install playwright Pillow")
    print(f"playwright install chromium")
    print(f"\nOptional AI providers:")
    print(f"pip install anthropic openai")
    sys.exit(1)


# Configuration
DATA_DIR = Path.home() / ".ai_browser"
DATA_DIR.mkdir(exist_ok=True)
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_DB = DATA_DIR / "history.db"
SETTINGS_FILE = DATA_DIR / "settings.json"
DOWNLOADS_DIR = Path.home() / "Downloads" / "AIBrowser"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AIConfig:
    """Configuration for AI providers"""
    provider: str
    model: str
    base_url: str = ""  # For LM Studio and local models
    api_key: str = "not-needed"  # LM Studio doesn't need key
    supports_vision: bool = False
    supports_thinking: bool = False
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class Tab:
    """Browser tab"""
    id: int
    title: str = "New Tab"
    url: str = ""
    page: Optional[Page] = None
    history: List[str] = field(default_factory=list)
    history_index: int = -1
    zoom_level: float = 1.0
    is_loading: bool = False
    favicon: Optional[str] = None

    def can_go_back(self) -> bool:
        return self.history_index > 0

    def can_go_forward(self) -> bool:
        return self.history_index < len(self.history) - 1


@dataclass
class Bookmark:
    """Bookmark entry"""
    id: int
    title: str
    url: str
    folder: str = "Default"
    tags: List[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Download:
    """Download entry"""
    id: int
    url: str
    filename: str
    filepath: str
    size: int = 0
    completed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Settings:
    """Browser settings"""
    default_search_engine: str = "https://www.google.com/search?q="
    home_page: str = "https://www.google.com"
    download_location: str = str(DOWNLOADS_DIR)
    private_mode: bool = False
    block_popups: bool = True
    enable_javascript: bool = True
    user_agent: str = ""
    theme: str = "light"


class AIProvider(ABC):
    """Base class for AI providers"""

    def __init__(self, config: AIConfig):
        self.config = config

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message and get response"""
        pass

    @abstractmethod
    async def execute_command(self, command: str,
                             tab: Tab) -> Dict[str, Any]:
        """Execute a natural language command"""
        pass


class LMStudioProvider(AIProvider):
    """LM Studio provider - local LLM with OpenAI-compatible API"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        if openai is None:
            raise ImportError("openai package required for LM Studio. Install with: pip install openai")

        # LM Studio default endpoint
        base_url = config.base_url or "http://localhost:1234/v1"
        self.client = openai.AsyncOpenAI(
            base_url=base_url,
            api_key="lm-studio"  # LM Studio doesn't validate this
        )

    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message to LM Studio"""

        # LM Studio supports OpenAI format
        formatted_messages = []
        for msg in messages:
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=formatted_messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error connecting to LM Studio: {str(e)}\n\nMake sure LM Studio is running on {self.config.base_url or 'http://localhost:1234'}"

    async def execute_command(self, command: str, tab: Tab) -> Dict[str, Any]:
        """Execute a natural language command using LM Studio"""

        system_prompt = """You are an AI browser assistant. You control a web browser and help users navigate the internet.

Available actions (respond with JSON):
- navigate: Go to a URL
  {"action": "navigate", "parameters": {"url": "https://example.com"}, "explanation": "Going to example.com"}

- click: Click an element (use CSS selector)
  {"action": "click", "parameters": {"selector": "button.login"}, "explanation": "Clicking login button"}

- type: Type text into an input field
  {"action": "type", "parameters": {"selector": "input[name='q']", "text": "search query"}, "explanation": "Typing search query"}

- scroll: Scroll the page
  {"action": "scroll", "parameters": {"direction": "down", "amount": 500}, "explanation": "Scrolling down"}

- read: Read page content
  {"action": "read", "parameters": {}, "explanation": "Reading the page"}

- search: Search for text on page
  {"action": "search", "parameters": {"query": "text to find"}, "explanation": "Searching for text"}

- extract: Extract information
  {"action": "extract", "parameters": {"query": "what to extract"}, "explanation": "Extracting data"}

- back: Go back in history
  {"action": "back", "parameters": {}, "explanation": "Going back"}

- forward: Go forward in history
  {"action": "forward", "parameters": {}, "explanation": "Going forward"}

For multiple steps, return an array: [{"action": "navigate", ...}, {"action": "click", ...}]

Current page info:
URL: {url}
Title: {title}

User command: {command}

Respond ONLY with valid JSON action(s)."""

        messages = [
            {"role": "system", "content": system_prompt.format(
                url=tab.url,
                title=tab.title,
                command=command
            )},
            {"role": "user", "content": command}
        ]

        response = await self.chat(messages)

        # Parse JSON response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "action": "error",
                    "explanation": f"Could not parse command. AI response: {response}"
                }
        except json.JSONDecodeError:
            return {
                "action": "error",
                "explanation": f"Invalid JSON response: {response}"
            }


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider with vision support"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        if anthropic is None:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message to Claude"""

        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue

            content = []
            if isinstance(msg["content"], str):
                content = [{"type": "text", "text": msg["content"]}]
            else:
                content = msg["content"]

            if screenshot and self.config.supports_vision and msg["role"] == "user":
                image_data = base64.b64encode(screenshot).decode('utf-8')
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data
                    }
                })

            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })

        system_msg = next((m["content"] for m in messages if m["role"] == "system"),
                         "You are a helpful AI assistant browsing the web.")

        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_msg,
            messages=formatted_messages
        )

        return response.content[0].text

    async def execute_command(self, command: str, tab: Tab) -> Dict[str, Any]:
        """Execute command using Claude"""
        # Similar implementation to LMStudioProvider
        system_prompt = """You are an AI browser assistant. Respond with JSON actions."""

        messages = [
            {"role": "user", "content": f"Current: {tab.url}\n\nCommand: {command}\n\nRespond with JSON."}
        ]

        response = await self.chat(messages)

        try:
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"action": "error", "explanation": f"Could not parse: {response}"}
        except json.JSONDecodeError:
            return {"action": "error", "explanation": f"Invalid JSON: {response}"}


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        if openai is None:
            raise ImportError("openai package required. Install with: pip install openai")
        self.client = openai.AsyncOpenAI(api_key=config.api_key)

    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message to GPT"""

        formatted_messages = []
        for msg in messages:
            content = msg["content"]

            if screenshot and self.config.supports_vision and msg["role"] == "user":
                image_data = base64.b64encode(screenshot).decode('utf-8')
                content = [
                    {"type": "text", "text": content if isinstance(content, str) else content},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]

            formatted_messages.append({"role": msg["role"], "content": content})

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=formatted_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )

        return response.choices[0].message.content

    async def execute_command(self, command: str, tab: Tab) -> Dict[str, Any]:
        """Execute command using GPT"""
        messages = [
            {"role": "system", "content": "You are an AI browser assistant. Respond with JSON actions."},
            {"role": "user", "content": f"Current: {tab.url}\nCommand: {command}\nJSON:"}
        ]

        response = await self.chat(messages)

        try:
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"action": "error", "explanation": f"Could not parse: {response}"}
        except json.JSONDecodeError:
            return {"action": "error", "explanation": f"Invalid JSON: {response}"}


class HistoryManager:
    """Manage browsing history with SQLite"""

    def __init__(self, db_path: Path = HISTORY_DB):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize history database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                visit_count INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_url ON history(url)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_time ON history(visit_time DESC)
        """)
        conn.commit()
        conn.close()

    def add_visit(self, url: str, title: str):
        """Add or update history entry"""
        if not url or url.startswith('about:') or url.startswith('chrome:'):
            return

        conn = sqlite3.connect(self.db_path)
        # Check if URL exists
        cursor = conn.execute("SELECT id, visit_count FROM history WHERE url = ?", (url,))
        row = cursor.fetchone()

        if row:
            # Update visit count and time
            conn.execute(
                "UPDATE history SET visit_count = visit_count + 1, visit_time = CURRENT_TIMESTAMP, title = ? WHERE id = ?",
                (title, row[0])
            )
        else:
            # Insert new entry
            conn.execute(
                "INSERT INTO history (url, title) VALUES (?, ?)",
                (url, title)
            )

        conn.commit()
        conn.close()

    def search_history(self, query: str, limit: int = 50) -> List[Dict]:
        """Search history by URL or title"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT url, title, visit_time, visit_count
            FROM history
            WHERE url LIKE ? OR title LIKE ?
            ORDER BY visit_time DESC
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "url": row[0],
                "title": row[1],
                "visit_time": row[2],
                "visit_count": row[3]
            })

        conn.close()
        return results

    def get_recent(self, limit: int = 100) -> List[Dict]:
        """Get recent history"""
        return self.search_history("", limit)

    def clear_history(self, days: Optional[int] = None):
        """Clear history (all or by days)"""
        conn = sqlite3.connect(self.db_path)
        if days:
            conn.execute("""
                DELETE FROM history
                WHERE visit_time < datetime('now', ? || ' days')
            """, (f"-{days}",))
        else:
            conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()


class BookmarkManager:
    """Manage bookmarks"""

    def __init__(self, file_path: Path = BOOKMARKS_FILE):
        self.file_path = file_path
        self.bookmarks: List[Bookmark] = []
        self.load()

    def load(self):
        """Load bookmarks from file"""
        if self.file_path.exists():
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.bookmarks = [Bookmark(**b) for b in data]

    def save(self):
        """Save bookmarks to file"""
        with open(self.file_path, 'w') as f:
            json.dump([asdict(b) for b in self.bookmarks], f, indent=2)

    def add(self, title: str, url: str, folder: str = "Default", tags: List[str] = None) -> Bookmark:
        """Add a bookmark"""
        bookmark_id = max([b.id for b in self.bookmarks], default=0) + 1
        bookmark = Bookmark(
            id=bookmark_id,
            title=title,
            url=url,
            folder=folder,
            tags=tags or []
        )
        self.bookmarks.append(bookmark)
        self.save()
        return bookmark

    def remove(self, bookmark_id: int):
        """Remove a bookmark"""
        self.bookmarks = [b for b in self.bookmarks if b.id != bookmark_id]
        self.save()

    def search(self, query: str) -> List[Bookmark]:
        """Search bookmarks"""
        query_lower = query.lower()
        return [
            b for b in self.bookmarks
            if query_lower in b.title.lower() or
               query_lower in b.url.lower() or
               any(query_lower in tag.lower() for tag in b.tags)
        ]

    def get_by_folder(self, folder: str) -> List[Bookmark]:
        """Get bookmarks in a folder"""
        return [b for b in self.bookmarks if b.folder == folder]

    def get_folders(self) -> List[str]:
        """Get all folder names"""
        return list(set(b.folder for b in self.bookmarks))


class DownloadManager:
    """Manage downloads"""

    def __init__(self):
        self.downloads: List[Download] = []
        self.download_id_counter = 0

    def add_download(self, url: str, filename: str, filepath: str) -> Download:
        """Add a download"""
        self.download_id_counter += 1
        download = Download(
            id=self.download_id_counter,
            url=url,
            filename=filename,
            filepath=filepath
        )
        self.downloads.append(download)
        return download

    def get_downloads(self) -> List[Download]:
        """Get all downloads"""
        return self.downloads

    def mark_completed(self, download_id: int):
        """Mark download as completed"""
        for d in self.downloads:
            if d.id == download_id:
                d.completed = True
                break


class SettingsManager:
    """Manage browser settings"""

    def __init__(self, file_path: Path = SETTINGS_FILE):
        self.file_path = file_path
        self.settings = Settings()
        self.load()

    def load(self):
        """Load settings from file"""
        if self.file_path.exists():
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.settings = Settings(**data)

    def save(self):
        """Save settings to file"""
        with open(self.file_path, 'w') as f:
            json.dump(asdict(self.settings), f, indent=2)

    def update(self, **kwargs):
        """Update settings"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()


class BrowserAutomation:
    """Enhanced browser automation with tabs"""

    def __init__(self, settings: Settings):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self.settings = settings
        self.tabs: List[Tab] = []
        self.active_tab_id: Optional[int] = None
        self.tab_id_counter = 0

    async def start(self, headless: bool = False):
        """Start the browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)

        # Create context with settings
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "accept_downloads": True
        }

        if self.settings.user_agent:
            context_options["user_agent"] = self.settings.user_agent

        if self.settings.private_mode:
            # Incognito mode
            self.context = await self.browser.new_context(**context_options)
        else:
            # Normal mode with persistence
            self.context = await self.browser.new_context(**context_options)

        # Create first tab
        await self.new_tab()

    async def stop(self):
        """Stop the browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_tab(self, url: str = "") -> Tab:
        """Create a new tab"""
        self.tab_id_counter += 1
        page = await self.context.new_page()

        tab = Tab(id=self.tab_id_counter, page=page)
        self.tabs.append(tab)
        self.active_tab_id = tab.id

        if url:
            await self.navigate(url, tab)

        return tab

    async def close_tab(self, tab_id: int):
        """Close a tab"""
        tab = self.get_tab(tab_id)
        if tab and tab.page:
            await tab.page.close()
            self.tabs = [t for t in self.tabs if t.id != tab_id]

            # Switch to another tab if we closed the active one
            if self.active_tab_id == tab_id and self.tabs:
                self.active_tab_id = self.tabs[-1].id

    def get_tab(self, tab_id: Optional[int] = None) -> Optional[Tab]:
        """Get tab by ID or active tab"""
        if tab_id is None:
            tab_id = self.active_tab_id

        for tab in self.tabs:
            if tab.id == tab_id:
                return tab
        return None

    def switch_tab(self, tab_id: int):
        """Switch to a tab"""
        if any(t.id == tab_id for t in self.tabs):
            self.active_tab_id = tab_id

    async def navigate(self, url: str, tab: Optional[Tab] = None) -> Tab:
        """Navigate to a URL"""
        if tab is None:
            tab = self.get_tab()

        if not tab or not tab.page:
            raise ValueError("No active tab")

        # Add protocol if missing
        if not url.startswith(('http://', 'https://', 'about:', 'file://')):
            # Check if it's a search query or URL
            if ' ' in url or '.' not in url:
                # It's a search query
                url = self.settings.default_search_engine + quote_plus(url)
            else:
                url = 'https://' + url

        tab.is_loading = True

        try:
            await tab.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Update tab info
            tab.url = tab.page.url
            tab.title = await tab.page.title()
            tab.is_loading = False

            # Update history
            if tab.history_index < len(tab.history) - 1:
                # Clear forward history if we navigated from middle
                tab.history = tab.history[:tab.history_index + 1]

            tab.history.append(tab.url)
            tab.history_index = len(tab.history) - 1

        except Exception as e:
            tab.is_loading = False
            tab.title = "Error loading page"
            raise e

        return tab

    async def go_back(self, tab: Optional[Tab] = None):
        """Go back in history"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.can_go_back():
            tab.history_index -= 1
            url = tab.history[tab.history_index]
            await tab.page.goto(url)
            tab.url = url
            tab.title = await tab.page.title()

    async def go_forward(self, tab: Optional[Tab] = None):
        """Go forward in history"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.can_go_forward():
            tab.history_index += 1
            url = tab.history[tab.history_index]
            await tab.page.goto(url)
            tab.url = url
            tab.title = await tab.page.title()

    async def reload(self, tab: Optional[Tab] = None, force: bool = False):
        """Reload the page"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page:
            if force:
                await tab.page.reload()
            else:
                await tab.page.reload()

    async def stop_loading(self, tab: Optional[Tab] = None):
        """Stop page loading"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page and tab.is_loading:
            # Playwright doesn't have a stop method, so we navigate to about:blank
            # In practice, most pages will finish loading quickly
            tab.is_loading = False

    async def set_zoom(self, level: float, tab: Optional[Tab] = None):
        """Set zoom level"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page:
            tab.zoom_level = level
            # This is a simple zoom by changing viewport
            # For proper zoom, you'd need to inject CSS or use browser devtools protocol

    async def find_in_page(self, query: str, tab: Optional[Tab] = None) -> List[str]:
        """Find text in page"""
        if tab is None:
            tab = self.get_tab()

        if not tab or not tab.page:
            return []

        # Use JavaScript to find text
        content = await tab.page.content()
        lines = content.split('\n')
        matches = [line for line in lines if query.lower() in line.lower()]
        return matches[:20]  # Return first 20 matches

    async def get_content(self, tab: Optional[Tab] = None) -> str:
        """Get page text content"""
        if tab is None:
            tab = self.get_tab()

        if not tab or not tab.page:
            return ""

        return await tab.page.evaluate("() => document.body.innerText")

    async def get_screenshot(self, tab: Optional[Tab] = None) -> bytes:
        """Take a screenshot"""
        if tab is None:
            tab = self.get_tab()

        if not tab or not tab.page:
            return b""

        screenshot = await tab.page.screenshot(full_page=False, type="png")

        # Compress for AI
        image = Image.open(BytesIO(screenshot))
        max_size = (1280, 720)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()

    async def click(self, selector: str, tab: Optional[Tab] = None):
        """Click an element"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page:
            await tab.page.click(selector, timeout=10000)

    async def type_text(self, selector: str, text: str, tab: Optional[Tab] = None):
        """Type text into an input"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page:
            await tab.page.fill(selector, text)

    async def scroll(self, direction: str = "down", amount: int = 500, tab: Optional[Tab] = None):
        """Scroll the page"""
        if tab is None:
            tab = self.get_tab()

        if tab and tab.page:
            if direction == "down":
                await tab.page.evaluate(f"window.scrollBy(0, {amount})")
            else:
                await tab.page.evaluate(f"window.scrollBy(0, -{amount})")

    async def search_text(self, query: str, tab: Optional[Tab] = None) -> List[str]:
        """Search for text on the page"""
        content = await self.get_content(tab)
        lines = content.split('\n')
        return [line.strip() for line in lines if query.lower() in line.lower()][:20]


class AIBrowser:
    """Main AI Browser with full features"""

    def __init__(self):
        self.settings_manager = SettingsManager()
        self.browser = BrowserAutomation(self.settings_manager.settings)
        self.history = HistoryManager()
        self.bookmarks = BookmarkManager()
        self.downloads = DownloadManager()

        self.ai_providers: Dict[str, AIProvider] = {}
        self.current_provider: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []

    def add_provider(self, name: str, provider: AIProvider):
        """Add an AI provider"""
        self.ai_providers[name] = provider
        if not self.current_provider:
            self.current_provider = name

    def set_provider(self, name: str):
        """Set the active AI provider"""
        if name in self.ai_providers:
            self.current_provider = name
            print(f"✓ Switched to {name}")
        else:
            print(f"✗ Provider {name} not found. Available: {list(self.ai_providers.keys())}")

    async def start(self, headless: bool = False):
        """Start the browser"""
        await self.browser.start(headless=headless)
        print("✓ Browser started!")
        print(f"  Mode: {'Private' if self.settings_manager.settings.private_mode else 'Normal'}")

    async def stop(self):
        """Stop the browser"""
        await self.browser.stop()
        print("✓ Browser stopped!")

    async def execute_action(self, action: Dict[str, Any]) -> str:
        """Execute a browser action"""
        action_type = action.get("action")
        params = action.get("parameters", {})
        explanation = action.get("explanation", "")

        if explanation:
            print(f"  → {explanation}")

        tab = self.browser.get_tab()
        if not tab:
            return "No active tab"

        try:
            if action_type == "navigate":
                await self.browser.navigate(params["url"], tab)
                self.history.add_visit(tab.url, tab.title)
                return f"✓ Navigated to {tab.url}"

            elif action_type == "back":
                await self.browser.go_back(tab)
                return f"✓ Went back to {tab.url}"

            elif action_type == "forward":
                await self.browser.go_forward(tab)
                return f"✓ Went forward to {tab.url}"

            elif action_type == "reload":
                await self.browser.reload(tab)
                return f"✓ Reloaded {tab.url}"

            elif action_type == "click":
                await self.browser.click(params["selector"], tab)
                return f"✓ Clicked {params['selector']}"

            elif action_type == "type":
                await self.browser.type_text(params["selector"], params["text"], tab)
                return f"✓ Typed into {params['selector']}"

            elif action_type == "scroll":
                direction = params.get("direction", "down")
                await self.browser.scroll(direction, params.get("amount", 500), tab)
                return f"✓ Scrolled {direction}"

            elif action_type == "read":
                content = await self.browser.get_content(tab)
                preview = content[:2000] + "..." if len(content) > 2000 else content
                return f"Page content:\n{preview}"

            elif action_type == "search":
                results = await self.browser.search_text(params.get("query", ""), tab)
                return f"Found {len(results)} matches:\n" + "\n".join(results[:10])

            elif action_type == "extract":
                results = await self.browser.search_text(params.get("query", ""), tab)
                return "\n".join(results[:10])

            else:
                return f"✗ Unknown action: {action_type}"

        except Exception as e:
            return f"✗ Error: {str(e)}"

    async def execute_command(self, command: str) -> str:
        """Execute a natural language command"""
        if not self.current_provider:
            return "✗ No AI provider configured!"

        provider = self.ai_providers[self.current_provider]
        tab = self.browser.get_tab()

        if not tab:
            return "✗ No active tab"

        print(f"\n🤖 Processing with {self.current_provider}...")

        # Get command plan from AI
        actions = await provider.execute_command(command, tab)

        # Handle both single action and multiple actions
        if isinstance(actions, dict):
            actions = [actions]

        results = []
        for action in actions:
            if action.get("action") == "error":
                results.append("✗ " + action.get("explanation", "Unknown error"))
            else:
                result = await self.execute_action(action)
                results.append(result)

        return "\n".join(results)

    async def chat(self, message: str, include_vision: bool = True) -> str:
        """Chat with AI about the current page"""
        if not self.current_provider:
            return "✗ No AI provider configured!"

        provider = self.ai_providers[self.current_provider]
        tab = self.browser.get_tab()

        if not tab:
            return "✗ No active tab"

        content = await self.browser.get_content(tab)

        context_msg = f"""Current page:
URL: {tab.url}
Title: {tab.title}

Content preview:
{content[:1000] if content else 'No content'}

User: {message}"""

        self.conversation_history.append({
            "role": "user",
            "content": context_msg
        })

        # Get screenshot if vision is supported
        screenshot = None
        if include_vision and provider.config.supports_vision:
            screenshot = await self.browser.get_screenshot(tab)

        response = await provider.chat(self.conversation_history, screenshot)

        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return response

    def show_status(self):
        """Show browser status"""
        print("\n" + "="*60)
        print("AI BROWSER STATUS")
        print("="*60)

        # AI Provider
        print(f"\n🤖 AI Provider: {self.current_provider}")
        print(f"   Available: {', '.join(self.ai_providers.keys())}")

        # Tabs
        print(f"\n📑 Tabs ({len(self.browser.tabs)}):")
        for tab in self.browser.tabs:
            active = "  ➜" if tab.id == self.browser.active_tab_id else "   "
            loading = " [Loading...]" if tab.is_loading else ""
            print(f"{active} Tab {tab.id}: {tab.title[:40]}{loading}")
            print(f"      {tab.url[:60]}")

        # Bookmarks
        print(f"\n⭐ Bookmarks: {len(self.bookmarks.bookmarks)}")
        folders = self.bookmarks.get_folders()
        if folders:
            print(f"   Folders: {', '.join(folders)}")

        # History
        recent = self.history.get_recent(5)
        print(f"\n📜 Recent History ({len(recent)} total):")
        for item in recent[:3]:
            print(f"   • {item['title'][:40]}")
            print(f"     {item['url'][:60]}")

        # Settings
        print(f"\n⚙️  Settings:")
        print(f"   Mode: {'🔒 Private' if self.settings_manager.settings.private_mode else '🌐 Normal'}")
        print(f"   Search: {self.settings_manager.settings.default_search_engine[:40]}")
        print(f"   Downloads: {self.settings_manager.settings.download_location[:40]}")

        print("\n" + "="*60)

    async def interactive_mode(self):
        """Run interactive command mode"""
        print("\n" + "="*70)
        print("🌐 AI BROWSER - Interactive Mode")
        print("="*70)

        self.show_status()

        print("\n💡 Commands:")
        print("  Natural language: 'Go to reddit.com' or 'read the top post'")
        print("  chat: <message>   - Chat about the page")
        print("  tabs              - List all tabs")
        print("  tab <id>          - Switch to tab")
        print("  newtab [url]      - Open new tab")
        print("  closetab [id]     - Close tab")
        print("  back / forward    - Navigate history")
        print("  reload            - Reload page")
        print("  bookmark [title]  - Bookmark current page")
        print("  bookmarks         - List bookmarks")
        print("  history [query]   - Search history")
        print("  find: <text>      - Find in page")
        print("  status            - Show status")
        print("  use: <provider>   - Switch AI provider")
        print("  settings          - Show/edit settings")
        print("  quit / exit       - Exit browser")
        print("\n" + "="*70 + "\n")

        while True:
            try:
                tab = self.browser.get_tab()
                prompt = f"\n[Tab {tab.id if tab else '?'}] > " if tab else "\n> "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Exit commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break

                # Status
                if user_input.lower() == 'status':
                    self.show_status()
                    continue

                # Tab management
                if user_input.lower() == 'tabs':
                    print(f"\n📑 Open Tabs ({len(self.browser.tabs)}):")
                    for t in self.browser.tabs:
                        active = "➜ " if t.id == self.browser.active_tab_id else "  "
                        print(f"{active}Tab {t.id}: {t.title}")
                        print(f"     {t.url}")
                    continue

                if user_input.lower().startswith('tab '):
                    try:
                        tab_id = int(user_input[4:].strip())
                        self.browser.switch_tab(tab_id)
                        print(f"✓ Switched to tab {tab_id}")
                    except ValueError:
                        print("✗ Invalid tab ID")
                    continue

                if user_input.lower().startswith('newtab'):
                    url = user_input[6:].strip() if len(user_input) > 6 else ""
                    new_tab = await self.browser.new_tab(url)
                    print(f"✓ Opened new tab {new_tab.id}")
                    continue

                if user_input.lower().startswith('closetab'):
                    try:
                        tab_id = int(user_input[8:].strip()) if len(user_input) > 8 else tab.id if tab else None
                        if tab_id:
                            await self.browser.close_tab(tab_id)
                            print(f"✓ Closed tab {tab_id}")
                    except ValueError:
                        print("✗ Invalid tab ID")
                    continue

                # Navigation
                if user_input.lower() == 'back':
                    await self.browser.go_back()
                    print(f"✓ Went back to {tab.url}")
                    continue

                if user_input.lower() == 'forward':
                    await self.browser.go_forward()
                    print(f"✓ Went forward to {tab.url}")
                    continue

                if user_input.lower() == 'reload':
                    await self.browser.reload()
                    print("✓ Page reloaded")
                    continue

                # Bookmarks
                if user_input.lower().startswith('bookmark'):
                    if not tab:
                        print("✗ No active tab")
                        continue

                    title = user_input[8:].strip() if len(user_input) > 8 else tab.title
                    self.bookmarks.add(title, tab.url)
                    print(f"✓ Bookmarked: {title}")
                    continue

                if user_input.lower() == 'bookmarks':
                    print(f"\n⭐ Bookmarks ({len(self.bookmarks.bookmarks)}):")
                    for b in self.bookmarks.bookmarks:
                        print(f"  [{b.id}] {b.title}")
                        print(f"      {b.url}")
                        if b.tags:
                            print(f"      Tags: {', '.join(b.tags)}")
                    continue

                # History
                if user_input.lower().startswith('history'):
                    query = user_input[7:].strip() if len(user_input) > 7 else ""
                    results = self.history.search_history(query, limit=20)
                    print(f"\n📜 History ({len(results)} results):")
                    for item in results:
                        print(f"  • {item['title']}")
                        print(f"    {item['url']}")
                        print(f"    Visited: {item['visit_time']} ({item['visit_count']} times)")
                    continue

                # Find in page
                if user_input.lower().startswith('find:'):
                    query = user_input[5:].strip()
                    matches = await self.browser.find_in_page(query)
                    print(f"\n🔍 Found {len(matches)} matches:")
                    for match in matches[:10]:
                        print(f"  • {match[:100]}")
                    continue

                # Settings
                if user_input.lower() == 'settings':
                    settings = self.settings_manager.settings
                    print("\n⚙️  Settings:")
                    print(f"  Search Engine: {settings.default_search_engine}")
                    print(f"  Home Page: {settings.home_page}")
                    print(f"  Downloads: {settings.download_location}")
                    print(f"  Private Mode: {settings.private_mode}")
                    print(f"  Block Popups: {settings.block_popups}")
                    print(f"  JavaScript: {settings.enable_javascript}")
                    print(f"  Theme: {settings.theme}")
                    continue

                # Switch provider
                if user_input.lower().startswith('use:'):
                    provider_name = user_input[4:].strip()
                    self.set_provider(provider_name)
                    continue

                # Chat mode
                if user_input.lower().startswith('chat:'):
                    message = user_input[5:].strip()
                    response = await self.chat(message)
                    print(f"\n🤖 {self.current_provider}:\n{response}")
                    continue

                # Execute as natural language command
                result = await self.execute_command(user_input)
                print(f"\n{result}")

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'quit' to exit.")
            except Exception as e:
                print(f"\n✗ Error: {str(e)}")


async def main():
    """Main function"""
    print("🚀 Initializing AI Browser with LM Studio support...")

    browser = AIBrowser()

    # Configure AI providers
    # Priority 1: LM Studio (local)
    try:
        lm_studio_config = AIConfig(
            provider="lmstudio",
            model="local-model",  # This can be changed in LM Studio
            base_url=os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
            api_key="not-needed",
            supports_vision=False,
            max_tokens=4096
        )
        browser.add_provider("lmstudio", LMStudioProvider(lm_studio_config))
        print("✓ LM Studio configured (http://localhost:1234)")
    except Exception as e:
        print(f"⚠️  LM Studio not available: {e}")

    # Optional: Anthropic Claude
    claude_api_key = os.getenv("ANTHROPIC_API_KEY")
    if claude_api_key and anthropic:
        try:
            claude_config = AIConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                api_key=claude_api_key,
                supports_vision=True,
                supports_thinking=True,
                max_tokens=4096
            )
            browser.add_provider("claude", AnthropicProvider(claude_config))
            print("✓ Claude configured")
        except Exception as e:
            print(f"⚠️  Claude not available: {e}")

    # Optional: OpenAI GPT
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key and openai:
        try:
            gpt4_config = AIConfig(
                provider="openai",
                model="gpt-4o",
                api_key=openai_api_key,
                supports_vision=True,
                max_tokens=4096
            )
            browser.add_provider("gpt4", OpenAIProvider(gpt4_config))
            print("✓ GPT-4 configured")
        except Exception as e:
            print(f"⚠️  GPT-4 not available: {e}")

    if not browser.ai_providers:
        print("\n❌ No AI providers configured!")
        print("\n💡 To use LM Studio:")
        print("  1. Download LM Studio from https://lmstudio.ai/")
        print("  2. Load a model (recommended: Llama 3, Mistral, or Phi-3)")
        print("  3. Start the local server (default: http://localhost:1234)")
        print("  4. Run this browser again")
        print("\n💡 Or set API keys:")
        print("  export ANTHROPIC_API_KEY='your-key'")
        print("  export OPENAI_API_KEY='your-key'")
        return

    # Start browser
    await browser.start(headless=False)

    try:
        await browser.interactive_mode()
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
