"""Residual Generator for Cloud Digital Twin Diagnostics.

Calculates raw and defensive relative residuals between received vehicle telemetry
and nominal Digital Twin predictions across all supported sensor streams.
"""

from enum import Enum
import math
from typing import Any, Dict, Optional, Set
from digital_twin.models import (
    AnomalyStatus,
    ExpectedMeasurement,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.telemetry_freshness import TelemetryFreshnessEvaluator
from digital_twin.twin_config import DigitalTwinConfig


class ResidualValidityStatus(str, Enum):
    """Detailed data and mathematical validity status of a residual evaluation."""
    VALID = "valid"
    MISSING_OBSERVED = "missing_observed"
    MISSING_EXPECTED = "missing_expected"
    INVALID_VALUE = "invalid_value"
    CATEGORICAL_STATUS = "categorical_status"
    CATEGORICAL_MISMATCH = "categorical_mismatch"
    STALE_DATA = "stale_data"
    UNSUPPORTED_SENSOR = "unsupported_sensor"


class ResidualGenerator:
    """Computes raw and relative discrepancies between observed and expected telemetry."""

    SUPPORTED_SENSORS: Set[str] = {
        "speed_kmh",
        "rpm",
        "engine_load",
        "engine_temperature_c",
        "cooling_fan_status",
    }

    CATEGORICAL_SENSORS: Set[str] = {
        "cooling_fan_status",
    }

    def __init__(
        self,
        epsilon: float = 1e-4,
        freshness_evaluator: Optional[TelemetryFreshnessEvaluator] = None,
        config: Optional[DigitalTwinConfig] = None,
    ) -> None:
        """Initialize the residual generator.
        
        Args:
            epsilon: Small positive constant preventing division-by-zero in relative residuals.
            freshness_evaluator: Optional custom TelemetryFreshnessEvaluator instance.
            config: Optional master DigitalTwinConfig.
        """
        if epsilon <= 0:
            raise ValueError(f"epsilon must be strictly positive (>0), got {epsilon}")
        self.epsilon = epsilon
        self.freshness_evaluator = freshness_evaluator or TelemetryFreshnessEvaluator(config=config)

    def _is_valid_number(self, val: Any) -> bool:
        """Verify if a value is a finite, real numerical float/int."""
        if val is None or isinstance(val, bool):
            return False
        try:
            num = float(val)
            return not (math.isnan(num) or math.isinf(num))
        except (ValueError, TypeError):
            return False

    def calculate_raw_residual(self, observed: float, expected: float) -> float:
        """Compute raw residual r = observed - expected."""
        return round(float(observed) - float(expected), 4)

    def calculate_relative_residual(
        self,
        observed: float,
        expected: float,
        sensor_name: str,
    ) -> Optional[float]:
        """Compute safe relative residual r_rel = (observed - expected) / max(|expected|, epsilon).
        
        Note: Categorical signals (e.g. cooling_fan_status) return None for relative residuals.
        """
        if sensor_name in self.CATEGORICAL_SENSORS:
            return None

        diff = float(observed) - float(expected)
        denom = max(abs(float(expected)), self.epsilon)
        return round(diff / denom, 4)

    def compute_residual(
        self,
        vehicle_id: str,
        sensor_name: str,
        observed_value: Any,
        expected_value: Any,
        timestamp: float,
        data_age_s: Optional[float] = None,
        is_stale: bool = False,
        is_accepted: bool = True,
    ) -> SensorResidual:
        """Evaluate discrepancy between an observed telemetry point and nominal expectation.
        
        Returns a structured SensorResidual instance.
        """
        # 1. Missing Observed Value Handling
        if observed_value is None:
            exp_val = float(expected_value) if self._is_valid_number(expected_value) else None
            raw_res = SensorResidual(
                vehicle_id=vehicle_id,
                sensor_name=sensor_name,
                timestamp=timestamp,
                observed_value=None,
                expected_value=exp_val,
                residual=None,
                absolute_residual=None,
                relative_residual=None,
                data_age_s=data_age_s,
                is_stale=is_stale,
                is_accepted=is_accepted,
                anomaly_status=AnomalyStatus.INSUFFICIENT_DATA,
                details=ResidualValidityStatus.MISSING_OBSERVED.value,
            )
            return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

        # 2. Missing Expected Value Handling
        if expected_value is None or not self._is_valid_number(expected_value):
            obs_val = float(observed_value) if self._is_valid_number(observed_value) else None
            raw_res = SensorResidual(
                vehicle_id=vehicle_id,
                sensor_name=sensor_name,
                timestamp=timestamp,
                observed_value=obs_val,
                expected_value=None,
                residual=None,
                absolute_residual=None,
                relative_residual=None,
                data_age_s=data_age_s,
                is_stale=is_stale,
                is_accepted=is_accepted,
                anomaly_status=AnomalyStatus.INSUFFICIENT_DATA,
                details=ResidualValidityStatus.MISSING_EXPECTED.value,
            )
            return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

        # 3. Invalid / Non-Numeric Value Handling (e.g. NaN, Inf, non-numeric strings)
        if not self._is_valid_number(observed_value):
            raw_res = SensorResidual(
                vehicle_id=vehicle_id,
                sensor_name=sensor_name,
                timestamp=timestamp,
                observed_value=None,
                expected_value=float(expected_value),
                residual=None,
                absolute_residual=None,
                relative_residual=None,
                data_age_s=data_age_s,
                is_stale=is_stale,
                is_accepted=False,
                anomaly_status=AnomalyStatus.INVALID_DATA,
                details=ResidualValidityStatus.INVALID_VALUE.value,
            )
            return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

        obs_float = float(observed_value)
        exp_float = float(expected_value)

        # 4. Stale Telemetry Handling
        if is_stale:
            raw_r = self.calculate_raw_residual(obs_float, exp_float)
            rel_r = self.calculate_relative_residual(obs_float, exp_float, sensor_name)
            raw_res = SensorResidual(
                vehicle_id=vehicle_id,
                sensor_name=sensor_name,
                timestamp=timestamp,
                observed_value=obs_float,
                expected_value=exp_float,
                residual=raw_r,
                absolute_residual=round(abs(raw_r), 4),
                relative_residual=rel_r,
                data_age_s=data_age_s,
                is_stale=True,
                is_accepted=False,
                anomaly_status=AnomalyStatus.STALE_DATA,
                details=ResidualValidityStatus.STALE_DATA.value,
            )
            return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

        # 5. Categorical Signal Handling (e.g. Cooling Fan Status)
        if sensor_name in self.CATEGORICAL_SENSORS:
            raw_r = self.calculate_raw_residual(obs_float, exp_float)
            status_detail = (
                ResidualValidityStatus.CATEGORICAL_MISMATCH.value
                if abs(raw_r) > 1e-4
                else ResidualValidityStatus.CATEGORICAL_STATUS.value
            )
            raw_res = SensorResidual(
                vehicle_id=vehicle_id,
                sensor_name=sensor_name,
                timestamp=timestamp,
                observed_value=obs_float,
                expected_value=exp_float,
                residual=raw_r,
                absolute_residual=round(abs(raw_r), 4),
                relative_residual=None,  # Not applicable for categorical
                data_age_s=data_age_s,
                is_stale=False,
                is_accepted=is_accepted,
                anomaly_status=AnomalyStatus.NORMAL,
                details=status_detail,
            )
            return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

        # 6. Standard Continuous Numerical Residual Calculation
        raw_r = self.calculate_raw_residual(obs_float, exp_float)
        rel_r = self.calculate_relative_residual(obs_float, exp_float, sensor_name)

        raw_res = SensorResidual(
            vehicle_id=vehicle_id,
            sensor_name=sensor_name,
            timestamp=timestamp,
            observed_value=obs_float,
            expected_value=exp_float,
            residual=raw_r,
            absolute_residual=round(abs(raw_r), 4),
            relative_residual=rel_r,
            data_age_s=data_age_s,
            is_stale=False,
            is_accepted=is_accepted,
            anomaly_status=AnomalyStatus.NORMAL,
            details=ResidualValidityStatus.VALID.value,
        )
        return self.freshness_evaluator.evaluate_residual(raw_res, aoi_seconds=data_age_s)

    def compute_residuals_for_frame(
        self,
        vehicle_id: str,
        observed_telemetry: Dict[str, Any],
        expected_measurement: ExpectedMeasurement,
        timestamp: Optional[float] = None,
        data_ages: Optional[Dict[str, float]] = None,
    ) -> Dict[str, SensorResidual]:
        """Compute residuals for all supported vehicle sensor signals in a telemetry frame."""
        t_eval = timestamp if timestamp is not None else expected_measurement.timestamp
        data_ages = data_ages or {}
        residuals: Dict[str, SensorResidual] = {}

        # Expected mappings
        exp_map = {
            "speed_kmh": expected_measurement.expected_speed_kmh,
            "rpm": expected_measurement.expected_rpm,
            "engine_load": expected_measurement.expected_engine_load,
            "engine_temperature_c": expected_measurement.expected_engine_temperature_c,
            "cooling_fan_status": expected_measurement.expected_cooling_fan_status,
        }

        for sensor in self.SUPPORTED_SENSORS:
            obs_val = observed_telemetry.get(sensor)
            exp_val = exp_map.get(sensor)
            age = data_ages.get(sensor)

            res = self.compute_residual(
                vehicle_id=vehicle_id,
                sensor_name=sensor,
                observed_value=obs_val,
                expected_value=exp_val,
                timestamp=t_eval,
                data_age_s=age,
            )
            residuals[sensor] = res

        return residuals
