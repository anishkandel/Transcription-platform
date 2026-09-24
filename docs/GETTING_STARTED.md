# Kaituhi Kōrero — How It Works & How to Run

One guide for teammates: what the prototype does today, how the live Zoom path works, and how to configure and start everything (Docker, `.env`, Cloudflare Tunnel, Zoom Marketplace).

---

## 1. What this project is

**Kaituhi Kōrero** is an internship prototype for Te Hiku Media. It captures meeting audio, sends it to **Papa Reo** (te reo Māori / English speech recognition), and shows a live transcript in a web app.

| Layer | Choice |
|-------|--------|
| Meetings | Zoom (OAuth + Meetings API + RTMS) |
| Speech | Papa Reo Streaming (raw PCM WebSocket) with Standard API fallback |
| Backend | Python / FastAPI, SQLite, WebSockets |
| Frontend | React (Vite) |
| Ops | Docker Compose |

**Demo without live Zoom:** upload audio or use **Mock RTMS** on the Session page.  
**Live Zoom:** Cloudflare Tunnel + Zoom Developer Pack + Marketplace app (webhooks + RTMS).

---

## 2. How it works today (architecture)

### Happy path (live Zoom)

```text
1. Register / login in the web app
2. Connect Zoom (OAuth)
3. Scheduled Meetings → Open session  (binds meeting_id → session_id)
4. Keep the Session page open (browser WebSocket)
5. Start / join the Zoom meeting
6. Zoom auto-starts RTMS → webhook meeting.rtms_started
7. Backend connects to Zoom signaling + media WebSockets
8. PCM audio → ~4s WAV slices → Papa Reo HTTP API
9. hub.broadcast → Session page Live transcript
```

### Three kinds of connections (do not mix them up)

| Connection | Who | Purpose |
|------------|-----|---------|
| Browser → `/ws/sessions/{session_id}` | Frontend | Receive `transcript.partial` and Zoom status events |
| Backend → Zoom **signaling** WS | Backend | RTMS handshake / keep-alive / ready ack |
| Backend → Zoom **media** WS | Backend | Receive meeting PCM audio |

Papa Reo is **HTTP only** on this path (no Papa Reo WebSocket for live RTMS).

`hub.broadcast(session_id, message)` is an in-process fan-out to browsers connected on that session. If the Session page is closed, live updates are not queued for later delivery.

### Main code map

| Piece | Path |
|-------|------|
| Zoom API + webhook + bind/start RTMS | `backend/app/api/zoom.py` |
| Live RTMS consumer | `backend/app/services/zoom/rtms_live.py` |
| Meeting ↔ session binding | `backend/app/services/zoom/rtms_registry.py` |
| Papa Reo client | `backend/app/services/speech/papa_reo.py` |
| WebSocket hub | `backend/app/services/websocket_manager.py` |
| Session UI | `frontend/src/pages/SessionPage.tsx` |
| Meetings UI | `frontend/src/pages/ZoomPage.tsx` |

### Product UI flow (current)

1. **Scheduled Meetings → Open session** — primary entry (creates session + bind).
2. Join Zoom — RTMS should start automatically when Marketplace auto-start + Developer Pack are set up.
3. Session page **Retry / manual start RTMS** — fallback only.
4. **Mock RTMS** / file upload — demos without live Zoom audio.

---

## 3. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recommended), **or** Python 3.11+ and Node.js 18+
- Git
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) for Zoom HTTPS (OAuth + webhooks)
- Zoom account + Marketplace access
- Zoom **Developer Pack** (trial or paid) for live RTMS: https://zoom.us/pricing/developer
- Papa Reo API key from Te Hiku

---

## 4. Clone and create `.env`

From the repo root `kaituhi-korero/`:

**Windows (PowerShell):**

```powershell
copy .env.example .env
```

**macOS / Linux:**

```bash
cp .env.example .env
```

Then edit `.env`. Values you **must** set for a full Zoom + transcript setup:

