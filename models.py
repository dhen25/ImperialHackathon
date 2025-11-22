"""
Data models for Compute-Energy Convergence System
Production-grade models with validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class Region(str, Enum):
    """UK Grid Supply Point regions aligned with Octopus Energy and National Grid"""
    SCOTLAND = "scotland"
    NORTH_SCOTLAND = "north_scotland"
    SOUTH_SCOTLAND = "south_scotland"
    NORTH_ENGLAND = "north_england"
    NORTH_EAST_ENGLAND = "north_east_england"
    NORTH_WEST_ENGLAND = "north_west_england"
    YORKSHIRE = "yorkshire"
    WALES = "wales"
    NORTH_WALES = "north_wales"
    SOUTH_WALES = "south_wales"
    WEST_MIDLANDS = "west_midlands"
    EAST_MIDLANDS = "east_midlands"
    EAST_ENGLAND = "east_england"
    LONDON = "london"
    SOUTH_ENGLAND = "south_england"
    SOUTH_EAST_ENGLAND = "south_east_england"
    SOUTH_WEST_ENGLAND = "south_west_england"


class FlexibilityType(str, Enum):
    """Types of workload flexibility"""
    FIXED = "fixed"  # Must run immediately, no flexibility
    DEFERRABLE = "deferrable"  # Can be delayed within window
    PAUSABLE = "pausable"  # Can be paused and resumed
    THROTTLABLE = "throttlable"  # Can adjust compute intensity


class Priority(str, Enum):
    """Job priority levels"""
    CRITICAL = "critical"  # Must run ASAP, minimal flexibility
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"  # Maximum flexibility for grid optimization


class JobStatus(str, Enum):
    """Job lifecycle states"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GridSignal(BaseModel):
    """Real-time grid data from multiple APIs"""
    region: Region
    timestamp: datetime

    # Carbon intensity (from Carbon Intensity API)
    carbon_intensity_g_per_kwh: float = Field(..., description="gCO2/kWh")
    carbon_forecast: Optional[float] = Field(None, description="Forecasted carbon intensity")

    # Electricity pricing (from Octopus Agile or Elexon)
    price_per_kwh: float = Field(..., description="£/kWh")
    price_per_mwh: float = Field(..., description="£/MWh")

    # Generation mix (from Carbon Intensity API)
    generation_mix: Dict[str, float] = Field(default_factory=dict, description="% by fuel type")
    renewable_fraction: float = Field(..., description="Renewable % (0-1)")

    # Grid stress indicators (calculated from National Grid ESO data)
    demand_mw: Optional[float] = Field(None, description="Current demand in MW")
    frequency_hz: Optional[float] = Field(None, description="Grid frequency")
    stress_level: float = Field(..., description="Grid stress 0-1, 1=high stress")

    # Data provenance
    data_source: str = Field(..., description="API source of data")

    class Config:
        json_schema_extra = {
            "example": {
                "region": "london",
                "timestamp": "2025-11-22T14:30:00Z",
                "carbon_intensity_g_per_kwh": 250,
                "price_per_kwh": 0.15,
                "price_per_mwh": 150,
                "generation_mix": {"gas": 40, "wind": 30, "nuclear": 20, "solar": 10},
                "renewable_fraction": 0.40,
                "stress_level": 0.6,
                "data_source": "carbon_intensity_api"
            }
        }


class ComputeAsset(BaseModel):
    """Represents a compute resource (GPU cluster, server rack, etc.)"""
    asset_id: str
    asset_type: str = Field(..., description="e.g., GPU_CLUSTER, SERVER_RACK, TPU_POD")
    region: Region
    max_power_kw: float = Field(..., description="Maximum power draw in kW")
    min_power_kw: float = Field(0, description="Minimum power draw in kW")
    flexibility_type: FlexibilityType
    is_deferrable: bool = True
    is_throttlable: bool = False

    # Cost model
    hourly_cost_gbp: Optional[float] = Field(None, description="£/hour operational cost")


class JobSubmission(BaseModel):
    """API input for submitting a compute job"""
    job_id: Optional[str] = Field(None, description="Auto-generated if not provided")
    job_name: str = Field(..., description="Human-readable job name")
    job_type: str = Field(..., description="e.g., AI_TRAINING, BATCH_PROCESSING, HPC_SIMULATION")

    asset_id: str
    duration_hours: float = Field(..., gt=0, description="Expected runtime in hours")

    # Flexibility window
    earliest_start: datetime
    latest_finish: datetime

    # Regional constraints
    allowed_regions: List[Region] = Field(..., min_length=1)

    # Flexibility parameters
    flexibility_type: FlexibilityType = FlexibilityType.DEFERRABLE
    priority: Priority = Priority.NORMAL

    # Energy constraints
    carbon_cap_g_per_kwh: Optional[float] = Field(None, description="Max acceptable carbon intensity")
    max_price_per_kwh: Optional[float] = Field(None, description="Max acceptable electricity price")

    # Power profile
    estimated_power_kw: float = Field(..., gt=0, description="Average power consumption")

    @validator('latest_finish')
    def validate_time_window(cls, v, values):
        if 'earliest_start' in values and v <= values['earliest_start']:
            raise ValueError('latest_finish must be after earliest_start')
        return v

    @validator('latest_finish')
    def validate_duration_fits(cls, v, values):
        if all(k in values for k in ['earliest_start', 'duration_hours']):
            from datetime import timedelta
            min_window = values['earliest_start'] + timedelta(hours=values['duration_hours'])
            if v < min_window:
                raise ValueError(f'Time window too small for job duration')
        return v


