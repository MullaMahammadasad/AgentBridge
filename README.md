# AgentBridge: AI-Native Task Execution & Commerce Platform
# LISTEN TO AUDIO FILE FOR BETTER UNDERSTANDING
> **"Stop making AI use the human web. Build a web made for AI."**
> AgentBridge is a machine-native infrastructure layer designed to convert the human-oriented World Wide Web into a structured JSON/CSV layer, allowing AI agents to navigate, search, and transact autonomously.

---

## 🚀 The Vision
Most digital services today are built for human eyes, utilizing visual interfaces and dynamic HTML that are inefficient and fragile for AI systems. **AgentBridge** replaces these traditional human-facing websites with machine-native communication protocols, creating a parallel internet where AI agents communicate directly via structured data rather than visual browsers.

## 🛠️ Key Features
*   **The `docs.ai` Protocol**: Replaces visual UIs with schema-based API descriptions, allowing AIs to programmatically understand any service.
*   **Dual-Layer Browser System**: A "JSON Browser" for AI operations that mirrors actions in a visual "Chromium Browser" for human oversight.
*   **Standardized Agent Protocol**: A shared communication schema (JSON/GraphQL) for all AI-to-AI interactions, ensuring consistent search and transaction logic.
*   **Hybrid Sync Transport**: Real-time synchronization between the AI layer and the visual browser using WebSockets with an HTTP Polling fallback.
*   **Secure Transactions**: Built-in HMAC-SHA256 request signing, API key authentication, and a mandatory **Human-in-the-Loop** approval process for all payments.

## 🏗️ System Architecture
AgentBridge operates as a layered infrastructure:

1.  **Human-Facing Agent (Main AI)**: Parses natural language intent and converts it into structured machine requests.
2.  **JSON Browser (AI Layer)**: The independent execution environment where the AI reads structured data and makes decisions.
3.  **Vendor Scrapers/Agents**: Convert messy HTML from sites like Amazon into clean `docs.ai` formatted data.
4.  **Result Aggregator & Decision Engine**: Filters and ranks the top results based on user constraints.
5.  **Finalizer Module**: Automates the checkout flow via Playwright after receiving human confirmation.

## 💻 Technology Stack
| Layer | Tool | Purpose |
| :--- | :--- | :--- |
| **AI Brain** | Local Llama 3 (Ollama) | Autonomous reasoning (free/offline). |
| **Browser Engine**| Playwright + Chromium | Headless control and visual mirroring. |
| **Scaling** | Azure Functions | Parallelizes 20+ crawl tasks simultaneously. |
| **Storage** | MongoDB Atlas | Distributed storage for `docs.ai` knowledge bases. |
| **State Memory** | Redis Cloud | Maintains session memory across forked agents. |
| **Observability** | New Relic + Blackfire | Monitoring agentic calls and code-level profiling. |

## 🗺️ Roadmap
*   **Phase 1: Foundation (Current)**: Implement MongoDB integration, JSON Web Crawler, and local Llama 3 agent.
*   **Phase 2: Scale**: Deploy to DigitalOcean and use Azure Functions to fork tasks across the web.
*   **Phase 3: Monitor**: Integrate New Relic and Sentry for deep observability and error tracing.
*   **Phase 4: Launch**: Deploy the `agentbridge.tech` public API and expand to multi-vendor support (eBay, Walmart, etc.).

## 🔧 Installation & Usage
### Prerequisites
*   Python 3.13+
*   Ollama (with Llama 3)
*   Playwright

### Setup
```bash
# Clone the repository
git clone https://github.com/youruser/agentbridge.git

# Install dependencies
pip install -r requirements.txt

# Configure runtime credentials in environment variables (never hardcode)
export HEROKU_LOGIN_USERNAME="..."
export HEROKU_LOGIN_PASSWORD="..."
export SANDBOX_USERNAME="..."
export SANDBOX_PASSWORD="..."
export QUOTES_LOGIN_USERNAME="..."
export QUOTES_LOGIN_PASSWORD="..."

# Launch the Dual-Layer Service
python json_browser_service.py
```

### Example Task
**User Intent:** "Find a gaming laptop under $1000 and add the best one to my cart."
**AgentBridge Logic:**
1.  **Main AI** generates a JSON search request: `{"task": "search", "category": "laptop", "budget": 1000}`.
2.  **Vendor Scraper** fetches Amazon data and converts it to `docs.ai` format.
3.  **Decision Engine** ranks the results and presents them to the user.
4.  Upon approval, the **Finalizer** injects session data into the **Chromium Bridge** to complete the cart action.

## 🛡️ Security & Ethics
AgentBridge is designed with a "Safety-First" philosophy. Every agent has a unique cryptographic key, and no financial transaction can occur without explicit **Human-in-the-Loop** approval. Full audit logs are maintained for every AI action.

---

*AgentBridge Prototype v1.0 | 2026 | Confidential Research Document*.
