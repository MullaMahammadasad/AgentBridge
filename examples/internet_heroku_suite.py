import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.auto_accept_dialogs()

        results = {}

        # 1) Login
        await b.navigate("https://the-internet.herokuapp.com/login")
        await b.type("#username", "tomsmith")
        await b.type("#password", "SuperSecretPassword!")
        await b.click('button[type="submit"]')
        await b.wait_for("#flash", timeout=8000)
        r = await b.extract({"flash": "#flash"})
        results["login_flash"] = r["action_result"]["extracted"]["flash"]

        # 2) Checkboxes
        await b.navigate("https://the-internet.herokuapp.com/checkboxes")
        # click first checkbox (toggle)
        await b.click("#checkboxes input:nth-of-type(1)")
        r = await b.extract({"title": "h3"})
        results["checkboxes_title"] = r["action_result"]["extracted"]["title"]

        # 3) Dropdown
        await b.navigate("https://the-internet.herokuapp.com/dropdown")
        await b.select("#dropdown", "2")
        # extract selected option text
        r = await b.extract({"selected": "#dropdown option:checked"})
        results["dropdown_selected"] = r["action_result"]["extracted"]["selected"]

        # 4) Dynamic loading (Example 1)
        await b.navigate("https://the-internet.herokuapp.com/dynamic_loading/1")
        await b.click("#start button")
        await b.wait_for("#finish", timeout=15000)
        r = await b.extract({"finish_text": "#finish"})
        results["dynamic_finish_text"] = r["action_result"]["extracted"]["finish_text"]

        # 5) JS Alerts
        await b.navigate("https://the-internet.herokuapp.com/javascript_alerts")
        await b.click('button[onclick="jsAlert()"]')   # auto-accept enabled
        r = await b.extract({"result": "#result"})
        results["js_alert_result"] = r["action_result"]["extracted"]["result"]

        # Screenshot proof
        shot = await b.screenshot(full_page=True)
        results["screenshot_b64_len"] = len(shot["action_result"]["screenshot"])

        print("SUITE RESULTS:")
        for k, v in results.items():
            print(f"- {k}: {v}")

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())