| Variable | What to put |
|----------|-------------|
| `SECRET_KEY` | Any long random string |
| `PAPAREO_API_KEY` | Your Papa Reo token (do not commit real secrets) |
| `ZOOM_CLIENT_ID` | From Marketplace → App Credentials |
| `ZOOM_CLIENT_SECRET` | From Marketplace → App Credentials |
| `PUBLIC_BACKEND_URL` | Your **current** Cloudflare backend tunnel URL, e.g. `https://xxxx.trycloudflare.com` |
| `ZOOM_REDIRECT_URI` | `{PUBLIC_BACKEND_URL}/api/zoom/oauth/callback` |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | From Marketplace Event Subscription secret |
| `ZOOM_RTMS_ENABLED` | `true` for live RTMS |
| `ZOOM_AUTO_START_RTMS_ON_MEETING_STARTED` | `true` recommended |
| `PUBLIC_FRONTEND_URL` | Usually `http://127.0.0.1:5173` (or a frontend tunnel if Zoom Surface Home URL needs it) |
| `CORS_ORIGINS` | Include frontend origins, e.g. `http://localhost:5173,http://127.0.0.1:5173` |

Docker Compose overrides DB/upload paths inside the container to `./data` under `/app` and mounts host `./data` — you normally do not need to change `DATABASE_URL` for Docker.

Leave `ZOOM_*` empty only if you will use **Mock RTMS / file upload** and skip Zoom.

After any `.env` change, **restart** the backend (or `docker compose restart backend`).

---

## 5. Start the app with Docker (recommended)

1. Start **Docker Desktop**.
2. From `kaituhi-korero/`:

```powershell
docker compose up --build
```

Detached:

```powershell
docker compose up --build -d
```

Useful commands:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

URLs:

| Service | URL |
|---------|-----|
| Web UI | http://127.0.0.1:5173 |
| API docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |

Register an account in the UI first, then optionally Connect Zoom.

Frontend in Docker uses an **empty** `VITE_API_BASE_URL` and proxies `/api` and `/ws` to the `backend` service so cookies work. Do **not** set `VITE_API_BASE_URL=http://localhost:8000` in the browser for Docker.

---

## 6. Start without Docker (optional)

**Backend:**

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

---

## 7. Cloudflare Tunnel (HTTPS for Zoom)

Zoom will not accept `http://127.0.0.1` for OAuth redirect or webhooks. Use a **quick Cloudflare Tunnel**.

### Install cloudflared

- Download: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
- Ensure `cloudflared` is on your `PATH`.

### Tunnel the backend (required for OAuth + webhooks)

With backend on port 8000:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the printed URL, for example:

```text
https://ingredients-samuel-city-compared.trycloudflare.com
```

Then set:

```env
PUBLIC_BACKEND_URL=https://ingredients-samuel-city-compared.trycloudflare.com
ZOOM_REDIRECT_URI=https://ingredients-samuel-city-compared.trycloudflare.com/api/zoom/oauth/callback
```

Restart the backend. Leave this `cloudflared` process **running** while testing Zoom.

### Optional: tunnel the frontend (Zoom in-meeting Home URL)

```powershell
cloudflared tunnel --url http://127.0.0.1:5173
```

Use that hostname as Surface **Home URL** / Domain Allow List if you load the React app inside Zoom. This repo’s Vite config already sets `allowedHosts: true`.

### When the tunnel URL changes

Quick tunnels get a **new** hostname every restart. Update:

1. `.env` (`PUBLIC_BACKEND_URL`, `ZOOM_REDIRECT_URI`) → restart backend  
2. Marketplace OAuth Redirect URL + Allow List  
3. Marketplace Event Subscription endpoint URL → Save → Validate  
4. Surface Home URL / domains (if using a frontend tunnel)

---

## 8. Zoom Marketplace configuration (full path)

### 8.1 Create a General App

1. https://marketplace.zoom.us/ → sign in  
2. **Develop** → **Build App** → **General app**  
3. **User-managed**  
4. Stay in Development / Local Test (no need to publish)  
5. Copy **Client ID** / **Client Secret** into `.env`

### 8.2 OAuth redirect

In Basic Information / OAuth:

- **OAuth Redirect URL:**  
  `https://<BACKEND_TUNNEL>/api/zoom/oauth/callback`
- **Allow List:** same URL (or tunnel origin)

Must match `ZOOM_REDIRECT_URI` exactly.

### 8.3 Scopes

Add at least:

**Meetings / user**

