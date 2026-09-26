"""Telemetry Freshness & Residual Validity Evaluation for Cloud Digital Twin.

Evaluates data age (Age of Information - AoI) and sensor validity to determine
whether generated residuals are trustworthy for baseline and diagnostic anomaly detection.
Distinguishes between fresh, aging, stale, invalid, and missing telemetry without
modifying physical residual calculations or discarding valuable diagnostic metadata.
"""

import math
from typing import Any, Dict, Optional, Tuple
from digital_twin.models import (
    AnomalyStatus,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.twin_config import (
    DigitalTwinConfig,
    FreshnessThresholds,
)


class TelemetryFreshnessEvaluator:
    """Evaluates telemetry age and data validity to determine diagnostic trustworthiness."""

    def __init__(
        self,
        thresholds: Optional[FreshnessThresholds] = None,
        config: Optional[DigitalTwinConfig] = None,
    ) -> None:
        """Initialize the telemetry freshness evaluator.
        
        Args:
            thresholds: Specific freshness thresholds (fresh_aoi_threshold_s, stale_aoi_threshold_s).
            config: Optional master DigitalTwinConfig.
        """
        if config is not None:
            self.thresholds = config.freshness_thresholds
        elif thresholds is not None:
            self.thresholds = thresholds
        else:
            self.thresholds = FreshnessThresholds()

        self.thresholds.validate()

    def _is_valid_number(self, val: Any) -> bool:
        """Verify if a value is a finite, real numerical float/int."""
        if val is None or isinstance(val, bool):
            return False
        try:
            num = float(val)
            return not (math.isnan(num) or math.isinf(num))
        except (ValueError, TypeError):
            return False

    def classify_aoi(self, aoi_seconds: Optional[float]) -> Tuple[FreshnessStatus, str]:
        """Classify temporal freshness status strictly from Age-of-Information (AoI).
        
        Args:
            aoi_seconds: Age of Information in seconds (t_eval - t_gen).
            
        Returns:
            Tuple of (FreshnessStatus, detailed_reason_string).
        """
        # 1. Missing AoI
        if aoi_seconds is None:
            return (
                FreshnessStatus.MISSING,
                "Data age (AoI) is undefined or not tracked",
            )

        # 2. Invalid / Non-finite AoI
        if not self._is_valid_number(aoi_seconds):
            return (
                FreshnessStatus.INVALID,
                f"Data age (AoI) is invalid or non-finite ({aoi_seconds})",
            )

        aoi = float(aoi_seconds)

        # 3. Negative AoI (Causality violation)
        if aoi < 0.0:
            return (
                FreshnessStatus.INVALID,
                f"Data age (AoI) is negative ({aoi:.4f}s), indicating causality violation",
            )

        # 4. Fresh Telemetry: 0 <= AoI <= fresh_threshold
        if aoi <= self.thresholds.fresh_aoi_threshold_s:
            return (
                FreshnessStatus.FRESH,
                f"Telemetry is fresh (AoI={aoi:.4f}s <= {self.thresholds.fresh_aoi_threshold_s:.2f}s)",
            )

        # 5. Aging Telemetry: fresh_threshold < AoI <= stale_threshold
        if aoi <= self.thresholds.stale_aoi_threshold_s:
            return (
                FreshnessStatus.AGING,
                f"Telemetry is aging (AoI={aoi:.4f}s in ({self.thresholds.fresh_aoi_threshold_s:.2f}s, {self.thresholds.stale_aoi_threshold_s:.2f}s])",
            )

        # 6. Stale Telemetry: AoI > stale_threshold
        return (
            FreshnessStatus.STALE,
            f"Telemetry is stale (AoI={aoi:.4f}s > {self.thresholds.stale_aoi_threshold_s:.2f}s)",
        )

    def evaluate_freshness(
        self,
        aoi_seconds: Optional[float],
        is_valid_data: bool = True,
        is_missing_data: bool = False,
        is_stale: bool = False,
    ) -> Tuple[FreshnessStatus, str]:
        """Comprehensive evaluation of telemetry freshness considering validity, staleness, and AoI.
        
        Args:
            aoi_seconds: Age of Information in seconds.
            is_valid_data: Whether data value is numerically valid and non-corrupt.
            is_missing_data: Whether measurement observation is missing/dropped.
            is_stale: Whether transport/estimator flagged measurement as stale or rejected.
            
        Returns:
            Tuple of (FreshnessStatus, detailed_reason_string).
        """
        # 1. Invalid data check takes precedence
        if not is_valid_data:
            return (FreshnessStatus.INVALID, "Invalid or corrupted telemetry value (NaN/Inf/type error)")

        # 2. Missing data check
        if is_missing_data:
            return (FreshnessStatus.MISSING, "Missing telemetry observation")

        # 3. Explicitly stale/rejected check
        if is_stale:
            aoi_str = f"AoI={aoi_seconds:.4f}s" if (aoi_seconds is not None and self._is_valid_number(aoi_seconds)) else "AoI=N/A"
            return (FreshnessStatus.STALE, f"Telemetry flagged as stale/out-of-order ({aoi_str})")

        # 4. AoI-based qualification
        return self.classify_aoi(aoi_seconds)

    def is_diagnostic_eligible(
        self,
        residual: SensorResidual,
        allow_aging: bool = False,
    ) -> bool:
        """Determine whether a generated residual is trustworthy for fresh anomaly detection.
        
        Rules for diagnostic eligibility:
            1. Must be accepted by the digital twin estimator (is_accepted == True).
            2. Must not be flagged stale (is_stale == False).
            3. Must have valid numerical observed/expected values (not INVALID_DATA or INSUFFICIENT_DATA).
            4. Must have a calculated residual value (residual is not None).
            5. Must be FRESH (or AGING if explicitly allowed via allow_aging=True).
        
        Args:
            residual: SensorResidual instance to evaluate.
            allow_aging: If True, aging telemetry is considered eligible; if False (default), only fresh telemetry is eligible.
            
        Returns:
            True if eligible for baseline anomaly evaluation, False otherwise.
        """
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

    def evaluate_residual(
        self,
        residual: SensorResidual,
        aoi_seconds: Optional[float] = None,
        allow_aging: bool = False,
    ) -> SensorResidual:
        """Enrich a SensorResidual with freshness qualification and diagnostic eligibility.
        
        Preserves original residual calculations, diagnostic classifications, and diagnostic metadata.
        
        Args:
            residual: The input SensorResidual from ResidualGenerator.
            aoi_seconds: Optional explicit AoI override (defaults to residual.data_age_s).
            allow_aging: Whether aging data should be marked as diagnostic_eligible.
            
        Returns:
            A new SensorResidual instance with updated freshness_status, diagnostic_eligible,
            and freshness_reason fields without mutating the input residual.
        """
        effective_aoi = aoi_seconds if aoi_seconds is not None else residual.data_age_s

        # Identify primary condition from Stage 4A evaluations
        is_invalid = residual.anomaly_status == AnomalyStatus.INVALID_DATA
        is_missing = (
            not is_invalid
            and (
                residual.observed_value is None
                or residual.expected_value is None
                or residual.anomaly_status == AnomalyStatus.INSUFFICIENT_DATA
            )
        )
        is_stale = residual.is_stale or residual.anomaly_status == AnomalyStatus.STALE_DATA

        status, reason = self.evaluate_freshness(
            aoi_seconds=effective_aoi,
            is_valid_data=not is_invalid,
            is_missing_data=is_missing,
            is_stale=is_stale,
        )

        # Retain rejection context if telemetry was rejected
        if not residual.is_accepted and status not in (FreshnessStatus.INVALID, FreshnessStatus.MISSING):
            if is_stale or status == FreshnessStatus.STALE:
                status = FreshnessStatus.STALE
            reason = f"Rejected telemetry: {reason}"

        # Construct evaluated residual copy preserving all metadata
        evaluated = SensorResidual(
            vehicle_id=residual.vehicle_id,
            sensor_name=residual.sensor_name,
            timestamp=residual.timestamp,
            observed_value=residual.observed_value,
            expected_value=residual.expected_value,
            residual=residual.residual,
            absolute_residual=residual.absolute_residual,
            relative_residual=residual.relative_residual,
            data_age_s=effective_aoi,
            is_stale=residual.is_stale or (status == FreshnessStatus.STALE),
            is_accepted=residual.is_accepted,
            anomaly_status=residual.anomaly_status,
            threshold=residual.threshold,
            details=residual.details,
            freshness_status=status,
            freshness_reason=reason,
            diagnostic_eligible=False,
        )

        # Set diagnostic eligibility
        evaluated.diagnostic_eligible = self.is_diagnostic_eligible(
            evaluated, allow_aging=allow_aging
        )
        return evaluated

    def evaluate_residuals_for_frame(
        self,
        residuals: Dict[str, SensorResidual],
        aoi_map: Optional[Dict[str, float]] = None,
        allow_aging: bool = False,
    ) -> Dict[str, SensorResidual]:
        """Evaluate freshness and diagnostic eligibility across all sensor residuals in a frame.
        
        Args:
            residuals: Mapping of sensor_name -> SensorResidual.
            aoi_map: Optional mapping of sensor_name -> AoI in seconds.
            allow_aging: Whether aging data should be marked as diagnostic_eligible.
            
        Returns:
            New dictionary mapping sensor_name -> evaluated SensorResidual.
        """
        aoi_map = aoi_map or {}
        evaluated_frame: Dict[str, SensorResidual] = {}
        for sensor, res in residuals.items():
            aoi = aoi_map.get(sensor)
            evaluated_frame[sensor] = self.evaluate_residual(
                res, aoi_seconds=aoi, allow_aging=allow_aging
            )
        return evaluated_frame
