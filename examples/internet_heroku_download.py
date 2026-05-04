import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    downloads_dir = str(Path("downloads").absolute())
    state_path = str(Path("state") / "storage.json")

    b = JSONBrowser(headless=False)
    await b.initialize(storage_state_path=state_path, downloads_dir=downloads_dir)

    try:
        await b.navigate("https://the-internet.herokuapp.com/download")

        # Click first download link
        info = await b.click_and_download("#content a:nth-of-type(1)")
        print("downloaded:", info["action_result"])

        # screenshot for proof
        shot = await b.screenshot(full_page=True)
        print("screenshot_b64_len:", len(shot["action_result"]["screenshot"]))

        # Save state (cookies/localStorage) just to demonstrate
        saved = await b.save_storage_state()
        print("saved_state:", saved["action_result"])

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
