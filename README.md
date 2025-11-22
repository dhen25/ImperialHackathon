# Compute-Energy Convergence System

**Production-grade AI workload scheduling optimized for carbon intensity and electricity costs using real-time UK grid data**

## Overview

This system solves **Problem Statement 2: Compute–Energy Convergence in a DEG World** by treating AI training and HPC workloads as flexible energy demands that can be intelligently scheduled based on:

- **Real-time carbon intensity** (UK Carbon Intensity API)
- **Real-time electricity prices** (Octopus Energy Agile API)
- **Grid availability and stress levels**
- **Beckn Protocol workflows** for flexibility marketplace integration
- **P415-compatible** flexibility market participation

### Key Features

✅ **Production Data Sources** - No simulated data, all from real APIs
✅ **Multi-Agent Architecture** - Job Agent, Energy Agent, Policy Agent, Beckn Adapter
✅ **Carbon-Aware Scheduling** - Automatically shifts workloads to low-carbon windows
✅ **Cost Optimization** - Minimizes electricity costs while meeting deadlines
✅ **Beckn Protocol Integration** - Exposes flexibility as marketplace catalog items
✅ **P444 Audit Compliance** - Full decision logging for regulatory review
✅ **Web Interface** - Flask-based dashboard for job management and visualization

---

## Problem Statement 2 Requirements Mapping

| Requirement | Implementation |
|-------------|----------------|
| Minimize £/inference under carbon cap | `policy_agent.py` - optimization with carbon constraints |
| Model compute as flexible loads | `models.py` - Job, ComputeAsset with flexibility parameters |
| Forecast compute workload spikes | `energy_agent.py` - 48h forecast from real APIs |
| Orchestration commands (defer, shift region) | `scheduler.py` - job lifecycle management |
| Decision logging for audit | `audit_logger.py` - P444-compliant JSON logs |
| Beckn catalog/order lifecycle | `beckn_routes.py` - search/confirm workflows |
| Multi-agent negotiation | Job Agent ↔ Energy Agent ↔ Policy Agent coordination |
| Carbon-aware scheduling | Priority ranking by carbon intensity + renewable fraction |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Web Application                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Job Form │  │ Dashboard│  │ Job List │  │  Beckn   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API
┌───────────────────────────┴─────────────────────────────────┐
│                      Core Agent System                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Job Agent   │  │ Energy Agent │  │ Policy Agent │     │
│  │ (Workloads)  │  │ (Grid Data)  │  │ (Optimizer)  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│  ┌──────┴──────────────────┴──────────────────┴────────┐   │
│  │              Scheduler & Orchestrator               │   │
│  └─────────────────────────┬───────────────────────────┘   │
│  ┌─────────────────────────┴───────────────────────────┐   │
│  │          Beckn Adapter + Audit Logger               │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ API Clients
┌───────────────────────────┴─────────────────────────────────┐
│                   Real-Time Data APIs                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ UK Carbon    │  │ Octopus Agile│  │ National Grid│     │
│  │ Intensity API│  │ Tariff API   │  │ ESO Data     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- **Python 3.11+**
- **pip** or **pipenv**
- **Internet connection** (for API access)

### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd compute-energy-system
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Application

```bash
python app.py
```

The system will start on `http://localhost:5000`

---

## Usage

### 1. Register a Compute Asset

First, register your GPU cluster or compute infrastructure:

```bash
curl -X POST http://localhost:5000/api/assets \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "gpu_cluster_01",
    "asset_type": "GPU_CLUSTER",
    "region": "london",
    "max_power_kw": 200,
    "flexibility_type": "deferrable",
    "is_deferrable": true
  }'
```

### 2. Submit a Compute Job

```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "GPT Training Run",
    "job_type": "AI_TRAINING",
    "asset_id": "gpu_cluster_01",
    "duration_hours": 4,
    "earliest_start": "2025-11-23T00:00:00Z",
    "latest_finish": "2025-11-24T00:00:00Z",
    "allowed_regions": ["london", "scotland"],
    "flexibility_type": "deferrable",
    "priority": "normal",
    "estimated_power_kw": 200,
    "carbon_cap_g_per_kwh": 150,
    "max_price_per_kwh": 0.20
  }'
```

### 3. Trigger Scheduling

```bash
curl -X POST http://localhost:5000/api/schedule-all
```

The system will:
1. Fetch real-time carbon intensity and prices from APIs
2. Evaluate all possible execution windows
3. Select optimal region and time (lowest carbon + cost)
4. Create schedule with baseline comparison
5. Log decision for audit

### 4. View Results

```bash
curl http://localhost:5000/api/jobs/<job_id>
```

Response includes:
- **Optimized schedule** (region, start time, end time)
- **Carbon savings** (kg CO₂ and %)
- **Cost savings** (£ and %)
- **Flexibility value** (P415 revenue estimate)

---

## API Endpoints

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/assets` | Register compute asset |
| GET | `/api/assets` | List all assets |
| POST | `/api/jobs` | Submit new job |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/<id>` | Get job details |
| POST | `/api/jobs/<id>/schedule` | Schedule specific job |
| POST | `/api/schedule-all` | Schedule all pending jobs |

