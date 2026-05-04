import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.navigate("http://127.0.0.1:8000/")

        # Alerts
        await b.auto_accept_dialogs()

        # Login admin/admin
        await b.type("#username", "admin")
        await b.type("#password", "admin")
        await b.click("#loginBtn")

        login = await b.extract({"login_result": "#loginResult"})
        print("login_result:", login["action_result"]["extracted"]["login_result"])

        # Dynamic load
        await b.click("#loadBtn")
        wait = await b.wait_for_text("#dynamic", "Loaded!", timeout=6000)
        print("dynamic_loaded:", wait["action_result"]["matched"])

        # Dropdown
        await b.select("#choice", "two")
        choice = await b.extract({"choice_out": "#choiceOut"})
        print("choice_out:", choice["action_result"]["extracted"]["choice_out"])

        # Alert button (auto-accept)
        await b.click("#alertBtn")
        print("alert clicked (should auto-accept)")

        # Screenshot
        shot = await b.screenshot(full_page=True)
        print("screenshot_b64_len:", len(shot["action_result"]["screenshot"]))

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())