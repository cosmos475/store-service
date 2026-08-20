# Deploy to Google Cloud Run

This bot ships with a `Dockerfile`, so it deploys to Cloud Run with no extra
build configuration.

## 1. Set your project

```sh
gcloud config set project YOUR_PROJECT_ID
```

## 2. Build and deploy

```sh
gcloud run deploy store-service \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars \
BOT_TOKEN=your_bot_token,\
MONGO_URI=your_mongodb_connection_string,\
OWNER_ID=your_telegram_user_id
```

Cloud Run will print a service URL when this finishes (e.g.
`https://store-service-xxxxx.a.run.app`). This bot doesn't need that URL for
core functionality (it's polling-based, not webhook-based) — the manual
"Keep Alive" ping button in the admin panel specifically looks for
`RENDER_EXTERNAL_URL`, so it won't be usable here unless you set that
variable manually to this Cloud Run URL.

## 3. Verify

```sh
gcloud run services describe store-service --region us-central1
```

Visit the printed service URL's `/health` path — it should return `OK`.

See `.env.example` in the repo root for what each variable means and how to
obtain it (BotFather, userinfobot, MongoDB Atlas, etc).