### Energy Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/energy/current/<region>` | Current grid signal |
| GET | `/api/energy/forecast/<region>?hours=48` | Forecast signals |

### Beckn Protocol

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/beckn/search` | Discover flexibility slots |
| POST | `/api/beckn/confirm` | Confirm slot booking |

### Statistics & Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/statistics` | Aggregate metrics |
| GET | `/api/logs` | Audit logs |
| GET | `/api/logs/<job_id>` | Job-specific logs |

---

## Real Data Sources

### 1. UK Carbon Intensity API

**Provider**: National Grid ESO
**URL**: `https://api.carbonintensity.org.uk/`
**Auth**: None (public)
**Data**: Real-time and forecast carbon intensity (gCO₂/kWh) for 17 UK regions

**Implementation**: `api_clients.py` - `CarbonIntensityAPI` class

### 2. Octopus Energy Agile API

**Provider**: Octopus Energy
**URL**: `https://api.octopus.energy/v1/products/`
**Auth**: None for public tariff data
**Data**: Half-hourly electricity prices (£/kWh) for all UK regions

**Implementation**: `api_clients.py` - `OctopusEnergyAPI` class

### 3. National Grid ESO Data

**Provider**: National Grid ESO
**URL**: `https://data.nationalgrideso.com/`
**Auth**: None (open data)
**Data**: Grid demand, frequency, generation mix

**Implementation**: `api_clients.py` - `NationalGridESOAPI` class (placeholder for full integration)

---

## Configuration

### Environment Variables (Optional)

Create `.env` file:

```env
# Optional API keys (most APIs don't require auth)
ELEXON_API_KEY=your_key_here
SHEFFIELD_SOLAR_API_KEY=your_key_here

# Caching
CACHE_TTL_SECONDS=1800

# Regions
ENABLED_REGIONS=scotland,london,south_england
DEFAULT_REGION=london
```

### Optimization Weights

Edit `policy_agent.py`:

```python
self.weights = {
    'carbon': 0.6,  # Primary: minimize carbon
    'cost': 0.3,    # Secondary: minimize cost
    'deadline': 0.1  # Tertiary: avoid deadline risk
}
```

---

## Testing

### Test with Real APIs

```bash
# Get current carbon intensity for London
curl http://localhost:5000/api/energy/current/london

# Get 48h forecast
curl http://localhost:5000/api/energy/forecast/london?hours=48
```

### Example Test Scenario

```bash
# 1. Register asset
curl -X POST http://localhost:5000/api/assets -H "Content-Type: application/json" -d '{"asset_id":"test_gpu","asset_type":"GPU_CLUSTER","region":"london","max_power_kw":100,"flexibility_type":"deferrable","is_deferrable":true}'

# 2. Submit job
curl -X POST http://localhost:5000/api/jobs -H "Content-Type: application/json" -d '{"job_name":"Test Job","job_type":"AI_TRAINING","asset_id":"test_gpu","duration_hours":2,"earliest_start":"2025-11-23T00:00:00Z","latest_finish":"2025-11-24T00:00:00Z","allowed_regions":["london"],"flexibility_type":"deferrable","priority":"normal","estimated_power_kw":100}'

# 3. Schedule
curl -X POST http://localhost:5000/api/schedule-all

# 4. Check results
curl http://localhost:5000/api/statistics
```

---

## Deployment

### Production Checklist

- [ ] Use production WSGI server (Gunicorn, uWSGI)
- [ ] Set `debug=False` in `app.py`
- [ ] Configure reverse proxy (Nginx)
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure log rotation
- [ ] Set up database (PostgreSQL) instead of in-memory storage
- [ ] Implement Redis for caching
- [ ] Set up backup procedures

### Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

---

## Compliance & Audit

### P444 Compliance

All scheduling decisions are logged to `decisions.jsonl` with:
- Timestamp
- Input data sources (API endpoints, timestamps)
- Considered options (all candidate windows)
- Selected option and rationale
- Trade-offs (carbon, cost, delay)
- Outcome (actual schedule)

### P415 Flexibility Market Integration

The Beckn adapter exposes flexibility slots that can be integrated with P415-compatible settlement systems. Each slot includes:
- Flexibility value (£/kg CO₂ saved)
- Available capacity (kWh)
- Time window
- Regional constraints

---

## Troubleshooting

### API Connection Issues

**Problem**: `Error fetching grid signal`
**Solution**: Check internet connection and API availability at `https://api.carbonintensity.org.uk/`

### No Jobs Scheduled

**Problem**: Jobs remain in "pending" status
**Solution**: Check that:
1. Asset is registered
2. Time window allows flexibility
3. Carbon/price constraints are not too restrictive

### Empty Forecast Data

**Problem**: "No forecast data available for window"
**Solution**: Ensure `earliest_start` is in the future and within 48 hours

---

## Contributing

This is a production system. For contributions:

1. Fork the repository
2. Create feature branch
3. Test with real APIs
4. Submit pull request with documentation

---

## License

[Specify your license]

---

## Contact

For production deployment support: [Your contact info]

---

## Acknowledgments

- **UK Carbon Intensity API** - National Grid ESO
- **Octopus Energy** - Agile Tariff API
- **National Grid ESO** - Open data portal
- **Beckn Protocol** - Open grid coordination standard
