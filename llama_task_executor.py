"""
Llama-Powered Task Executor for JSON Browser
Uses Ollama (local Llama) to understand natural language tasks and execute them
"""

import requests
import json
import time
import sys
from typing import List, Dict, Any

# Configuration
BROWSER_API_URL = "http://127.0.0.1:8000"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b-instruct"

class LlamaTaskExecutor:
    """Execute tasks on JSON Browser using Llama for natural language understanding"""
    
    def __init__(self):
        self.browser_api = BROWSER_API_URL
        self.ollama_api = OLLAMA_API_URL
        self.model = OLLAMA_MODEL
        self.session = requests.Session()
        
    def check_services(self) -> bool:
        """Check if both services are running"""
        try:
            # Check Browser Service
            resp = self.session.get(f"{self.browser_api}/health", timeout=2)
            if resp.status_code != 200:
                print("❌ Browser Service not responding")
                return False
            print("✅ Browser Service: OK")
        except Exception as e:
            print(f"❌ Browser Service Error: {e}")
            return False
        
        try:
            # Check Ollama Service
            resp = self.session.post(
                f"{self.ollama_api}",
                json={"model": self.model, "prompt": "test", "stream": False},
                timeout=5
            )
            if resp.status_code != 200:
                print("❌ Ollama Service not responding")
                return False
            print(f"✅ Ollama Service: OK (Model: {self.model})")
        except Exception as e:
            print(f"❌ Ollama Service Error: {e}")
            return False
        
        return True
    
    def ask_llama(self, task: str) -> List[Dict[str, Any]]:
        """Ask Llama to generate browser actions from a task description"""
        
        prompt = f"""You are a web automation expert. Convert this task into JSON actions for a browser control system.

IMPORTANT RULES:
1. Always ensure URLs start with 'https://' or 'http://'
2. Use only valid CSS selectors
3. Return ONLY the JSON array, no other text
4. Keep responses concise
5. For link extraction, use selector 'a'
6. For text input, use 'text' parameter (not 'value')
7. For text patterns, use appropriate CSS selectors
8. Add wait_for actions before typing to ensure elements are ready
9. Use wait_for with timeout 10000 for elements that need loading time

Available actions:
- navigate: navigate to a URL
- wait_for: wait for an element to be visible (timeout in ms, default 5000)
- click: click an element by CSS selector
- type: type text in an element by CSS selector (use 'text' key)
- extract: extract data using CSS selectors as patterns
- screenshot: take a screenshot of current page
- create_tab: create a new browser tab
- list_tabs: list all open tabs
- switch_mode: switch between 'fresh' and 'persistent' modes
- get_mode: get current browser mode

Task: {task}

Generate a JSON action list. Examples:

For "navigate to google.com and search for python":
[
  {{"action": "navigate", "params": {{"url": "https://google.com"}}}},
  {{"action": "wait_for", "params": {{"selector": "input[name='q']", "timeout": 10000}}}},
  {{"action": "type", "params": {{"selector": "input[name='q']", "text": "python"}}}},
  {{"action": "click", "params": {{"selector": "button[type='submit']"}}}}
]

For "navigate to example.com":
[
  {{"action": "navigate", "params": {{"url": "https://example.com"}}}}
]

For "take a screenshot":
[
  {{"action": "screenshot", "params": {{}}}}
]

For "extract all links from current page":
[
  {{"action": "extract", "params": {{"patterns": {{"links": "a"}}}}}}
]

For "create 3 new tabs":
[
  {{"action": "create_tab", "params": {{}}}},
  {{"action": "create_tab", "params": {{}}}},
  {{"action": "create_tab", "params": {{}}}}
]

Generate actions for task: {task}
Return ONLY valid JSON array:"""

        print(f"🤖 {self.model} is thinking...", end="", flush=True)
        
        try:
            response = self.session.post(
                self.ollama_api,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"\n❌ Ollama Error: {response.status_code}")
                return []
            
            result = response.json()
            response_text = result.get("response", "").strip()
            print(" ✓")
            
            # Extract JSON from response
            try:
                # Try to find JSON array in response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    actions = json.loads(json_str)
                    
                    # Validate and fix common issues
                    if isinstance(actions, list):
                        for action in actions:
                            # Fix URLs without protocol
                            if action.get("action") == "navigate":
                                url = action.get("params", {}).get("url", "")
                                if url and not url.startswith(("http://", "https://")):
                                    action["params"]["url"] = f"https://{url}"
                            
                            # Fix type action - normalize 'value' to 'text'
                            if action.get("action") == "type":
                                params = action.get("params", {})
                                if "value" in params and "text" not in params:
                                    params["text"] = params.pop("value")
                        
                        return actions
            except json.JSONDecodeError as e:
                print(f"⚠️  Could not parse JSON: {e}")
                print(f"   Response: {response_text[:100]}...")
                return []
        
        except requests.Timeout:
            print("\n❌ Ollama timeout - model may be too large or slow")
            return []
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return []
    
    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single browser action"""
        
        action_type = action.get("action", "unknown")
        params = action.get("params", {})
        
        # Map action to endpoint
        action_map = {
            "navigate": ("POST", "/navigate", params),
            "click": ("POST", "/click", params),
            "type": ("POST", "/type", params),
            "extract": ("POST", "/extract", params),
            "screenshot": ("POST", "/screenshot", {}),
            "create_tab": ("POST", "/tabs/create", {}),
            "list_tabs": ("GET", "/tabs/list", {}),
            "switch_mode": ("POST", "/chromium/mode/switch", params),
            "get_mode": ("GET", "/chromium/mode", {}),
            "wait_for": ("POST", "/wait_for", params),
        }
        
        if action_type not in action_map:
            return {"success": False, "error": f"Unknown action: {action_type}"}
        
        method, endpoint, body = action_map[action_type]
        url = f"{self.browser_api}{endpoint}"
        
        try:
            # Use longer timeout for screenshot
            timeout = 30 if action_type == "screenshot" else 15
            
            if method == "GET":
                resp = self.session.get(url, timeout=timeout)
            else:
                resp = self.session.post(url, json=body, timeout=timeout)
            
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_task(self, task: str) -> None:
        """Execute a full task"""
        print(f"\n{'='*60}")
        print(f"🎯 Task: {task}")
        print(f"{'='*60}\n")
        
        # Get actions from Llama
        actions = self.ask_llama(task)
        
        if not actions:
            print("❌ No actions generated")
            return
        
        print(f"✅ Generated {len(actions)} action(s):")
        for i, action in enumerate(actions, 1):
            print(f"   {i}. {action.get('action', 'unknown')} {action.get('params', {})}")
        
        print(f"\n🚀 Executing actions...\n")
        
        # Execute each action
        for i, action in enumerate(actions, 1):
            action_type = action.get("action", "unknown")
            params = action.get("params", {})
            
            print(f"[{i}/{len(actions)}] → Executing: {action_type}")
            
            # Add context
            if action_type == "navigate":
                print(f"   📍 Navigating to: {params.get('url')}")
            elif action_type == "click":
                print(f"   🖱️  Clicking: {params.get('selector')}")
            elif action_type == "type":
                print(f"   ⌨️  Typing '{params.get('text')}' in: {params.get('selector')}")
            elif action_type == "extract":
                print(f"   📊 Extracting data...")
            elif action_type == "screenshot":
                print(f"   📸 Taking screenshot (may take a moment)...")
            elif action_type == "switch_mode":
                print(f"   🔄 Switching to: {params.get('mode')} mode")
            elif action_type == "get_mode":
                print(f"   ℹ️  Getting current mode...")
            elif action_type == "wait_for":
                print(f"   ⏳ Waiting for: {params.get('selector')}")
            
            # Execute
            result = self.execute_action(action)
            
            if result.get("success", False):
                print(f"   ✅ Success")
                
                # Show extracted data if available
                if action_type == "extract" and "action_result" in result:
                    extracted = result["action_result"].get("extracted", {})
                    if extracted:
                        print(f"   📄 Extracted:")
                        for key, value in extracted.items():
                            if isinstance(value, str) and len(value) > 50:
                                print(f"      {key}: {value[:50]}...")
                            elif isinstance(value, list):
                                print(f"      {key}: {len(value)} items")
                            else:
                                print(f"      {key}: {value}")
                    else:
                        print(f"   (No data extracted)")
                
                # Show tab count if available
                if action_type == "list_tabs" and "action_result" in result:
                    tabs = result["action_result"].get("tabs", [])
                    print(f"   📑 Tabs: {len(tabs)}")
                    for tab in tabs:
                        print(f"      - {tab.get('id')}: {tab.get('url')}")
                
                # Show URL if navigated
                if action_type == "navigate" and "browser_state" in result:
                    url = result["browser_state"].get("url", "")
                    title = result["browser_state"].get("title", "")
                    if url:
                        print(f"      URL: {url}")
                    if title:
                        print(f"      Title: {title}")
                
                # Show current mode
                if action_type == "get_mode" and "active_mode" in result:
                    print(f"      Mode: {result.get('active_mode')}")
            else:
                error = result.get("error", "Unknown error")
                print(f"   ❌ Failed: {error}")
            
            print()
        
        print(f"{'='*60}")
        print(f"✅ Task completed!")
        print(f"{'='*60}\n")
    
    def interactive_mode(self) -> None:
        """Interactive task entry mode"""
        print("\n" + "="*60)
        print("🤖 Llama Task Executor - Interactive Mode")
        print("="*60)
        print("\nGive commands in natural language:")
        print("  'navigate to google.com and search for python'")
        print("  'take a screenshot'")
        print("  'extract all links'")
        print("  'create 3 new tabs'")
        print("  'switch to persistent mode'")
        print("  'quit' to exit\n")
        
        while True:
            try:
                task = input("🎯 Your task: ").strip()
                
                if task.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not task:
                    continue
                
                self.execute_task(task)
            
            except KeyboardInterrupt:
                print("\n👋 Interrupted")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def run_examples(self) -> None:
        """Run example tasks"""
        examples = [
            "Navigate to example.com",
            "Extract all links from the page",
            "Create 3 new tabs",
            "Switch to persistent mode",
            "Get current browser mode",
            "List all open tabs",
        ]
        
        print("\n" + "="*60)
        print("🤖 Running Example Tasks")
        print("="*60)
        
        for i, task in enumerate(examples, 1):
            self.execute_task(task)
            if i < len(examples):
                print("⏳ Waiting before next example...\n")
                time.sleep(2)


def main():
    executor = LlamaTaskExecutor()
    
    print("\n" + "="*60)
    print("🤖 Llama Task Executor for JSON Browser")
    print("="*60 + "\n")
    
    # Check services
    if not executor.check_services():
        print("\n❌ Services not available. Please ensure:")
        print("   1. Browser Service: python json_browser_service.py")
        print("   2. Ollama: ollama serve")
        sys.exit(1)
    
    print()
    
    # Run mode
    if len(sys.argv) > 1 and sys.argv[1] == "examples":
        executor.run_examples()
    else:
        executor.interactive_mode()


if __name__ == "__main__":
    main()
