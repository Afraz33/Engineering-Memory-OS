# Engineering Memory OS

Engineering Memory OS is a local-first engineering workspace built with React, FastAPI, CockroachDB, and Redis. The project is containerized using Docker and supports separate development and production configurations through Docker Compose.

## Tech Stack

* Frontend: React + Vite + TypeScript + Tailwind CSS
* Backend: FastAPI
* Database: CockroachDB
* Cache: Redis
* Containerization: Docker & Docker Compose
* Reverse Proxy (Production): Nginx

## Project Structure

```text
.
├── backend/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   ├── package.json
│   └── pnpm-lock.yaml
│
├── nginx/
│   └── nginx.conf
│
├── docker-compose-dev.yaml
├── docker-compose-prod.yaml
└── README.md
```

## Requirements

* Docker
* Docker Compose (v2)
* Docker Buildx

Verify installation:

```bash
docker --version
docker compose version
docker buildx version
```

## Development

Start the development environment:

```bash
docker compose -f docker-compose-dev.yaml up --build
```

Stop the environment:

```bash
docker compose -f docker-compose-dev.yaml down
```

Rebuild containers:

```bash
docker compose -f docker-compose-dev.yaml up --build
```

## Development Services

| Service           | URL                        |
| ----------------- | -------------------------- |
| Frontend          | http://localhost:5173      |
| FastAPI           | http://localhost:8000      |
| Swagger UI        | http://localhost:8000/docs |
| CockroachDB Admin | http://localhost:8080      |
| Cockroach SQL     | localhost:26257            |
| Redis             | localhost:6379             |

## Production

Build and start:

```bash
docker compose -f docker-compose-prod.yaml up --build -d
```

Stop:

```bash
docker compose -f docker-compose-prod.yaml down
```

## Useful Commands

View running containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs
```

Follow logs:

```bash
docker compose logs -f
```

Restart a service:

```bash
docker compose restart backend
```

Rebuild a single service:

```bash
docker compose build backend
```

Open a shell inside a container:

```bash
docker compose exec backend bash
```

or

```bash
docker compose exec frontend sh
```

Stop and remove containers:

```bash
docker compose down
```

Remove containers, networks, and volumes:

```bash
docker compose down -v
```

## Environment Variables

Backend services use environment variables provided through Docker Compose.

Typical variables include:

```text
DATABASE_URL=
REDIS_URL=
```

## Health Check

The frontend displays the health of:

* FastAPI server
* CockroachDB
* Redis

The backend should expose:

```
GET /health
```

Example response:

```json
{
  "server": true,
  "database": true,
  "redis": true
}
```
