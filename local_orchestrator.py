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
PAGINATION_MAX_PAGES = int(os.getenv("PAGINATION_MAX_PAGES", "50"))

AUTONOMOUS_MODE = os.getenv("AUTONOMOUS_MODE", "false").lower() in {"1", "true", "yes"}
AUTONOMOUS_HEADLESS = os.getenv("AUTONOMOUS_HEADLESS", "true").lower() in {"1", "true", "yes"}

COMMON_NEXT_SELECTORS = ", ".join([
    "li.next a",
    "a[rel='next']",
    "a[aria-label*='next' i]",
    "button[aria-label*='next' i]",
    ".next a",
    "a.next",
    ".pagination a[rel='next']",
])

COMMON_ITEM_SELECTORS = ", ".join([
    "article.product_pod",
    "article",
    "li",
    ".card",
    ".item",
    ".product",
    ".quote",
])

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
7) If goal includes explicit selectors (item selector/next selector/extract ...), use them exactly.
8) Do NOT use select/type unless the goal explicitly mentions form inputs or dropdowns.

Max steps: {MAX_STEPS}

Goal: {goal}
Current state JSON: {json.dumps(state, ensure_ascii=False)}
""".strip()


def pagination_fallback_prompt(goal: str, state: Dict[str, Any]) -> str:
    return f"""
Return ONLY valid JSON. No markdown. No explanations.
If pagination fallback is not appropriate, return {{"enabled": false}}.
Otherwise, make a best-effort guess even if you are not fully confident.

Schema:
{{
  "enabled": true,
  "item_selector": "css for a single item row/card",
  "fields": {{"field_name": "css within the item"}},
  "next_selector": "css for next-page button/link",
  "max_pages": 5
}}

Rules:
- Use stable selectors (id, data-*, aria-*).
- Prefer a next button/link that is visible and clickable.
- fields should describe data you can extract repeatedly on each page.
- Keep fields minimal.
- If unsure, guess common patterns for next buttons and item cards.

