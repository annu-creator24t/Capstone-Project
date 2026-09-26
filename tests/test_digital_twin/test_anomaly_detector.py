"""Unit Tests for Module 3 Stage 4C — Baseline Anomaly Detector."""

import unittest
from digital_twin.anomaly_detector import BaselineAnomalyDetector
from digital_twin.models import (
    AnomalyLevel,
    AnomalyStatus,
    ExpectedMeasurement,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.residual_generator import ResidualGenerator
from digital_twin.telemetry_freshness import TelemetryFreshnessEvaluator
from digital_twin.twin_config import (
    AnomalyThresholds,
    DigitalTwinConfig,
    FreshnessThresholds,
    SignalThreshold,
)


class TestBaselineAnomalyDetector(unittest.TestCase):
    """Test suite for two-level thresholding, relative residuals, persistence, and eligibility."""

    def setUp(self) -> None:
        self.config = AnomalyThresholds(
            speed_kmh=SignalThreshold(
                warning_threshold=8.0,
                anomaly_threshold=12.0,
                relative_warning_threshold=0.15,
                relative_anomaly_threshold=0.25,
                unit="km/h",
            ),
            rpm=SignalThreshold(
                warning_threshold=200.0,
                anomaly_threshold=350.0,
                relative_warning_threshold=0.10,
                relative_anomaly_threshold=0.18,
                unit="RPM",
            ),
            engine_load=SignalThreshold(
                warning_threshold=0.12,
                anomaly_threshold=0.20,
                relative_warning_threshold=None,
                relative_anomaly_threshold=None,
                unit="ratio",
            ),
            engine_temperature_c=SignalThreshold(
                warning_threshold=5.0,
                anomaly_threshold=8.0,
                relative_warning_threshold=0.06,
                relative_anomaly_threshold=0.10,
                unit="°C",
            ),
            cooling_fan_status=SignalThreshold(
                warning_threshold=0.0,
                anomaly_threshold=0.5,
                unit="state",
            ),
            warning_persistence_count=1,
            anomaly_persistence_count=3,
            allow_aging=False,
        )
        self.detector = BaselineAnomalyDetector(config=self.config)
        self.freshness_evaluator = TelemetryFreshnessEvaluator(
            thresholds=FreshnessThresholds(fresh_aoi_threshold_s=1.0, stale_aoi_threshold_s=3.0)
        )
        self.generator = ResidualGenerator(freshness_evaluator=self.freshness_evaluator)

    def _make_fresh_residual(
        self,
        sensor_name: str,
        observed: float,
        expected: float,
        vehicle_id: str = "EV_001",
        data_age_s: float = 0.1,
    ) -> SensorResidual:
        return self.generator.compute_residual(
            vehicle_id=vehicle_id,
            sensor_name=sensor_name,
            observed_value=observed,
            expected_value=expected,
            timestamp=10.0,
            data_age_s=data_age_s,
        )

    # -------------------------------------------------------------------------
    # 1. Basic Thresholding (Tests 1 - 5)
    # -------------------------------------------------------------------------
    def test_01_residual_below_warning_is_normal(self) -> None:
        """Verify residual magnitude below warning threshold is classified as NORMAL."""
        # Temperature diff: 93.0 - 90.0 = 3.0°C < warning (5.0°C)
        res = self._make_fresh_residual("engine_temperature_c", 93.0, 90.0)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NORMAL)
        self.assertTrue(eval_res.is_confirmed)

    def test_02_residual_exactly_at_warning_threshold_is_normal(self) -> None:
        """Verify residual magnitude exactly at warning threshold (5.0°C) is NORMAL."""
        # 95.0 - 90.0 = 5.0°C (relative = 5/90 = 0.0555 < 0.06)
        res = self._make_fresh_residual("engine_temperature_c", 95.0, 90.0)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NORMAL)

    def test_03_residual_above_warning_threshold_is_warning(self) -> None:
        """Verify residual magnitude above warning threshold (6.0°C > 5.0°C) is WARNING."""
        # 96.0 - 90.0 = 6.0°C
        res = self._make_fresh_residual("engine_temperature_c", 96.0, 90.0)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.WARNING)
        self.assertTrue(eval_res.is_confirmed)

    def test_04_residual_exactly_at_anomaly_threshold_is_warning(self) -> None:
        """Verify residual magnitude exactly at anomaly threshold (8.0°C) is WARNING."""
        # 98.0 - 90.0 = 8.0°C, relative 8/90 = 0.0888 < 0.10
        res = self._make_fresh_residual("engine_temperature_c", 98.0, 90.0)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.WARNING)

    def test_05_residual_above_anomaly_threshold_is_anomaly_when_confirmed(self) -> None:
        """Verify consecutive anomalous residuals confirm ANOMALY when persistence is reached."""
        # 100.0 - 90.0 = 10.0°C > anomaly (8.0°C)
        res = self._make_fresh_residual("engine_temperature_c", 100.0, 90.0)

        # Sample 1: Candidate anomaly -> Level WARNING (not yet confirmed)
        r1 = self.detector.detect(res)
        self.assertEqual(r1.anomaly_level, AnomalyLevel.WARNING)
        self.assertFalse(r1.is_confirmed)

        # Sample 2: Level WARNING
        r2 = self.detector.detect(res)
        self.assertEqual(r2.anomaly_level, AnomalyLevel.WARNING)
        self.assertFalse(r2.is_confirmed)

        # Sample 3: Persistence reached (3/3) -> Level ANOMALY confirmed
        r3 = self.detector.detect(res)
        self.assertEqual(r3.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertTrue(r3.is_confirmed)
        self.assertEqual(r3.persistence_count, 3)

    # -------------------------------------------------------------------------
    # 2. Negative Residuals (Tests 6 - 7)
    # -------------------------------------------------------------------------
    def test_06_large_positive_residual_detected(self) -> None:
        """Verify large positive speed deviation (+15 km/h) triggers anomaly."""
        res = self._make_fresh_residual("speed_kmh", 65.0, 50.0)
        # 3 samples to confirm
        self.detector.detect(res)
        self.detector.detect(res)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertEqual(eval_res.residual, 15.0)

    def test_07_large_negative_residual_detected(self) -> None:
        """Verify large negative speed deviation (-15 km/h) triggers anomaly via absolute magnitude."""
        res = self._make_fresh_residual("speed_kmh", 35.0, 50.0)
        # 3 samples to confirm
        self.detector.detect(res)
        self.detector.detect(res)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertEqual(eval_res.residual, -15.0)
        self.assertEqual(eval_res.absolute_residual, 15.0)

    # -------------------------------------------------------------------------
    # 3. Relative Residual Thresholds (Tests 8 - 10)
    # -------------------------------------------------------------------------
    def test_08_relative_warning_threshold_triggered(self) -> None:
        """Verify relative warning threshold triggers WARNING even if absolute threshold is not breached."""
        # Custom config: warning 100.0, relative warning 0.05 (5%)
        cfg = AnomalyThresholds(
            rpm=SignalThreshold(
                warning_threshold=500.0,
                anomaly_threshold=1000.0,
                relative_warning_threshold=0.05,
                relative_anomaly_threshold=0.15,
                unit="RPM",
            )
        )
        det = BaselineAnomalyDetector(config=cfg)
        # 2120 - 2000 = 120 RPM (< 500 RPM absolute), but 120/2000 = 0.06 (6% > 5% rel warning)
        res = self._make_fresh_residual("rpm", 2120.0, 2000.0)
        eval_res = det.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.WARNING)
        self.assertIn("6.00%", eval_res.reason)

    def test_09_relative_anomaly_threshold_triggered(self) -> None:
        """Verify relative anomaly threshold triggers ANOMALY upon persistence."""
        cfg = AnomalyThresholds(
            rpm=SignalThreshold(
                warning_threshold=500.0,
                anomaly_threshold=1000.0,
                relative_warning_threshold=0.05,
                relative_anomaly_threshold=0.10,  # 10%
                unit="RPM",
            ),
            anomaly_persistence_count=1,
        )
        det = BaselineAnomalyDetector(config=cfg)
        # 2250 - 2000 = 250 RPM (< 1000 RPM absolute), but 250/2000 = 12.5% (> 10% rel anomaly)
        res = self._make_fresh_residual("rpm", 2250.0, 2000.0)
        eval_res = det.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertTrue(eval_res.is_confirmed)

    def test_10_none_relative_residual_handled_gracefully(self) -> None:
        """Verify sensors with relative_residual = None (e.g. engine_load) evaluate only absolute threshold."""
        # engine_load: warning 0.12, anomaly 0.20
        res = self._make_fresh_residual("engine_load", 0.65, 0.50)
        eval_res = self.detector.detect(res)
        # 0.65 - 0.50 = 0.15 > 0.12 (WARNING)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.WARNING)

    # -------------------------------------------------------------------------
    # 4. Freshness & Eligibility (Tests 11 - 16)
    # -------------------------------------------------------------------------
    def test_11_fresh_eligible_residual_is_evaluated(self) -> None:
        """Verify fresh eligible residual is normally evaluated."""
        res = self._make_fresh_residual("engine_temperature_c", 90.0, 90.0, data_age_s=0.2)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NORMAL)
        self.assertTrue(eval_res.diagnostic_eligible)

    def test_12_aging_residual_not_evaluated_by_default(self) -> None:
        """Verify aging residual (AoI = 2.0s) is NOT_EVALUATED by default, but evaluated when allow_aging=True."""
        res = self._make_fresh_residual("engine_temperature_c", 105.0, 90.0, data_age_s=2.0)
        # Default: not eligible
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NOT_EVALUATED)
        self.assertFalse(eval_res.diagnostic_eligible)

        # Explicit allow_aging override
        eval_res_allowed = self.detector.detect(res, allow_aging=True)
        self.assertEqual(eval_res_allowed.anomaly_level, AnomalyLevel.WARNING)

    def test_13_stale_residual_not_evaluated(self) -> None:
        """Verify stale residual (AoI = 5.0s, is_stale=True) is NOT_EVALUATED."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            observed_value=110.0,
            expected_value=90.0,
            timestamp=10.0,
            data_age_s=5.0,
            is_stale=True,
        )
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NOT_EVALUATED)
        self.assertFalse(eval_res.diagnostic_eligible)
        self.assertIn("stale", eval_res.reason.lower())

    def test_14_invalid_residual_not_evaluated(self) -> None:
        """Verify NaN/corrupt telemetry is NOT_EVALUATED."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            observed_value=float("nan"),
            expected_value=50.0,
            timestamp=10.0,
            data_age_s=0.1,
        )
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NOT_EVALUATED)
        self.assertFalse(eval_res.diagnostic_eligible)

    def test_15_missing_residual_not_evaluated(self) -> None:
        """Verify missing observed telemetry is NOT_EVALUATED."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="rpm",
            observed_value=None,
            expected_value=2200.0,
            timestamp=10.0,
            data_age_s=0.1,
        )
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NOT_EVALUATED)
        self.assertFalse(eval_res.diagnostic_eligible)

    def test_16_rejected_residual_not_evaluated(self) -> None:
        """Verify unaccepted/rejected packet residual is NOT_EVALUATED."""
        res = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            observed_value=70.0,
            expected_value=50.0,
            timestamp=10.0,
            data_age_s=0.1,
            is_accepted=False,
        )
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NOT_EVALUATED)
        self.assertFalse(eval_res.diagnostic_eligible)

    # -------------------------------------------------------------------------
    # 5. Categorical Fan Status (Tests 17 - 19)
    # -------------------------------------------------------------------------
    def test_17_matching_fan_state_is_normal(self) -> None:
        """Verify matching fan state (Observed=1, Expected=1) is NORMAL."""
        res = self._make_fresh_residual("cooling_fan_status", 1, 1)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.NORMAL)
        self.assertTrue(eval_res.is_confirmed)

    def test_18_mismatching_fan_state_triggers_anomaly(self) -> None:
        """Verify mismatching fan state (Observed=0, Expected=1) confirms ANOMALY with persistence."""
        res = self._make_fresh_residual("cooling_fan_status", 0, 1)
        self.detector.detect(res)
        self.detector.detect(res)
        eval_res = self.detector.detect(res)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertTrue(eval_res.is_confirmed)

    def test_19_categorical_relative_residual_remains_none(self) -> None:
        """Verify categorical signal has relative_residual = None throughout evaluation."""
        res = self._make_fresh_residual("cooling_fan_status", 0, 1)
        eval_res = self.detector.detect(res)
        self.assertIsNone(eval_res.relative_residual)
        self.assertIsNone(eval_res.relative_threshold_used)

    # -------------------------------------------------------------------------
    # 6. Persistence & Hysteresis (Tests 20 - 26)
    # -------------------------------------------------------------------------
    def test_20_single_anomaly_below_required_persistence_not_confirmed(self) -> None:
        """Verify single anomalous frame is not confirmed as ANOMALY when count < persistence."""
        res = self._make_fresh_residual("speed_kmh", 80.0, 50.0)  # +30 km/h
        eval_res = self.detector.detect(res)
        self.assertFalse(eval_res.is_confirmed)
        self.assertEqual(eval_res.anomaly_level, AnomalyLevel.WARNING)
        self.assertEqual(eval_res.persistence_count, 1)

    def test_21_consecutive_anomaly_count_reaches_threshold_confirmed(self) -> None:
        """Verify reaching persistence count (3) confirms ANOMALY."""
        res = self._make_fresh_residual("speed_kmh", 80.0, 50.0)
        self.detector.detect(res)
        self.detector.detect(res)
        r3 = self.detector.detect(res)
        self.assertTrue(r3.is_confirmed)
        self.assertEqual(r3.anomaly_level, AnomalyLevel.ANOMALY)
        self.assertEqual(r3.persistence_count, 3)

    def test_22_normal_sample_resets_anomaly_persistence(self) -> None:
        """Verify an interleaved normal sample resets consecutive anomaly counter."""
        anom_res = self._make_fresh_residual("speed_kmh", 80.0, 50.0)
        norm_res = self._make_fresh_residual("speed_kmh", 50.0, 50.0)

        # 2 anomalies
        self.detector.detect(anom_res)
        self.detector.detect(anom_res)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "speed_kmh")["anomaly_count"], 2)

        # 1 normal sample -> resets counter to 0
        self.detector.detect(norm_res)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "speed_kmh")["anomaly_count"], 0)

        # Next anomaly starts at count 1
        r_new = self.detector.detect(anom_res)
        self.assertEqual(r_new.persistence_count, 1)
        self.assertFalse(r_new.is_confirmed)

    def test_23_different_sensors_maintain_independent_counters(self) -> None:
        """Verify persistence counters are isolated across different sensor streams."""
        res_speed = self._make_fresh_residual("speed_kmh", 80.0, 50.0)
        res_temp = self._make_fresh_residual("engine_temperature_c", 100.0, 90.0)

        self.detector.detect(res_speed)
        self.detector.detect(res_speed)

        self.assertEqual(self.detector.get_persistence_count("EV_001", "speed_kmh")["anomaly_count"], 2)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "engine_temperature_c")["anomaly_count"], 0)

        self.detector.detect(res_temp)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "speed_kmh")["anomaly_count"], 2)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "engine_temperature_c")["anomaly_count"], 1)

    def test_24_different_vehicle_ids_maintain_independent_counters(self) -> None:
        """Verify persistence counters are isolated across different vehicle IDs."""
        res_v1 = self._make_fresh_residual("speed_kmh", 80.0, 50.0, vehicle_id="EV_001")
        res_v2 = self._make_fresh_residual("speed_kmh", 80.0, 50.0, vehicle_id="EV_002")

        self.detector.detect(res_v1)
        self.detector.detect(res_v1)

        self.assertEqual(self.detector.get_persistence_count("EV_001", "speed_kmh")["anomaly_count"], 2)
        self.assertEqual(self.detector.get_persistence_count("EV_002", "speed_kmh")["anomaly_count"], 0)

    def test_25_invalid_or_stale_sample_does_not_increment_counters(self) -> None:
        """Verify stale/invalid frames do not increment or falsely advance persistence."""
        res_anom = self._make_fresh_residual("rpm", 3000.0, 2000.0)
        self.detector.detect(res_anom)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "rpm")["anomaly_count"], 1)

        # Stale update
        res_stale = self.generator.compute_residual(
            vehicle_id="EV_001",
            sensor_name="rpm",
            observed_value=3000.0,
            expected_value=2000.0,
            timestamp=11.0,
            is_stale=True,
        )
        self.detector.detect(res_stale)
        # Counter remains 1
        self.assertEqual(self.detector.get_persistence_count("EV_001", "rpm")["anomaly_count"], 1)

    def test_26_persistence_reset_works(self) -> None:
        """Verify detector reset clears persistence tracking state completely."""
        res = self._make_fresh_residual("rpm", 3000.0, 2000.0)
        self.detector.detect(res)
        self.detector.detect(res)
        self.assertEqual(self.detector.get_persistence_count("EV_001", "rpm")["anomaly_count"], 2)

        self.detector.reset()
        self.assertEqual(self.detector.get_persistence_count("EV_001", "rpm")["anomaly_count"], 0)

    # -------------------------------------------------------------------------
    # 7. Configuration Validation (Tests 27 - 29)
    # -------------------------------------------------------------------------
    def test_27_invalid_threshold_ordering_rejected(self) -> None:
        """Verify warning_threshold >= anomaly_threshold raises ValueError."""
        with self.assertRaises(ValueError):
            SignalThreshold(warning_threshold=10.0, anomaly_threshold=8.0).validate()

        with self.assertRaises(ValueError):
            SignalThreshold(warning_threshold=10.0, anomaly_threshold=10.0).validate()

    def test_28_negative_thresholds_rejected(self) -> None:
        """Verify negative threshold values raise ValueError."""
        with self.assertRaises(ValueError):
            SignalThreshold(warning_threshold=-1.0, anomaly_threshold=5.0).validate()

    def test_29_invalid_persistence_count_rejected(self) -> None:
        """Verify persistence count < 1 raises ValueError."""
        with self.assertRaises(ValueError):
            AnomalyThresholds(warning_persistence_count=0).validate()

        with self.assertRaises(ValueError):
            AnomalyThresholds(anomaly_persistence_count=-2).validate()

    # -------------------------------------------------------------------------
    # 8. Frame Detection & Immutability (Tests 30 - 31)
    # -------------------------------------------------------------------------
    def test_30_detect_frame_evaluates_all_sensors(self) -> None:
        """Verify detect_frame processes all five vehicle sensors in a telemetry frame."""
        obs = {
            "speed_kmh": 50.0,            # Normal
            "rpm": 2200.0,                # Normal
            "engine_load": 0.65,          # 0.65 - 0.50 = 0.15 (Warning)
            "engine_temperature_c": 102.0,# 102 - 88 = 14°C (Anomaly candidate)
            "cooling_fan_status": 0,      # Normal
        }
        exp = ExpectedMeasurement(
            vehicle_id="EV_001",
            timestamp=10.0,
            expected_speed_kmh=50.0,
            expected_rpm=2200.0,
            expected_engine_load=0.50,
            expected_engine_temperature_c=88.0,
            expected_cooling_fan_status=0,
        )
        aoi_map = {s: 0.1 for s in obs}
        residuals = self.generator.compute_residuals_for_frame(
            vehicle_id="EV_001",
            observed_telemetry=obs,
            expected_measurement=exp,
            data_ages=aoi_map,
        )

        results = self.detector.detect_frame(residuals)
        self.assertEqual(len(results), 5)
        self.assertEqual(results["speed_kmh"].anomaly_level, AnomalyLevel.NORMAL)
        self.assertEqual(results["rpm"].anomaly_level, AnomalyLevel.NORMAL)
        self.assertEqual(results["engine_load"].anomaly_level, AnomalyLevel.WARNING)
        self.assertEqual(results["engine_temperature_c"].anomaly_level, AnomalyLevel.WARNING)  # 1st sample
        self.assertEqual(results["cooling_fan_status"].anomaly_level, AnomalyLevel.NORMAL)

    def test_31_serialization_and_metadata_preservation(self) -> None:
        """Verify AnomalyEvaluationResult serializes cleanly to dictionary with all research metadata."""
        res = self._make_fresh_residual("engine_temperature_c", 98.0, 90.0)
        eval_res = self.detector.detect(res)
        data = eval_res.to_dict()

        self.assertEqual(data["vehicle_id"], "EV_001")
        self.assertEqual(data["sensor_name"], "engine_temperature_c")
        self.assertEqual(data["anomaly_level"], "warning")
        self.assertEqual(data["freshness_status"], "fresh")
        self.assertTrue(data["diagnostic_eligible"])
        self.assertEqual(data["residual"], 8.0)


if __name__ == "__main__":
    unittest.main()
