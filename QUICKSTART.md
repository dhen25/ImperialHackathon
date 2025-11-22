# Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

### 2. Start the Application (30 seconds)

```bash
python app.py
```

Server starts at: `http://localhost:5000`

### 3. Run Test Script (2 minutes)

Open a new terminal:

```bash
python test_system.py
```

This will:
- ✓ Register a test GPU cluster
- ✓ Submit an AI training job
- ✓ Fetch **real** UK carbon intensity & electricity prices
- ✓ Optimize the schedule
- ✓ Show carbon & cost savings

### 4. Open Web Interface

Visit: http://localhost:5000

- **Submit Job**: http://localhost:5000/submit-job
- **View Jobs**: http://localhost:5000/jobs
- **Dashboard**: http://localhost:5000/dashboard
- **Beckn Slots**: http://localhost:5000/beckn-slots

---

## What You'll See

After running the test script:

```
Carbon Impact:
├─ Estimated: 40.0 kg CO₂
├─ Baseline: 280.0 kg CO₂
└─ Saved: 240.0 kg (85.7%)

Cost Impact:
├─ Estimated: £80.00
├─ Baseline: £120.00
└─ Saved: £40.00 (33.3%)

P415 Flexibility Value:
└─ £120.00
```

The system automatically:
1. Queries **real** UK Carbon Intensity API
2. Queries **real** Octopus Energy Agile prices
3. Finds the greenest, cheapest execution window
4. Schedules the job there instead of running immediately

**Result**: Massive carbon savings + cost savings + flexibility revenue

---

## API Examples

### Submit a Job via API

```bash
curl -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "GPT-4 Fine-tuning",
    "job_type": "AI_TRAINING",
    "asset_id": "test_gpu_cluster",
    "duration_hours": 8,
    "earliest_start": "2025-11-23T00:00:00Z",
    "latest_finish": "2025-11-25T00:00:00Z",
    "allowed_regions": ["london", "scotland"],
    "flexibility_type": "deferrable",
    "priority": "normal",
    "estimated_power_kw": 200
  }'
```

### Schedule All Pending Jobs

```bash
curl -X POST http://localhost:5000/api/schedule-all
```

### Get Statistics

```bash
curl http://localhost:5000/api/statistics
```

---

## Next Steps

1. **Register your real compute infrastructure**
   ```bash
   curl -X POST http://localhost:5000/api/assets -H "Content-Type: application/json" -d '{...}'
   ```

2. **Integrate with your job submission pipeline**
   - Use the `/api/jobs` endpoint
   - Jobs are automatically optimized for carbon & cost

3. **Monitor the dashboard**
   - Track carbon savings
   - Track cost savings
   - View flexibility value (P415 revenue)

4. **Integrate with Beckn-compatible flexibility markets**
   - Use `/api/beckn/search` to expose flexibility
   - Use `/api/beckn/confirm` to confirm bookings

---

## Troubleshooting

**Problem**: `Error fetching grid signal`
**Solution**: Check internet connection. The APIs are:
- https://api.carbonintensity.org.uk/
- https://api.octopus.energy/

**Problem**: Jobs not scheduling
**Solution**: Ensure time window allows flexibility (>duration_hours)

**Problem**: Port 5000 already in use
**Solution**: Change port in `app.py`: `app.run(port=5001)`

---

## Production Deployment

For production use:

```bash
# Install Gunicorn
pip install gunicorn

# Run with production server
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
```

See `README.md` for full deployment checklist.
