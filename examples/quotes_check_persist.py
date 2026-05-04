import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_browser import JSONBrowser


async def main():
    profile_dir = str((Path("profiles") / "quotes_profile").absolute())

    b = JSONBrowser(headless=False)
    await b.initialize(user_data_dir=profile_dir)

    try:
        await b.navigate("https://quotes.toscrape.com/")

        r = await b.extract({
            "logout": {"css": 'a[href="/logout"]', "all": False},
            "login": {"css": 'a[href="/login"]', "all": False},
        })

        logout_txt = r["action_result"]["extracted"]["logout"]
        login_txt = r["action_result"]["extracted"]["login"]

        if logout_txt:
            print("Session persisted ✅ (found Logout)")
        else:
            print("Session not persisted on this demo site ⚠️ (found Login)")

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())