- `user:read:user`
- `meeting:read:list_meetings`
- `meeting:read:list_upcoming_meetings`
- `meeting:read:meeting`
- `meeting:write:meeting`
- `meeting:update:meeting`
- `meeting:delete:meeting`

**RTMS**

- `meeting:read:meeting_audio`
- `meeting:update:participant_rtms_app_status`

Save. After every scope change, **Connect Zoom** again in the web app so the token includes new scopes.

### 8.4 Event Subscription

1. Turn **Event Subscription** on  
2. Endpoint URL:  
   `https://<BACKEND_TUNNEL>/api/zoom/webhook`  
3. Auth: **Default Header Provided by Zoom**  
4. Subscribe at least:
   - `meeting.rtms_started`
   - `meeting.rtms_stopped`
   - `meeting.started` (recommended; used with auto-start)
5. Save → copy **Secret Token** → `ZOOM_WEBHOOK_SECRET_TOKEN`  
6. **Validate** — backend should log `[zoom-webhook]`

Validation OK ≠ live `meeting.rtms_started` during a meeting; that still needs RTMS entitlement + auto-start / start API.

### 8.5 Surface (in-meeting)

- Enable **Meetings**
- **Allow auto-start for RTMS apps:** On  
- Optional Home URL: frontend tunnel URL  
- Domain Allow List: frontend tunnel hostname  
- Leave Meeting SDK / Phone / Chat embeds Off unless you need them

### 8.6 Developer Pack

1. https://zoom.us/pricing/developer  
2. Start trial or buy credits  
3. An active trial is enough for development

### 8.7 Install / Local Test

Add the app to your Zoom user (Local Test / Apps on account). Host meetings with **that same account**. Enable account settings that allow apps to access meeting / realtime content when available.

### 8.8 Connect Zoom in the product

1. Open http://127.0.0.1:5173 → Register / Sign in  
2. **Scheduled Meetings** or **Settings** → **Connect Zoom**  
3. Approve scopes → Refresh meetings  

### 8.9 Live test

1. **Open session** for a meeting (keep page open)  
2. Start the Zoom meeting  
3. Backend logs should include something like:

```text
[zoom-rtms] bound session=...
[zoom-webhook] event='meeting.rtms_started'
[zoom-rtms] handle_rtms_started ... session_id='...'
[zoom-rtms] consumer_started ...
```

4. Speak → Live transcript updates  
5. Use **Retry / manual start RTMS** only if nothing starts  

---

## 9. Quick verification checklist

- [ ] `docker compose up --build` (or local uvicorn + Vite)  
- [ ] `.env` created from `.env.example` and filled  
- [ ] Backend tunnel running; `.env` URLs match current hostname  
- [ ] Marketplace OAuth redirect matches callback  
- [ ] Scopes + Event Subscription + webhook secret  
- [ ] Developer Pack active  
- [ ] Surface RTMS auto-start On; app Local Test installed  
- [ ] Connect Zoom in UI  
- [ ] Open session → join meeting → see `[zoom-rtms]` + transcript  
- [ ] Or: Mock RTMS / file upload without Zoom  

---

## 10. Common failures

| Symptom | Fix |
|---------|-----|
| Redirect URL invalid | Use HTTPS tunnel callback, not localhost |
| Webhook Validate fails | Tunnel down / wrong path / secret / backend not on 8000 |
| No `meeting.rtms_started` | Developer Pack, event types, auto-start, app install |
| Webhook OK, UI Idle | Open session / bind; keep Session WebSocket open; check `session_id` in `[zoom-rtms]` logs |
| Vite host not allowed | Restart frontend; `allowedHosts` already enabled in this repo |
| Cookie / auth weird in Docker | Keep `VITE_API_BASE_URL` empty; use Vite proxy |
| Tunnel hostname changed | Update `.env` + Marketplace OAuth + webhook URL |

---

## 11. Repo layout

```text
kaituhi-korero/
  backend/           FastAPI + Zoom + speech
  frontend/          React UI
  data/              SQLite + uploads (Docker volume)
  docs/              This guide
  docker-compose.yml
  .env.example
  .env               Local secrets (do not commit)
```

That is the full current setup path for teammates: run the stack, configure `.env`, expose HTTPS with Cloudflare, finish Zoom Marketplace, then Open session and join the meeting for live transcription.
