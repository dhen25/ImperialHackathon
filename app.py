"""
Flask Application - Compute-Energy Convergence System
Production-grade web interface and API
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("app.log", rotation="500 MB", level="DEBUG")

from models import (
    JobSubmission, ComputeAsset, Region, FlexibilityType,
    Priority, JobStatus
)
from job_agent import job_agent
from energy_agent import energy_agent
from policy_agent import policy_agent
from scheduler import scheduler
from beckn_routes import beckn_adapter
from audit_logger import audit_logger

# Initialize Flask app
app = Flask(__name__)
CORS(app)

logger.info("Starting Compute-Energy Convergence System")


# WEB INTERFACE ROUTES

@app.route('/')
def index():
    """Homepage"""
    return render_template('index.html')


@app.route('/submit-job')
def submit_job_page():
    """Job submission form"""
    return render_template('submit_job.html')


@app.route('/jobs')
def jobs_page():
    """Jobs list view"""
    return render_template('jobs.html')


@app.route('/jobs/<job_id>')
def job_detail_page(job_id):
    """Job detail view"""
    return render_template('job_detail.html', job_id=job_id)


@app.route('/dashboard')
def dashboard_page():
    """Dashboard with metrics"""
    return render_template('dashboard.html')


@app.route('/beckn-slots')
def beckn_slots_page():
    """Beckn flexibility slots view"""
    return render_template('beckn_slots.html')


# API ROUTES - JOB MANAGEMENT

@app.route('/api/assets', methods=['POST'])
def create_asset():
    """Register a compute asset"""
    try:
        data = request.json
        asset = ComputeAsset(**data)
        job_agent.register_asset(asset)
        return jsonify(asset.model_dump()), 201
    except Exception as e:
        logger.error(f"Error creating asset: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/assets', methods=['GET'])
def list_assets():
    """List all assets"""
    assets = job_agent.list_assets()
    return jsonify([a.model_dump() for a in assets])


@app.route('/api/jobs', methods=['POST'])
def create_job():
    """Submit a new compute job"""
    try:
        data = request.json

        # Parse datetime fields
        data['earliest_start'] = datetime.fromisoformat(data['earliest_start'].replace('Z', '+00:00'))
        data['latest_finish'] = datetime.fromisoformat(data['latest_finish'].replace('Z', '+00:00'))

        # Parse enum fields
        data['allowed_regions'] = [Region(r) for r in data['allowed_regions']]
        data['flexibility_type'] = FlexibilityType(data.get('flexibility_type', 'deferrable'))
        data['priority'] = Priority(data.get('priority', 'normal'))

        submission = JobSubmission(**data)
        job = job_agent.submit_job(submission)

        return jsonify(job.model_dump(mode='json')), 201
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs"""
    status = request.args.get('status')
    if status:
        jobs = job_agent.list_jobs(status=JobStatus(status))
    else:
        jobs = job_agent.list_jobs()

    return jsonify([j.model_dump(mode='json') for j in jobs])


@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """Get job details"""
    job = job_agent.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job.model_dump(mode='json'))


@app.route('/api/jobs/<job_id>/schedule', methods=['POST'])
def schedule_job_route(job_id):
    """Manually trigger scheduling for a job"""
    try:
        success = scheduler.schedule_job(job_id)
        if success:
            job = job_agent.get_job(job_id)
            return jsonify({
                'success': True,
                'job': job.model_dump(mode='json')
            })
        else:
            return jsonify({'error': 'Scheduling failed'}), 500
    except Exception as e:
        logger.error(f"Error scheduling job {job_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule-all', methods=['POST'])
def schedule_all_jobs():
    """Schedule all pending jobs"""
    try:
        results = scheduler.schedule_all_pending()
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error scheduling all jobs: {e}")
        return jsonify({'error': str(e)}), 500


# API ROUTES - ENERGY DATA

@app.route('/api/energy/current/<region>', methods=['GET'])
def get_current_energy(region):
    """Get current energy signal for a region"""
    try:
        region_enum = Region(region)
        signal = energy_agent.get_current_grid_signal(region_enum)
        return jsonify(signal.model_dump(mode='json'))
    except Exception as e:
        logger.error(f"Error fetching energy data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/energy/forecast/<region>', methods=['GET'])
def get_energy_forecast(region):
    """Get energy forecast for a region"""
    try:
        region_enum = Region(region)
        hours_ahead = int(request.args.get('hours', 48))
        forecast = energy_agent.get_forecast_signals(region_enum, hours_ahead)
        return jsonify([s.model_dump(mode='json') for s in forecast])
    except Exception as e:
        logger.error(f"Error fetching forecast: {e}")
        return jsonify({'error': str(e)}), 500


# API ROUTES - BECKN PROTOCOL

@app.route('/api/beckn/search', methods=['POST'])
def beckn_search():
    """Beckn /search - Discover flexibility slots"""
    try:
        data = request.json or {}
        region = data.get('region')
        hours_ahead = data.get('hours_ahead', 48)

        slots = beckn_adapter.search_flexibility_slots(region, hours_ahead)
        return jsonify([s.model_dump(mode='json') for s in slots])
    except Exception as e:
        logger.error(f"Beckn search error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/beckn/confirm', methods=['POST'])
def beckn_confirm():
    """Beckn /confirm - Confirm a flexibility slot"""
    try:
        data = request.json
        slot_id = data.get('slot_id')
        job_id = data.get('job_id')

        result = beckn_adapter.confirm_slot(slot_id, job_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Beckn confirm error: {e}")
        return jsonify({'error': str(e)}), 500


# API ROUTES - STATISTICS & LOGS

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get aggregate statistics"""
    try:
        stats = job_agent.get_job_statistics()
        flexibility = job_agent.get_flexibility_summary()

        return jsonify({
            'job_stats': stats,
            'flexibility': flexibility
        })
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get audit logs"""
    try:
        limit = int(request.args.get('limit', 100))
        logs = audit_logger.get_recent_logs(limit)
        return jsonify([log.model_dump(mode='json') for log in logs])
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs/<job_id>', methods=['GET'])
def get_job_logs(job_id):
    """Get logs for specific job"""
    try:
        logs = audit_logger.get_logs_for_job(job_id)
        return jsonify([log.model_dump(mode='json') for log in logs])
    except Exception as e:
        logger.error(f"Error fetching job logs: {e}")
        return jsonify({'error': str(e)}), 500


# HEALTH CHECK

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


if __name__ == '__main__':
    logger.info("Flask app starting on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
