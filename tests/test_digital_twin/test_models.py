"""Unit Tests for Module 3 Stage 1 — Digital Twin Data Models and Configurations."""

import unittest
from digital_twin.models import (
    AnomalyStatus,
    DigitalTwinState,
    ExpectedMeasurement,
    SensorResidual,
    SynchronizationStatus,
)
from digital_twin.twin_config import (
    DigitalTwinConfig,
    ResidualThresholds,
    SynchronizationThresholds,
)


class TestDigitalTwinModels(unittest.TestCase):
    """Test suite for Digital Twin state structures, expected measurements, and residuals."""

    def test_digital_twin_state_serialization(self) -> None:
        """Verify state fields, default initialization, and dictionary conversion."""
        state = DigitalTwinState(
            vehicle_id="EV_001",
            timestamp=10.0,
            estimated_speed_kmh=50.0,
            estimated_rpm=2200.0,
            estimated_engine_load=0.45,
            estimated_engine_temperature_c=91.5,
            estimated_cooling_fan_status=1,
            last_observation_timestamp=9.8,
            sync_status=SynchronizationStatus.SYNCHRONIZED,
        )

        data = state.to_dict()
        self.assertEqual(data["vehicle_id"], "EV_001")
        self.assertEqual(data["timestamp"], 10.0)
        self.assertEqual(data["estimated_speed_kmh"], 50.0)
        self.assertEqual(data["estimated_engine_temperature_c"], 91.5)
        self.assertEqual(data["sync_status"], "synchronized")

    def test_expected_measurement_serialization(self) -> None:
        """Verify expected measurement model keys and serialization."""
        expected = ExpectedMeasurement(
            vehicle_id="EV_001",
            timestamp=5.0,
            expected_speed_kmh=45.0,
            expected_rpm=2000.0,
            expected_engine_load=0.40,
            expected_engine_temperature_c=88.0,
            expected_cooling_fan_status=0,
        )
        data = expected.to_dict()
        self.assertEqual(data["expected_speed_kmh"], 45.0)
        self.assertEqual(data["expected_engine_temperature_c"], 88.0)

    def test_sensor_residual_calculation_and_relative_diff(self) -> None:
        """Verify automatic residual, absolute residual, and safe relative residual calculation."""
        res = SensorResidual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            timestamp=12.0,
            observed_value=96.0,
            expected_value=90.0,
            data_age_s=0.2,
        )

        self.assertAlmostEqual(res.residual, 6.0, places=4)
        self.assertAlmostEqual(res.absolute_residual, 6.0, places=4)
        # Relative: 6.0 / 90.0 = 0.0667 (6.67%)
        self.assertAlmostEqual(res.relative_residual, 0.0667, places=4)
        self.assertEqual(res.anomaly_status, AnomalyStatus.NORMAL)

    def test_sensor_residual_missing_observed_value(self) -> None:
        """Verify handling of missing/dropped telemetry without calculation crashes."""
        res = SensorResidual(
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            timestamp=15.0,
            observed_value=None,
            expected_value=90.0,
            anomaly_status=AnomalyStatus.INSUFFICIENT_DATA,
        )

        self.assertIsNone(res.residual)
        self.assertIsNone(res.absolute_residual)
        self.assertIsNone(res.relative_residual)
        self.assertEqual(res.anomaly_status, AnomalyStatus.INSUFFICIENT_DATA)

    def test_sensor_residual_zero_denominator_safety(self) -> None:
        """Verify safe handling when expected value is 0 (prevents ZeroDivisionError)."""
        res = SensorResidual(
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            timestamp=1.0,
            observed_value=5.0,
            expected_value=0.0,
        )
        self.assertAlmostEqual(res.residual, 5.0, places=4)
        self.assertIsNotNone(res.relative_residual)
        self.assertAlmostEqual(res.relative_residual, 50000.0, places=1)

    def test_twin_config_validation(self) -> None:
        """Verify DigitalTwinConfig bounds and threshold checks."""
        valid_cfg = DigitalTwinConfig()
        valid_cfg.validate()

        with self.assertRaises(ValueError):
            DigitalTwinConfig(thermal_capacity=-10.0).validate()

        with self.assertRaises(ValueError):
            DigitalTwinConfig(fan_off_temp_c=100.0, fan_on_temp_c=90.0).validate()

        with self.assertRaises(ValueError):
            DigitalTwinConfig(
                sync_thresholds=SynchronizationThresholds(stale_aoi_threshold_s=-1.0)
            ).validate()


if __name__ == "__main__":
    unittest.main()
