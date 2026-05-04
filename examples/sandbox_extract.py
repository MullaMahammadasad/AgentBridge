import os
import sys
import asyncio

# Ensure project root is on sys.path when running from /examples
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    b = JSONBrowser(headless=False)  # set True if you don't want to see the browser
    await b.initialize()

    try:
        await b.navigate("http://127.0.0.1:8000/")

        r = await b.extract(
            {
                "title": "#title",
                "login_button": "#loginBtn",
                "all_links": {"css": "a", "all": True},
            }
        )

        print("success:", r["success"])
        print("extracted:", r["action_result"]["extracted"])
    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())