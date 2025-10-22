# AI Browser

A powerful custom browser that connects to multiple AI providers (Claude, GPT-4, OpenAI o1) with vision capabilities and natural language control.

## Features

- **Multi-AI Support**: Connect to multiple AI providers simultaneously
  - Anthropic Claude (with vision and thinking)
  - OpenAI GPT-4o (with vision)
  - OpenAI o1 (advanced thinking, no vision)

- **Vision Capabilities**: AI can see and understand web pages through screenshots

- **Natural Language Commands**: Control the browser with plain English
  - "Go to reddit and read the top post"
  - "Search for Python tutorials"
  - "Click the login button"
  - "What is this page about?"

- **Interactive Chat**: Have conversations with AI about page content

- **Web Automation**: Navigate, click, type, scroll, extract data

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Set API Keys

Set your API keys as environment variables:

```bash
# For Claude
export ANTHROPIC_API_KEY='your-anthropic-key'

# For OpenAI (GPT-4, o1)
export OPENAI_API_KEY='your-openai-key'
```

Or create a `.env` file:

```bash
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
```

## Usage

### Run the Browser

```bash
python ai_browser.py
```

The browser will start in interactive mode with a visible window.

### Commands

#### Natural Language Commands

Just type what you want to do:

```
> Go to reddit.com
> Read the top post
> Search for "Python" on this page
> Click the first link
> Scroll down
```

#### Chat Mode

Ask questions about the current page:

```
> chat: What is this page about?
> chat: Summarize the main article
> chat: What are the comments saying?
```

#### Switch AI Provider

```
> use: claude
> use: gpt4
> use: o1
```

#### Exit

```
> quit
```

## Examples

### Example 1: Browse Reddit

```
> Go to reddit.com and read the top post

Processing command with claude...
  → Navigating to Reddit
  → Clicking the first post
  → Reading the post content

Page content:
TIL that...
[Post content here]
```

### Example 2: Research with AI

```
> Go to news.ycombinator.com

> chat: What are the trending topics today?

claude: Based on the current page, the trending topics are:
1. New AI developments...
2. Web3 discussion...
3. Programming languages...
```

### Example 3: Extract Information

```
> Go to python.org

> chat: Find me the latest Python version

claude: According to the page, the latest Python version is 3.12.0
```

## Architecture

### Components

1. **AIProvider**: Abstract base class for AI integrations
   - `AnthropicProvider`: Claude with vision support
   - `OpenAIProvider`: GPT-4 and o1 models

2. **BrowserAutomation**: Playwright-based browser control
   - Navigate, click, type, scroll
   - Screenshot capture
   - Content extraction

3. **AIBrowser**: Main orchestrator
   - Manages multiple AI providers
   - Executes commands
   - Maintains conversation history
   - Interactive command loop

### How It Works

1. User enters a natural language command
2. AI provider analyzes the command and page context
3. AI generates structured actions (JSON)
4. Browser automation executes the actions
5. Results are returned to the user

### Available Actions

The AI can generate these actions:

- `navigate(url)`: Go to a URL
- `click(selector)`: Click an element
- `type(selector, text)`: Type into a field
- `scroll(direction)`: Scroll the page
- `read()`: Get page content
- `screenshot()`: Capture the page
- `extract(query)`: Find specific information
- `search(query)`: Search for text

## Configuration

### Adding Custom AI Providers

You can add custom AI providers by extending the `AIProvider` class:

```python
class CustomProvider(AIProvider):
    async def chat(self, messages, screenshot=None):
        # Implement chat logic
        pass

    async def execute_command(self, command, page_context):
        # Implement command execution
        pass

# Add to browser
config = AIConfig(
    provider="custom",
    model="custom-model",
    api_key="your-key",
    supports_vision=True
)
browser.add_provider("custom", CustomProvider(config))
```

### Headless Mode

To run without a visible browser window:

```python
await browser.start(headless=True)
```

## Tips

1. **Be Specific**: The more specific your commands, the better results
   - Good: "Go to reddit.com and click the first post in r/programming"
   - Less good: "Go to reddit"

2. **Use Chat for Analysis**: Use chat mode when you want the AI to understand and explain content

3. **Vision Models**: Claude and GPT-4o can see the page, o1 cannot (but has better reasoning)

4. **Switch Models**: Different models have different strengths
   - Claude: Best for complex reasoning and vision
   - GPT-4o: Fast with good vision
   - o1: Advanced reasoning without vision

## Troubleshooting

### Missing Dependencies

```bash
pip install playwright anthropic openai Pillow
playwright install chromium
```

### API Key Errors

Make sure your API keys are set:

```bash
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

### Playwright Issues

If Playwright fails to start:

```bash
playwright install --force chromium
```

### Timeout Errors

Some pages take longer to load. The browser waits up to 30 seconds.

## Advanced Usage

### Programmatic Usage

You can use the browser programmatically:

```python
import asyncio
from ai_browser import AIBrowser, AIConfig, AnthropicProvider

async def automate():
    browser = AIBrowser()

    # Configure AI
    config = AIConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        api_key="your-key",
        supports_vision=True
    )
    browser.add_provider("claude", AnthropicProvider(config))

    # Start browser
    await browser.start()

    # Execute commands
    await browser.execute_command("Go to example.com")
    response = await browser.chat("What is on this page?")
    print(response)

    # Stop browser
    await browser.stop()

asyncio.run(automate())
```

### Custom Automation Scripts

Create your own automation scripts:

```python
async def daily_news():
    browser = AIBrowser()
    # ... setup ...

    await browser.execute_command("Go to news.ycombinator.com")
    summary = await browser.chat("Summarize the top 5 stories")

    await browser.execute_command("Go to reddit.com/r/programming")
    reddit_summary = await browser.chat("What are people discussing?")

    return {
        "hn": summary,
        "reddit": reddit_summary
    }
```

## License

MIT

## Contributing

Feel free to submit issues and pull requests!

## Future Enhancements

- Add more AI providers (Google Gemini, Mistral, etc.)
- Support for multiple tabs
- Session recording/replay
- Custom action plugins
- Voice control
- Multi-modal interactions
