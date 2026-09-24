# Kaituhi Kōrero — Māori Meeting Transcription Platform

Internship prototype for Te Hiku Media: capture meeting audio (Zoom first), send it to Papa Reo for bilingual te reo Māori / English transcription, then view and export transcripts in a web app.

## Full setup guide

**Everything in one place (how it works, `.env`, Docker, Cloudflare Tunnel, Zoom Marketplace):**

→ **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**

## Quick start (Docker)

```powershell
cd kaituhi-korero
copy .env.example .env
# edit .env — at least SECRET_KEY and PAPAREO_API_KEY; add Zoom + tunnel URLs for live RTMS
docker compose up --build
```

- Web UI: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  

Register an account, then use **Mock RTMS** / file upload, or follow the Zoom + Cloudflare steps in the guide for live meetings.

## Stack

| Layer | Choice |
|-------|--------|
| Meetings | Zoom OAuth + Meetings API + RTMS |
| Speech | Papa Reo Standard API |
| Backend | FastAPI, SQLite, WebSockets |
| Frontend | React (Vite) |
| Ops | Docker Compose |

## Repo layout

```text
kaituhi-korero/
  backend/
  frontend/
  data/
  docs/GETTING_STARTED.md
  docker-compose.yml
  .env.example
```
