"""Request validators for JSON Browser API"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class NavigateRequest(BaseModel):
    url: str
    timeout: int = 30000


class ClickRequest(BaseModel):
    selector: str
    timeout: int = 5000


class TypeRequest(BaseModel):
    selector: str
    text: str
    timeout: int = 5000


class ExtractRequest(BaseModel):
    patterns: Dict[str, Any]


class ExecuteScriptRequest(BaseModel):
    script: str
    args: List[Any] = []


class SwitchTabRequest(BaseModel):
    page_id: str


class ChromiumModeRequest(BaseModel):
    mode: str  # "fresh" or "persistent"
