"""
Example: Fresh vs Persistent Chromium comparison
"""

import asyncio
from json_browser import JSONBrowser


async def demo_fresh():
    """Fresh instance (clears data each time)"""
    print("\n🔄 FRESH INSTANCE (
