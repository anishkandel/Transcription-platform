# Kaituhi Kōrero - Quick Docker Setup Guide

## 1. Install Docker Desktop

Install Docker Desktop and make sure it is running.

Check Docker:

```bash
docker --version
docker compose version
```

## 2. Extract the Project

Extract the project ZIP to a folder on your computer.

Example:

```text
C:\Users\YourName\Desktop\kaituhi-korero
```

The project folder should contain:

```text
kaituhi-korero/
├── backend/
├── frontend/
├── data/
├── docker-compose.yml
└── .env
```

## 3. Check the `.env` File

Make sure the provided `.env` file is in the same project root folder as `docker-compose.yml`.

Example:

```text
kaituhi-korero/
├── docker-compose.yml
├── .env
├── backend/
└── frontend/
```

## 4. Open a Terminal in the Project Folder

In File Explorer, open the project folder.

Click the address bar, type:

```text
powershell
```

and press Enter.

Or navigate manually:

```bat
cd /d "C:\path\to\kaituhi-korero"
```

## 5. Check the Project Files

Run:

```bat
dir
```

You should see:

```text
docker-compose.yml
backend
frontend
.env
```

## 6. Build and Start the Application

Run:

```bash
docker compose up --build
```

The first run may take a few minutes.

Docker will start:

- PostgreSQL database
- FastAPI backend
- React/Vite frontend

Wait until the backend shows:

```text
Application startup complete.
```

and the frontend shows that Vite is ready.

## 7. Open the Application

Frontend:

```text
http://localhost:5173
```

Backend health check:

```text
http://localhost:8000/health
```

API documentation:

```text
http://localhost:8000/docs
```

## 8. Stop the Application

In the terminal where Docker is running, press:

```text
CTRL + C
```

Then run:

```bash
docker compose down
```

## 9. Start the Application Again Later

Normally, run:

```bash
docker compose up
```

If dependencies, Dockerfiles, or requirements have changed, run:

```bash
docker compose up --build
```

## 10. Check Running Containers

Run:

```bash
docker ps
```

You should see containers similar to:

```text
kaituhi-db
kaituhi-backend
kaituhi-frontend
```

## 11. Troubleshooting

View all logs:

```bash
docker compose logs
```

Backend logs:

```bash
docker compose logs backend
```

Database logs:

```bash
docker compose logs db
```

Frontend logs:

```bash
docker compose logs frontend
```

If a completely fresh local database is required:

```bash
docker compose down -v
docker compose up --build
```

**Warning:** `docker compose down -v` deletes the Docker PostgreSQL data.

## Quick Start

After Docker Desktop is installed and the project has been extracted:

```bash
cd path\to\project
docker compose up --build
```

Then open:

```text
http://localhost:5173
```
