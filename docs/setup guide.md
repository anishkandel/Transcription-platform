Kaituhi Kōrero - Quick Docker Setup Guide
1. Install Docker Desktop

Download and install Docker Desktop.

After installation, open Docker Desktop and wait until it says Docker is running.

Then open PowerShell or Command Prompt and check:

docker --version

Then:

docker compose version

Both commands should return version information.

2. Extract the project ZIP

Extract the project somewhere easy to find.

Example:

C:\Users\YourName\Desktop\kaituhi-korero

The project folder should contain something like:

kaituhi-korero/
├── backend/
├── frontend/
├── data/
├── docker-compose.yml
└── .env
3. Make sure .env is in the project root

The .env file should be in the same folder as:

docker-compose.yml

Example:

kaituhi-korero/
├── docker-compose.yml
├── .env
├── backend/
└── frontend/
4. Open terminal in the project folder

In File Explorer, open the project folder.

Click the address bar, type:

powershell

and press Enter.

Or manually use:

cd /d "C:\path\to\kaituhi-korero"

Example:

cd /d "C:\Users\YourName\Desktop\kaituhi-korero"
5. Check the files

Run:

dir

Make sure you can see:

docker-compose.yml
backend
frontend
.env
6. Build and start the project

Run:

docker compose up --build

The first run may take a few minutes because Docker needs to download and build:

PostgreSQL
Python backend
Node frontend

Wait until you see something similar to:

Application startup complete

and:

VITE ready
7. Open the application

Frontend:

http://localhost:5173

Backend health check:

http://localhost:8000/health

API documentation:

http://localhost:8000/docs
8. Stop the project

In the terminal running Docker, press:

CTRL + C

Then run:

docker compose down
9. Start it again later

Normally you do not need to rebuild every time.

Open terminal in the project root and run:

docker compose up

If code dependencies or Docker files changed, use:

docker compose up --build
10. Check running containers

If you want to check whether everything is running:

docker ps

You should see containers similar to:

kaituhi-db
kaituhi-backend
kaituhi-frontend
11. If something goes wrong

Check logs:

docker compose logs

Backend only:

docker compose logs backend

Database only:

docker compose logs db

Frontend only:

docker compose logs frontend

If you need a completely fresh local database:

docker compose down -v
docker compose up --build

Important: -v deletes the Docker PostgreSQL data, so only use it when a fresh database is okay.

So for most teammates, the main workflow is basically:

cd path\to\project
docker compose up --build

then open:

http://localhost:5173