"""
Example: Using JSON Browser as a library (direct import)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from json_browser import JSONBrowser


async def example_basic():
    """Basic example"""
    browser = JSONBrowser(mode="fresh", headless=False)

    try:
        await browser.initialize()
        print("✓ Browser initialized")

        # Navigate
        response = await browser.navigate("https://example.com")
        print(f"✓ Navigated: {response['success']}")
        print(f"  URL: {response['browser_state']['url']}")

        # Take screenshot (base64 string)
        screenshot = await browser.screenshot()
        b64 = screenshot["action_result"]["screenshot"]
        print(f"✓ Screenshot: {len(b64)} base64 chars")

    finally:
        await browser.shutdown()


async def example_multi_tab():
    """Multi-tab example"""
    browser = JSONBrowser(mode="persistent", headless=False)

    try:
        await browser.initialize()
        print("\n📑 Tab Management Example:\n")

        # Navigate on tab 1
        await browser.navigate("https://example.com")
        tabs1 = await browser.list_tabs()
        print(f"✓ Tabs after first nav: {len(tabs1['action_result']['tabs'])}")

        # Create tab 2
        created = await browser.create_tab()
        tab2_id = created["action_result"]["id"]
        print(f"✓ Created tab 2: {tab2_id}")

        # Navigate on tab 2
        await browser.navigate("https://www.iana.org/domains/reserved")
        state2 = await browser.get_state()
        print(f"✓ Tab 2 URL: {state2['browser_state']['url']}")

        # Switch back to tab 1 (page_0)
        await browser.switch_tab("page_0")
        state1 = await browser.get_state()
        print(f"✓ Switched back to tab 1 URL: {state1['browser_state']['url']}")

    finally:
        await browser.shutdown()


async def example_extract():
    """Data extraction example (REAL extraction)"""
    browser = JSONBrowser(mode="fresh", headless=False)

    try:
        await browser.initialize()
        print("\n📊 Data Extraction Example:\n")

        await browser.navigate("https://example.com")

        result = await browser.extract(
            {
                "title": "h1",
                "all_paragraphs": {"css": "p", "all": True},
                "first_link": {"css": "a", "attr": "href"},
                "all_links": {"css": "a", "attr": "href", "all": True},
            }
        )

        print("✓ Extract success:", result["success"])
        print("Extracted:")
        print(result["action_result"]["extracted"])

    finally:
        await browser.shutdown()


async def main():
    print("\n" + "=" * 60)
    print("JSON BROWSER - LIBRARY MODE EXAMPLES")
    print("=" * 60)

    print("\n📝 Basic Example:\n")
    await example_basic()

    print("\n" + "-" * 60)
    await example_multi_tab()

    print("\n" + "-" * 60)
    await example_extract()

    print("\n" + "=" * 60)
    print("✓ All examples completed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())