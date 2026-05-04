import base64
import os
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright
from .errors import ChromiumLaunchError
from .logger import get_logger

logger = get_logger(__name__)

class ChromiumBridge:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages = []
        self._active_page_index = 0
        self.storage_state_path: Optional[str] = None
        self.downloads_dir: Optional[str] = None
        self.user_data_dir: Optional[str] = None

    def _page(self):
        if not self._pages:
            raise RuntimeError("No page available. Call new_page() first.")
        return self._pages[self._active_page_index]

    async def launch(self, storage_state_path: str | None = None, downloads_dir: str | None = None, user_data_dir: str | None = None) -> None:
        try:
            self.storage_state_path = storage_state_path
            self.downloads_dir = downloads_dir
            self.user_data_dir = user_data_dir
            self._playwright = await async_playwright().start()

            if downloads_dir:
                Path(downloads_dir).mkdir(parents=True, exist_ok=True)

            if user_data_dir:
                Path(user_data_dir).mkdir(parents=True, exist_ok=True)
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=self.headless,
                    accept_downloads=True,
                )
                self._browser = None
                self._pages = list(self._context.pages)
                if not self._pages:
                    page = await self._context.new_page()
                    self._pages = [page]
                self._active_page_index = 0
                logger.info("Chromium launched (persistent profile)")
                return

            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            kwargs = {"accept_downloads": True}
            if storage_state_path and os.path.exists(storage_state_path):
                kwargs["storage_state"] = storage_state_path
            self._context = await self._browser.new_context(**kwargs)
            logger.info("Chromium launched")
        except Exception as e:
            raise ChromiumLaunchError(str(e)) from e

    async def new_page(self) -> str:
        page = await self._context.new_page()
        self._pages.append(page)
        self._active_page_index = len(self._pages) - 1
        return f"page_{self._active_page_index}"

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages = []
        self._active_page_index = 0
        logger.info("Chromium closed")

    async def navigate(self, url: str) -> str:
        p = self._page()
        await p.goto(url, wait_until="domcontentloaded")
        return p.url

    async def screenshot_b64(self, full_page: bool = False) -> str:
        data = await self._page().screenshot(full_page=full_page)
        return base64.b64encode(data).decode("utf-8")

    async def list_pages(self):
        return [{"id": f"page_{i}", "url": p.url} for i, p in enumerate(self._pages)]

    async def switch_page(self, page_id: str) -> None:
        idx = int(page_id.split("_", 1)[1])
        self._active_page_index = idx

    async def click(self, css: str, timeout: int = 5000) -> None:
        await self._page().locator(css).first.click(timeout=timeout)

    async def type(self, css: str, text: str, clear: bool = True, timeout: int = 5000) -> None:
        loc = self._page().locator(css).first
        await loc.wait_for(state="attached", timeout=timeout)
        if clear:
            await loc.fill("", timeout=timeout)
        await loc.type(text, timeout=timeout)

    async def select(self, css: str, value: str, timeout: int = 5000) -> None:
        await self._page().locator(css).first.select_option(value=value, timeout=timeout)

    async def wait_for(self, css: str, timeout: int = 5000, state: str = "visible") -> None:
        await self._page().locator(css).first.wait_for(state=state, timeout=timeout)

    async def wait_for_text(self, css: str, expected_substring: str, timeout: int = 5000) -> bool:
        loc = self._page().locator(css).first
        await loc.wait_for(state="attached", timeout=timeout)
        txt = (await loc.inner_text()) or ""
        return expected_substring in txt

    def enable_auto_accept_dialogs(self) -> None:
        p = self._page()
        async def _on_dialog(dialog):
            await dialog.accept()
        p.on("dialog", _on_dialog)

    async def upload_file(self, css: str, file_path: str, timeout: int = 5000) -> None:
        loc = self._page().locator(css).first
        await loc.wait_for(state="attached", timeout=timeout)
        await loc.set_input_files(file_path, timeout=timeout)

    async def click_and_download(self, css: str, timeout: int = 30000) -> dict:
        p = self._page()
        async with p.expect_download(timeout=timeout) as dli:
            await p.locator(css).first.click()
        dl = await dli.value
        name = dl.suggested_filename
        if self.downloads_dir:
            Path(self.downloads_dir).mkdir(parents=True, exist_ok=True)
            target = str(Path(self.downloads_dir) / name)
            await dl.save_as(target)
            return {"path": target, "suggested_filename": name}
        tmp = await dl.path()
        return {"path": str(tmp) if tmp else None, "suggested_filename": name}

    async def save_storage_state(self) -> str | None:
        if not self._context or not self.storage_state_path:
            return None
        Path(self.storage_state_path).parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=self.storage_state_path)
        return self.storage_state_path

    async def get_url(self) -> str:
        return self._page().url

    async def get_title(self) -> str:
        return await self._page().title()

    async def get_html(self) -> str:
        return await self._page().content()
