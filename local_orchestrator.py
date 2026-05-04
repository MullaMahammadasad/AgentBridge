import os
import re
import json
import csv
import uuid
import sys
import asyncio
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from json_browser import JSONBrowser

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
ALLOW_DOMAINS = [d.strip() for d in os.getenv("ALLOW_DOMAINS", "").split(",") if d.strip()]
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
REQUIRE_CONFIRM_KEYWORDS = [k.strip().lower() for k in os.getenv("REQUIRE_CONFIRM_KEYWORDS", "").split(",") if k.strip()]
ACTION_RETRY_COUNT = int(os.getenv("ACTION_RETRY_COUNT", "1"))
ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "artifacts")

app = FastAPI(title="Local AI Orchestrator (Ollama)")
browser: Optional[JSONBrowser] = None
pending_confirmations: Dict[str, Dict[str, Any]] = {}


class RunRequest(BaseModel):
    goal: str
    start_url: Optional[str] = None
    profile_name: str = "default_profile"
    headless: bool = False
    require_confirmation: bool = True


class ConfirmRequest(BaseModel):
    run_id: str
    approve: bool


class Action(BaseModel):
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    steps: List[Action]


def is_domain_allowed(url: str) -> bool:
    if not ALLOW_DOMAINS:
        return True
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in ALLOW_DOMAINS)


def needs_confirmation(goal: str, steps: List[Action]) -> bool:
    text = goal.lower() + " " + " ".join(
        f"{s.action} {json.dumps(s.params, ensure_ascii=False).lower()}" for s in steps
    )
    return any(k in text for k in REQUIRE_CONFIRM_KEYWORDS)


def planner_prompt(goal: str, state: Dict[str, Any]) -> str:
    return f"""
Return ONLY valid JSON. No markdown. No explanations.
Follow this schema exactly:
{{
  "steps": [
    {{"action":"navigate","params":{{"url":"https://..."}}}},
    {{"action":"wait_for","params":{{"css":"..."}}}},
    {{"action":"type","params":{{"css":"...", "text":"..."}}}},
    {{"action":"click","params":{{"css":"..."}}}},
    {{"action":"select","params":{{"css":"...", "value":"..."}}}},
    {{"action":"extract","params":{{"patterns":{{"k":"css"}}}}}}
  ]
}}

Allowed actions only: navigate, click, type, select, wait_for, extract, screenshot
Hard rules:
1) Never invent actions outside allowed list.
2) Prefer wait_for before click/type/extract on dynamic pages.
3) Prefer extract over screenshot.
4) Use stable selectors when possible (id, data-* , semantic classes).
5) Keep steps minimal and deterministic.
6) Do not include duplicate navigate steps unless required.

Max steps: {MAX_STEPS}

Goal: {goal}
Current state JSON: {json.dumps(state, ensure_ascii=False)}
""".strip()


def plan_with_ollama(goal: str, state: Dict[str, Any]) -> Dict[str, Any]:
    prompt = planner_prompt(goal, state)
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
            "format": "json",
        },
        timeout=120,
    )
    r.raise_for_status()
    txt = r.json().get("response", "").strip()

    try:
        return json.loads(txt)
    except Exception:
        s = txt.find("{")
        e = txt.rfind("}")
        if s >= 0 and e > s:
            return json.loads(txt[s:e + 1])
        raise


async def get_browser(profile_name: str, headless: bool) -> JSONBrowser:
    global browser
    if browser is None:
        browser = JSONBrowser(headless=headless)
        profile_dir = os.path.abspath(os.path.join("profiles", profile_name))
        await browser.initialize(user_data_dir=profile_dir)
    return browser


async def execute_step(b: JSONBrowser, step: Action) -> Dict[str, Any]:
    a = step.action
    p = step.params or {}

    if a == "navigate":
        url = p.get("url")
        if not url:
            raise ValueError("navigate requires url")
        if not is_domain_allowed(url):
            raise ValueError(f"Domain not allowed: {url}")
        return await b.navigate(url)

    if a == "click":
        return await b.click(p["css"], timeout=p.get("timeout", 5000))

    if a == "type":
        return await b.type(
            p["css"],
            p["text"],
            clear=p.get("clear", True),
            timeout=p.get("timeout", 5000),
        )

    if a == "select":
        return await b.select(p["css"], p["value"], timeout=p.get("timeout", 5000))

    if a == "wait_for":
        return await b.wait_for(
            p["css"],
            timeout=p.get("timeout", 5000),
            state=p.get("state", "visible"),
        )

    if a == "extract":
        return await b.extract(p["patterns"])

    if a == "screenshot":
        return await b.screenshot(full_page=p.get("full_page", False))

    raise ValueError(f"Unsupported action: {a}")


async def execute_step_with_retry(b: JSONBrowser, step: Action, retries: int = ACTION_RETRY_COUNT) -> Dict[str, Any]:
    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            return await execute_step(b, step)
        except Exception as e:
            last_error = str(e)
            if attempt < retries:
                await asyncio.sleep(0.8)
                continue
            raise ValueError(last_error)


