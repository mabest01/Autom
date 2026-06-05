# HelloWork Job Application Automation System

Automated job scraping and application system for HelloWork. Scrapes alternance job listings, generates personalized French cover messages using Claude AI, and optionally auto-applies.

---

## Architecture

- **Backend**: FastAPI + Playwright + Anthropic Claude (Python 3.11)
- **Frontend**: React 18 + TypeScript dashboard
- **Database**: SQLite via aiosqlite
- **Scheduler**: APScheduler (scrapes every N hours, auto-applies 30 min later)
- **Infrastructure**: Docker Compose + Nginx reverse proxy

---

## AWS EC2 Deployment Guide

### 1. Prerequisites

- Ubuntu 22.04 LTS (recommended AMI: `ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*`)
- Instance type: **t2.small** minimum (t2.medium recommended for Playwright browser)
- Security group inbound rules:
  - Port 22 (SSH) from your IP
  - Port 80 (HTTP) from 0.0.0.0/0
  - Port 443 (HTTPS) from 0.0.0.0/0
- At least 20 GB EBS storage (Playwright + Chromium requires ~500 MB)

---

### 2. Install Docker and Docker Compose

SSH into your EC2 instance, then run:

```bash
# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add ubuntu user to docker group (avoids needing sudo)
sudo usermod -aG docker ubuntu

# Apply group change without logout
newgrp docker

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Verify installations
docker --version
docker compose version
```

---

### 3. Clone the Repository and Configure Environment

```bash
# Clone your repository (replace with your actual repo URL)
git clone https://github.com/YOUR_USERNAME/hellowork-automation.git
cd hellowork-automation

# Copy and edit the environment file
cp .env.example .env
nano .env
```

Fill in your credentials in `.env`:

```env
HELLOWORK_EMAIL=your_hellowork_email@example.com
HELLOWORK_PASSWORD=your_hellowork_password
ANTHROPIC_API_KEY=sk-ant-...
SEARCH_KEYWORDS=alternance data,alternance développeur,alternance informatique
SEARCH_LOCATION=Île-de-France
SCRAPE_INTERVAL_HOURS=6
AUTO_APPLY=true
```

Save and exit (`Ctrl+X`, `Y`, `Enter` in nano).

---

### 4. Build and Start Services

```bash
# Build and start all services in detached mode
docker compose up -d --build

# Verify all containers are running
docker compose ps
```

Expected output:
```
NAME                    STATUS
autom-backend-1         Up (healthy)
autom-frontend-1        Up (healthy)
autom-certbot-1         Up
```

Access the dashboard at: `http://YOUR_EC2_PUBLIC_IP`
Access the API directly at: `http://YOUR_EC2_PUBLIC_IP:8000`
API docs (Swagger): `http://YOUR_EC2_PUBLIC_IP:8000/docs`

---

### 5. Setting Up HTTPS with Certbot

You need a domain name pointing to your EC2 IP before proceeding.

```bash
# Point your domain A record to your EC2 public IP first, then:

# Run certbot to obtain a certificate
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d your-domain.com \
    -d www.your-domain.com \
    --email your@email.com \
    --agree-tos \
    --non-interactive
```

Then edit `nginx/nginx.conf` to uncomment the HTTPS server block and update `your-domain.com`.

```bash
# Reload nginx with updated config
docker compose restart frontend
```

The certbot service renews certificates automatically every 12 hours.

---

### 6. Auto-Restart Policy

The `restart: unless-stopped` policy in `docker-compose.yml` ensures containers restart automatically after:
- Server reboots
- Container crashes
- Docker daemon restarts

To verify restart policy:
```bash
docker inspect autom-backend-1 | grep RestartPolicy
```

To start services on system boot, ensure Docker itself starts on boot:
```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

### 7. Monitoring Logs

```bash
# View all service logs (live)
docker compose logs -f

# View only backend logs
docker compose logs -f backend

# View only frontend/nginx logs
docker compose logs -f frontend

# View last 100 lines of backend logs
docker compose logs --tail=100 backend

# Application-level logs (written to ./logs/app.log)
tail -f logs/app.log
```

---

### 8. Updating the Application

```bash
# Pull latest code changes
git pull origin main

# Rebuild and restart services
docker compose up -d --build

# If only backend code changed (no dependency changes):
docker compose restart backend

# If frontend changed, rebuild frontend only:
docker compose up -d --build frontend
```

---

### 9. Managing Data

```bash
# View all jobs in the database
docker compose exec backend python3 -c "
import asyncio, json
from database import get_jobs
async def main():
    jobs = await get_jobs()
    print(json.dumps(jobs[:5], indent=2, default=str))
asyncio.run(main())
"

# Backup the SQLite database
docker compose exec backend cp jobs.db /app/logs/jobs_backup_$(date +%Y%m%d).db

# Copy backup to host
docker compose cp backend:/app/logs/jobs_backup_$(date +%Y%m%d).db ./
```

---

### 10. Troubleshooting Common Issues

#### Container won't start

```bash
# Check container status and recent logs
docker compose ps
docker compose logs --tail=50 backend
```

#### Playwright / Chromium errors

```bash
# Verify Playwright is installed inside the container
docker compose exec backend playwright --version

# Run Playwright diagnostics
docker compose exec backend python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = b.new_page()
    page.goto('https://example.com')
    print('Title:', page.title())
    b.close()
"
```

#### Backend API not responding

```bash
# Check if backend is healthy
curl http://localhost:8000/health

# Restart backend
docker compose restart backend
```

#### Database issues

```bash
# Enter backend container shell
docker compose exec backend bash

# Check database file
ls -lh jobs.db

# Run SQLite directly
sqlite3 jobs.db ".tables"
sqlite3 jobs.db "SELECT COUNT(*) FROM jobs;"
```

#### "No jobs found" after scraping

1. Verify HelloWork credentials in `.env` are correct
2. Check if HelloWork's HTML structure has changed (selectors may need updating in `scraper.py`)
3. Check browser session: `docker compose exec backend ls -la browser_data/`
4. View screenshots for debugging: `ls screenshots/`

#### Port 80 already in use

```bash
# Find what's using port 80
sudo lsof -i :80
sudo systemctl stop apache2  # if apache is running
sudo systemctl stop nginx    # if host nginx is running
```

#### Memory issues (t2.micro)

Playwright with Chromium requires ~300-500MB RAM. Use at least t2.small.
```bash
# Check memory usage
free -h
docker stats --no-stream
```

---

## Manual Operations

### Trigger a scrape manually

```bash
curl -X POST http://localhost:8000/scrape
```

### View statistics

```bash
curl http://localhost:8000/stats | python3 -m json.tool
```

### Apply to a specific job

```bash
curl -X POST http://localhost:8000/apply/1
```

### Update a cover message

```bash
curl -X PUT http://localhost:8000/jobs/1/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Bonjour, je souhaite postuler..."}'
```
