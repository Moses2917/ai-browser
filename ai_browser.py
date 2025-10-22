#!/usr/bin/env python3
"""
AI Browser - A custom browser that connects to multiple AI providers
Supports vision-capable models and natural language commands
"""

import os
import sys
import json
import base64
import asyncio
import re
from typing import Optional, Dict, List, Any, Literal
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from io import BytesIO

try:
    from playwright.async_api import async_playwright, Page, Browser
    import anthropic
    import openai
    from PIL import Image
except ImportError as e:
    print(f"Missing dependencies. Install with:")
    print(f"pip install playwright anthropic openai Pillow")
    print(f"playwright install chromium")
    sys.exit(1)


@dataclass
class AIConfig:
    """Configuration for AI providers"""
    provider: str
    model: str
    api_key: str
    supports_vision: bool = False
    supports_thinking: bool = False
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class PageContext:
    """Current page context"""
    url: str = ""
    title: str = ""
    content: str = ""
    screenshot: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "content_preview": self.content[:500] if self.content else ""
        }


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
                             page_context: PageContext) -> Dict[str, Any]:
        """Execute a natural language command"""
        pass


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider with vision support"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message to Claude"""

        # Convert messages format if needed
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue  # System messages handled separately

            content = []
            if isinstance(msg["content"], str):
                content = [{"type": "text", "text": msg["content"]}]
            else:
                content = msg["content"]

            # Add screenshot if vision is supported
            if screenshot and self.config.supports_vision and msg["role"] == "user":
                # Encode image
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

        # Extract system message
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

    async def execute_command(self, command: str,
                             page_context: PageContext) -> Dict[str, Any]:
        """Execute a natural language command using Claude"""

        system_prompt = """You are an AI browser assistant. You can control a web browser and help users navigate and interact with web pages.

Available actions:
- navigate(url): Go to a URL
- click(selector): Click an element (use CSS selector)
- type(selector, text): Type text into an input field
- scroll(direction): Scroll up or down
- read(): Read the current page content
- screenshot(): Take a screenshot
- extract(query): Extract specific information from the page
- search(query): Search for text on the page

When given a command, respond with a JSON object containing:
{
  "action": "action_name",
  "parameters": {...},
  "explanation": "What you're doing"
}

For complex commands that require multiple steps, return an array of action objects.

Examples:
User: "Go to reddit.com"
Response: {"action": "navigate", "parameters": {"url": "https://reddit.com"}, "explanation": "Navigating to Reddit"}

User: "Read the top post"
Response: [
  {"action": "navigate", "parameters": {"url": "https://reddit.com"}, "explanation": "Going to Reddit"},
  {"action": "click", "parameters": {"selector": "div[data-testid='post-container']:first-child"}, "explanation": "Clicking the first post"},
  {"action": "read", "parameters": {}, "explanation": "Reading the post content"}
]

Current page context:
URL: {url}
Title: {title}
"""

        messages = [
            {
                "role": "user",
                "content": f"Current page: {page_context.url}\nTitle: {page_context.title}\n\nCommand: {command}"
            }
        ]

        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=2000,
            system=system_prompt.format(
                url=page_context.url,
                title=page_context.title
            ),
            messages=messages
        )

        response_text = response.content[0].text

        # Parse JSON response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "action": "error",
                    "explanation": f"Could not parse command. AI response: {response_text}"
                }
        except json.JSONDecodeError:
            return {
                "action": "error",
                "explanation": f"Invalid JSON response: {response_text}"
            }


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider with vision support"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(api_key=config.api_key)

    async def chat(self, messages: List[Dict[str, Any]],
                   screenshot: Optional[bytes] = None) -> str:
        """Send chat message to GPT"""

        formatted_messages = []
        for msg in messages:
            content = msg["content"] if isinstance(msg["content"], str) else msg["content"]

            # Add screenshot for vision models
            if screenshot and self.config.supports_vision and msg["role"] == "user":
                image_data = base64.b64encode(screenshot).decode('utf-8')
                content = [
                    {"type": "text", "text": content if isinstance(content, str) else content[0]["text"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    }
                ]

            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=formatted_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )

        return response.choices[0].message.content

    async def execute_command(self, command: str,
                             page_context: PageContext) -> Dict[str, Any]:
        """Execute a natural language command using GPT"""

        system_prompt = """You are an AI browser assistant. You can control a web browser and help users navigate and interact with web pages.

Available actions:
- navigate(url): Go to a URL
- click(selector): Click an element (use CSS selector)
- type(selector, text): Type text into an input field
- scroll(direction): Scroll up or down
- read(): Read the current page content
- screenshot(): Take a screenshot
- extract(query): Extract specific information from the page

Respond ONLY with valid JSON containing the action(s) to take."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Current page: {page_context.url}\nTitle: {page_context.title}\n\nCommand: {command}\n\nRespond with JSON action(s)."
            }
        ]

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )

        response_text = response.choices[0].message.content

        try:
            json_match = re.search(r'\{.*\}|\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "action": "error",
                    "explanation": f"Could not parse command: {response_text}"
                }
        except json.JSONDecodeError:
            return {
                "action": "error",
                "explanation": f"Invalid JSON response: {response_text}"
            }


class BrowserAutomation:
    """Browser automation using Playwright"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start(self, headless: bool = False):
        """Start the browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        # Set viewport size
        await self.page.set_viewport_size({"width": 1920, "height": 1080})

    async def stop(self):
        """Stop the browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str) -> PageContext:
        """Navigate to a URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        await self.page.goto(url, wait_until="networkidle", timeout=30000)
        return await self.get_page_context()

    async def click(self, selector: str):
        """Click an element"""
        await self.page.click(selector, timeout=10000)
        await self.page.wait_for_load_state("networkidle")

    async def type_text(self, selector: str, text: str):
        """Type text into an input"""
        await self.page.fill(selector, text)

    async def scroll(self, direction: str = "down", amount: int = 500):
        """Scroll the page"""
        if direction == "down":
            await self.page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            await self.page.evaluate(f"window.scrollBy(0, -{amount})")

    async def get_content(self) -> str:
        """Get page text content"""
        return await self.page.evaluate("""() => {
            return document.body.innerText;
        }""")

    async def get_screenshot(self) -> bytes:
        """Take a screenshot"""
        screenshot = await self.page.screenshot(full_page=False, type="png")

        # Compress screenshot for AI processing
        image = Image.open(BytesIO(screenshot))
        # Resize if too large
        max_size = (1280, 720)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format='PNG', optimize=True)
        return output.getvalue()

    async def get_page_context(self) -> PageContext:
        """Get current page context"""
        context = PageContext()
        context.url = self.page.url
        context.title = await self.page.title()
        context.content = await self.get_content()
        context.screenshot = await self.get_screenshot()
        return context

    async def extract_links(self) -> List[Dict[str, str]]:
        """Extract all links from the page"""
        return await self.page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links.map(link => ({
                text: link.innerText.trim(),
                href: link.href
            })).filter(link => link.text && link.href);
        }""")

    async def search_text(self, query: str) -> List[str]:
        """Search for text on the page"""
        content = await self.get_content()
        lines = content.split('\n')
        return [line for line in lines if query.lower() in line.lower()]


