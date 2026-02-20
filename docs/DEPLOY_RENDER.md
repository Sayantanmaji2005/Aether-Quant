# Deploy To Render (Permanent Public URL)

## Prerequisites

- GitHub repo pushed (already done)
- Render account

## Steps

1. Open Render dashboard and click `New +` -> `Blueprint`.
2. Connect GitHub and select repo: `Sayantanmaji2005/Aether-Quant`.
3. Render will detect `render.yaml` and show:
   - Web service: `aether-quant-web`
   - Postgres database: `aether-quant-db`
4. Click `Apply`.
5. Wait for deploy to complete.
6. Open generated public URL:
   - format: `https://aether-quant-web.onrender.com` (or similar)

## First-time DB init

After first deploy, open Render Shell for the web service and run:

```bash
aetherquant db-init
```

## Verify deployment

Open these endpoints:

- `/healthz`
- `/readyz`

Example:

- `https://<your-render-url>/healthz`
- `https://<your-render-url>/readyz`

Then test an API route from the UI:

1. Open `https://<your-render-url>/`.
2. In Render dashboard, open service `aether-quant-web` -> `Environment`.
3. Copy `AETHERQ_API_KEY` (or `AETHERQ_ADMIN_API_KEY` for admin routes).
4. Paste that key into the UI API key field and run a workflow.

## Notes

- `AETHERQ_API_KEY` and `AETHERQ_ADMIN_API_KEY` are auto-generated from `render.yaml`.
- `AETHERQ_DATABASE_URL` is auto-wired from Render Postgres.
- If you want live broker mode in cloud, set broker env vars in Render service settings.
