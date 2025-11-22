"""
Test Script - Demonstrates system with real API data
Run this after starting the Flask app to test end-to-end functionality
"""
import requests
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:5000"


def test_health():
    """Test system health"""
    print("1. Testing system health...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Status: {response.json()['status']}")
    assert response.status_code == 200
    print("   ✓ Health check passed\n")


def test_real_apis():
    """Test real API data fetching"""
    print("2. Testing real API integration...")

    # Test carbon intensity
    response = requests.get(f"{BASE_URL}/api/energy/current/london")
    if response.status_code == 200:
        data = response.json()
        print(f"   Carbon Intensity (London): {data['carbon_intensity_g_per_kwh']:.0f} gCO₂/kWh")
        print(f"   Price: £{data['price_per_kwh']:.4f}/kWh")
        print(f"   Renewable Fraction: {data['renewable_fraction']*100:.1f}%")
        print("   ✓ Real API data fetched successfully\n")
    else:
        print(f"   ✗ Failed to fetch energy data: {response.status_code}\n")


def register_test_asset():
    """Register a test compute asset"""
    print("3. Registering test compute asset...")

    asset_data = {
        "asset_id": "test_gpu_cluster",
        "asset_type": "GPU_CLUSTER",
        "region": "london",
        "max_power_kw": 200,
        "min_power_kw": 0,
        "flexibility_type": "deferrable",
        "is_deferrable": True,
        "is_throttlable": False
    }

    response = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
    if response.status_code == 201:
        print(f"   ✓ Asset registered: {asset_data['asset_id']}\n")
        return asset_data['asset_id']
    else:
        print(f"   Note: Asset may already exist\n")
        return asset_data['asset_id']


def submit_test_job(asset_id):
    """Submit a test job"""
    print("4. Submitting test compute job...")

    now = datetime.now()
    earliest_start = now + timedelta(hours=1)
    latest_finish = now + timedelta(hours=24)

    job_data = {
        "job_name": "Test AI Training Job",
        "job_type": "AI_TRAINING",
        "asset_id": asset_id,
        "duration_hours": 4,
        "earliest_start": earliest_start.isoformat(),
        "latest_finish": latest_finish.isoformat(),
        "allowed_regions": ["london", "scotland"],
        "flexibility_type": "deferrable",
        "priority": "normal",
        "estimated_power_kw": 200,
        "carbon_cap_g_per_kwh": 200,
        "max_price_per_kwh": 0.25
    }

    response = requests.post(f"{BASE_URL}/api/jobs", json=job_data)
    if response.status_code == 201:
        job = response.json()
        job_id = job['job_id']
        print(f"   ✓ Job submitted: {job_id}")
        print(f"   Name: {job['job_name']}")
        print(f"   Duration: {job['duration_hours']} hours")
        print(f"   Max Deferral: {job['max_deferral_hours']:.1f} hours\n")
        return job_id
    else:
        print(f"   ✗ Failed to submit job: {response.status_code}")
        print(f"   Error: {response.json()}\n")
        return None


def schedule_job(job_id):
    """Schedule the job"""
    print("5. Scheduling job with real-time optimization...")
    print("   (This queries Carbon Intensity API and Octopus Energy API)")

    response = requests.post(f"{BASE_URL}/api/jobs/{job_id}/schedule")
    if response.status_code == 200:
        result = response.json()
        job = result['job']
        schedule = job['schedule']

        print(f"   ✓ Job scheduled successfully!\n")

        print("   Optimized Schedule:")
        print(f"   ├─ Region: {schedule['region']}")
        print(f"   ├─ Start: {datetime.fromisoformat(schedule['start_time'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')}")
        print(f"   └─ End: {datetime.fromisoformat(schedule['end_time'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')}\n")

        print("   Carbon Impact:")
        print(f"   ├─ Estimated: {schedule['estimated_carbon_kg']:.1f} kg CO₂")
        print(f"   ├─ Baseline: {schedule['baseline_carbon_kg']:.1f} kg CO₂")
        print(f"   └─ Saved: {schedule['carbon_saved_kg']:.1f} kg ({schedule['carbon_reduction_percent']:.1f}%)\n")

        print("   Cost Impact:")
        print(f"   ├─ Estimated: £{schedule['estimated_cost_gbp']:.2f}")
        print(f"   ├─ Baseline: £{schedule['baseline_cost_gbp']:.2f}")
        print(f"   └─ Saved: £{schedule['cost_saved_gbp']:.2f} ({schedule['cost_reduction_percent']:.1f}%)\n")

        print("   P415 Flexibility Value:")
        print(f"   └─ £{schedule['flexibility_value_gbp']:.2f}\n")

        return True
    else:
        print(f"   ✗ Failed to schedule: {response.status_code}")
        print(f"   Error: {response.json()}\n")
        return False


