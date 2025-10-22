# AI Browser

A powerful custom browser with **LM Studio support** (local AI) and modern browser features including tabs, bookmarks, history, and AI-powered navigation.

## Key Features

### AI Integration (Primary: LM Studio)

- **LM Studio Support** - Run local AI models (Llama 3, Mistral, Phi-3, etc.)
  - No API keys needed
  - Complete privacy - everything runs locally
  - Free to use
  - Works offline

- **Optional Cloud AI** - Claude, GPT-4 (with vision)

### Full Browser Features (Like Chrome!)

#### Tab Management
- Multiple tabs with easy switching
- Open/close tabs dynamically
- Tab history per tab
- Visual tab status indicators

#### Bookmarks
- Save favorite pages
- Organize in folders
- Tag bookmarks
- Search bookmarks
- Persistent storage

#### History
- SQLite-based history tracking
- Search history by URL or title
- Visit counts and timestamps
- Clear history (all or by days)

#### Navigation
- Back/forward buttons
- Reload page
- Smart address bar (auto-detects URLs vs searches)
- Search engine integration (Google default)

#### Content Tools
- Find in page
- Zoom controls
- Read page content
- Extract information
- Search on page

#### Privacy & Settings
- Incognito/private mode
- Customizable search engine
- Download location settings
- Persistent settings storage

## Installation

### 1. Install Dependencies

```bash
pip install playwright Pillow openai
playwright install chromium
```

**Optional** (only if you want Claude or GPT-4):
```bash
pip install anthropic openai
```

### 2. Setup LM Studio (Recommended)

1. Download LM Studio: https://lmstudio.ai/
2. Install and open LM Studio
3. Download a model (recommended):
   - **Llama 3.2** (fast, great quality)
   - **Mistral 7B** (balanced)
   - **Phi-3** (lightweight)
   - **DeepSeek Coder** (for technical tasks)

4. Start the local server:
   - Click "Local Server" tab in LM Studio
   - Click "Start Server"
   - Default: http://localhost:1234

5. Run the browser:
```bash
python ai_browser.py
```

### 3. Optional: Cloud AI Providers

If you want to use Claude or GPT-4 instead of LM Studio:

```bash
export ANTHROPIC_API_KEY='your-key'
export OPENAI_API_KEY='your-key'
```

Or create a `.env` file:
```
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
LM_STUDIO_URL=http://localhost:1234/v1
```

## Usage

### Start the Browser

```bash
python ai_browser.py
```

The browser will automatically:
1. Try to connect to LM Studio (local)
2. Fall back to Claude or GPT-4 if API keys are set

### Interactive Commands

#### Natural Language Commands

Just type what you want:

```
> Go to reddit.com
> Read the top post
> Search for "Python tutorials"
> Click the first link
> Scroll down
```

#### Chat About Pages

Ask the AI about what's on the page:

```
> chat: What is this page about?
> chat: Summarize the main article
> chat: What are the top comments?
```

#### Tab Management

```
> tabs               # List all tabs
> tab 2              # Switch to tab 2
> newtab reddit.com  # Open new tab
> closetab 1         # Close tab 1
```

#### Navigation

```
> back               # Go back
> forward            # Go forward
> reload             # Reload page
```

#### Bookmarks

```
> bookmark           # Bookmark current page
> bookmark My Favorite Site  # Custom title
> bookmarks          # List all bookmarks
```

#### History

```
> history            # Show recent history
> history python     # Search history for "python"
```

#### Find & Search

```
> find: keyword      # Find text on page
```

#### Settings & Status

```
> status             # Show browser status
> settings           # Show current settings
> use: lmstudio      # Switch to LM Studio
> use: claude        # Switch to Claude
```

#### Exit

```
> quit
> exit
```

## Examples

### Example 1: Research with Local AI

```
> Go to news.ycombinator.com

🤖 Processing with lmstudio...
  → Navigating to Hacker News
✓ Navigated to https://news.ycombinator.com

> chat: What are the top 3 stories today?

🤖 lmstudio:
Based on the page, the top 3 stories are:
1. "New AI breakthrough in reasoning"
2. "Rust 1.75 released"
3. "How we scaled to 1M users"
```

### Example 2: Multi-Tab Research

