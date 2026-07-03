# Notes Delivery Bot

A Telegram bot that automatically delivers handwritten notes (PDFs, videos, HTML files) to approved users' private channels, while keeping source channels completely private. Built with **aiogram (official Telegram Bot API only)**, MongoDB Atlas, and deployed on Render.

## Overview

- Owner manages products (e.g. GK, English) via an inline Admin Panel — no code changes needed.
- Users set their own destination channel and request access to a product.
- Owner approves/rejects each request.
- **Archive-from-now-on delivery:** from the moment a product's source channel is set, the bot archives every new post as it arrives. On approval, a user receives everything archived so far for that product, then continues to receive new posts live. The bot cannot retrieve a channel's *pre-existing* history — this is a fundamental limitation of the official Bot API (no MTProto/user session is used). Upload notes to the source channel only *after* creating the product.
- Messages are copied (not forwarded) — no source channel name, forward tag, or link is ever exposed.
- Sync progress, resume, and failure handling are all persisted in MongoDB so nothing is lost on restart.
- If a product's source channel is later updated, its archive is cleared so content from two different channels is never mixed.

## Folder Structure

```
notes-bot/
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── database/
│   ├── client.py
│   ├── products.py
│   ├── users.py
│   ├── subscriptions.py
│   ├── progress.py
│   ├── settings.py
│   └── messages.py       # archived source-message references (new)
├── handlers/
│   ├── user_start.py
│   ├── user_status.py
│   ├── product_selection.py
│   ├── owner_commands.py
│   ├── admin_panel.py
│   ├── admin_products.py
│   ├── admin_settings.py
│   ├── admin_users.py
│   └── admin_tasks.py
├── engine/
│   ├── client_holder.py
│   ├── sync.py            # replays archived-but-undelivered messages
│   ├── archiver.py        # archives new source posts + live delivery (replaces listener.py)
│   ├── queue_manager.py
│   └── notifier.py
├── utils/
│   ├── keyboards.py
│   ├── validators.py
│   └── formatters.py
└── web/
    └── server.py
```

## Environment Variables

| Variable | Description |
|---|---|
| `BOT_TOKEN` | From @BotFather |
| `MONGO_URI` | MongoDB Atlas connection string |
| `OWNER_ID` | Your numeric Telegram user ID |
| `PORT` | Provided automatically by Render (defaults to 8080 locally) |

No `API_ID` / `API_HASH` / MTProto session is required — this bot uses only the official Bot API via `aiogram`.

Copy `.env.example` to `.env` for local development.

## Python Version

**3.11** (set in Render as the runtime; locally use `python3.11`)

## Start Command

```
python main.py
```

---

## BotFather Setup

1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, choose a name and username.
3. Copy the **Bot Token** → `BOT_TOKEN`.
4. Get your numeric Telegram ID (e.g. via @userinfobot) → `OWNER_ID`.

## MongoDB Atlas Setup

1. Create a free cluster at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas).
2. Database Access → create a user with read/write permissions.
3. Network Access → add `0.0.0.0/0` (allow from anywhere, required for Render).
4. Connect → Drivers → copy the connection string → `MONGO_URI` (insert your DB user password).

## GitHub Setup

1. Create a new repository.
2. Push this project:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo>.git
   git push -u origin main
   ```
3. Ensure `.env` is **not** committed (already in `.gitignore`).

## Render Deployment Steps

1. Go to [render.com](https://render.com) → New → **Web Service**.
2. Connect your GitHub repo.
3. Runtime: **Python 3**.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. Add all environment variables from the table above under **Environment**.
7. Instance Type: at least the free/starter tier (no autosleep dependency needed since it's a Web Service with a live health endpoint — but see note below on free-tier idling).
8. Deploy. Render will hit `GET /health` to confirm the service is live.

## Bot Setup After Deployment

1. Add your bot as **admin** (with post permission) to every source channel you own — do this *before* uploading notes, since archiving only starts once the product's source is set.
2. In each destination channel a user wants notes delivered to, they must add the bot as admin with post permission.
3. Message the bot as owner → `/start` → use the Admin Panel to add a product (name + forward a message from the source channel).
4. Only after the product is saved, start uploading notes to that source channel — everything posted from then on will be archived and delivered to approved users.

---

## Common Troubleshooting

**Bot doesn't respond after deploy**
- Check Render logs for polling startup messages — if missing, verify `BOT_TOKEN` is correct.
- Confirm `/health` returns `200 OK` (Render dashboard → Events).

**New notes aren't being delivered**
- Confirm the bot is admin in the source channel *and* the product was created *before* the notes were posted — the bot cannot back-fill pre-existing channel history via the Bot API.

**Destination channel rejected during setup**
- Bot must be admin in the destination channel with **Post Messages** permission enabled specifically (not just general admin).

**Sync stuck / not resuming after Render restart**
- Check MongoDB `progress` collection — `sync_status` should be `in_progress` for interrupted syncs; `main.py` auto-resumes these on startup. If stuck as `failed`, use **🔁 Retry Failed Syncs** in the Admin Panel.

**MongoDB connection errors**
- Confirm Network Access allows `0.0.0.0/0` and the password in `MONGO_URI` doesn't contain unescaped special characters (URL-encode if needed).

**Duplicate messages after resume**
- Should not occur — progress is tracked by `last_message_id` per user+product against the `messages` archive collection. If seen, check that only one bot instance is running (no duplicate Render deploys, and no other process is also polling with the same `BOT_TOKEN`).

**Render service sleeping / going idle**
- Free tier Web Services on Render may spin down after inactivity. Since this bot needs to run continuously (polling for new channel posts), use a paid instance tier that doesn't sleep.

**Rate limit errors from Telegram**
- Increase the forward delay via Admin Panel → Settings (up to 3.0s) if you see rate-limit errors in logs.
