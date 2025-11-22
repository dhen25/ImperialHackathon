"""
Job Agent - Manages compute workloads and assets
Handles job submission, validation, storage, and state management
"""
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
import uuid

from models import (
    Job, JobSubmission, JobStatus, ComputeAsset,
    FlexibilityType, Priority, Region, Schedule
)


class JobAgent:
    """
    Job Agent responsible for:
    1. Registering compute assets (GPU clusters, servers, etc.)
    2. Accepting and validating job submissions
    3. Tracking job state through lifecycle
    4. Providing job metadata for scheduling decisions
    """

    def __init__(self):
        # In-memory storage (for production, use database)
        self.jobs: Dict[str, Job] = {}
        self.assets: Dict[str, ComputeAsset] = {}
        logger.info("Job Agent initialized")

    # Asset Management

    def register_asset(self, asset: ComputeAsset) -> ComputeAsset:
        """Register a compute asset"""
        self.assets[asset.asset_id] = asset
        logger.info(f"Registered asset: {asset.asset_id} ({asset.asset_type}) "
                   f"in {asset.region.value}, {asset.max_power_kw}kW")
        return asset

    def get_asset(self, asset_id: str) -> Optional[ComputeAsset]:
        """Get asset by ID"""
        return self.assets.get(asset_id)

    def list_assets(self, region: Optional[Region] = None) -> List[ComputeAsset]:
        """List all assets, optionally filtered by region"""
        assets = list(self.assets.values())
        if region:
            assets = [a for a in assets if a.region == region]
        return assets

    # Job Submission and Validation

    def submit_job(self, submission: JobSubmission) -> Job:
        """
        Submit a new compute job
        Validates constraints and creates internal job object
        """
        # Generate job ID if not provided
        job_id = submission.job_id or f"job_{uuid.uuid4().hex[:8]}"

        # Validate asset exists
        asset = self.get_asset(submission.asset_id)
        if not asset:
            raise ValueError(f"Asset {submission.asset_id} not found")

        # Validate time window
        self._validate_time_window(submission)

        # Validate regions
        if asset.region not in submission.allowed_regions:
            logger.warning(f"Asset in {asset.region.value} but allowed regions are {submission.allowed_regions}")

        # Create internal job object
        job = Job(
            job_id=job_id,
            job_name=submission.job_name,
            job_type=submission.job_type,
            asset_id=submission.asset_id,
            duration_hours=submission.duration_hours,
            earliest_start=submission.earliest_start,
            latest_finish=submission.latest_finish,
            allowed_regions=submission.allowed_regions,
            flexibility_type=submission.flexibility_type,
            priority=submission.priority,
            carbon_cap_g_per_kwh=submission.carbon_cap_g_per_kwh,
            max_price_per_kwh=submission.max_price_per_kwh,
            estimated_power_kw=submission.estimated_power_kw,
            status=JobStatus.PENDING,
            submitted_at=datetime.now()
        )

        # Calculate derived fields
        job.calculate_max_deferral()

        # Store job
        self.jobs[job_id] = job

        logger.info(f"Submitted job {job_id}: {job.job_name} "
                   f"({job.duration_hours}h, flexibility: {job.max_deferral_hours:.1f}h, "
                   f"priority: {job.priority.value})")

        return job

    def _validate_time_window(self, submission: JobSubmission):
        """Validate that time window is valid"""
        if submission.latest_finish <= submission.earliest_start:
            raise ValueError("latest_finish must be after earliest_start")

        window_hours = (submission.latest_finish - submission.earliest_start).total_seconds() / 3600

        if window_hours < submission.duration_hours:
            raise ValueError(
                f"Time window ({window_hours:.1f}h) is smaller than job duration ({submission.duration_hours}h)"
            )

        # Warn if deadline is very tight
        if window_hours < submission.duration_hours * 1.5:
            logger.warning(f"Job {submission.job_name} has very tight deadline "
                          f"(window: {window_hours:.1f}h, duration: {submission.duration_hours}h)")

    # Job Retrieval

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        priority: Optional[Priority] = None,
        region: Optional[Region] = None
    ) -> List[Job]:
        """List jobs with optional filters"""
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]
        if priority:
            jobs = [j for j in jobs if j.priority == priority]
        if region:
            jobs = [j for j in jobs if region in j.allowed_regions]

        return jobs

    def get_pending_jobs(self) -> List[Job]:
        """Get all jobs awaiting scheduling"""
        return self.list_jobs(status=JobStatus.PENDING)

    def get_running_jobs(self) -> List[Job]:
        """Get all currently running jobs"""
        return self.list_jobs(status=JobStatus.RUNNING)

    # Job State Management

    def update_job_status(self, job_id: str, new_status: JobStatus) -> Job:
        """Update job status and set timestamps"""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        old_status = job.status
        job.status = new_status

        # Update timestamps
        now = datetime.now()
        if new_status == JobStatus.SCHEDULED:
            job.scheduled_at = now
        elif new_status == JobStatus.RUNNING:
            job.started_at = now
        elif new_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.completed_at = now

        logger.info(f"Job {job_id} status: {old_status.value} → {new_status.value}")
        return job

    def attach_schedule(self, job_id: str, schedule: Schedule) -> Job:
        """Attach a schedule to a job"""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.schedule = schedule
        job.status = JobStatus.SCHEDULED
        job.scheduled_at = datetime.now()

        logger.info(f"Attached schedule to job {job_id}: "
                   f"{schedule.region.value}, {schedule.start_time}")

        return job

    # Job Analytics

    def get_job_statistics(self) -> Dict:
        """Get aggregate statistics across all jobs"""
        all_jobs = list(self.jobs.values())

        if not all_jobs:
            return {
                'total_jobs': 0,
                'by_status': {},
                'by_priority': {},
                'total_carbon_saved_kg': 0,
                'total_cost_saved_gbp': 0
            }

        # Count by status
        status_counts = {}
        for status in JobStatus:
            status_counts[status.value] = len([j for j in all_jobs if j.status == status])

        # Count by priority
        priority_counts = {}
        for priority in Priority:
            priority_counts[priority.value] = len([j for j in all_jobs if j.priority == priority])

        # Calculate total savings
        total_carbon_saved = sum(
            j.schedule.carbon_saved_kg for j in all_jobs
            if j.schedule
        )
        total_cost_saved = sum(
            j.schedule.cost_saved_gbp for j in all_jobs
            if j.schedule
        )

        stats = {
            'total_jobs': len(all_jobs),
            'by_status': status_counts,
            'by_priority': priority_counts,
            'total_carbon_saved_kg': round(total_carbon_saved, 2),
            'total_cost_saved_gbp': round(total_cost_saved, 2),
            'avg_carbon_reduction_percent': round(
                sum(j.schedule.carbon_reduction_percent for j in all_jobs if j.schedule) / max(len([j for j in all_jobs if j.schedule]), 1),
                1
            ),
            'avg_cost_reduction_percent': round(
                sum(j.schedule.cost_reduction_percent for j in all_jobs if j.schedule) / max(len([j for j in all_jobs if j.schedule]), 1),
                1
            )
        }

        logger.info(f"Job statistics: {stats['total_jobs']} jobs, "
                   f"{stats['total_carbon_saved_kg']}kg carbon saved, "
                   f"£{stats['total_cost_saved_gbp']} cost saved")

        return stats

    def get_flexibility_summary(self) -> Dict:
        """Summarize available flexibility from pending jobs"""
        pending = self.get_pending_jobs()

        if not pending:
            return {
                'pending_jobs': 0,
                'total_deferrable_kwh': 0,
                'total_flex_hours': 0,
                'avg_deferral_hours': 0
            }

        total_energy = sum(
            j.estimated_power_kw * j.duration_hours
            for j in pending
            if j.flexibility_type != FlexibilityType.FIXED
        )

        total_flex_hours = sum(
            j.max_deferral_hours or 0
            for j in pending
            if j.flexibility_type != FlexibilityType.FIXED
        )

        flex_jobs = [j for j in pending if j.flexibility_type != FlexibilityType.FIXED]
        avg_deferral = total_flex_hours / len(flex_jobs) if flex_jobs else 0

        return {
            'pending_jobs': len(pending),
            'flexible_jobs': len(flex_jobs),
            'total_deferrable_kwh': round(total_energy, 1),
            'total_flex_hours': round(total_flex_hours, 1),
            'avg_deferral_hours': round(avg_deferral, 1)
        }

    # Utility Methods

    def can_defer(self, job_id: str) -> bool:
        """Check if a job can be deferred"""
        job = self.get_job(job_id)
        if not job:
            return False

        return (
            job.flexibility_type != FlexibilityType.FIXED and
            job.status == JobStatus.PENDING and
            job.max_deferral_hours and
            job.max_deferral_hours > 0
        )

    def is_deadline_approaching(self, job_id: str, threshold_hours: float = 2.0) -> bool:
        """Check if job deadline is approaching"""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False

        now = datetime.now()
        hours_until_deadline = (job.latest_finish - now).total_seconds() / 3600

        return hours_until_deadline <= threshold_hours

    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            logger.info(f"Deleting job {job_id} ({job.job_name})")
            del self.jobs[job_id]
            return True
        return False


# Singleton instance
job_agent = JobAgent()