class ThrottlingSegment(BaseModel):
    """Represents a time segment with specific power level"""
    start_time: datetime
    end_time: datetime
    power_fraction: float = Field(..., ge=0, le=1, description="0-1, fraction of max power")
    carbon_intensity: float
    price_per_kwh: float


class Schedule(BaseModel):
    """Optimized schedule for a compute job"""
    schedule_id: str
    job_id: str

    # Chosen execution parameters
    region: Region
    start_time: datetime
    end_time: datetime

    # For throttlable jobs, power profile over time
    throttling_profile: Optional[List[ThrottlingSegment]] = None

    # Energy metrics
    estimated_energy_kwh: float
    estimated_carbon_kg: float
    estimated_cost_gbp: float

    # Baseline comparison (if job ran immediately at earliest_start)
    baseline_carbon_kg: float
    baseline_cost_gbp: float

    # Savings
    carbon_saved_kg: float
    cost_saved_gbp: float
    carbon_reduction_percent: float
    cost_reduction_percent: float

    # P415 flexibility value
    flexibility_value_gbp: Optional[float] = Field(None, description="Estimated flexibility revenue")

    # Provenance
    created_at: datetime
    data_sources: List[str] = Field(..., description="APIs used for this schedule")

    class Config:
        json_schema_extra = {
            "example": {
                "schedule_id": "sched_001",
                "job_id": "job_001",
                "region": "scotland",
                "start_time": "2025-11-23T02:00:00Z",
                "end_time": "2025-11-23T06:00:00Z",
                "estimated_energy_kwh": 800,
                "estimated_carbon_kg": 40,
                "estimated_cost_gbp": 80,
                "baseline_carbon_kg": 280,
                "baseline_cost_gbp": 120,
                "carbon_saved_kg": 240,
                "cost_saved_gbp": 40,
                "carbon_reduction_percent": 85.7,
                "cost_reduction_percent": 33.3
            }
        }


class Job(BaseModel):
    """Internal job representation with full context"""
    job_id: str
    job_name: str
    job_type: str
    asset_id: str

    duration_hours: float
    earliest_start: datetime
    latest_finish: datetime
    allowed_regions: List[Region]

    flexibility_type: FlexibilityType
    priority: Priority

    carbon_cap_g_per_kwh: Optional[float]
    max_price_per_kwh: Optional[float]
    estimated_power_kw: float

    # State
    status: JobStatus = JobStatus.PENDING
    schedule: Optional[Schedule] = None

    # Timestamps
    submitted_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Derived fields
    max_deferral_hours: Optional[float] = None

    def calculate_max_deferral(self):
        """Calculate maximum hours this job can be deferred"""
        from datetime import timedelta
        window = self.latest_finish - self.earliest_start
        self.max_deferral_hours = window.total_seconds() / 3600 - self.duration_hours


class BecknSlot(BaseModel):
    """Beckn protocol catalog item representing a flexible execution slot"""
    slot_id: str
    job_id: str

    # Time window
    start_time: datetime
    end_time: datetime
    duration_hours: float

    # Location
    region: Region

    # Energy characteristics
    expected_energy_kwh: float
    expected_carbon_kg: float
    expected_cost_gbp: float
    carbon_intensity_g_per_kwh: float

    # Flexibility value
    flexibility_value_gbp: float = Field(..., description="Value offered for this slot")
    renewable_fraction: float

    # Beckn metadata
    provider_id: str = "compute-energy-system"
    item_type: str = "flexible_compute_slot"


class DecisionLog(BaseModel):
    """Audit log entry for all scheduling decisions (P444 compliance)"""
    log_id: str
    timestamp: datetime

    job_id: str
    decision_type: str  # SCHEDULE, DEFER, REJECT, THROTTLE, etc.

    # Input data
    input_signals: Dict[str, Any] = Field(..., description="Grid signals used")
    input_constraints: Dict[str, Any] = Field(..., description="Job constraints")

    # Decision rationale
    considered_options: List[Dict[str, Any]] = Field(..., description="All options evaluated")
    selected_option: Dict[str, Any]
    selection_rationale: str

    # Trade-offs
    tradeoffs: Dict[str, float] = Field(default_factory=dict)  # carbon_saving, cost_saving, delay_hours

    # Outcome
    schedule: Optional[Schedule] = None

    # Compliance
    data_sources: List[str] = Field(..., description="APIs queried")
    operator_override: bool = False
    override_reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "log_001",
                "timestamp": "2025-11-22T14:35:00Z",
                "job_id": "job_001",
                "decision_type": "SCHEDULE",
                "selection_rationale": "Optimal carbon-cost balance in Scotland night window",
                "tradeoffs": {
                    "carbon_saving_kg": 240,
                    "cost_saving_gbp": 40,
                    "delay_hours": 8
                },
                "data_sources": ["carbon_intensity_api", "octopus_agile_api"]
            }
        }
