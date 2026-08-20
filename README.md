# 🗃️ Store Service Bot

A Telegram bot that automatically delivers handwritten notes (PDFs, videos, HTML files) to approved users' private channels, while keeping source channels completely private. Built with **aiogram** (official Telegram Bot API only — no MTProto/user session), backed by **MongoDB**.

> 🚀 **This bot can be deployed on Render, Heroku, Koyeb, Railway, Google Cloud Run, Google Colab, VPS, and Termux.** See [Deployment](#-deployment).

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Behavior](#-key-behavior)
- [Bot UI / UX Walkthrough](#-bot-ui--ux-walkthrough)
  - [Owner: Admin Panel](#owner-admin-panel)
  - [Owner: Adding a Product](#owner-adding-a-product)
  - [Owner: Owner-Only Commands](#owner-owner-only-commands)
  - [User: First-Time Setup](#user-first-time-setup)
  - [User: Requesting a Product](#user-requesting-a-product)
  - [User: Status & Destination](#user-status--destination)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [BotFather Setup](#-botfather-setup)
- [MongoDB Atlas Setup](#-mongodb-atlas-setup)
- [Bot Setup After Deployment](#-bot-setup-after-deployment)
- [Repository Structure](#-repository-structure)
- [Troubleshooting](#-troubleshooting)

---

## 🔎 Overview

- Owner manages products (e.g. GK, English) via an inline **Admin Panel** — no code changes needed.
- Users set their own destination channel and request access to a product.
- Owner approves/rejects each request.
- **Archive-from-now-on delivery:** from the moment a product's source channel is set, the bot archives every new post as it arrives. On approval, a user receives everything archived so far for that product, then continues to receive new posts live.
- Messages are **copied** (not forwarded) — no source channel name, forward tag, or link is ever exposed.
- Sync progress, resume, and failure handling are all persisted in MongoDB so nothing is lost on restart.
- If a product's source channel is later updated, its archive is cleared so content from two different channels is never mixed.

## ⚠️ Key Behavior

The bot **cannot retrieve a channel's pre-existing history** — this is a fundamental limitation of the official Bot API (no MTProto/user session is used). Upload notes to the source channel only *after* creating the product; anything posted before that point will never reach subscribed users.

---

## 🎛 Bot UI / UX Walkthrough

### Owner: Admin Panel

Sending `/start` as the owner opens the **Admin Panel** directly:

```
➕ Add Product
📦 Manage Products
⚙️ Settings
👑 Admin Panel
```

**👑 Admin Panel** expands into:

```
👥 All Users
✅ Allowed Users
⏳ Pending Requests
🚫 Banned Users
🔄 Active Tasks
📊 Statistics
🔁 Retry Failed Syncs
🟢 Keep Alive
⬅️ Back
```

- **👥 All Users / ✅ Allowed Users / 🚫 Banned Users** — browsable lists.
- **⏳ Pending Requests** — shows each user's product request with **✅ Allow** / **❌ Reject** buttons.
- **🔄 Active Tasks** — running/paused sync jobs, each with pause/resume controls.
- **📊 Statistics** — user and delivery counts at a glance.
- **🔁 Retry Failed Syncs** — re-queues any sync that ended in a `failed` state.
- **🟢 Keep Alive** — opens a sub-menu:
  ```
  🔄 Ping Now
  📊 Status
  ⬅️ Back
  ```
  Manually pings the bot's own `/health` endpoint (via `RENDER_EXTERNAL_URL`) to help prevent free-tier idling. Shows "Not configured" if `RENDER_EXTERNAL_URL` isn't set (expected on platforms without a public URL, e.g. Google Colab).

**⚙️ Settings** lets the owner pick the delay between delivered messages:
```
1.0s   2.0s ✅   3.0s
⬅️ Back
```

**📦 Manage Products** lists every product; tapping one opens:
```
✏️ Rename        🔗 Update Source
🔕 Enable/Disable 🗑 Delete
⬅️ Back
```
> Updating a product's source channel **clears its archive** — content from two different channels is never mixed.

### Owner: Adding a Product

1. Admin Panel → **➕ Add Product**
2. Bot asks for the product name → owner sends it as plain text.
3. Bot asks the owner to **forward a message from the source channel**.
4. Bot verifies it has admin/post access to that channel, then saves the product.
5. From this point on, every new post in that source channel is archived automatically.

### Owner: Owner-Only Commands

| Command | Purpose |
|---|---|
| `/start` | Opens the Admin Panel (owner only). |
| `/ban <user_id>` | Bans a user from using the bot. |
| `/unban <user_id>` | Lifts a ban. |
| `/resume` | Manually resumes any sync jobs stuck in an interrupted state. |

### User: First-Time Setup

1. User sends `/start`.
2. If no destination channel is set yet, the bot asks them to **forward any message from their destination channel**.
3. Bot verifies it has admin/post access there, saves it, then shows the **Main Menu**.

### User: Requesting a Product

The Main Menu lists every enabled product as a button, plus:
```
📊 Status   🔁 Change Destination
```

1. User taps a product name.
2. Bot shows that product's panel with a **request access** action.
3. Owner receives a notification with **✅ Allow** / **❌ Reject** buttons.
4. On approval, the bot immediately starts syncing all archived posts for that product to the user's destination channel, then keeps delivering new posts live.

### User: Status & Destination

- **📊 Status** — shows sync state per subscribed product:
  ```
  🟢 In Progress   ⏸ Paused   ✅ Completed   🚫 Cancelled   ❌ Failed
  ```
  with pause/resume controls on active syncs.
- **🔁 Change Destination** — re-triggers the "forward a message from your channel" flow to switch destinations at any time.

---

## 🔑 Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BOT_TOKEN` | ✅ Yes | — | Bot token from @BotFather |
| `MONGO_URI` | ✅ Yes | — | MongoDB connection string (e.g. from MongoDB Atlas) |
| `OWNER_ID` | ✅ Yes | — | Your numeric Telegram user ID — the bot's admin |
| `PORT` | ❌ No | `8080` | Port for the built-in aiohttp health server (usually set automatically by the host) |
| `RENDER_EXTERNAL_URL` | ❌ No | — | Used only by the manual **Keep Alive → Ping Now** button. Render sets this automatically; leave unset elsewhere — the feature just reports "Not configured" instead of failing |

No `API_ID` / `API_HASH` / MTProto session is required — this bot uses only the official Bot API via `aiogram`. Copy `.env.example` to `.env` for local development.

---

## 🚀 Deployment

This bot is **polling-based** (`dp.start_polling`, not a Telegram webhook), so it doesn't strictly need a public URL to function. The included aiohttp server only exists as a health-check endpoint (`/health`) for platforms (like Render's free tier) that require the process to bind a port. It supports **Render, Heroku, Koyeb, Railway, Google Cloud Run, Google Colab, VPS, and Termux**.

### One-Click Deploy

| Platform | Deploy |
|---|---|
| Render | [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/cosmos475/store-service) |
| Heroku | [![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/cosmos475/store-service) |
| Koyeb | [![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/cosmos475/store-service&branch=main&name=store-service) |
| Google Colab | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/cosmos475/store-service/blob/main/colab_deploy.ipynb) |
| Google Cloud | [![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://ssh.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/cosmos475/store-service&cloudshell_tutorial=.cloudshell/GCLOUD.md) |

> ⚠️ None of these badges fully automate deployment — each opens that platform's setup screen where you still need to fill in environment variables manually (see the table above). They save the "find and configure a new app" step, not the "enter your credentials" step.

> ℹ️ **Railway**: this bot can also be deployed on Railway — it auto-detects the Python app via Nixpacks and picks up `requirements.txt` + `Procfile` with no extra configuration needed. There's no one-click badge here because Railway deploy buttons require a pre-registered Railway template (a manual one-time setup on Railway's side, separate from this repo). To deploy: create a new Railway project → "Deploy from GitHub repo" → select this repo → set the environment variables from the table above.

### Render (primary supported platform)

1. Go to [render.com](https://render.com) → New → **Web Service**.
2. Connect your GitHub repo (or use the badge above, which reads `render.yaml` automatically).
3. Runtime: **Python 3** · Build Command: `pip install -r requirements.txt` · Start Command: `python main.py`.
4. Add `BOT_TOKEN`, `MONGO_URI`, `OWNER_ID` under **Environment**.
5. Deploy. Render will hit `GET /health` to confirm the service is live.
6. Free tier note: this bot needs to run continuously (polling for new channel posts); a free Web Service may spin down after inactivity, so a paid instance tier is recommended for uninterrupted delivery.

### Heroku

Uses the included `app.json` and `Procfile`. After clicking the badge above, fill in the prompted fields (`BOT_TOKEN`, `MONGO_URI`, `OWNER_ID`).

### Koyeb / Google Cloud Run

Both use the included `Dockerfile` directly — no extra build configuration needed. For manual Cloud Run deployment via `gcloud` CLI, see `.cloudshell/GCLOUD.md`.

### Google Colab (temporary/testing)

Click the Colab badge above to open `colab_deploy.ipynb`. Fill in the mandatory fields (`BOT_TOKEN`, `MONGO_URI`, `OWNER_ID`) and run the single cell — it clones the repo, installs dependencies, and runs `python3 main.py`. The **Keep Alive → Ping Now** button will show "Not configured" here since Colab has no public URL, but nothing else is affected. The cell blocks and streams logs live; press ■ to stop.

> ⚠️ Colab sessions are temporary (disconnect on tab close, inactivity, or after Colab's free-tier time limit — up to ~12 hours). Use this for quick testing only; for always-on hosting, use Render/Heroku/Koyeb/Railway above.

### VPS

```bash
git clone https://github.com/cosmos475/store-service.git
cd store-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net"
export OWNER_ID="your_telegram_user_id"
python3 main.py
```

Or via Docker, using the included `Dockerfile`:

```bash
git clone https://github.com/cosmos475/store-service.git
cd store-service
sudo apt install docker.io -y
sudo docker build -t store-service .
sudo docker run -it --rm --env-file .env store-service
```

No public URL is required — this bot works over polling on any VPS with outbound internet access.

### Termux (Android)

```bash
pkg update && pkg upgrade -y
pkg install python git -y
git clone https://github.com/cosmos475/store-service.git
cd store-service
pip install -r requirements.txt
export BOT_TOKEN="your_bot_token"
export MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net"
export OWNER_ID="your_telegram_user_id"
python3 main.py
```

> If any MongoDB-related package fails to build on Termux, run `pkg install libffi openssl` first, then retry `pip install -r requirements.txt`. A remote MongoDB instance (e.g. MongoDB Atlas's free tier) is recommended over trying to run MongoDB on-device.

---

## 🤖 BotFather Setup

1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, choose a name and username.
3. Copy the **Bot Token** → `BOT_TOKEN`.
4. Get your numeric Telegram ID (e.g. via @userinfobot) → `OWNER_ID`.

## 🍃 MongoDB Atlas Setup

1. Create a free cluster at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas).
2. Database Access → create a user with read/write permissions.
3. Network Access → add `0.0.0.0/0` (allow from anywhere, required for most hosts).
4. Connect → Drivers → copy the connection string → `MONGO_URI` (insert your DB user password).

## 🏁 Bot Setup After Deployment

1. Add your bot as **admin** (with post permission) to every source channel you own — do this *before* uploading notes, since archiving only starts once the product's source is set.
2. In each destination channel a user wants notes delivered to, they must add the bot as admin with post permission.
3. Message the bot as owner → `/start` → use the Admin Panel to add a product (name + forward a message from the source channel).
4. Only after the product is saved, start uploading notes to that source channel — everything posted from then on will be archived and delivered to approved users.

---

## 🗂 Repository Structure

```
store-service/
├── main.py
├── config.py
├── requirements.txt
├── render.yaml               # Render service definition
├── Procfile                  # Heroku process definition
├── Dockerfile                 # Used by Koyeb, Railway, Google Cloud Run, VPS-via-Docker
├── app.json                  # Heroku one-click deploy manifest
├── colab_deploy.ipynb         # Google Colab one-click deploy notebook
├── .cloudshell/                # Google Cloud Shell walkthrough
│   ├── tutorial.yaml
│   └── GCLOUD.md
├── .env.example
├── database/
│   ├── client.py
│   ├── products.py
│   ├── users.py
│   ├── subscriptions.py
│   ├── progress.py
│   ├── settings.py
│   └── messages.py            # archived source-message references
├── handlers/
│   ├── user_start.py
│   ├── user_status.py
│   ├── product_selection.py
│   ├── owner_commands.py
│   ├── admin_panel.py
│   ├── admin_products.py
│   ├── admin_settings.py
│   ├── admin_users.py
│   ├── admin_tasks.py
│   └── admin_keepalive.py
├── engine/
│   ├── client_holder.py
│   ├── sync.py                # replays archived-but-undelivered messages
│   ├── archiver.py             # archives new source posts + live delivery
│   ├── queue_manager.py
│   └── notifier.py
├── utils/
│   ├── keyboards.py
│   ├── validators.py
│   └── formatters.py
└── web/
    └── server.py
```

---

## 🧯 Troubleshooting

**Bot doesn't respond after deploy**
- Check host logs for polling startup messages — if missing, verify `BOT_TOKEN` is correct.
- Confirm `/health` returns `200 OK`.

**New notes aren't being delivered**
- Confirm the bot is admin in the source channel *and* the product was created *before* the notes were posted — the bot cannot back-fill pre-existing channel history via the Bot API.

**Destination channel rejected during setup**
- Bot must be admin in the destination channel with **Post Messages** permission enabled specifically (not just general admin).

**Sync stuck / not resuming after a restart**
- Check MongoDB `progress` collection — `sync_status` should be `in_progress` for interrupted syncs; `main.py` auto-resumes these on startup. If stuck as `failed`, use **🔁 Retry Failed Syncs** in the Admin Panel, or the owner-only `/resume` command.

**MongoDB connection errors**
- Confirm Network Access allows `0.0.0.0/0` and the password in `MONGO_URI` doesn't contain unescaped special characters (URL-encode if needed).

**Duplicate messages after resume**
- Should not occur — progress is tracked by `last_message_id` per user+product against the `messages` archive collection. If seen, check that only one bot instance is running (no duplicate deploys, and no other process is also polling with the same `BOT_TOKEN`).

**Render service sleeping / going idle**
- Free tier Web Services on Render may spin down after inactivity. Since this bot needs to run continuously (polling for new channel posts), use a paid instance tier that doesn't sleep, or use the built-in **Keep Alive → Ping Now** feature to help mitigate idling.

**Rate limit errors from Telegram**
- Increase the forward delay via Admin Panel → Settings (up to 3.0s) if you see rate-limit errors in logs.
