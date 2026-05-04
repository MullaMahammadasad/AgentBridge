from datetime import datetime
import uuid

from .chromium_bridge import ChromiumBridge
from .rate_limiter import RateLimiter
from .state_manager import StateManager
from .tab_manager import TabManager


class JSONBrowser:
    def __init__(self, mode: str = "fresh", headless: bool = False, rate_limit: bool = True):
        self.mode = mode
        self.headless = headless
        self.client_id = f"client_{uuid.uuid4().hex[:8]}"

        self.bridge = ChromiumBridge(headless=headless)
        self.state = StateManager(self.bridge)
        self.tabs = TabManager(self.bridge)
        self.limiter = RateLimiter() if rate_limit else None

    async def initialize(
        self,
        storage_state_path: str | None = None,
        downloads_dir: str | None = None,
        user_data_dir: str | None = None,
    ):
        await self.bridge.launch(
            storage_state_path=storage_state_path,
            downloads_dir=downloads_dir,
            user_data_dir=user_data_dir,
        )

        if not getattr(self.bridge, "_pages", []):
            await self.bridge.new_page()

    async def shutdown(self):
        await self.bridge.close()

    async def _wrap(self, action: str, fn):
        try:
            if self.limiter:
                self.limiter.check(self.client_id)

            result = await fn()
            browser_state = await self.state.get_full_state()
            return {
                "success": True,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": action,
                "browser_state": browser_state,
                "action_result": result,
                "error": None,
            }
        except Exception as e:
            try:
                browser_state = await self.state.get_full_state()
            except Exception:
                browser_state = {}

            return {
                "success": False,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": action,
                "browser_state": browser_state,
                "action_result": None,
                "error": str(e),
            }

    async def navigate(self, url: str):
        async def run():
            final_url = await self.bridge.navigate(url)
            return {"url": final_url}
        return await self._wrap("navigate", run)

    async def screenshot(self, full_page: bool = False):
        async def run():
            b64 = await self.bridge.screenshot_b64(full_page=full_page)
            return {"screenshot": b64}
        return await self._wrap("screenshot", run)

    async def extract(self, patterns: dict):
        async def run():
            return await self.state.extract_data(patterns)
        return await self._wrap("extract", run)

    async def create_tab(self):
        async def run():
            return await self.tabs.create_tab()
        return await self._wrap("create_tab", run)

    async def list_tabs(self):
        async def run():
            return {"tabs": await self.tabs.list_tabs()}
        return await self._wrap("list_tabs", run)

    async def switch_tab(self, tab_id: str):
        async def run():
            return await self.tabs.switch_tab(tab_id)
        return await self._wrap("switch_tab", run)

    async def get_state(self):
        async def run():
            return await self.state.get_full_state()
        return await self._wrap("get_state", run)

    async def click(self, css: str, timeout: int = 5000):
        async def run():
            await self.bridge.click(css, timeout=timeout)
            return {"clicked": css}
        return await self._wrap("click", run)

    async def type(self, css: str, text: str, clear: bool = True, timeout: int = 5000):
        async def run():
            await self.bridge.type(css, text, clear=clear, timeout=timeout)
            return {"typed": css, "text_len": len(text)}
        return await self._wrap("type", run)

    async def select(self, css: str, value: str, timeout: int = 5000):
        async def run():
            await self.bridge.select(css, value, timeout=timeout)
            return {"selected": css, "value": value}
        return await self._wrap("select", run)

    async def wait_for(self, css: str, timeout: int = 5000, state: str = "visible"):
        async def run():
            await self.bridge.wait_for(css, timeout=timeout, state=state)
            return {"waited_for": css, "state": state}
        return await self._wrap("wait_for", run)

    async def wait_for_text(self, css: str, expected_substring: str, timeout: int = 5000):
        async def run():
            ok = await self.bridge.wait_for_text(css, expected_substring, timeout=timeout)
            return {"css": css, "expected_substring": expected_substring, "matched": ok}
        return await self._wrap("wait_for_text", run)

    async def auto_accept_dialogs(self):
        async def run():
            self.bridge.enable_auto_accept_dialogs()
            return {"dialogs": "auto-accept enabled"}
        return await self._wrap("auto_accept_dialogs", run)

    async def upload_file(self, css: str, file_path: str, timeout: int = 5000):
        async def run():
            await self.bridge.upload_file(css, file_path, timeout=timeout)
            return {"uploaded_to": css, "file_path": file_path}
        return await self._wrap("upload_file", run)

    async def save_storage_state(self):
        async def run():
            path = await self.bridge.save_storage_state()
            return {"storage_state_path": path}
        return await self._wrap("save_storage_state", run)

    async def click_and_download(self, css: str, timeout: int = 30000):
        async def run():
            info = await self.bridge.click_and_download(css, timeout=timeout)
            return info
        return await self._wrap("click_and_download", run)
