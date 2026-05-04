import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.navigate("https://the-internet.herokuapp.com/login")

        # Fill login form (valid demo creds for this site)
        await b.type("#username", "tomsmith")
        await b.type("#password", "SuperSecretPassword!")
        await b.click('button[type="submit"]')

        # Wait for flash message and extract it
        await b.wait_for("#flash", timeout=8000)

        r = await b.extract(
            {
                "url": {"css": "body", "attr": "data-url"},  # will likely be None; just shows attr extraction
                "flash": "#flash",
                "logout_button": {"css": "a.button", "all": False},
            }
        )

        print("success:", r["success"])
        print("flash:", r["action_result"]["extracted"]["flash"])

        # Screenshot for proof
        shot = await b.screenshot(full_page=True)
        print("screenshot_b64_len:", len(shot["action_result"]["screenshot"]))

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())