Goal: {goal}
Current state JSON: {json.dumps(state, ensure_ascii=False)}
""".strip()


def _segment_for_label(text: str, label: str, next_labels: List[str]) -> Optional[str]:
    next_part = "|".join(re.escape(l) for l in next_labels)
    pattern = rf"{re.escape(label)}\s*:\s*(.*?)(?=({next_part})\s*:|$)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip().rstrip(".")


def _extract_forced_selectors(goal: str) -> Dict[str, Any]:
    item_selector = _segment_for_label(goal, "item selector", ["next selector", "extract", "fields"])
    next_selector = _segment_for_label(goal, "next selector", ["item selector", "extract", "fields"])
    extract_segment = _segment_for_label(goal, "extract", ["item selector", "next selector", "fields"])

    fields: Dict[str, str] = {}
    if extract_segment:
        parts = re.split(r"\s*(?:,|;|\band\b)\s*", extract_segment, flags=re.IGNORECASE)
        for part in parts:
            if not part.strip():
                continue
            match = re.match(r"^\s*([^:]+?)\s*:\s*(.+)\s*$", part)
            if not match:
                continue
            name, selector = match.groups()
            key = name.strip().lower().replace(" ", "_")
            fields[key] = selector.strip().rstrip(".")

    return {
        "item_selector": item_selector,
        "next_selector": next_selector,
        "fields": fields,
    }


def _goal_allows_form_actions(goal: str) -> bool:
    goal_l = goal.lower()
    if re.search(r"\b(form|input|enter|fill|dropdown|search)\b", goal_l):
        return True
    if re.search(r"\bselect\b", goal_l) and "selector" not in goal_l:
        return True
    return False


def _extract_first_url(goal: str) -> Optional[str]:
    match = re.search(r"https?://[^\s)\]]+", goal)
    if not match:
        return None
    return match.group(0).rstrip(".")


def _first_selector(selector: Optional[str]) -> Optional[str]:
    if not selector:
        return selector
    return selector.split(",")[0].strip()


def _prefix_fields_with_item_selector(fields: Dict[str, Any], item_selector: Optional[str]) -> Dict[str, Any]:
    if not item_selector:
        return fields
    prefixed: Dict[str, Any] = {}
    for key, selector in fields.items():
        if isinstance(selector, dict):
            css = selector.get("css")
            if css and item_selector not in css:
                parts = [p.strip() for p in css.split(",") if p.strip()]
                prefixed_parts = [f"{item_selector} {p}" for p in parts]
                selector = {**selector, "css": ", ".join(prefixed_parts) if prefixed_parts else css}
            prefixed[key] = selector
            continue
        if item_selector in selector:
            prefixed[key] = selector
            continue
        parts = [p.strip() for p in selector.split(",") if p.strip()]
        prefixed_parts = [f"{item_selector} {p}" for p in parts]
        prefixed[key] = ", ".join(prefixed_parts) if prefixed_parts else selector
    return prefixed


def _ensure_list_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, selector in fields.items():
        if isinstance(selector, dict):
            normalized[key] = {"all": True, **selector}
            continue
        normalized[key] = {"css": selector, "all": True}
    return normalized


def _fallback_field_defaults(fields: Dict[str, Any]) -> Dict[str, Any]:
    alt = dict(fields)
    if "title" in alt:
        alt["title"] = "article.product_pod h3 a"
    if "price" in alt:
        alt["price"] = "article.product_pod .price_color"
    return alt


def _extraction_is_empty(extracted: Dict[str, Any]) -> bool:
    for value in extracted.values():
        if isinstance(value, list) and len(value) > 0:
            return False
        if value not in (None, [], ""):
            return False
    return True


def _sanitize_plan_steps(steps: List[Action]) -> List[Action]:
    sanitized: List[Action] = []
    for step in steps:
        if step.action == "extract":
            patterns = (step.params or {}).get("patterns")
            if not isinstance(patterns, dict):
                continue
        sanitized.append(step)
    return sanitized


def _dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        key = (item.get("title"), item.get("price"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    replacements = {
        "Â£": "£",
        "â??": "’",
        "â€™": "’",
        "â€œ": "“",
        "â€�": "”",
        "â€“": "–",
        "â€”": "—",
        "Ã©": "é",
        "Ã¨": "è",
        "Ã¢": "â",
        "Ã¶": "ö",
        "Ã¼": "ü",
        "Ã¤": "ä",
        "ÃŸ": "ß",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value


def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        normalized.append({k: _normalize_text(v) for k, v in item.items()})
    return normalized


def _lenient_json_loads(txt: str) -> Dict[str, Any]:
    cleaned = txt.strip()
    try:
        return json.loads(cleaned)
    except Exception:
        s = cleaned.find("{")
        e = cleaned.rfind("}")
        if s >= 0 and e > s:
            cleaned = cleaned[s:e + 1]
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        return json.loads(cleaned)


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

    return _lenient_json_loads(txt)


def pagination_fallback_plan(goal: str, state: Dict[str, Any]) -> Dict[str, Any]:
    prompt = pagination_fallback_prompt(goal, state)
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
            "format": "json",
        },
        timeout=120,
    )
    r.raise_for_status()
    txt = r.json().get("response", "").strip()

    return _lenient_json_loads(txt)


def _should_force_fallback(goal: str) -> bool:
    goal_l = goal.lower()
    return any(k in goal_l for k in [
        "paginate",
        "pagination",
        "all pages",
        "across all pages",
        "next page",
        "next-page",
        "next button",
    ])


def _guess_fields_from_goal(goal: str) -> Dict[str, str]:
    goal_l = goal.lower()
    fields: Dict[str, str] = {}

    if "title" in goal_l or "name" in goal_l:
        fields["title"] = "article.product_pod h3 a"
    if "price" in goal_l or "cost" in goal_l:
        fields["price"] = "article.product_pod .price_color"
    if "author" in goal_l:
        fields["author"] = ".author, [class*='author' i]"
    if "quote" in goal_l or "text" in goal_l:
        fields["text"] = ".text, blockquote, q"

    if not fields:
        fields["text"] = "body"

    return fields


def _normalize_extracted_items(extracted: Dict[str, Any], field_names: List[str]) -> List[Dict[str, Any]]:
    lists: Dict[str, List[Any]] = {}
    max_len = 0
    for name in field_names:
        value = extracted.get(name, [])
        if isinstance(value, list):
            lists[name] = value
        elif value is None:
            lists[name] = []
        else:
            lists[name] = [value]
        max_len = max(max_len, len(lists[name]))

    items = []
    for i in range(max_len):
        row = {}
        for name in field_names:
            row[name] = lists[name][i] if i < len(lists[name]) else None
        items.append(row)
    return items


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
    if AUTONOMOUS_MODE:
        req.require_confirmation = False
        if AUTONOMOUS_HEADLESS:
            req.headless = True
        if not req.start_url:
            req.start_url = _extract_first_url(req.goal)
        if not req.start_url:
            raise HTTPException(status_code=400, detail="Autonomous mode requires start_url or a URL in goal.")

    b = await get_browser(req.profile_name, req.headless)

    if req.start_url and not is_domain_allowed(req.start_url):
        raise HTTPException(status_code=400, detail=f"Domain not allowed: {req.start_url}")

    state = await b.get_state()

    try:
        plan_json = plan_with_ollama(req.goal, state)
        plan = Plan(**plan_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama planning failed: {e}")

    if not _goal_allows_form_actions(req.goal):
        plan.steps = [step for step in plan.steps if step.action not in {"select", "type"}]

    plan.steps = _sanitize_plan_steps(plan.steps)

    if req.start_url:
        if plan.steps and plan.steps[0].action == "navigate":
            plan.steps[0].params["url"] = req.start_url
        else:
            plan.steps.insert(0, Action(action="navigate", params={"url": req.start_url}))

    if _should_force_fallback(req.goal):
        plan.steps = [step for step in plan.steps if step.action == "navigate"]

    plan_json = {"steps": [step.model_dump() for step in plan.steps]}

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
            continue

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

    # LLM-driven pagination fallback
    fallback_plan = None
    try:
        fallback_state = await b.get_state()
        fallback_plan = pagination_fallback_plan(req.goal, fallback_state)
    except Exception as fallback_err:
        results.append({
            "index": len(results) + 1,
            "error": f"Fallback planner failed: {fallback_err}",
            "fallback": True,
        })

    forced = _extract_forced_selectors(req.goal)
    forced_fields = forced.get("fields") or {}
    forced_item_selector = forced.get("item_selector")
    forced_next_selector = forced.get("next_selector")

    fallback_enabled = bool(fallback_plan) and fallback_plan.get("enabled", True)
    if not fallback_enabled and _should_force_fallback(req.goal):
        fallback_enabled = True
    if forced_fields or forced_item_selector or forced_next_selector:
        fallback_enabled = True

    if fallback_enabled:
        fields = forced_fields or (fallback_plan or {}).get("fields") or _guess_fields_from_goal(req.goal)
        next_selector = forced_next_selector or (fallback_plan or {}).get("next_selector") or COMMON_NEXT_SELECTORS
        item_selector_raw = forced_item_selector or (fallback_plan or {}).get("item_selector")

        if not fields:
            fields = _guess_fields_from_goal(req.goal)
        if not next_selector:
            next_selector = COMMON_NEXT_SELECTORS
        if not item_selector_raw:
            item_selector_raw = COMMON_ITEM_SELECTORS

        item_selector = _first_selector(item_selector_raw) or item_selector_raw
        max_pages = int((fallback_plan or {}).get("max_pages", PAGINATION_MAX_PAGES))

        if _should_force_fallback(req.goal):
            max_pages = max(max_pages, PAGINATION_MAX_PAGES)

        if item_selector and fields and next_selector:
            all_items: List[Dict[str, Any]] = []
            page_num = 1
            try:
                while True:
                    effective_fields = _ensure_list_fields(_prefix_fields_with_item_selector(fields, item_selector))
                    extract_step = Action(
                        action="extract",
                        params={"patterns": effective_fields},
                    )
                    fr = await execute_step_with_retry(b, extract_step, ACTION_RETRY_COUNT)
                    extracted = fr["action_result"]["extracted"]

                    if _extraction_is_empty(extracted):
                        retry_fields = _ensure_list_fields(
                            _prefix_fields_with_item_selector(_fallback_field_defaults(fields), item_selector)
                        )
                        extract_step = Action(
                            action="extract",
                            params={"patterns": retry_fields},
                        )
                        fr = await execute_step_with_retry(b, extract_step, ACTION_RETRY_COUNT)
                        extracted = fr["action_result"]["extracted"]

                    items = _normalize_extracted_items(extracted, list(effective_fields.keys()))
                    all_items.extend(items)

                    if page_num >= max_pages:
                        break

                    try:
                        await b.click(next_selector, timeout=2000)
                        await asyncio.sleep(1)
                        await b.wait_for(item_selector, timeout=3000)
                        page_num += 1
                    except Exception as click_exc:
                        results.append({
                            "index": len(results) + 1,
                            "warning": f"No more pages after page {page_num}: {click_exc}",
                            "fallback": True,
                        })
                        break
            except Exception as main_exc:
                results.append({
                    "index": len(results) + 1,
                    "error": f"Error during pagination fallback: {main_exc}",
                    "fallback": True,
                })

            all_items = _normalize_items(_dedupe_items(all_items))

            results.append({
                "index": len(results) + 1,
                "items": all_items,
                "total_items": len(all_items),
                "fallback": True,
            })
        else:
            results.append({
                "index": len(results) + 1,
                "warning": "Fallback pagination disabled: missing selectors",
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
            continue

    pending_confirmations.pop(req.run_id, None)
    return {"status": "done", "results": results, "final_state": await b.get_state()}


@app.post("/shutdown")
async def shutdown_browser():
    global browser
    if browser:
        await browser.shutdown()
        browser = None
    return {"status": "shutdown"}