class AIBrowser:
    """Main AI Browser class"""

    def __init__(self):
        self.browser = BrowserAutomation()
        self.ai_providers: Dict[str, AIProvider] = {}
        self.current_provider: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.page_context = PageContext()

    def add_provider(self, name: str, provider: AIProvider):
        """Add an AI provider"""
        self.ai_providers[name] = provider
        if not self.current_provider:
            self.current_provider = name

    def set_provider(self, name: str):
        """Set the active AI provider"""
        if name in self.ai_providers:
            self.current_provider = name
            print(f"Switched to {name}")
        else:
            print(f"Provider {name} not found. Available: {list(self.ai_providers.keys())}")

    async def start(self, headless: bool = False):
        """Start the browser"""
        await self.browser.start(headless=headless)
        print("Browser started!")

    async def stop(self):
        """Stop the browser"""
        await self.browser.stop()
        print("Browser stopped!")

    async def execute_action(self, action: Dict[str, Any]) -> str:
        """Execute a browser action"""
        action_type = action.get("action")
        params = action.get("parameters", {})
        explanation = action.get("explanation", "")

        if explanation:
            print(f"  → {explanation}")

        try:
            if action_type == "navigate":
                self.page_context = await self.browser.navigate(params["url"])
                return f"Navigated to {self.page_context.url}"

            elif action_type == "click":
                await self.browser.click(params["selector"])
                self.page_context = await self.browser.get_page_context()
                return f"Clicked {params['selector']}"

            elif action_type == "type":
                await self.browser.type_text(params["selector"], params["text"])
                return f"Typed '{params['text']}' into {params['selector']}"

            elif action_type == "scroll":
                direction = params.get("direction", "down")
                await self.browser.scroll(direction)
                return f"Scrolled {direction}"

            elif action_type == "read":
                content = await self.browser.get_content()
                # Return first 2000 chars
                preview = content[:2000] + "..." if len(content) > 2000 else content
                return f"Page content:\n{preview}"

            elif action_type == "screenshot":
                screenshot = await self.browser.get_screenshot()
                return f"Screenshot taken ({len(screenshot)} bytes)"

            elif action_type == "extract":
                query = params.get("query", "")
                results = await self.browser.search_text(query)
                return f"Found {len(results)} matches:\n" + "\n".join(results[:10])

            elif action_type == "search":
                query = params.get("query", "")
                results = await self.browser.search_text(query)
                return f"Search results:\n" + "\n".join(results[:10])

            else:
                return f"Unknown action: {action_type}"

        except Exception as e:
            return f"Error executing {action_type}: {str(e)}"

    async def execute_command(self, command: str) -> str:
        """Execute a natural language command"""
        if not self.current_provider:
            return "No AI provider configured!"

        provider = self.ai_providers[self.current_provider]

        print(f"\nProcessing command with {self.current_provider}...")

        # Get command plan from AI
        actions = await provider.execute_command(command, self.page_context)

        # Handle both single action and multiple actions
        if isinstance(actions, dict):
            actions = [actions]

        results = []
        for action in actions:
            if action.get("action") == "error":
                results.append(action.get("explanation", "Unknown error"))
            else:
                result = await self.execute_action(action)
                results.append(result)

        return "\n".join(results)

    async def chat(self, message: str, include_vision: bool = True) -> str:
        """Chat with AI about the current page"""
        if not self.current_provider:
            return "No AI provider configured!"

        provider = self.ai_providers[self.current_provider]

        # Add context about current page
        context_msg = f"""Current page context:
URL: {self.page_context.url}
Title: {self.page_context.title}

Content preview:
{self.page_context.content[:1000] if self.page_context.content else 'No content'}

User: {message}"""

        self.conversation_history.append({
            "role": "user",
            "content": context_msg
        })

        # Get screenshot if vision is supported
        screenshot = None
        if include_vision and provider.config.supports_vision and self.page_context.screenshot:
            screenshot = self.page_context.screenshot

        response = await provider.chat(self.conversation_history, screenshot)

        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        # Keep conversation history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        return response

    async def interactive_mode(self):
        """Run interactive command mode"""
        print("\n" + "="*60)
        print("AI BROWSER - Interactive Mode")
        print("="*60)
        print(f"\nActive AI: {self.current_provider}")
        print(f"Available providers: {list(self.ai_providers.keys())}")
        print("\nCommands:")
        print("  - Type naturally: 'Go to reddit.com'")
        print("  - Chat about page: 'chat: What is this page about?'")
        print("  - Switch AI: 'use: provider_name'")
        print("  - Quit: 'quit' or 'exit'")
        print("\n" + "="*60 + "\n")

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                # Switch provider
                if user_input.lower().startswith('use:'):
                    provider_name = user_input[4:].strip()
                    self.set_provider(provider_name)
                    continue

                # Chat mode
                if user_input.lower().startswith('chat:'):
                    message = user_input[5:].strip()
                    response = await self.chat(message)
                    print(f"\n{self.current_provider}: {response}")
                    continue

                # Execute as command
                result = await self.execute_command(user_input)
                print(f"\n{result}")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                print(f"\nError: {str(e)}")


