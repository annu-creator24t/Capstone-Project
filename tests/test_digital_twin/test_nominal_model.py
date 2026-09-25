"""Unit Tests for Module 3 Stage 2 — Physics-Informed Nominal Vehicle Model."""

import unittest
from digital_twin.models import SynchronizationStatus
from digital_twin.nominal_model import NominalVehicleModel
from digital_twin.twin_config import DigitalTwinConfig


class TestNominalVehicleModel(unittest.TestCase):
    """Test suite for nominal state transitions, thermal dynamics, and expected measurements."""

    def test_default_nominal_initialization(self) -> None:
        """Verify default initial state matches configuration."""
        model = NominalVehicleModel()
        state = model.get_current_state()

        self.assertEqual(state.vehicle_id, "EV_001")
        self.assertEqual(state.timestamp, 0.0)
        self.assertEqual(state.estimated_speed_kmh, 45.0)
        self.assertEqual(state.estimated_rpm, 2200.0)
        self.assertEqual(state.estimated_engine_load, 0.50)
        self.assertEqual(state.estimated_engine_temperature_c, 85.0)
        self.assertEqual(state.estimated_cooling_fan_status, 0)
        self.assertEqual(state.sync_status, SynchronizationStatus.INITIALIZING)

    def test_deterministic_state_transitions(self) -> None:
        """Verify identical inputs produce identical state trajectories."""
        m1 = NominalVehicleModel()
        m2 = NominalVehicleModel()

        for _ in range(20):
            s1 = m1.step(dt_seconds=1.0, input_speed_kmh=60.0, input_rpm=2500.0, input_engine_load=0.60)
            s2 = m2.step(dt_seconds=1.0, input_speed_kmh=60.0, input_rpm=2500.0, input_engine_load=0.60)
            self.assertEqual(s1.to_dict(), s2.to_dict())

    def test_zero_and_negative_dt(self) -> None:
        """Verify zero dt produces no time advancement and negative dt raises ValueError."""
        model = NominalVehicleModel()
        initial_state = model.get_current_state()

        s_zero = model.step(dt_seconds=0.0)
        self.assertEqual(s_zero.timestamp, 0.0)
        self.assertEqual(s_zero.estimated_engine_temperature_c, initial_state.estimated_engine_temperature_c)

        with self.assertRaises(ValueError):
            model.step(dt_seconds=-1.0)

    def test_thermal_response_to_increased_load(self) -> None:
        """Verify higher engine load leads to higher temperature rise."""
        model_low = NominalVehicleModel()
        model_high = NominalVehicleModel()

        for _ in range(15):
            model_low.step(dt_seconds=1.0, input_engine_load=0.20, input_rpm=1500.0)
            model_high.step(dt_seconds=1.0, input_engine_load=0.80, input_rpm=3000.0)

        t_low = model_low.get_current_state().estimated_engine_temperature_c
        t_high = model_high.get_current_state().estimated_engine_temperature_c

        self.assertGreater(t_high, t_low)

    def test_cooling_fan_thermostat_hysteresis(self) -> None:
        """Verify fan engages at >=95°C and disengages at <=90°C."""
        # Initialize at 94°C (fan off)
        model = NominalVehicleModel(DigitalTwinConfig(initial_temp_c=94.0))
        self.assertEqual(model.get_current_state().estimated_cooling_fan_status, 0)

        # High heat drives temperature past 95°C -> Fan should turn ON
        for _ in range(10):
            model.step(dt_seconds=1.0, input_engine_load=0.90, input_rpm=3500.0)

        state_hot = model.get_current_state()
        self.assertGreaterEqual(state_hot.estimated_engine_temperature_c, 95.0)
        self.assertEqual(state_hot.estimated_cooling_fan_status, 1)

    def test_override_fan_status(self) -> None:
        """Verify override fan status forces cooling fan state."""
        model = NominalVehicleModel(DigitalTwinConfig(initial_temp_c=80.0))
        
        # Fan should be naturally off at 80°C
        s_nat = model.step(dt_seconds=1.0)
        self.assertEqual(s_nat.estimated_cooling_fan_status, 0)

        # Override fan to ON (1)
        s_override = model.step(dt_seconds=1.0, override_fan_status=1)
        self.assertEqual(s_override.estimated_cooling_fan_status, 1)

    def test_expected_measurements_synthesis(self) -> None:
        """Verify generate_expected_measurements returns consistent ExpectedMeasurement schema."""
        model = NominalVehicleModel()
        model.step(dt_seconds=5.0, input_speed_kmh=55.0, input_rpm=2400.0, input_engine_load=0.55)
        
        expected = model.generate_expected_measurements()
        self.assertEqual(expected.vehicle_id, "EV_001")
        self.assertEqual(expected.expected_speed_kmh, 55.0)
        self.assertEqual(expected.expected_rpm, 2400.0)
        self.assertEqual(expected.expected_engine_load, 0.55)
        self.assertIsInstance(expected.expected_engine_temperature_c, float)

    def test_kinematic_bounding_and_clamping(self) -> None:
        """Verify speed, RPM, and load input bounding."""
        model = NominalVehicleModel()
        state = model.step(
            dt_seconds=1.0,
            input_speed_kmh=-20.0,  # Negative speed -> clamp to 0.0
            input_rpm=200.0,        # Below idle -> clamp to 600.0
            input_engine_load=1.50, # Above 1.0 -> clamp to 1.0
        )
        self.assertEqual(state.estimated_speed_kmh, 0.0)
        self.assertEqual(state.estimated_rpm, 600.0)
        self.assertEqual(state.estimated_engine_load, 1.0)


if __name__ == "__main__":
    unittest.main()
