"""
Energy Agent - Processes real-time grid data for compute scheduling
Integrates multiple APIs to provide comprehensive energy signals
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger
import statistics

from models import Region, GridSignal
from api_clients import carbon_api, octopus_api, grid_api


class EnergyAgent:
    """
    Energy Agent responsible for:
    1. Fetching real-time grid data from multiple APIs
    2. Generating forecasts for carbon intensity and prices
    3. Scoring time windows for compute scheduling
    4. Calculating grid stress indicators
    """

    def __init__(self):
        logger.info("Energy Agent initialized")
        self.data_sources = [
            "carbon_intensity_api",
            "octopus_agile_api",
            "national_grid_eso"
        ]

    def get_current_grid_signal(self, region: Region) -> GridSignal:
        """
        Get current real-time grid signal for a region
        Aggregates data from all available APIs
        """
        logger.info(f"Fetching current grid signal for {region.value}")

        try:
            # Fetch carbon intensity
            carbon_data = carbon_api.get_current_intensity(region.value)
            carbon_intensity = self._extract_carbon_intensity(carbon_data)
            generation_mix = carbon_api.get_generation_mix(region.value)
            renewable_fraction = self._calculate_renewable_fraction(generation_mix)

            # Fetch electricity price
            price_per_kwh = octopus_api.get_current_price(region.value)
            if price_per_kwh is None:
                price_per_kwh = 0.15  # Fallback average price
                logger.warning(f"Using fallback price for {region.value}")

            # Fetch grid stress indicators
            demand_mw = grid_api.get_current_demand()
            frequency_hz = grid_api.get_grid_frequency()
            stress_level = self._calculate_stress_level(
                carbon_intensity, demand_mw, frequency_hz
            )

            signal = GridSignal(
                region=region,
                timestamp=datetime.now(),
                carbon_intensity_g_per_kwh=carbon_intensity,
                price_per_kwh=price_per_kwh,
                price_per_mwh=price_per_kwh * 1000,
                generation_mix=generation_mix.get('mix', {}),
                renewable_fraction=renewable_fraction,
                demand_mw=demand_mw,
                frequency_hz=frequency_hz,
                stress_level=stress_level,
                data_source=",".join(self.data_sources)
            )

            logger.info(f"Grid signal: {carbon_intensity}gCO2/kWh, £{price_per_kwh:.4f}/kWh, {renewable_fraction:.1%} renewable")
            return signal

        except Exception as e:
            logger.error(f"Error fetching grid signal: {e}")
            raise

    def get_forecast_signals(self, region: Region, hours_ahead: int = 48) -> List[GridSignal]:
        """
        Get forecasted grid signals for next N hours
        Uses API forecasts for carbon and price
        """
        logger.info(f"Fetching {hours_ahead}h forecast for {region.value}")

        signals = []

        try:
            # Fetch carbon intensity forecast
            carbon_forecast = carbon_api.get_intensity_forecast(hours_ahead)

            # Fetch price forecast
            price_forecast = octopus_api.get_price_forecast(region.value, hours_ahead)

            # Create GridSignal objects for each period
            # Carbon forecast is in 30-min blocks, price is also 30-min
            for i, carbon_period in enumerate(carbon_forecast):
                timestamp = datetime.fromisoformat(carbon_period['from'].replace('Z', '+00:00'))

                # Find matching price period
                price_per_kwh = 0.15  # Default
                for price_period in price_forecast:
                    price_time = datetime.fromisoformat(price_period['timestamp'].replace('Z', '+00:00'))
                    if abs((timestamp - price_time).total_seconds()) < 1800:  # Within 30 min
                        price_per_kwh = price_period['price_per_kwh']
                        break

                carbon_intensity = carbon_period['intensity']['forecast']

                # Estimate renewable fraction (if not in API response)
                renewable_fraction = self._estimate_renewable_from_carbon(carbon_intensity)

                # Estimate stress level
                stress_level = self._estimate_stress_from_time(timestamp)

                signal = GridSignal(
                    region=region,
                    timestamp=timestamp,
                    carbon_intensity_g_per_kwh=carbon_intensity,
                    carbon_forecast=carbon_intensity,
                    price_per_kwh=price_per_kwh,
                    price_per_mwh=price_per_kwh * 1000,
                    generation_mix={},
                    renewable_fraction=renewable_fraction,
                    demand_mw=None,
                    frequency_hz=None,
                    stress_level=stress_level,
                    data_source="carbon_intensity_api,octopus_agile_api"
                )

                signals.append(signal)

            logger.info(f"Generated {len(signals)} forecast signals")
            return signals

        except Exception as e:
            logger.error(f"Error fetching forecast: {e}")
            raise

    def find_optimal_windows(
        self,
        region: Region,
        window_start: datetime,
        window_end: datetime,
        duration_hours: float,
        carbon_cap: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[Tuple[datetime, float]]:
        """
        Find optimal time windows within a flexibility range
        Returns list of (start_time, score) tuples, sorted by score (lower is better)

        Score combines:
        - Carbon intensity (primary)
        - Price (secondary)
        - Grid stress (tertiary)
        """
        logger.info(f"Finding optimal windows in {region.value} from {window_start} to {window_end}")

        # Get forecast signals
        hours_ahead = int((window_end - datetime.now()).total_seconds() / 3600) + 24
        forecast = self.get_forecast_signals(region, hours_ahead)

        # Filter signals within the window
        relevant_signals = [
            s for s in forecast
            if window_start <= s.timestamp <= window_end
        ]

        if not relevant_signals:
            logger.warning("No forecast data available for window")
            return []

        # Find all possible start times for the job duration
        candidate_starts = []
        duration_seconds = duration_hours * 3600

        for i, signal in enumerate(relevant_signals):
            potential_start = signal.timestamp
            potential_end = potential_start + timedelta(seconds=duration_seconds)

            # Check if job would fit within window
            if potential_end > window_end:
                continue

            # Get signals covering the job duration
            job_signals = [
                s for s in relevant_signals
                if potential_start <= s.timestamp < potential_end
            ]

            if not job_signals:
                continue

            # Calculate average metrics for this start time
            avg_carbon = statistics.mean(s.carbon_intensity_g_per_kwh for s in job_signals)
            avg_price = statistics.mean(s.price_per_kwh for s in job_signals)
            avg_stress = statistics.mean(s.stress_level for s in job_signals)
            avg_renewable = statistics.mean(s.renewable_fraction for s in job_signals)

            # Apply hard constraints
            if carbon_cap and avg_carbon > carbon_cap:
                continue
            if max_price and avg_price > max_price:
                continue

            # Calculate composite score (lower is better)
            # Weighted scoring: carbon (60%), price (30%), stress (10%)
            normalized_carbon = avg_carbon / 500  # Normalize to ~0-1 (500 is high carbon)
            normalized_price = avg_price / 0.30  # Normalize to ~0-1 (£0.30 is high price)
            normalized_stress = avg_stress

            score = (
                0.6 * normalized_carbon +
                0.3 * normalized_price +
                0.1 * normalized_stress
            )

            candidate_starts.append((
                potential_start,
                score,
                avg_carbon,
                avg_price,
                avg_renewable
            ))

        # Sort by score
        candidate_starts.sort(key=lambda x: x[1])

        logger.info(f"Found {len(candidate_starts)} candidate windows")

        if candidate_starts:
            best = candidate_starts[0]
            logger.info(f"Best window: {best[0]} (score: {best[1]:.3f}, "
                       f"carbon: {best[2]:.0f}g/kWh, price: £{best[3]:.4f}/kWh)")

        return candidate_starts

    def compare_regions(
        self,
        regions: List[Region],
        start_time: datetime,
        duration_hours: float
    ) -> Dict[Region, Dict]:
        """
        Compare multiple regions for a given time window
        Returns dict mapping region to its metrics
        """
        logger.info(f"Comparing {len(regions)} regions for {start_time}")

        end_time = start_time + timedelta(hours=duration_hours)
        comparison = {}

        for region in regions:
            try:
                # Get forecast for this region
                hours_ahead = int((end_time - datetime.now()).total_seconds() / 3600) + 1
                forecast = self.get_forecast_signals(region, hours_ahead)

                # Filter to job window
                job_signals = [
                    s for s in forecast
                    if start_time <= s.timestamp < end_time
                ]

                if not job_signals:
                    logger.warning(f"No data for {region.value}")
                    continue

                # Calculate averages
                avg_carbon = statistics.mean(s.carbon_intensity_g_per_kwh for s in job_signals)
                avg_price = statistics.mean(s.price_per_kwh for s in job_signals)
                avg_renewable = statistics.mean(s.renewable_fraction for s in job_signals)

                comparison[region] = {
                    'carbon_intensity': avg_carbon,
                    'price_per_kwh': avg_price,
                    'renewable_fraction': avg_renewable,
                    'score': 0.7 * (avg_carbon / 500) + 0.3 * (avg_price / 0.30)
                }

            except Exception as e:
                logger.error(f"Error comparing region {region.value}: {e}")

        # Sort by score
        sorted_regions = sorted(comparison.items(), key=lambda x: x[1]['score'])

        if sorted_regions:
            best_region, metrics = sorted_regions[0]
            logger.info(f"Best region: {best_region.value} "
                       f"(carbon: {metrics['carbon_intensity']:.0f}g/kWh, "
                       f"price: £{metrics['price_per_kwh']:.4f}/kWh)")

        return comparison

    # Helper methods

    def _extract_carbon_intensity(self, carbon_data: Dict) -> float:
        """Extract carbon intensity value from API response"""
        try:
            if 'data' in carbon_data and len(carbon_data['data']) > 0:
                intensity = carbon_data['data'][0]['intensity']
                # Try actual first, fall back to forecast
                return float(intensity.get('actual', intensity.get('forecast', 250)))
            return 250.0  # Fallback
        except (KeyError, IndexError, TypeError):
            logger.warning("Could not extract carbon intensity, using default")
            return 250.0

    def _calculate_renewable_fraction(self, generation_mix: Dict) -> float:
        """Calculate renewable fraction from generation mix"""
        try:
            mix = generation_mix.get('mix', [])
            renewable_types = {'wind', 'solar', 'hydro', 'biomass'}

            if isinstance(mix, list):
                total_renewable = sum(
                    item['perc'] for item in mix
                    if item['fuel'].lower() in renewable_types
                )
                return total_renewable / 100.0
            return 0.3  # Fallback average
        except (KeyError, TypeError):
            return 0.3

    def _calculate_stress_level(
        self,
        carbon_intensity: float,
        demand_mw: Optional[float],
        frequency_hz: Optional[float]
    ) -> float:
        """
        Calculate grid stress level (0-1)
        High stress = high carbon + high demand + frequency deviations
        """
        stress = 0.0

        # Carbon contribution (0-0.5)
        # High carbon (>400) indicates stressed grid
        if carbon_intensity > 400:
            stress += 0.5
        elif carbon_intensity > 300:
            stress += 0.3
        elif carbon_intensity > 200:
            stress += 0.1

        # Demand contribution (0-0.3)
        if demand_mw:
            if demand_mw > 40000:  # Peak demand
                stress += 0.3
            elif demand_mw > 35000:
                stress += 0.2
            elif demand_mw > 30000:
                stress += 0.1

        # Frequency contribution (0-0.2)
        if frequency_hz:
            freq_deviation = abs(frequency_hz - 50.0)
            if freq_deviation > 0.2:
                stress += 0.2
            elif freq_deviation > 0.1:
                stress += 0.1

        return min(stress, 1.0)

    def _estimate_renewable_from_carbon(self, carbon_intensity: float) -> float:
        """Estimate renewable fraction from carbon intensity"""
        # Low carbon typically means more renewables
        # UK grid: <100g/kWh is very green, >400g/kWh is very dirty
        if carbon_intensity < 100:
            return 0.7
        elif carbon_intensity < 200:
            return 0.5
        elif carbon_intensity < 300:
            return 0.3
        else:
            return 0.15

    def _estimate_stress_from_time(self, timestamp: datetime) -> float:
        """Estimate grid stress from time of day"""
        hour = timestamp.hour

        # Peak hours (17-20): high stress
        if 17 <= hour < 20:
            return 0.8
        # Work hours (8-17, 20-22): medium stress
        elif (8 <= hour < 17) or (20 <= hour < 22):
            return 0.5
        # Night hours (22-8): low stress
        else:
            return 0.2


# Singleton instance
energy_agent = EnergyAgent()
