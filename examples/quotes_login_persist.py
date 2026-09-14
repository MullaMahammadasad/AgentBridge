import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


async def main():
    username = get_required_env("QUOTES_LOGIN_USERNAME")
    password = get_required_env("QUOTES_LOGIN_PASSWORD")
    profile_dir = str((Path("profiles") / "quotes_profile").absolute())

    b = JSONBrowser(headless=False)
    await b.initialize(user_data_dir=profile_dir)

    try:
        await b.navigate("https://quotes.toscrape.com/login")

        await b.type('input[name="username"]', username)
        await b.type('input[name="password"]', password)
        await b.click('input[type="submit"]')

        # After login, Logout link appears
        await b.wait_for('a[href="/logout"]', timeout=10000)

        r = await b.extract({"logout": 'a[href="/logout"]'})
        print("Logged in, logout link text:", r["action_result"]["extracted"]["logout"])

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())