```
> newtab python.org
✓ Opened new tab 2

> newtab github.com
✓ Opened new tab 3

> tabs

📑 Open Tabs (3):
➜ Tab 3: GitHub
     https://github.com
  Tab 2: Python.org
     https://python.org
  Tab 1: Hacker News
     https://news.ycombinator.com

> tab 2
✓ Switched to tab 2

> bookmark Python Official
✓ Bookmarked: Python Official
```

### Example 3: Automated Navigation

```
> Go to reddit.com, find r/programming, and read the top post

🤖 Processing with lmstudio...
  → Navigating to Reddit
  → Searching for r/programming
  → Clicking top post
  → Reading content

Page content:
TIL: How to optimize Python code...
[content here]
```

## Architecture

### Components

```
AIBrowser
├── LMStudioProvider (primary)
├── AnthropicProvider (optional)
├── OpenAIProvider (optional)
├── BrowserAutomation
│   ├── Tab Management
│   ├── Navigation
│   └── Content Interaction
├── HistoryManager (SQLite)
├── BookmarkManager (JSON)
├── DownloadManager
└── SettingsManager
```

### Data Storage

All data is stored in `~/.ai_browser/`:
- `history.db` - Browsing history (SQLite)
- `bookmarks.json` - Bookmarks
- `settings.json` - Browser settings
- Downloads: `~/Downloads/AIBrowser/`

### How It Works

1. **User types command** → "Go to reddit and read the top post"
2. **AI processes** → Converts to structured actions (JSON)
3. **Browser executes** → Navigates, clicks, extracts content
4. **Results returned** → User sees the output

### Actions Available to AI

The AI can generate these browser actions:

- `navigate` - Go to URL
- `click` - Click element (CSS selector)
- `type` - Type into input field
- `scroll` - Scroll page
- `read` - Get page content
- `search` - Find text on page
- `extract` - Extract specific information
- `back` - Go back in history
- `forward` - Go forward in history

## LM Studio Tips

### Best Models for Browsing

1. **Llama 3.2 3B** - Fast, great for quick commands
2. **Mistral 7B v0.3** - Balanced performance
3. **Phi-3 Medium** - Lightweight, good quality
4. **DeepSeek Coder** - Best for technical sites
5. **Gemma 2 9B** - Great reasoning

### Recommended Settings in LM Studio

- **Temperature**: 0.7 (balanced)
- **Max Tokens**: 4096
- **Context Length**: 8192+
- **GPU Layers**: Max (for speed)

### Troubleshooting LM Studio

**Browser can't connect:**
```bash
# Check if LM Studio server is running
curl http://localhost:1234/v1/models

# If not, start it in LM Studio:
# Local Server tab → Start Server
```

**Slow responses:**
- Use smaller models (3B-7B parameters)
- Enable GPU acceleration in LM Studio
- Reduce max tokens to 2048

**Model gives bad instructions:**
- Try a different model (Llama 3 is most reliable)
- Use chat mode instead: `chat: summarize this page`

## Advanced Usage

### Programmatic Usage

```python
import asyncio
from ai_browser import AIBrowser, AIConfig, LMStudioProvider

async def automate():
    browser = AIBrowser()

    # Configure LM Studio
    config = AIConfig(
        provider="lmstudio",
        model="local-model",
        base_url="http://localhost:1234/v1",
    )
    browser.add_provider("lmstudio", LMStudioProvider(config))

    await browser.start()

    # Navigate and extract
    await browser.execute_command("Go to example.com")
    result = await browser.chat("What is on this page?")
    print(result)

    await browser.stop()

asyncio.run(automate())
```

### Custom AI Provider

You can add any OpenAI-compatible API:

```python
# For Ollama
config = AIConfig(
    provider="ollama",
    model="llama3.2",
    base_url="http://localhost:11434/v1",
)

# For LocalAI
config = AIConfig(
    provider="localai",
    model="gpt-3.5-turbo",
    base_url="http://localhost:8080/v1",
)
```

### Automation Scripts

Create a daily news aggregator:

```python
async def daily_news():
    browser = AIBrowser()
    # ... setup ...

    await browser.execute_command("Go to news.ycombinator.com")
    hn_summary = await browser.chat("Summarize top 5 stories")

    await browser.execute_command("newtab reddit.com/r/programming")
    reddit_summary = await browser.chat("What are people discussing?")

    return {
        "hacker_news": hn_summary,
        "reddit": reddit_summary
    }
```

