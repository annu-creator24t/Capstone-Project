"""Baseline Residual Anomaly Detector for Cloud Digital Twin Diagnostics.

Evaluates eligible sensor residuals against configurable two-level signal thresholds
(warning and anomaly), supports relative residual validation, categorical actuator mismatch
detection, and deterministic persistence counters to eliminate transient alert noise.
"""

from collections import defaultdict
from typing import Any, Dict, Optional, Tuple
from digital_twin.models import (
    AnomalyLevel,
    AnomalyStatus,
    AnomalyEvaluationResult,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.twin_config import (
    AnomalyThresholds,
    DigitalTwinConfig,
    SignalThreshold,
)


class BaselineAnomalyDetector:
    """Deterministic two-level baseline anomaly detector with persistence tracking."""

    CATEGORICAL_SENSORS = {"cooling_fan_status"}

    def __init__(
        self,
        config: Optional[AnomalyThresholds] = None,
        master_config: Optional[DigitalTwinConfig] = None,
    ) -> None:
        """Initialize the baseline anomaly detector.
        
        Args:
            config: Dedicated AnomalyThresholds configuration.
            master_config: Optional master DigitalTwinConfig.
        """
        if master_config is not None:
            self.config = master_config.anomaly_thresholds
        elif config is not None:
            self.config = config
        else:
            self.config = AnomalyThresholds()

        self.config.validate()

        # State tracking for alert persistence: (vehicle_id, sensor_name) -> counters
        self._persistence_state: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
            lambda: {"anomaly_count": 0, "warning_count": 0}
        )

    def is_eligible_for_detection(
        self,
        residual: SensorResidual,
        allow_aging: bool = False,
    ) -> bool:
        """Verify whether a residual meets Stage 4B validity and freshness eligibility."""
        if not residual.is_accepted or residual.is_stale:
            return False

        if residual.anomaly_status in (
            AnomalyStatus.INVALID_DATA,
            AnomalyStatus.INSUFFICIENT_DATA,
            AnomalyStatus.STALE_DATA,
        ):
            return False

        if residual.residual is None:
            return False

        if residual.freshness_status == FreshnessStatus.FRESH:
            return True

        if allow_aging and residual.freshness_status == FreshnessStatus.AGING:
            return True

        return False

    def detect(
        self,
        residual: SensorResidual,
        allow_aging: Optional[bool] = None,
    ) -> AnomalyEvaluationResult:
        """Evaluate a single SensorResidual against two-level baseline thresholds.
        
        Args:
            residual: The SensorResidual produced by ResidualGenerator.
            allow_aging: Optional override for aging telemetry eligibility.
            
        Returns:
            Structured AnomalyEvaluationResult instance.
        """
        effective_allow_aging = (
            allow_aging if allow_aging is not None else self.config.allow_aging
        )
        stream_key = (residual.vehicle_id, residual.sensor_name)
        state = self._persistence_state[stream_key]

        # 1. Eligibility Check (Stale, Invalid, Missing, Rejected)
        if not self.is_eligible_for_detection(residual, allow_aging=effective_allow_aging):
            # Do NOT increment persistence counters for ineligible data
            reason = (
                residual.freshness_reason
                or residual.details
                or f"Data not eligible (status={residual.anomaly_status.value}, freshness={residual.freshness_status.value})"
            )
            return AnomalyEvaluationResult(
                vehicle_id=residual.vehicle_id,
                sensor_name=residual.sensor_name,
                timestamp=residual.timestamp,
                observed_value=residual.observed_value,
                expected_value=residual.expected_value,
                residual=residual.residual,
                absolute_residual=residual.absolute_residual,
                relative_residual=residual.relative_residual,
                anomaly_level=AnomalyLevel.NOT_EVALUATED,
                diagnostic_eligible=False,
                freshness_status=residual.freshness_status,
                data_age_s=residual.data_age_s,
                threshold_used=None,
                relative_threshold_used=None,
                persistence_count=state["anomaly_count"],
                is_confirmed=False,
                reason=f"Not evaluated: {reason}",
                details=residual.details,
            )

        # 2. Categorical Actuator Evaluation (cooling_fan_status)
        if residual.sensor_name in self.CATEGORICAL_SENSORS:
            th = self.config.get_signal_threshold(residual.sensor_name)
            abs_r = residual.absolute_residual if residual.absolute_residual is not None else abs(residual.residual)
            is_mismatch = abs_r > 1e-4

            if is_mismatch:
                state["anomaly_count"] += 1
                state["warning_count"] = 0
                is_confirmed = state["anomaly_count"] >= self.config.anomaly_persistence_count
                level = AnomalyLevel.ANOMALY if is_confirmed else AnomalyLevel.WARNING
                reason = (
                    f"Categorical actuator mismatch (observed={residual.observed_value}, expected={residual.expected_value}) "
                    f"[consecutive={state['anomaly_count']}/{self.config.anomaly_persistence_count}]"
                )
                th_used = th.anomaly_threshold if th else 0.5
            else:
                state["anomaly_count"] = 0
                state["warning_count"] = 0
                is_confirmed = True
                level = AnomalyLevel.NORMAL
                reason = "Categorical actuator status matched nominal expectation"
                th_used = th.warning_threshold if th else 0.0

            return AnomalyEvaluationResult(
                vehicle_id=residual.vehicle_id,
                sensor_name=residual.sensor_name,
                timestamp=residual.timestamp,
                observed_value=residual.observed_value,
                expected_value=residual.expected_value,
                residual=residual.residual,
                absolute_residual=residual.absolute_residual,
                relative_residual=None,  # Not applicable for categorical
                anomaly_level=level,
                diagnostic_eligible=True,
                freshness_status=residual.freshness_status,
                data_age_s=residual.data_age_s,
                threshold_used=th_used,
                relative_threshold_used=None,
                persistence_count=state["anomaly_count"],
                is_confirmed=is_confirmed,
                reason=reason,
                details=residual.details,
            )

        # 3. Continuous Numerical Sensor Evaluation
        th = self.config.get_signal_threshold(residual.sensor_name)
        abs_r = residual.absolute_residual if residual.absolute_residual is not None else abs(residual.residual)
        rel_r = abs(residual.relative_residual) if residual.relative_residual is not None else None

        # Determine threshold breaches
        is_anom_abs = (abs_r > th.anomaly_threshold) if th else False
        is_anom_rel = (
            th.relative_anomaly_threshold is not None
            and rel_r is not None
            and rel_r > th.relative_anomaly_threshold
        ) if th else False
        candidate_anomaly = is_anom_abs or is_anom_rel

        is_warn_abs = (abs_r > th.warning_threshold) if th else False
        is_warn_rel = (
            th.relative_warning_threshold is not None
            and rel_r is not None
            and rel_r > th.relative_warning_threshold
        ) if th else False
        candidate_warning = is_warn_abs or is_warn_rel

        unit_str = f" {th.unit}" if (th and th.unit) else ""

        # Process candidate state & update persistence
        if candidate_anomaly:
            state["anomaly_count"] += 1
            state["warning_count"] = 0
            is_confirmed = state["anomaly_count"] >= self.config.anomaly_persistence_count
            level = AnomalyLevel.ANOMALY if is_confirmed else AnomalyLevel.WARNING
            th_used = th.anomaly_threshold if th else None
            rel_th_used = th.relative_anomaly_threshold if th else None

            breach_parts = []
            if is_anom_abs and th:
                breach_parts.append(f"|r|={abs_r:.4f}{unit_str} > {th.anomaly_threshold}{unit_str}")
            if is_anom_rel and th and rel_r is not None:
                breach_parts.append(f"|r_rel|={rel_r*100:.2f}% > {th.relative_anomaly_threshold*100:.2f}%")

            reason = (
                f"Anomaly threshold exceeded ({', '.join(breach_parts)}) "
                f"[consecutive={state['anomaly_count']}/{self.config.anomaly_persistence_count}]"
            )

        elif candidate_warning:
            state["anomaly_count"] = 0
            state["warning_count"] += 1
            is_confirmed = state["warning_count"] >= self.config.warning_persistence_count
            level = AnomalyLevel.WARNING if is_confirmed else AnomalyLevel.NORMAL
            th_used = th.warning_threshold if th else None
            rel_th_used = th.relative_warning_threshold if th else None

            breach_parts = []
            if is_warn_abs and th:
                breach_parts.append(f"|r|={abs_r:.4f}{unit_str} > {th.warning_threshold}{unit_str}")
            if is_warn_rel and th and rel_r is not None:
                breach_parts.append(f"|r_rel|={rel_r*100:.2f}% > {th.relative_warning_threshold*100:.2f}%")

            reason = (
                f"Warning threshold exceeded ({', '.join(breach_parts)}) "
                f"[consecutive={state['warning_count']}/{self.config.warning_persistence_count}]"
            )

        else:
            # Nominal residual within limits
            state["anomaly_count"] = 0
            state["warning_count"] = 0
            is_confirmed = True
            level = AnomalyLevel.NORMAL
            th_used = th.warning_threshold if th else None
            rel_th_used = th.relative_warning_threshold if th else None
            reason = f"Residual magnitude (|r|={abs_r:.4f}{unit_str}) is nominal"

        return AnomalyEvaluationResult(
            vehicle_id=residual.vehicle_id,
            sensor_name=residual.sensor_name,
            timestamp=residual.timestamp,
            observed_value=residual.observed_value,
            expected_value=residual.expected_value,
            residual=residual.residual,
            absolute_residual=residual.absolute_residual,
            relative_residual=residual.relative_residual,
            anomaly_level=level,
            diagnostic_eligible=True,
            freshness_status=residual.freshness_status,
            data_age_s=residual.data_age_s,
            threshold_used=th_used,
            relative_threshold_used=rel_th_used,
            persistence_count=state["anomaly_count"],
            is_confirmed=is_confirmed,
            reason=reason,
            details=residual.details,
        )

    def detect_frame(
        self,
        residuals: Dict[str, SensorResidual],
        allow_aging: Optional[bool] = None,
    ) -> Dict[str, AnomalyEvaluationResult]:
        """Evaluate an entire frame of SensorResiduals.
        
        Args:
            residuals: Mapping of sensor_name -> SensorResidual.
            allow_aging: Optional override for aging telemetry eligibility.
            
        Returns:
            Mapping of sensor_name -> AnomalyEvaluationResult.
        """
        results: Dict[str, AnomalyEvaluationResult] = {}
        for sensor, res in residuals.items():
            results[sensor] = self.detect(res, allow_aging=allow_aging)
        return results

    def reset(
        self,
        vehicle_id: Optional[str] = None,
        sensor_name: Optional[str] = None,
    ) -> None:
        """Reset persistence tracking state for all or a specific sensor stream."""
        if vehicle_id is not None and sensor_name is not None:
            self._persistence_state.pop((vehicle_id, sensor_name), None)
        elif vehicle_id is not None:
            keys_to_remove = [k for k in self._persistence_state if k[0] == vehicle_id]
            for k in keys_to_remove:
                self._persistence_state.pop(k, None)
        else:
            self._persistence_state.clear()

    def get_persistence_count(self, vehicle_id: str, sensor_name: str) -> Dict[str, int]:
        """Retrieve current persistence counter snapshot for a stream."""
        state = self._persistence_state.get((vehicle_id, sensor_name))
        if state is None:
            return {"anomaly_count": 0, "warning_count": 0}
        return dict(state)
