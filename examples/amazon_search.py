"""
Example: Amazon search workflow
"""

import asyncio
from json_browser import JSONBrowser
from json_browser.logger import get_logger

logger = get_logger(__name__)


async def main():
    browser = JSONBrowser(mode="fresh", headless=False)
    
    try:
        print("\n" + "="*60)
        print("AMAZON SEARCH WORKFLOW")
        print("="*60 + "\n")
        
        await browser.initialize()
        print("✓ Browser initialized\n")
        
        # Step 1: Navigate to Amazon
        print("Step 1: Navigate to Amazon...")
        response = await browser.navigate("https://www.amazon.com")
        print(f"  ✓ Loaded: {response['browser_state']['url']}\n")
        
        # Step 2: Search for product
        print("Step 2: Search for 'gaming laptop'...")
        await browser.type("#twotabsearchtextbox", "gaming laptop")
        await browser.click("button[type='submit']")
        print("  ✓ Searching...\n")
        
        # Wait for results
        await asyncio.sleep(2)
        
        # Step 3: Extract product data
        print("Step 3: Extract product results...")
        response = await browser.extract({
            "titles": "h2 a span",
            "prices": "span.a-price-whole"
        })
        
        if response['success']:
            print(f"  ✓ Found products:")
            data = response['action_result']['extracted']
            if isinstance(data.get('titles'), list):
                for i, title in enumerate(data['titles'][:3], 1):
                    print(f"    {i}. {title}")
        print()
        
        # Step 4: Take screenshot
        print("Step 4: Taking screenshot...")
        response = await browser.screenshot()
        print(f"  ✓ Screenshot: {len(response['action_result']['screenshot'])} bytes\n")
        
        # Step 5: Browser stats
        print("Step 5: Browser statistics:")
        stats = browser.get_stats()
        print(f"  • Requests: {stats['requests']}")
        print(f"  • Errors: {stats['errors']}")
        print(f"  • Active tabs: {stats['active_tabs']}")
        print(f"  • Uptime: {stats['uptime_seconds']}s\n")
        
        print("="*60)
        print("✓ Workflow completed successfully")
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"Workflow error: {e}")
        print(f"\n❌ Error: {e}\n")
    
    finally:
        await browser.shutdown()


if __name__ == "__main__":
    asyncio.run(main())