def _flatten_for_csv(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_for_csv(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((new_key, v))
    return dict(items)


def save_artifacts(payload: Dict[str, Any]) -> Dict[str, str]:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    rid = uuid.uuid4().hex[:8]
    base = f"run_{stamp}_{rid}"

    json_path = os.path.join(ARTIFACTS_DIR, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(ARTIFACTS_DIR, f"{base}.csv")
    row = _flatten_for_csv(payload)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    return {"json": json_path, "csv": csv_path}


async def _run_internal(req: RunRequest) -> Dict[str, Any]:
    b = await get_browser(req.profile_name, req.headless)

    if req.start_url and not is_domain_allowed(req.start_url):
        raise HTTPException(status_code=400, detail=f"Domain not allowed: {req.start_url}")

    state = await b.get_state()

    try:
        plan_json = plan_with_ollama(req.goal, state)
        plan = Plan(**plan_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama planning failed: {e}")

    if len(plan.steps) > MAX_STEPS:
        raise HTTPException(status_code=400, detail=f"Plan exceeds MAX_STEPS={MAX_STEPS}")

    if req.require_confirmation and needs_confirmation(req.goal, plan.steps):
        run_id = f"run_{os.urandom(4).hex()}"
        pending_confirmations[run_id] = {"request": req.model_dump(), "plan": plan_json}
        return {"status": "needs_confirmation", "run_id": run_id, "plan": plan_json}

    results = []

    # Run AI-planned steps:
    for i, step in enumerate(plan.steps, start=1):
        try:
            r = await execute_step_with_retry(b, step, ACTION_RETRY_COUNT)
            results.append({"index": i, "step": step.model_dump(), "result": r})
        except Exception as e:
            results.append({"index": i, "step": step.model_dump(), "error": str(e)})
            break

    # Defensive: check browser is alive before fallback
    try:
        await b.get_state()
    except Exception as e:
        results.append({
            "index": len(results) + 1,
            "error": "Browser dead before fallback extract: " + str(e),
            "fallback": True
        })
        return {
            "status": "failed",
            "plan": plan_json,
            "results": results,
            "final_state": None
        }

    # Universal fallback, paginated extraction:
   all_quotes = []
page_num = 1

try:
    while True:
        extract_step = Action(
            action="extract",
            params={
                "patterns": {
                    "quotes_texts": ".quote .text",
                    "quotes_authors": ".quote .author"
                }
            }
        )
        fr = await execute_step_with_retry(b, extract_step, ACTION_RETRY_COUNT)
        texts = fr["action_result"]["extracted"].get("quotes_texts", [])
        authors = fr["action_result"]["extracted"].get("quotes_authors", [])
        if isinstance(texts, str): texts = [texts]
        if isinstance(authors, str): authors = [authors]
        for q, a in zip(texts, authors):
            q_clean = re.sub(r'^[“”"]|[””"]$', '', q).strip() if isinstance(q, str) else q
            a_clean = a.strip() if isinstance(a, str) else a
            all_quotes.append({"quote": q_clean, "author": a_clean})
        print(f"Extracted {len(texts)} quotes on page {page_num}")
        try:
            await b.click('.next a', timeout=2000)  # <--- CHANGED (no .page)
            await b.wait_for('.quote .text', timeout=3000)  # <--- CHANGED (no .page)
            page_num += 1
        except Exception as click_exc:
            print(f"No more next pages after page {page_num}: {click_exc}")
            break
except Exception as main_exc:
    results.append({
        "index": len(results) + 1,
        "error": f"Error during autonomous pagination fallback: {main_exc}",
        "fallback": True,
    })

results.append({
    "index": len(results) + 1,
    "quotes_array": all_quotes,
    "total_quotes": len(all_quotes),
    "fallback": True,
})

    return {
        "status": "done",
        "plan": plan_json,
        "results": results,
        "final_state": await b.get_state()
    }


@app.post("/run")
async def run_task(req: RunRequest):
    return await _run_internal(req)


@app.post("/run_and_save")
async def run_and_save(req: RunRequest):
    result = await _run_internal(req)
    files = save_artifacts(result)
    return {**result, "artifacts": files}


@app.post("/confirm")
async def confirm_run(req: ConfirmRequest):
    item = pending_confirmations.get(req.run_id)
    if not item:
        raise HTTPException(status_code=404, detail="run_id not found")
    if not req.approve:
        pending_confirmations.pop(req.run_id, None)
        return {"status": "cancelled"}

    rr = RunRequest(**item["request"])
    plan = Plan(**item["plan"])
    b = await get_browser(rr.profile_name, rr.headless)

    results = []
    for i, step in enumerate(plan.steps, start=1):
        try:
            r = await execute_step_with_retry(b, step, ACTION_RETRY_COUNT)
            results.append({"index": i, "step": step.model_dump(), "result": r})
        except Exception as e:
            results.append({"index": i, "step": step.model_dump(), "error": str(e)})
            break

    pending_confirmations.pop(req.run_id, None)
    return {"status": "done", "results": results, "final_state": await b.get_state()}


@app.post("/shutdown")
async def shutdown_browser():
    global browser
    if browser:
        await browser.shutdown()
        browser = None
    return {"status": "shutdown"}