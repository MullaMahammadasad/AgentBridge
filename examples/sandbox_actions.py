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
    username = get_required_env("SANDBOX_USERNAME")
    password = get_required_env("SANDBOX_PASSWORD")

    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.navigate("http://127.0.0.1:8000/")

        # Alerts
        await b.auto_accept_dialogs()

        await b.type("#username", username)
        await b.type("#password", password)
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