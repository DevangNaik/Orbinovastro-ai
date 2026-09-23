# Deploying the ORBINOVASTRO AI backend

This gets the FastAPI backend a real, permanent `https://...` URL that your
published Codex Sites page can call — the `BASE_URL` that `CODEX_SITES_INTEGRATION.md`
currently has as a placeholder.

**I can't do this step for you.** Creating a hosting account isn't something
I'm able to do on your behalf (same reason I couldn't create the Supabase or
Stripe accounts) — but everything below is written so it takes about 10
minutes and no technical decisions beyond clicking a few buttons.

## What's already prepared

- `Dockerfile` (in this folder) — builds the backend into a deployable image.
  Verified in the sandbox: dependencies install cleanly, the server boots,
  `/health` and `/api/chart` both return correct results, and CORS behaves
  as expected (see "ALLOWED_ORIGINS" below). The one thing not testable from
  here is the Docker build itself — this sandbox's network policy blocks
  pulling images from Docker Hub — but the Dockerfile is a standard,
  minimal `python:3.11-slim` + `pip install` + `uvicorn` setup; Render (or
  any host) builds it on its own infrastructure, not this sandbox.
- `render.yaml` — a Render "Blueprint" that pre-fills a new Web Service's
  settings when Render reads this repo.
- `.dockerignore` — keeps `.env`, the local subscriber database, and test
  files out of the built image.
- `backend/app/main.py` now reads an `ALLOWED_ORIGINS` environment variable
  (comma-separated) to lock CORS down to just your real sites instead of
  the old wide-open `*`. Tested: a disallowed origin gets no CORS header
  (the browser blocks it), an allowed one does.
- `.gitignore` — keeps `backend/.env` (your real API keys) and
  `backend/subscribers.db` out of the repo. **Important**: run `git add .`
  only after this file exists (it already does), so your real
  `OPENAI_API_KEY` never ends up in Git history, even in a private repo.

## Step by step (Render — the host I'd recommend; free tier is enough to start)

1. **Get this code into a GitHub repository under github.com/DevangNaik.**
   I can't create the repo myself (same limit as not being able to create
   the hosting/Supabase/Stripe accounts, and I don't have a way to push to
   your GitHub from here either) — but it's two steps:

   **a) Create an empty repo on GitHub:**
   - Go to <https://github.com/new> (while signed in as DevangNaik).
   - Repository name: `orbinovastro-ai` (or whatever you prefer — just
     reuse the same name in step 1b below).
   - Visibility: **Private** — this is your client's product code.
   - Leave "Add a README", ".gitignore", and "license" all **unchecked**
     (this repo already has its own `.gitignore`) so GitHub creates a
     completely empty repo.
   - Click **Create repository**.

   **b) Push this folder to it.** Open PowerShell, then:
   ```powershell
   cd "C:\Users\devan\OneDrive\Documents\Horoscopes\ORBINOVASTRO\ai_app"
   git init
   git add .
   git commit -m "Initial commit: ORBINOVASTRO AI app"
   git branch -M main
   git remote add origin https://github.com/DevangNaik/orbinovastro-ai.git
   git push -u origin main
   ```
   If `git` isn't installed, GitHub Desktop (desktop.github.com) does the
   same thing through a GUI instead — point it at this folder and publish
   it as a new private repository. If prompted to sign in during `git
   push`, use your GitHub account (DevangNaik) — this is between you and
   GitHub, not something I handle.
   - **Double-check before pushing**: run `git status` after `git add .`
     and confirm `backend/.env` does *not* appear in the list of files to
     be committed (the `.gitignore` should already exclude it) — that file
     holds your real API keys and should never reach GitHub.
2. Go to **render.com** and sign up (free). Connect your GitHub account
   when it asks.
3. Click **New +** → **Blueprint**, and point it at your repo. Render will
   read `render.yaml` and pre-fill a new Web Service named
   `orbinovastro-ai` (Docker runtime, free plan, health check on `/health`).
   If you'd rather not use the Blueprint, **New +** → **Web Service** and
   set it up by hand: Runtime = Docker, Dockerfile path = `./Dockerfile`,
   root/context = repo root.
4. Before the first deploy, set these **Environment Variables** in the
   Render dashboard (Settings → Environment):
   - `OPENAI_API_KEY` — your real key (same one from `backend/.env` locally;
     never commit this to the repo — `.dockerignore` already keeps your
     local `.env` out of the image).
   - `OPENAI_MODEL` — `gpt-4o-mini` (or whatever you're using).
   - `ALLOWED_ORIGINS` — your Sites page's URL and orbinovastro.com,
     comma-separated, e.g.
     `https://your-project.openai.site,https://orbinovastro.com`
     (send me the exact Sites URL if you want me to double check this).
   - `AUTH_ENABLED` — leave as `false` for now (matches everything else
     already documented).
   - Leave `SUPABASE_*` / `STRIPE_*` blank until those accounts exist.
5. Click **Deploy**. First build takes a few minutes (installing
   `pyswisseph` compiles a small C extension — normal, not an error).
6. Once it's live, Render shows a URL like
   `https://orbinovastro-ai.onrender.com`. Test it: open
   `https://orbinovastro-ai.onrender.com/health` in a browser — you should
   see `{"status":"ok"}`.
7. **Send me that URL** and I'll update `CODEX_SITES_INTEGRATION.md`'s
   `BASE_URL` and the roadmap doc to match — and let me know once you've
   pasted it into the Codex Sites project's config too, so I can note the
   integration as fully wired up.

**One free-tier quirk to know:** Render's free web services spin down after
15 minutes of no traffic and take ~30-50 seconds to wake back up on the next
request — the Sites page's first calculation after a quiet period may feel
slow, not broken. If that matters for how visitors will use it, an upgrade
to Render's cheapest paid tier (~$7/month) removes the spin-down.

## If you'd rather use Railway or a VPS instead

The same `Dockerfile` works on Railway (New Project → Deploy from GitHub
repo → it auto-detects the Dockerfile) with the same environment variables.
A VPS is more setup (install Docker or Python directly, put nginx + a real
TLS cert in front of it) — say the word if you'd rather go that route and
I'll write out those exact steps too.
