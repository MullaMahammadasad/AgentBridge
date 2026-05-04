from .logger import get_logger

logger = get_logger(__name__)


class StateManager:
    def __init__(self, bridge):
        self.bridge = bridge

    async def get_full_state(self):
        """
        Best-effort browser state snapshot.
        Never throws; returns partial info if something is unavailable.
        """
        state = {}

        try:
            state["url"] = await self.bridge.get_url()
        except Exception as e:
            logger.error(f"State error (url): {e}")
            state["url"] = None

        try:
            state["title"] = await self.bridge.get_title()
        except Exception as e:
            logger.error(f"State error (title): {e}")
            state["title"] = None

        try:
            state["tabs"] = await self.bridge.list_pages()
        except Exception as e:
            logger.error(f"State error (tabs): {e}")
            state["tabs"] = []

        try:
            state["active_tab_id"] = f"page_{self.bridge._active_page_index}"
        except Exception as e:
            logger.error(f"State error (active_tab_id): {e}")
            state["active_tab_id"] = None

        return state

    async def extract_data(self, patterns: dict):
        """
        Extract data by patterns:
          1) string spec:
             {"k": "css-selector"}
          2) dict spec:
             {"k": {"css": "...", "attr": "...", "all": bool}}

        Behavior:
        - Missing selectors are NORMAL and return None (or []).
        - No timeout/error log spam for optional fields.
        """
        page = self.bridge._page()
        extracted = {}

        for key, spec in patterns.items():
            try:
                # ---- string spec: {"key": "css"} ----
                if isinstance(spec, str):
                    selector = spec
                    loc_all = page.locator(selector)
                    count = await loc_all.count()

                    if count == 0:
                        extracted[key] = None
                        continue

                    item = loc_all.first
                    text = await item.inner_text()
                    extracted[key] = (text or "").strip()
                    continue

                # ---- dict spec: {"key": {"css":"...", "attr":"...", "all":bool}} ----
                if not isinstance(spec, dict):
                    extracted[key] = None
                    continue

                css = spec.get("css")
                attr = spec.get("attr")
                all_ = bool(spec.get("all", False))

                if not css:
                    extracted[key] = None
                    continue

                loc = page.locator(css)
                count = await loc.count()

                # If selector missing, do not error
                if count == 0:
                    extracted[key] = [] if all_ else None
                    continue

                if all_:
                    vals = []
                    for i in range(count):
                        item = loc.nth(i)
                        if attr:
                            vals.append(await item.get_attribute(attr))
                        else:
                            vals.append(((await item.inner_text()) or "").strip())
                    extracted[key] = vals
                else:
                    item = loc.first
                    if attr:
                        extracted[key] = await item.get_attribute(attr)
                    else:
                        extracted[key] = ((await item.inner_text()) or "").strip()

            except Exception as e:
                # Keep extraction resilient
                logger.error(f"Extract error ({key}): {e}")
                extracted[key] = [] if isinstance(spec, dict) and bool(spec.get("all", False)) else None

        return {"extracted": extracted}