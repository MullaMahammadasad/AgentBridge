import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_browser import JSONBrowser


async def main():
    b = JSONBrowser(headless=False)
    await b.initialize()

    try:
        await b.navigate("https://the-internet.herokuapp.com/upload")

        # Choose a file to upload
        file_path = os.path.abspath("requirements.txt")

        await b.upload_file("#file-upload", file_path)
        await b.click("#file-submit")

        await b.wait_for("h3", timeout=8000)
        r = await b.extract({"uploaded": "#uploaded-files"})

        print("Uploaded file shown by site:", r["action_result"]["extracted"]["uploaded"])

        shot = await b.screenshot(full_page=True)
        print("screenshot_b64_len:", len(shot["action_result"]["screenshot"]))

    finally:
        await b.shutdown()


if __name__ == "__main__":
    asyncio.run(main())