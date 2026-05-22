# Food Order Bot

Telegram-first food ordering bot that can talk to Swiggy MCP and Zomato MCP through a shared provider layer.

## Current MVP

- Telegram command flow.
- Swiggy and Zomato MCP provider definitions.
- Generic Streamable HTTP MCP client.
- Per-chat session memory store.
- OAuth route skeleton for provider login.
- WhatsApp Cloud API webhook skeleton.
- Checkout/order/payment calls require explicit confirmation.

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

For Telegram, create a bot with BotFather and set `TELEGRAM_BOT_TOKEN`.

For provider access, request MCP developer access from Swiggy/Zomato. Until OAuth credentials are approved, you can test read flows with `DEV_SWIGGY_ACCESS_TOKEN` or `DEV_ZOMATO_ACCESS_TOKEN` if you have a temporary bearer token.

## Telegram Commands

```text
/start
/providers
/connect swiggy
/connect zomato
/search swiggy biryani in Bengaluru
/menu swiggy <restaurant_id>
/cart swiggy
/checkout swiggy
/confirm
/cancel
```

## Safety

The bot never auto-confirms tools that can place orders, mutate carts, or trigger payment. Those calls create a pending action and require `/confirm`.

## Notes

Zomato's public MCP manifest currently says third-party apps are not allowed without discussion. Treat this as a personal-use prototype until provider approval is granted.
