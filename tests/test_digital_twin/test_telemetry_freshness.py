"""Unit Tests for Module 3 Stage 4B — Telemetry Freshness & Residual Validity."""

import math
import unittest
from digital_twin.models import (
    AnomalyStatus,
    ExpectedMeasurement,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.residual_generator import ResidualGenerator, ResidualValidityStatus
from digital_twin.telemetry_freshness import TelemetryFreshnessEvaluator
from digital_twin.twin_config import DigitalTwinConfig, FreshnessThresholds


class TestTelemetryFreshness(unittest.TestCase):
    """Test suite for data age (AoI) classification, validity, and diagnostic eligibility."""

    def setUp(self) -> None:
        self.thresholds = FreshnessThresholds(
            fresh_aoi_threshold_s=1.0,
            stale_aoi_threshold_s=3.0,
        )
        self.evaluator = TelemetryFreshnessEvaluator(thresholds=self.thresholds)
        self.generator = ResidualGenerator(freshness_evaluator=self.evaluator)

    # -------------------------------------------------------------------------
    # 1. Freshness Classification by AoI Bounds (Tests 1 - 6)
    # -------------------------------------------------------------------------
    def test_01_aoi_zero_is_fresh(self) -> None:
        """Verify AoI = 0 is classified as FRESH."""
        status, reason = self.evaluator.classify_aoi(0.0)
        self.assertEqual(status, FreshnessStatus.FRESH)
        self.assertIn("fresh", reason.lower())

    def test_02_aoi_below_fresh_threshold_is_fresh(self) -> None:
        """Verify AoI strictly below fresh threshold (e.g. 0.5s) is classified as FRESH."""
        status, _ = self.evaluator.classify_aoi(0.5)
        self.assertEqual(status, FreshnessStatus.FRESH)

    def test_03_aoi_exactly_at_fresh_threshold_is_fresh(self) -> None:
        """Verify AoI exactly on boundary (1.0s) is classified as FRESH."""
        status, _ = self.evaluator.classify_aoi(1.0)
        self.assertEqual(status, FreshnessStatus.FRESH)

    def test_04_aoi_between_fresh_and_stale_is_aging(self) -> None:
        """Verify AoI between fresh and stale thresholds (e.g. 2.0s) is classified as AGING."""
        status, reason = self.evaluator.classify_aoi(2.0)
        self.assertEqual(status, FreshnessStatus.AGING)
        self.assertIn("aging", reason.lower())

    def test_05_aoi_exactly_at_stale_threshold_is_aging(self) -> None:
        """Verify AoI exactly on stale boundary (3.0s) is classified as AGING."""
        status, _ = self.evaluator.classify_aoi(3.0)
        self.assertEqual(status, FreshnessStatus.AGING)

    def test_06_aoi_above_stale_threshold_is_stale(self) -> None:
        """Verify AoI above stale threshold (e.g. 3.01s, 5.0s) is classified as STALE."""
        status_edge, reason = self.evaluator.classify_aoi(3.0001)
        self.assertEqual(status_edge, FreshnessStatus.STALE)
        self.assertIn("stale", reason.lower())

        status_high, _ = self.evaluator.classify_aoi(10.0)
        self.assertEqual(status_high, FreshnessStatus.STALE)

    # -------------------------------------------------------------------------
    # 2. Invalid & Edge-Case AoI Conditions (Tests 7 - 10)
    # -------------------------------------------------------------------------
    def test_07_negative_aoi_is_invalid(self) -> None:
        """Verify negative AoI (causality violation) is classified as INVALID."""
        status, reason = self.evaluator.classify_aoi(-0.1)
        self.assertEqual(status, FreshnessStatus.INVALID)
        self.assertIn("negative", reason.lower())

    def test_08_none_aoi_is_missing(self) -> None:
        """Verify None AoI is classified as MISSING."""
        status, reason = self.evaluator.classify_aoi(None)
        self.assertEqual(status, FreshnessStatus.MISSING)
        self.assertIn("undefined", reason.lower())

    def test_09_nan_aoi_is_invalid(self) -> None:
        """Verify NaN AoI is classified as INVALID."""
        status, _ = self.evaluator.classify_aoi(float("nan"))
        self.assertEqual(status, FreshnessStatus.INVALID)

    def test_10_infinite_aoi_is_invalid(self) -> None:
        """Verify +Inf and -Inf AoI values are classified as INVALID."""
        status_pos_inf, _ = self.evaluator.classify_aoi(float("inf"))
        self.assertEqual(status_pos_inf, FreshnessStatus.INVALID)

        status_neg_inf, _ = self.evaluator.classify_aoi(float("-inf"))
        self.assertEqual(status_neg_inf, FreshnessStatus.INVALID)

    # -------------------------------------------------------------------------
    # 3. Residual Diagnostic Eligibility (Tests 11 - 16)
    # -------------------------------------------------------------------------
    def test_11_fresh_and_valid_residual_is_eligible(self) -> None:
        """Verify fresh and valid residual is marked diagnostic_eligible = True."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=92.0,
            expected_value=90.0,
            timestamp=10.0,
            data_age_s=0.2,
        )
        self.assertEqual(res.freshness_status, FreshnessStatus.FRESH)
        self.assertTrue(res.diagnostic_eligible)
        self.assertTrue(self.evaluator.is_diagnostic_eligible(res))

    def test_12_aging_and_valid_residual_marked_aging(self) -> None:
        """Verify aging residual is marked AGING and strictly not eligible unless allowed."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=95.0,
            expected_value=90.0,
            timestamp=10.0,
            data_age_s=2.5,
        )
        self.assertEqual(res.freshness_status, FreshnessStatus.AGING)
        # Default strict fresh evaluation -> False
        self.assertFalse(res.diagnostic_eligible)
        self.assertFalse(self.evaluator.is_diagnostic_eligible(res, allow_aging=False))
        # With allow_aging=True -> True
        self.assertTrue(self.evaluator.is_diagnostic_eligible(res, allow_aging=True))

    def test_13_stale_and_valid_residual_not_eligible(self) -> None:
        """Verify stale residual (AoI > 3.0s) is marked STALE and diagnostic_eligible = False."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            observed_value=60.0,
            expected_value=50.0,
            timestamp=10.0,
            data_age_s=4.5,
        )
        self.assertEqual(res.freshness_status, FreshnessStatus.STALE)
        self.assertFalse(res.diagnostic_eligible)
        self.assertFalse(self.evaluator.is_diagnostic_eligible(res, allow_aging=True))

    def test_14_invalid_residual_not_eligible(self) -> None:
        """Verify corrupted/NaN residual is marked INVALID and diagnostic_eligible = False."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_load",
            observed_value=float("nan"),
            expected_value=0.50,
            timestamp=10.0,
            data_age_s=0.1,
        )
        self.assertEqual(res.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertEqual(res.freshness_status, FreshnessStatus.INVALID)
        self.assertFalse(res.diagnostic_eligible)
        self.assertFalse(self.evaluator.is_diagnostic_eligible(res))

    def test_15_missing_residual_not_eligible(self) -> None:
        """Verify missing observed telemetry is marked MISSING and diagnostic_eligible = False."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="rpm",
            observed_value=None,
            expected_value=2200.0,
            timestamp=10.0,
            data_age_s=0.1,
        )
        self.assertEqual(res.anomaly_status, AnomalyStatus.INSUFFICIENT_DATA)
        self.assertEqual(res.freshness_status, FreshnessStatus.MISSING)
        self.assertFalse(res.diagnostic_eligible)
        self.assertFalse(self.evaluator.is_diagnostic_eligible(res))

    def test_16_rejected_telemetry_not_eligible(self) -> None:
        """Verify rejected telemetry (is_accepted = False) is diagnostic_eligible = False."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=90.0,
            expected_value=90.0,
            timestamp=10.0,
            data_age_s=0.1,
            is_accepted=False,
        )
        self.assertFalse(res.is_accepted)
        self.assertFalse(res.diagnostic_eligible)
        self.assertFalse(self.evaluator.is_diagnostic_eligible(res))

    # -------------------------------------------------------------------------
    # 4. Integration, Preservation & Immutability (Tests 17 - 21)
    # -------------------------------------------------------------------------
    def test_17_stage_4a_math_preserved_identically(self) -> None:
        """Verify mathematical raw, absolute, and relative residuals remain exact."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=96.0,
            expected_value=90.0,
            timestamp=5.0,
            data_age_s=0.05,
        )
        self.assertEqual(res.residual, 6.0)
        self.assertEqual(res.absolute_residual, 6.0)
        # 6.0 / 90.0 = 0.0667 (6.67%)
        self.assertAlmostEqual(res.relative_residual, 0.0667, places=4)
        self.assertEqual(res.freshness_status, FreshnessStatus.FRESH)
        self.assertTrue(res.diagnostic_eligible)

    def test_18_stale_residual_preserves_metadata(self) -> None:
        """Verify stale residual retains raw residual and data_age_s for research analysis."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=105.0,
            expected_value=90.0,
            timestamp=10.0,
            data_age_s=5.0,
            is_stale=True,
        )
        # Residual and age metadata are retained
        self.assertEqual(res.residual, 15.0)
        self.assertEqual(res.absolute_residual, 15.0)
        self.assertEqual(res.data_age_s, 5.0)
        self.assertTrue(res.is_stale)
        self.assertFalse(res.is_accepted)
        self.assertEqual(res.freshness_status, FreshnessStatus.STALE)
        self.assertFalse(res.diagnostic_eligible)

    def test_19_invalid_data_status_not_overwritten_by_stale_aoi(self) -> None:
        """Verify NaN telemetry with huge AoI remains INVALID_DATA (primary root cause)."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_load",
            observed_value=float("nan"),
            expected_value=0.50,
            timestamp=10.0,
            data_age_s=15.0,  # Stale AoI
        )
        self.assertEqual(res.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertEqual(res.freshness_status, FreshnessStatus.INVALID)
        self.assertEqual(res.details, ResidualValidityStatus.INVALID_VALUE.value)
        self.assertFalse(res.diagnostic_eligible)

    def test_20_missing_data_status_not_overwritten_by_stale_aoi(self) -> None:
        """Verify missing telemetry with huge AoI remains INSUFFICIENT_DATA."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            observed_value=None,
            expected_value=60.0,
            timestamp=10.0,
            data_age_s=12.0,  # Stale AoI
        )
        self.assertEqual(res.anomaly_status, AnomalyStatus.INSUFFICIENT_DATA)
        self.assertEqual(res.freshness_status, FreshnessStatus.MISSING)
        self.assertEqual(res.details, ResidualValidityStatus.MISSING_OBSERVED.value)
        self.assertFalse(res.diagnostic_eligible)

    def test_21_frame_evaluation_immutability(self) -> None:
        """Verify evaluate_residuals_for_frame produces new objects without mutating input dictionaries."""
        obs = {
            "speed_kmh": 60.0,
            "rpm": 2400.0,
            "engine_load": 0.50,
            "engine_temperature_c": 92.0,
            "cooling_fan_status": 0,
        }
        exp = ExpectedMeasurement(
            vehicle_id="EV_001",
            timestamp=10.0,
            expected_speed_kmh=60.0,
            expected_rpm=2400.0,
            expected_engine_load=0.50,
            expected_engine_temperature_c=88.0,
            expected_cooling_fan_status=0,
        )
        aoi_map = {
            "speed_kmh": 0.1,             # FRESH
            "rpm": 1.5,                   # AGING
            "engine_temperature_c": 4.0,  # STALE
            "engine_load": 0.05,          # FRESH
            "cooling_fan_status": 0.05,   # FRESH
        }

        residuals = self.generator.compute_residuals_for_frame(
            vehicle_id="EV_001",
            observed_telemetry=obs,
            expected_measurement=exp,
            data_ages=aoi_map,
        )

        evaluated = self.evaluator.evaluate_residuals_for_frame(residuals, aoi_map=aoi_map)

        self.assertEqual(evaluated["speed_kmh"].freshness_status, FreshnessStatus.FRESH)
        self.assertTrue(evaluated["speed_kmh"].diagnostic_eligible)

        self.assertEqual(evaluated["rpm"].freshness_status, FreshnessStatus.AGING)
        self.assertFalse(evaluated["rpm"].diagnostic_eligible)

        self.assertEqual(evaluated["engine_temperature_c"].freshness_status, FreshnessStatus.STALE)
        self.assertFalse(evaluated["engine_temperature_c"].diagnostic_eligible)
        self.assertEqual(evaluated["engine_temperature_c"].residual, 4.0)

        self.assertEqual(evaluated["cooling_fan_status"].freshness_status, FreshnessStatus.FRESH)
        self.assertTrue(evaluated["cooling_fan_status"].diagnostic_eligible)

    def test_22_freshness_threshold_validation(self) -> None:
        """Verify FreshnessThresholds bounds validation."""
        with self.assertRaises(ValueError):
            FreshnessThresholds(fresh_aoi_threshold_s=-1.0).validate()

        with self.assertRaises(ValueError):
            FreshnessThresholds(fresh_aoi_threshold_s=3.0, stale_aoi_threshold_s=2.0).validate()


if __name__ == "__main__":
    unittest.main()
