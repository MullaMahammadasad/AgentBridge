import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


async def main():
    username = get_required_env("HEROKU_LOGIN_USERNAME")
    password = get_required_env("HEROKU_LOGIN_PASSWORD")

    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.navigate("https://the-internet.herokuapp.com/login")

        await b.type("#username", username)
        await b.type("#password", password)
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