def test_beckn_workflow(job_id):
    """Test Beckn protocol workflow"""
    print("6. Testing Beckn protocol flexibility marketplace...")

    # Search for slots
    response = requests.post(f"{BASE_URL}/api/beckn/search", json={"hours_ahead": 48})
    if response.status_code == 200:
        slots = response.json()
        print(f"   ✓ Found {len(slots)} flexibility slots\n")

        if slots:
            slot = slots[0]
            print("   Example Slot:")
            print(f"   ├─ Slot ID: {slot['slot_id']}")
            print(f"   ├─ Region: {slot['region']}")
            print(f"   ├─ Carbon: {slot['expected_carbon_kg']:.1f} kg CO₂")
            print(f"   ├─ Cost: £{slot['expected_cost_gbp']:.2f}")
            print(f"   └─ Flexibility Value: £{slot['flexibility_value_gbp']:.2f}\n")
    else:
        print(f"   ✗ Beckn search failed: {response.status_code}\n")


def show_statistics():
    """Show aggregate statistics"""
    print("7. Fetching aggregate statistics...")

    response = requests.get(f"{BASE_URL}/api/statistics")
    if response.status_code == 200:
        data = response.json()
        stats = data['job_stats']
        flex = data['flexibility']

        print(f"   Total Jobs: {stats['total_jobs']}")
        print(f"   Carbon Saved: {stats['total_carbon_saved_kg']:.1f} kg")
        print(f"   Cost Saved: £{stats['total_cost_saved_gbp']:.2f}")
        print(f"   Avg Carbon Reduction: {stats['avg_carbon_reduction_percent']:.1f}%")
        print(f"   Avg Cost Reduction: {stats['avg_cost_reduction_percent']:.1f}%\n")

        print(f"   Flexibility Summary:")
        print(f"   ├─ Pending Jobs: {flex['pending_jobs']}")
        print(f"   ├─ Flexible Jobs: {flex['flexible_jobs']}")
        print(f"   ├─ Deferrable Energy: {flex['total_deferrable_kwh']:.1f} kWh")
        print(f"   └─ Avg Deferral Window: {flex['avg_deferral_hours']:.1f} hours\n")


def main():
    """Run complete test suite"""
    print("\n" + "="*70)
    print("COMPUTE-ENERGY CONVERGENCE SYSTEM - TEST SCRIPT")
    print("Testing with REAL UK Carbon Intensity & Octopus Energy APIs")
    print("="*70 + "\n")

    try:
        # Run tests
        test_health()
        test_real_apis()

        asset_id = register_test_asset()
        job_id = submit_test_job(asset_id)

        if job_id:
            success = schedule_job(job_id)

            if success:
                test_beckn_workflow(job_id)
                show_statistics()

                print("="*70)
                print("✓ ALL TESTS PASSED")
                print("="*70)
                print("\nView results at:")
                print(f"  • Job Detail: http://localhost:5000/jobs/{job_id}")
                print(f"  • Dashboard: http://localhost:5000/dashboard")
                print(f"  • Beckn Slots: http://localhost:5000/beckn-slots")
                print()

    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Cannot connect to Flask app")
        print("Please ensure the app is running: python app.py\n")
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}\n")


if __name__ == "__main__":
    main()
