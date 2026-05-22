# Swiggy Agent Bot

Swiggy-only Telegram bot powered by Swiggy MCP, FastAPI, CrewAI-style config-driven agents, OpenAI models, and SQLite.

## What It Does

- Lets a Telegram user connect their own Swiggy account.
- Supports Food, Instamart, and Dineout surfaces.
- Routes commands through dynamic agents loaded from `config/agents.yaml`.
- Calls Swiggy MCP over Streamable HTTP JSON-RPC.
- Stores users, auth tokens, sessions, pending confirmations, audits, and order/cart snapshots in SQLite.
- Blocks checkout/payment/booking until the user replies exactly `CONFIRM ORDER`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn food_order_bot.main:app --reload --port 3000
```

CrewAI currently supports Python versions below 3.14. For the full agent runtime, use Python 3.11-3.13 and install:

```bash
pip install -e ".[dev,agents]"
```

Required environment:

```text
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
PUBLIC_BASE_URL=http://localhost:3000
SWIGGY_CLIENT_ID=
SWIGGY_CLIENT_SECRET=
DATABASE_URL=sqlite:///./data/bot.db
AGENT_CONFIG_PATH=config/agents.yaml
```

For local MCP experiments only, `DEV_SWIGGY_ACCESS_TOKEN` can be used as a temporary fallback. Do not use it for real users.

## Telegram Commands

```text
/start
/connect
/search food biryani
/search instamart milk
/search dineout italian
/menu food <restaurant_id>
/cart food
/checkout food {"addressId":"home"}
/track food <order_id>
/cancel
CONFIRM ORDER
```

## Agent Config

Agents are not hardcoded into business logic. They are loaded from `config/agents.yaml` with:

```text
id, role, goal, model, reasoning_effort, allowed_tools, handoff_targets, safety_level
```

The orchestrator checks the registry before any MCP tool call. Read-only tools may retry. Cart mutation, checkout/payment, and booking tools do not auto-retry.

## Development

```bash
pytest
python -m compileall src tests
```

V1 is Telegram-only. WhatsApp and Zomato are intentionally out of scope for this first implementation.