async def main():
    """Main function"""
    print("Initializing AI Browser...")

    # Initialize browser
    browser = AIBrowser()

    # Configure AI providers
    # You can add multiple providers here

    # Anthropic Claude (with vision)
    claude_api_key = os.getenv("ANTHROPIC_API_KEY")
    if claude_api_key:
        claude_config = AIConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",  # Latest with vision
            api_key=claude_api_key,
            supports_vision=True,
            supports_thinking=True,
            max_tokens=4096
        )
        browser.add_provider("claude", AnthropicProvider(claude_config))
        print("✓ Claude configured")

    # OpenAI GPT-4 Vision
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        gpt4v_config = AIConfig(
            provider="openai",
            model="gpt-4o",  # GPT-4 with vision
            api_key=openai_api_key,
            supports_vision=True,
            max_tokens=4096
        )
        browser.add_provider("gpt4", OpenAIProvider(gpt4v_config))
        print("✓ GPT-4 configured")

    # OpenAI o1 (thinking model, no vision)
    if openai_api_key:
        o1_config = AIConfig(
            provider="openai",
            model="o1-preview",
            api_key=openai_api_key,
            supports_vision=False,
            supports_thinking=True,
            max_tokens=4096
        )
        browser.add_provider("o1", OpenAIProvider(o1_config))
        print("✓ OpenAI o1 configured")

    if not browser.ai_providers:
        print("\nError: No AI providers configured!")
        print("Set environment variables:")
        print("  export ANTHROPIC_API_KEY='your-key'")
        print("  export OPENAI_API_KEY='your-key'")
        return

    # Start browser (headless=False to see the browser)
    await browser.start(headless=False)

    try:
        # Run interactive mode
        await browser.interactive_mode()
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
