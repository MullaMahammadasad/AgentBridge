"""
Example: Calling JSON Browser Service via REST API
"""

import requests
import time
from typing import Dict, Any

SERVICE_URL = "http://localhost:5001"


def api_call(method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict[str, Any]:
    """Make API call to service"""
    url = f"{SERVICE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return {"error": str(e)}


def example_navigation():
    """Navigate and extract"""
    print("\n📱 Navigation Example:\n")
    
    print("1. Navigate to example.com...")
    result = api_call("POST", "/navigate", {"url": "https://example.com"})
    print(f"   ✓ Status: {result['success']}")
    print(f"   URL: {result['browser_state']['url']}")
    
    print("\n2. Take screenshot...")
    result = api_call("POST", "/screenshot")
    if result['success']:
        print(f"   ✓ Screenshot: {len(result['action_result']['screenshot'])} bytes")


def example_tab_management():
    """Manage tabs"""
    print("\n📑 Tab Management Example:\n")
    
    print("1. List current tabs...")
    result = api_call("GET", "/tabs/list")
    print(f"   ✓ Tabs: {len(result['action_result']['tabs'])}")
    
    print("\n2. Create new tab...")
    result = api_call("POST", "/tabs/create")
    new_tab_id = result['action_result']['page_id']
    print(f"   ✓ Created: {new_tab_id}")
    
    print("\n3. Navigate in new tab...")
    result = api_call("POST", "/navigate", {"url": "https://google.com"})
    print(f"   ✓ URL: {result['browser_state']['url']}")
    
    print("\n4. List tabs...")
    result = api_call("GET", "/tabs/list")
    print(f"   ✓ Total: {len(result['action_result']['tabs'])} tabs")


def example_mode_switching():
    """Switch between fresh and persistent"""
    print("\n🔄 Mode Switching Example:\n")
    
    print("1. Get current mode...")
    result = api_call("GET", "/chromium/mode")
    print(f"   ✓ Active: {result['active_mode']}")
    
    print("\n2. Switch to persistent...")
    result = api_call("POST", "/chromium/mode/switch", {"mode": "persistent"})
    print(f"   ✓ Switched: {result['old_mode']} → {result['new_mode']}")


def example_health():
    """Health check"""
    print("\n❤️  Health Check:\n")
    
    result = api_call("GET", "/health")
    if result['success'] or 'status' in result:
        print(f"   ✓ Status: {result.get('status', 'unknown')}")
        print(f"   Active Mode: {result.get('active_mode', 'unknown')}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("JSON BROWSER - REST API CLIENT EXAMPLES")
    print("="*60)
    print("\n⚠️  Make sure service is running:")
    print("   python json_browser_service.py\n")
    
    example_health()
    example_navigation()
    example_tab_management()
    example_mode_switching()
    
    print("\n" + "="*60)
    print("✓ All examples completed")
    print("="*60 + "\n")