# AgentBridge      
# JSON Browser - AI-Native Structured Web Interface

An intelligent browser designed for AI agents that replaces traditional browser automation with structured JSON operations [1].

### Vision
Instead of building automation for human-facing UIs, this browser provides an API-first structured web layer [2, 3]:

```text
AI Agent 
   ↓ (JSON) 
┌─────────────────────────┐ 
│ JSON Browser Service    │ 
│ - REST API              │ 
│ - Library Mode          │ 
└────────┬────────────────┘ 
   ↓ (DevTools/Playwright) 
┌─────────────────────────┐ 
│ Dual Chromium           │ 
│ - Fresh (Port 5001)     │ 
│ - Persistent (Port 5002)│ 
└─────────────────────────┘
Features
✅ Dual Chromium Instances
Fresh (Port 5001): Auto-deletes cookies and localStorage for private, clean runs
.
Persistent (Port 5002): Keeps state and session data across runs
.
✅ REST API
Navigate, click, type, and extract data using JSON payloads
.
Multi-tab creation, switching, and closing
.
Screenshot and DOM state queries
.
✅ Library Mode
Direct Python import using from json_browser import JSONBrowser
.
Async/await interface without needing to run an external service
.
✅ Graceful Error Handling
Automatic retry and partial results on failure, complete with debug traces
.
✅ Rate Limiting
Throttled to a maximum of 10 requests/second with per-client tracking
.
✅ Hybrid Visual Sync
WebSocket for real-time visual syncing
.
HTTP polling fallback
.
