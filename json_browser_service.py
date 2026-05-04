"""
JSON Browser REST API Service
Runs as standalone service, exposes REST endpoints
Supports both fresh and persistent Chromium instances on different ports
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from json_browser import JSONBrowser
from json_browser.validators import (
    NavigateRequest, ClickRequest, TypeRequest, ExtractRequest,
    ExecuteScriptRequest, SwitchTabRequest, ChromiumModeRequest
)
from json_browser.logger import get_logger

logger = get_logger(__name__)

# Global instances
fresh_browser: Optional[JSONBrowser] = None
persistent_browser: Optional[JSONBrowser] = None
active_mode: str = "fresh"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    global fresh_browser, persistent_browser
    
    logger.info("Starting JSON Browser Service...")
    
    # Initialize both instances
    fresh_browser = JSONBrowser(mode="fresh", headless=False, client_id="fresh_instance")
    persistent_browser = JSONBrowser(mode="persistent", headless=False, client_id="persistent_instance")
    
    await fresh_browser.initialize()
    await persistent_browser.initialize()
    
    logger.info("Both Chromium instances ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down JSON Browser Service...")
    await fresh_browser.shutdown()
    await persistent_browser.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(
    title="JSON Browser API",
    description="AI-native structured browser",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_active_browser() -> JSONBrowser:
    """Get currently active browser instance"""
    global fresh_browser, persistent_browser, active_mode
    return fresh_browser if active_mode == "fresh" else persistent_browser


# ===== Health =====

@app.get("/health")
async def health() -> Dict:
    """Health check"""
    browser = _get_active_browser()
    return {
        "status": "healthy",
        "active_mode": active_mode,
        "fresh_browser": fresh_browser.get_stats() if fresh_browser else None,
        "persistent_browser": persistent_browser.get_stats() if persistent_browser else None
    }


# ===== Navigation =====

@app.post("/navigate")
async def navigate(req: NavigateRequest) -> Dict:
    """Navigate to URL"""
    try:
        browser = _get_active_browser()
        result = await browser.navigate(req.url, timeout=req.timeout)
        return result
    except Exception as e:
        logger.error(f"Navigate error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Click =====

@app.post("/click")
async def click(req: ClickRequest) -> Dict:
    """Click element"""
    try:
        browser = _get_active_browser()
        result = await browser.click(req.selector, timeout=req.timeout)
        return result
    except Exception as e:
        logger.error(f"Click error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Type =====

@app.post("/type")
async def type_text(req: TypeRequest) -> Dict:
    """Type text"""
    try:
        browser = _get_active_browser()
        result = await browser.type(req.selector, req.text, timeout=req.timeout)
        return result
    except Exception as e:
        logger.error(f"Type error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Extract =====

@app.post("/extract")
async def extract(req: ExtractRequest) -> Dict:
    """Extract data"""
    try:
        browser = _get_active_browser()
        result = await browser.extract(req.patterns)
        return result
    except Exception as e:
        logger.error(f"Extract error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Screenshot =====

@app.post("/screenshot")
async def screenshot(full_page: bool = False) -> Dict:
    """Take screenshot"""
    try:
        browser = _get_active_browser()
        result = await browser.screenshot(full_page=full_page)
        return result
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Execute Script =====

@app.post("/execute-script")
async def execute_script(req: ExecuteScriptRequest) -> Dict:
    """Execute JavaScript"""
    try:
        browser = _get_active_browser()
        result = await browser.execute_script(req.script, req.args)
        return result
    except Exception as e:
        logger.error(f"Script error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== State =====

@app.get("/state")
async def get_state() -> Dict:
    """Get page state"""
    try:
        browser = _get_active_browser()
        result = await browser.get_state()
        return result
    except Exception as e:
        logger.error(f"State error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Tabs =====

@app.post("/tabs/create")
async def create_tab() -> Dict:
    """Create new tab"""
    try:
        browser = _get_active_browser()
        result = await browser.create_tab()
        return result
    except Exception as e:
        logger.error(f"Create tab error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tabs/switch")
async def switch_tab(req: SwitchTabRequest) -> Dict:
    """Switch tab"""
    try:
        browser = _get_active_browser()
        result = await browser.switch_tab(req.page_id)
        return result
    except Exception as e:
        logger.error(f"Switch tab error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tabs/close")
async def close_tab(page_id: str = Query(...)) -> Dict:
    """Close tab"""
    try:
        browser = _get_active_browser()
        result = await browser.close_tab(page_id)
        return result
    except Exception as e:
        logger.error(f"Close tab error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tabs/list")
async def list_tabs() -> Dict:
    """List tabs"""
    try:
        browser = _get_active_browser()
        result = await browser.list_tabs()
        return result
    except Exception as e:
        logger.error(f"List tabs error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ===== Chromium Mode =====

@app.post("/chromium/mode/switch")
async def switch_chromium_mode(req: ChromiumModeRequest) -> Dict:
    """Switch between fresh and persistent Chromium"""
    global active_mode
    
    old_mode = active_mode
    active_mode = req.mode
    
    browser = _get_active_browser()
    
    logger.info(f"Switched Chromium mode: {old_mode} → {req.mode}")
    
    return {
        "success": True,
        "old_mode": old_mode,
        "new_mode": req.mode,
        "active_browser": browser.get_stats()
    }


@app.get("/chromium/mode")
async def get_chromium_mode() -> Dict:
    """Get active Chromium mode"""
    return {
        "active_mode": active_mode,
        "available_modes": ["fresh", "persistent"]
    }


# ===== WebSocket Sync =====

@app.websocket("/ws/sync")
async def websocket_sync(websocket: WebSocket):
    """WebSocket for real-time state sync"""
    await websocket.accept()
    client_id = str(uuid.uuid4())
    
    logger.info(f"WebSocket client connected: {client_id}")
    
    try:
        while True:
            # Wait for client message
            message = await websocket.receive_text()
            
            if message == "ping":
                browser = _get_active_browser()
                state = await browser.get_state()
                await websocket.send_json({
                    "type": "pong",
                    "state": state
                })
            elif message == "screenshot":
                browser = _get_active_browser()
                result = await browser.screenshot()
                await websocket.send_json({
                    "type": "screenshot",
                    "data": result
                })
    
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
    finally:
        logger.info(f"WebSocket client disconnected: {client_id}")


if __name__ == "__main__":
    import sys
    
    fresh_port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    
    logger.info(f"Starting service on port {fresh_port}")
    
    uvicorn.run(app, host="0.0.0.0", port=fresh_port)