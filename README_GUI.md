# AI Browser - Real Browser with GUI

A fully-featured web browser with its own window, tabs, and AI integration!

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│ ◀ ▶ ⟳ ⌂  [https://example.com          ] ☆ 🤖AI + ☰       │
├─────────────────────────────────────────────────────────────┤
│ Tab 1: Google  │  Tab 2: Reddit  │  Tab 3: GitHub  │  +    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│                    YOUR WEBPAGE HERE                          │
│                    (Real Chromium rendering)                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## What Makes This a "Real Browser"

Unlike the previous Playwright version which automated an invisible browser, this is:

✅ **Real browser window** - Has its own UI you can see and interact with
✅ **Built-in rendering** - Uses QtWebEngine (Chromium's Blink engine)
✅ **Full browser controls** - Address bar, back/forward, reload, tabs
✅ **Real tabs** - Multiple pages in one window
✅ **Bookmarks & History** - Persistent storage
✅ **AI Integration** - Side panel with LM Studio

This is like Brave, Edge, or Opera - uses Chromium's rendering engine but with our own UI!

## Features

### Core Browser Features
- ✅ **Multiple Tabs** - Open as many tabs as you want
- ✅ **Address Bar** - Smart URL/search detection
- ✅ **Navigation** - Back, Forward, Reload, Home buttons
- ✅ **Bookmarks** - Star button to save favorites
- ✅ **History** - Track and search your browsing
- ✅ **Real Rendering** - Chromium Blink engine

### AI Features
- ✅ **AI Side Panel** - Chat with AI about the page
- ✅ **LM Studio Integration** - Uses local AI
- ✅ **Context-Aware** - AI knows what page you're on
- ✅ **Toggle On/Off** - Show/hide AI panel as needed

### UI Features
- ✅ **Clean Interface** - Modern, minimal design
- ✅ **Keyboard Shortcuts** - Enter to navigate, etc.
- ✅ **Status Bar** - Shows loading status
- ✅ **Tab Titles** - Shows page titles
- ✅ **Closeable Tabs** - X button on each tab

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements_gui.txt
```

This installs:
- PyQt5 - GUI framework
- PyQtWebEngine - Chromium rendering engine
- openai - For LM Studio

### 2. Run the Browser

```bash
python browser_gui.py
```

That's it! The browser window will open.

### 3. Optional: LM Studio (for AI)

If you want AI features:

1. Download LM Studio from https://lmstudio.ai/
2. Load a model (Llama 3, Mistral, etc.)
3. Start local server on port 1234
4. Click "🤖 AI" button in browser

## Usage

### Basic Browsing

1. **Navigate**: Type URL or search query in address bar, press Enter
2. **New Tab**: Click the "+" button
3. **Close Tab**: Click X on tab
4. **Bookmark**: Click the ☆ button (becomes ★ when bookmarked)
5. **Menu**: Click ☰ for bookmarks, history, settings

### AI Assistant

1. Click "🤖 AI" button to open AI panel
2. Type question about current page
3. Press Enter or click "Ask"
4. AI responds in chat window

Example questions:
- "Summarize this article"
- "What is this page about?"
- "Extract the main points"

### Keyboard Shortcuts

- `Ctrl+T` - New tab (TODO)
- `Ctrl+W` - Close tab (TODO)
- `Ctrl+R` - Reload page (TODO)
- `Alt+Left` - Back
- `Alt+Right` - Forward
- `Enter` - Navigate to URL/search

## How It Works

### Architecture

```
browser_gui.py (THIS FILE - the real browser!)
├── MainWindow - Main browser window
│   ├── Navigation Bar
│   │   ├── Back/Forward buttons
│   │   ├── URL bar
│   │   └── Bookmark button
│   ├── Tab System (QTabWidget)
│   │   └── BrowserTab (QWebEngineView)
│   └── AI Panel (optional sidebar)
│
├── BookmarkManager - Save/load bookmarks
├── HistoryManager - Track browsing
└── AIAssistant - LM Studio integration
```

### Why QtWebEngine?

QtWebEngine is Chromium's Blink rendering engine - the same engine that powers:
- Google Chrome
- Microsoft Edge
- Brave Browser
- Opera
- Vivaldi

So you're getting a "real" Chromium-based browser with custom UI!

## Comparison

### vs. Playwright Version (ai_browser.py)

| Feature | Playwright | GUI Browser |
|---------|-----------|-------------|
| Has visible window | ❌ | ✅ |
| User can click/interact | ❌ | ✅ |
| Address bar | ❌ | ✅ |
| Visual tabs | ❌ | ✅ |
| Bookmarks UI | ❌ | ✅ |
| AI commands | ✅ | ✅ |
| Automation | ✅ | ❌ |

### vs. Regular Browsers

| Feature | Chrome | AI Browser |
|---------|--------|------------|
| Multiple tabs | ✅ | ✅ |
| Bookmarks | ✅ | ✅ |
| History | ✅ | ✅ |
| AI Assistant | ❌ | ✅ (LM Studio) |
| Local/Private | ❌ | ✅ |
| Extensions | ✅ | ❌ (future) |

## Configuration

### Bookmarks

Stored in: `~/.ai_browser/bookmarks.json`

```json
[
  {
    "title": "Example Site",
    "url": "https://example.com",
    "created": "2025-10-22T10:30:00"
  }
]
```

### History

Stored in: `~/.ai_browser/history.json`

```json
[
  {
    "title": "Example",
    "url": "https://example.com",
    "timestamp": "2025-10-22T10:30:00"
  }
]
```

### AI Configuration

LM Studio must be running on `http://localhost:1234`

To change:
```python
# In browser_gui.py, line ~27
self.base_url = "http://localhost:1234/v1"  # Change port if needed
```

## Customization

### Change Home Page

```python
# In BrowserTab.__init__, line ~141
self.browser.setUrl(QUrl("https://www.google.com"))  # Change to your preference
```

### Change Window Size

```python
# In MainWindow.__init__, line ~316
self.setGeometry(100, 100, 1400, 900)  # (x, y, width, height)
```

### Disable AI Panel

```python
# In MainWindow.__init__, line ~368
self.ai_panel.setVisible(False)  # Keep False to hide by default
```

## Advanced Features

### Custom CSS

Inject custom CSS into pages:

```python
# In BrowserTab
self.browser.page().runJavaScript("""
    document.body.style.backgroundColor = 'black';
    document.body.style.color = 'white';
""")
```

### Ad Blocking (Future)

Can be added using QWebEngineUrlRequestInterceptor

### Developer Tools (Future)

Enable with:
```python
self.browser.page().setDevToolsPage(devtools_page)
```

## Troubleshooting

### "Failed to load Qt platform plugin"

Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install python3-pyqt5 python3-pyqt5.qtwebengine

# macOS
brew install pyqt5
```

### "AI not available"

1. Check LM Studio is running
2. Server started on port 1234
3. Model loaded

Test connection:
```bash
curl http://localhost:1234/v1/models
```

### Browser crashes

Increase memory:
```bash
# Run with more memory
python browser_gui.py
```

### Slow performance

1. Close unused tabs
2. Use lighter LM Studio model
3. Reduce window size

## Future Enhancements

Planned features:

- [ ] Extensions support
- [ ] Developer tools
- [ ] Downloads manager UI
- [ ] Settings dialog
- [ ] Themes (dark mode)
- [ ] Keyboard shortcuts
- [ ] Tab groups
- [ ] Session restore
- [ ] Sync across devices
- [ ] Ad blocker
- [ ] Privacy mode
- [ ] Password manager
- [ ] Form autofill

## Building Standalone App

Create executable:

```bash
pip install pyinstaller

pyinstaller --onefile --windowed browser_gui.py
```

This creates a single .exe/.app file!

## Contributing

Want to add features? The code is well-structured:

1. **MainWindow** - Main browser UI
2. **BrowserTab** - Individual tab
3. **AIPanel** - AI chat interface
4. **BookmarkManager** - Bookmark storage
5. **HistoryManager** - History storage

## License

MIT

## Credits

- Built with PyQt5 and QtWebEngine
- Uses Chromium's Blink engine
- LM Studio for local AI

---

**This is a REAL browser with its own window, not just automation!** 🚀
