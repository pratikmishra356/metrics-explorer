# Metrics Explorer Service

A query-only metrics exploration service that provides a unified REST API interface for AI agent services to explore dashboards, monitors, and metrics from multiple providers (Datadog, Prometheus, Grafana).

## Features

- **Provider-agnostic API**: Same endpoints and response format regardless of the underlying metrics provider
- **Organization-based routing**: Provider(s) determined by organization ID, looked up in database
- **OpenTelemetry semantic conventions**: Universal data models follow OTel standards for consistency
- **Multi-provider support**: Datadog, Prometheus, and Grafana

## Architecture

```
AI Agent Service → REST API → Organization Lookup → Provider Adapters → Provider APIs
                                                  ↓
                                          Universal OTel Format Response
```

## Quick Start

### Prerequisites

- **Python 3.11+** (including 3.13)
- PostgreSQL 14+

### Installation

1. Clone the repository and install dependencies:

```bash
cd metrics-explorer
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run database migrations:

```bash
alembic upgrade head
```

4. Start the server (from project root, with venv activated):

```bash
source venv/bin/activate   # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper script:

```bash
./scripts/run_backend.sh
```

5. (Optional) Run the React frontend for a dynamic UI to set org/provider and call APIs:

```bash
cd frontend && npm install && npm run dev
```

Then open **http://localhost:3002**. The dev server proxies `/api` to the backend. You can create organizations, add providers (Datadog, Prometheus, Grafana), and explore dashboards, monitors, and metrics.

Alternatively, in development the backend serves a simple static API tester at **http://localhost:8001/ui/** (if the `frontend` folder exists).

## API Endpoints

All endpoints require `X-Organization-Id` header to identify the organization.

### Dashboards

- `GET /api/v1/dashboards` - List all dashboards
- `GET /api/v1/dashboards/{dashboard_id}` - Get dashboard details

### Monitors

- `GET /api/v1/monitors` - List all monitors
- `GET /api/v1/monitors/{monitor_id}` - Get monitor details

### Metrics

- `POST /api/v1/metrics/query` - Query metrics
- `GET /api/v1/metrics/metadata` - Get metrics metadata

## Configuration

Provider credentials are stored per-organization in the database. Each organization can have multiple providers configured.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | Required |
| ENCRYPTION_KEY | Key for encrypting provider credentials | Required |
| LOG_LEVEL | Logging level | INFO |
| DEFAULT_QUERY_TIMEOUT | Query timeout in seconds | 30 |

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app tests
isort app tests
```

## License

MIT
