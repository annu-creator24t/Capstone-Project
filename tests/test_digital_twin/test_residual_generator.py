"""Unit Tests for Module 3 Stage 4A — Residual Generator."""

import unittest
from digital_twin.models import AnomalyStatus, ExpectedMeasurement
from digital_twin.residual_generator import ResidualGenerator, ResidualValidityStatus


class TestResidualGenerator(unittest.TestCase):
    """Test suite for raw residuals, defensive relative residuals, and edge-case data handling."""

    def setUp(self) -> None:
        self.generator = ResidualGenerator(epsilon=1e-4)

    def test_raw_residual_calculations(self) -> None:
        """Verify positive, negative, and zero raw residual calculations."""
        # Positive residual: 95.0 - 90.0 = +5.0
        r_pos = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_temperature_c",
            observed_value=95.0, expected_value=90.0, timestamp=1.0
        )
        self.assertEqual(r_pos.residual, 5.0)
        self.assertEqual(r_pos.absolute_residual, 5.0)
        self.assertEqual(r_pos.anomaly_status, AnomalyStatus.NORMAL)
        self.assertEqual(r_pos.details, ResidualValidityStatus.VALID.value)

        # Negative residual: 85.0 - 90.0 = -5.0
        r_neg = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_temperature_c",
            observed_value=85.0, expected_value=90.0, timestamp=2.0
        )
        self.assertEqual(r_neg.residual, -5.0)
        self.assertEqual(r_neg.absolute_residual, 5.0)

        # Zero residual: 90.0 - 90.0 = 0.0
        r_zero = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_temperature_c",
            observed_value=90.0, expected_value=90.0, timestamp=3.0
        )
        self.assertEqual(r_zero.residual, 0.0)
        self.assertEqual(r_zero.absolute_residual, 0.0)

    def test_relative_residual_with_safe_epsilon(self) -> None:
        """Verify relative residual formula r_rel = (obs - exp) / max(|exp|, eps)."""
        # Standard: (99.0 - 90.0) / 90.0 = 9.0 / 90.0 = 0.10 (10%)
        r = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_temperature_c",
            observed_value=99.0, expected_value=90.0, timestamp=1.0
        )
        self.assertAlmostEqual(r.relative_residual, 0.10, places=4)

        # Zero expected value: (5.0 - 0.0) / max(0.0, 1e-4) = 5.0 / 0.0001 = 50000.0 (no division by zero error)
        r_zero_exp = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="speed_kmh",
            observed_value=5.0, expected_value=0.0, timestamp=1.0
        )
        self.assertIsNotNone(r_zero_exp.relative_residual)
        self.assertAlmostEqual(r_zero_exp.relative_residual, 50000.0, places=1)

    def test_categorical_cooling_fan_status(self) -> None:
        """Verify categorical signals (cooling fan) do not compute relative residuals."""
        # Status match (Fan 1 vs Expected 1)
        r_match = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="cooling_fan_status",
            observed_value=1, expected_value=1, timestamp=1.0
        )
        self.assertEqual(r_match.residual, 0.0)
        self.assertIsNone(r_match.relative_residual)
        self.assertEqual(r_match.details, ResidualValidityStatus.CATEGORICAL_STATUS.value)

        # Status mismatch (Fan 0 vs Expected 1)
        r_mismatch = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="cooling_fan_status",
            observed_value=0, expected_value=1, timestamp=1.0
        )
        self.assertEqual(r_mismatch.residual, -1.0)
        self.assertIsNone(r_mismatch.relative_residual)
        self.assertEqual(r_mismatch.details, ResidualValidityStatus.CATEGORICAL_MISMATCH.value)

    def test_missing_observed_and_expected_values(self) -> None:
        """Verify handling of None values without crashing."""
        # Missing observed value (e.g. sensor dropout)
        r_obs_none = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="rpm",
            observed_value=None, expected_value=2200.0, timestamp=1.0
        )
        self.assertIsNone(r_obs_none.residual)
        self.assertIsNone(r_obs_none.relative_residual)
        self.assertEqual(r_obs_none.anomaly_status, AnomalyStatus.INSUFFICIENT_DATA)
        self.assertEqual(r_obs_none.details, ResidualValidityStatus.MISSING_OBSERVED.value)

        # Missing expected value
        r_exp_none = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="rpm",
            observed_value=2200.0, expected_value=None, timestamp=1.0
        )
        self.assertIsNone(r_exp_none.expected_value)
        self.assertIsNone(r_exp_none.residual)
        self.assertIsNone(r_exp_none.relative_residual)
        self.assertEqual(r_exp_none.anomaly_status, AnomalyStatus.INSUFFICIENT_DATA)
        self.assertEqual(r_exp_none.details, ResidualValidityStatus.MISSING_EXPECTED.value)

    def test_invalid_nan_inf_inputs(self) -> None:
        """Verify NaN, +Inf, -Inf, and non-numeric string values return INVALID_DATA."""
        r_nan = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_load",
            observed_value=float("nan"), expected_value=0.50, timestamp=1.0
        )
        self.assertEqual(r_nan.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertFalse(r_nan.is_accepted)
        self.assertIsNone(r_nan.residual)

        r_pos_inf = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_load",
            observed_value=float("inf"), expected_value=0.50, timestamp=1.0
        )
        self.assertEqual(r_pos_inf.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertIsNone(r_pos_inf.residual)

        r_neg_inf = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_load",
            observed_value=float("-inf"), expected_value=0.50, timestamp=1.0
        )
        self.assertEqual(r_neg_inf.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertIsNone(r_neg_inf.residual)

        r_str = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_load",
            observed_value="corrupt_string", expected_value=0.50, timestamp=1.0
        )
        self.assertEqual(r_str.anomaly_status, AnomalyStatus.INVALID_DATA)
        self.assertIsNone(r_str.residual)

    def test_near_zero_expected_values(self) -> None:
        """Verify epsilon safety for near-zero expected values below epsilon threshold."""
        # Expected value 1e-6 is smaller than epsilon=1e-4 -> denominator clamped to 1e-4
        r_near_zero = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="engine_load",
            observed_value=0.01, expected_value=1e-6, timestamp=1.0
        )
        self.assertIsNotNone(r_near_zero.relative_residual)
        # (0.01 - 0.000001) / 0.0001 = 0.009999 / 0.0001 = 99.99
        self.assertAlmostEqual(r_near_zero.relative_residual, 99.99, places=2)

    def test_stale_telemetry_handling(self) -> None:
        """Verify stale telemetry is flagged with STALE_DATA and is_accepted=False."""
        r_stale = self.generator.compute_residual(
            vehicle_id="EV_001", sensor_name="speed_kmh",
            observed_value=40.0, expected_value=45.0, timestamp=5.0, is_stale=True
        )
        self.assertEqual(r_stale.residual, -5.0)
        self.assertTrue(r_stale.is_stale)
        self.assertFalse(r_stale.is_accepted)
        self.assertEqual(r_stale.anomaly_status, AnomalyStatus.STALE_DATA)

    def test_frame_level_residual_generation_and_immutability(self) -> None:
        """Verify compute_residuals_for_frame processes all 5 sensors without mutating inputs."""
        obs_frame = {
            "speed_kmh": 60.0,
            "rpm": 2500.0,
            "engine_load": 0.55,
            "engine_temperature_c": 92.0,
            "cooling_fan_status": 1,
        }
        obs_copy = dict(obs_frame)

        exp = ExpectedMeasurement(
            vehicle_id="EV_001",
            timestamp=10.0,
            expected_speed_kmh=58.0,
            expected_rpm=2400.0,
            expected_engine_load=0.50,
            expected_engine_temperature_c=88.0,
            expected_cooling_fan_status=0,
        )

        residuals = self.generator.compute_residuals_for_frame(
            vehicle_id="EV_001",
            observed_telemetry=obs_frame,
            expected_measurement=exp,
            timestamp=10.0,
            data_ages={"engine_temperature_c": 0.15},
        )

        self.assertEqual(len(residuals), 5)
        self.assertEqual(residuals["speed_kmh"].residual, 2.0)
        self.assertEqual(residuals["rpm"].residual, 100.0)
        self.assertEqual(residuals["engine_load"].residual, 0.05)
        self.assertEqual(residuals["engine_temperature_c"].residual, 4.0)
        self.assertEqual(residuals["engine_temperature_c"].data_age_s, 0.15)
        self.assertEqual(residuals["cooling_fan_status"].details, "categorical_mismatch")

        # Verify input was not mutated
        self.assertEqual(obs_frame, obs_copy)


if __name__ == "__main__":
    unittest.main()