## Keyboard Shortcuts (Planned)

- `Ctrl+T` - New tab
- `Ctrl+W` - Close tab
- `Ctrl+Tab` - Next tab
- `Ctrl+Shift+Tab` - Previous tab
- `Ctrl+L` - Focus address bar
- `Ctrl+R` - Reload
- `Ctrl+F` - Find in page
- `Alt+Left` - Back
- `Alt+Right` - Forward

## Comparison with Other Browsers

| Feature | AI Browser | Chrome | Firefox | Browser Use |
|---------|-----------|---------|---------|-------------|
| Local AI (LM Studio) | ✅ | ❌ | ❌ | ❌ |
| Cloud AI | ✅ | ❌ | ❌ | ✅ |
| Multiple Tabs | ✅ | ✅ | ✅ | ✅ |
| Bookmarks | ✅ | ✅ | ✅ | ❌ |
| History | ✅ | ✅ | ✅ | ❌ |
| Natural Language | ✅ | ❌ | ❌ | ✅ |
| Complete Privacy | ✅ | ❌ | ❌ | ❌ |
| Offline AI | ✅ | ❌ | ❌ | ❌ |
| Open Source | ✅ | ❌ | ✅ | ❌ |

## Roadmap

### v2.0 (Next)
- [ ] Tab groups
- [ ] Session restore
- [ ] Extensions system
- [ ] Download manager UI
- [ ] Password manager
- [ ] Form autofill
- [ ] Reader mode
- [ ] Dark theme

### v3.0 (Future)
- [ ] Multi-window support
- [ ] Sync across devices
- [ ] Mobile version
- [ ] Voice commands
- [ ] Developer tools
- [ ] Custom CSS injection
- [ ] Ad blocker
- [ ] Cookie management

## Why LM Studio?

1. **Privacy** - Everything runs on your computer
2. **Free** - No API costs
3. **Fast** - Local inference is quick
4. **Offline** - Works without internet
5. **Customizable** - Use any model you want
6. **No Limits** - Unlimited usage

## Contributing

Contributions welcome! Areas needing help:

- Vision support for LM Studio (LLaVA models)
- Better CSS selectors for clicking
- Session management
- Extension system
- UI improvements

## Troubleshooting

### "No AI providers configured"

Make sure LM Studio is running:
1. Open LM Studio
2. Load a model
3. Start local server (http://localhost:1234)
4. Run browser again

### "Error connecting to LM Studio"

```bash
# Test connection
curl http://localhost:1234/v1/models

# Should return JSON with available models
```

### Tab Issues

- Can't close last tab: This is intentional (browser needs at least one tab)
- Tab switching slow: Close unused tabs or use a faster model

### History Not Saving

Check permissions:
```bash
ls -la ~/.ai_browser/
# Should show history.db, bookmarks.json, settings.json
```

### Commands Not Working

Try chat mode instead:
```
> chat: go to reddit.com
```

Or be more explicit:
```
> Navigate to https://reddit.com
```

## FAQ

**Q: Do I need API keys?**
A: No! Just use LM Studio (free, local AI)

**Q: Which AI model is best?**
A: Llama 3.2 3B for speed, Mistral 7B for quality

**Q: Can it run offline?**
A: Yes, with LM Studio

**Q: Does it support vision?**
A: Not yet with LM Studio, but yes with Claude/GPT-4

**Q: How much RAM do I need?**
A: 8GB for 3B models, 16GB for 7B models

**Q: Is my browsing history private?**
A: Yes, everything is stored locally on your computer

**Q: Can I use other local AI tools?**
A: Yes! Works with Ollama, LocalAI, or any OpenAI-compatible API

## License

MIT

## Credits

- Built with Playwright for browser automation
- Uses LM Studio for local AI
- Inspired by Chrome, Browser Use, and Anthropic's Claude

## Links

- LM Studio: https://lmstudio.ai/
- Playwright: https://playwright.dev/
- Report Issues: https://github.com/Moses2917/ai-browser/issues

---

**Made with AI-powered browsing in mind** 🚀
