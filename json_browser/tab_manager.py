class TabManager:
    def __init__(self, bridge):
        self.bridge = bridge

    async def create_tab(self):
        tab_id = await self.bridge.new_page()
        return {"id": tab_id}

    async def list_tabs(self):
        return await self.bridge.list_pages()

    async def switch_tab(self, tab_id: str):
        await self.bridge.switch_page(tab_id)
        return {"id": tab_id}