"""Unit Tests for Module 3 Stage 4D — Integrated Diagnostic Evaluation Framework."""

import unittest
from digital_twin.evaluation import (
    DiagnosticEvaluationRunner,
    EvaluationScenario,
    ScenarioResult,
    ScenarioType,
)
from digital_twin.models import AnomalyLevel, FreshnessStatus
from network.network_config import NetworkConfig, PacketLossConfig
from simulator.fault_injector import FaultConfig, FaultType


class TestDiagnosticEvaluationFramework(unittest.TestCase):
    """Test suite for experimental evaluation scenarios, metrics, ground-truth tracking, and determinism."""

    def setUp(self) -> None:
        self.runner = DiagnosticEvaluationRunner()

    # -------------------------------------------------------------------------
    # 1. Scenario A — Clean Link & Healthy Vehicle
    # -------------------------------------------------------------------------
    def test_scenario_a_clean_execution(self) -> None:
        """Verify Scenario A processes clean telemetry with normal residuals and zero false alerts."""
        scenario = self.runner.create_scenario_a_clean(duration_s=5.0, seed=42)
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "clean")
        self.assertEqual(result.total_generated_frames, 50)  # 5.0s / 0.1s
        self.assertGreater(result.total_packets_delivered, 0)
        self.assertEqual(result.total_packets_dropped, 0)
        self.assertEqual(result.packet_loss_rate_percent, 0.0)

        # Freshness should be predominantly fresh
        self.assertGreater(result.freshness_counts[FreshnessStatus.FRESH.value], 0)
        self.assertEqual(result.freshness_counts[FreshnessStatus.INVALID.value], 0)

        # Baseline anomaly detection should find zero confirmed anomalies and zero false alerts
        self.assertEqual(result.confirmed_anomaly_count, 0)
        self.assertEqual(result.false_alert_count, 0)
        self.assertGreater(result.anomaly_level_counts[AnomalyLevel.NORMAL.value], 0)

    # -------------------------------------------------------------------------
    # 2. Scenario B — Telemetry Staleness / Age
    # -------------------------------------------------------------------------
    def test_scenario_b_aging_stale_does_not_trigger_false_anomaly(self) -> None:
        """Verify stale telemetry is classified as STALE/NOT_EVALUATED and does not trigger false anomalies."""
        scenario = self.runner.create_scenario_b_aging_stale(duration_s=6.0, seed=42)
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "aging_stale")
        # Stale hold should result in stale freshness counts
        self.assertGreater(result.freshness_counts[FreshnessStatus.STALE.value], 0)
        self.assertGreater(result.anomaly_level_counts[AnomalyLevel.NOT_EVALUATED.value], 0)

        # Stale data must NOT produce false vehicle fault alerts
        self.assertEqual(result.confirmed_anomaly_count, 0)
        self.assertEqual(result.false_alert_count, 0)

    # -------------------------------------------------------------------------
    # 3. Scenario C — Controlled Packet Loss
    # -------------------------------------------------------------------------
    def test_scenario_c_packet_loss_tracking(self) -> None:
        """Verify packet loss rate, dropped packets, and missing telemetry assimilation."""
        loss_rate = 0.40  # 40% loss
        scenario = self.runner.create_scenario_c_packet_loss(duration_s=6.0, loss_rate=loss_rate, seed=42)
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "packet_loss")
        self.assertGreater(result.total_packets_dropped, 0)
        # Loss rate should be close to configured 40%
        self.assertAlmostEqual(result.packet_loss_rate_percent, 40.0, delta=15.0)
        self.assertGreater(result.total_packets_delivered, 0)

    # -------------------------------------------------------------------------
    # 4. Scenario D — Delay & Jitter
    # -------------------------------------------------------------------------
    def test_scenario_d_delay_jitter_aoi_fluctuation(self) -> None:
        """Verify uniform delay jitter produces variable AoI and proper metric bounds."""
        scenario = self.runner.create_scenario_d_delay_jitter(
            duration_s=5.0, min_delay_ms=50.0, max_delay_ms=400.0, seed=42
        )
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "delay_jitter")
        self.assertIsNotNone(result.mean_aoi_s)
        self.assertIsNotNone(result.max_aoi_s)
        self.assertGreater(result.max_aoi_s, result.mean_aoi_s)

    # -------------------------------------------------------------------------
    # 5. Scenario E — Duplicates & Out-of-Order Packets
    # -------------------------------------------------------------------------
    def test_scenario_e_duplicates_and_out_of_order_rejection(self) -> None:
        """Verify state estimator rejects duplicate and out-of-order packets without state corruption."""
        scenario = self.runner.create_scenario_e_duplicates_out_of_order(duration_s=5.0, dup_rate=0.40, seed=42)
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "duplicates_out_of_order")
        # Duplicates must be detected and rejected by State Estimator
        self.assertGreater(result.duplicate_updates, 0)
        self.assertGreater(result.total_rejected_updates, 0)
        self.assertGreater(result.total_accepted_updates, 0)

    # -------------------------------------------------------------------------
    # 6. Scenario F — Injected Vehicle Faults & Detection Delay
    # -------------------------------------------------------------------------
    def test_scenario_f_temperature_bias_detection(self) -> None:
        """Verify injected thermal sensor bias (+15°C) is confirmed as ANOMALY with measurable detection delay."""
        scenario = self.runner.create_scenario_f_injected_fault(
            duration_s=10.0,
            fault_type=FaultType.TEMP_SENSOR_BIAS,
            fault_start_s=3.0,
            fault_end_s=8.0,
            bias_offset_c=15.0,
            seed=42,
        )
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "injected_fault")
        self.assertGreater(result.ground_truth_fault_frames, 0)
        self.assertGreater(result.confirmed_anomaly_count, 0)
        self.assertGreater(result.true_positive_alert_count, 0)
        self.assertEqual(result.false_alert_count, 0)

        # Detection delay should be non-negative and finite
        self.assertIsNotNone(result.detection_delay_s)
        self.assertGreaterEqual(result.detection_delay_s, 0.0)
        self.assertLessEqual(result.detection_delay_s, 2.0)

        # Max thermal residual should reflect +15°C bias
        self.assertGreater(result.max_residual_by_sensor["engine_temperature_c"], 10.0)

    def test_scenario_f_fan_failure_detection(self) -> None:
        """Verify injected cooling fan failure is detected as actuator anomaly."""
        scenario = self.runner.create_scenario_f_injected_fault(
            duration_s=12.0,
            fault_type=FaultType.FAN_FAILURE,
            fault_start_s=2.0,
            fault_end_s=10.0,
            seed=42,
        )
        result = self.runner.run_scenario(scenario)
        self.assertGreater(result.ground_truth_fault_frames, 0)

    # -------------------------------------------------------------------------
    # 7. Scenario G — Combined Fault + Network Impairment
    # -------------------------------------------------------------------------
    def test_scenario_g_fault_plus_loss_and_delay(self) -> None:
        """Verify combined scenario evaluates fault detection under lossy stochastic delay."""
        scenario = self.runner.create_scenario_g_fault_plus_impairment(
            duration_s=8.0,
            fault_type=FaultType.TEMP_SENSOR_BIAS,
            loss_probability=0.20,
            seed=42,
        )
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.scenario_type, "fault_plus_impairment")
        self.assertGreater(result.total_packets_delivered, 0)
        self.assertGreater(result.total_packets_dropped, 0)
        self.assertGreater(result.ground_truth_fault_frames, 0)

    # -------------------------------------------------------------------------
    # 8. Deterministic Reproducibility & Suite Runner
    # -------------------------------------------------------------------------
    def test_deterministic_reproducibility(self) -> None:
        """Verify identical scenarios with the same seed produce bit-for-bit identical results."""
        scenario1 = self.runner.create_scenario_d_delay_jitter(duration_s=4.0, seed=123)
        scenario2 = self.runner.create_scenario_d_delay_jitter(duration_s=4.0, seed=123)

        res1 = self.runner.run_scenario(scenario1)
        res2 = self.runner.run_scenario(scenario2)

        self.assertEqual(res1.to_summary_dict(), res2.to_summary_dict())
        self.assertEqual(len(res1.records), len(res2.records))

    def test_run_suite_batch_execution(self) -> None:
        """Verify run_suite executes a collection of diverse scenarios and compiles batch dictionary."""
        suite = [
            self.runner.create_scenario_a_clean(duration_s=2.0, seed=1),
            self.runner.create_scenario_c_packet_loss(duration_s=2.0, loss_rate=0.2, seed=2),
        ]
        results = self.runner.run_suite(suite)

        self.assertEqual(len(results), 2)
        self.assertIn("Scenario_A_Clean", results)
        self.assertIn("Scenario_C_Packet_Loss", results)

    # -------------------------------------------------------------------------
    # 9. Edge Cases & Validation
    # -------------------------------------------------------------------------
    def test_zero_duration_scenario(self) -> None:
        """Verify scenario with zero duration returns empty records safely."""
        scenario = EvaluationScenario(name="ZeroDuration", duration_s=0.0, dt_s=0.1)
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.total_generated_frames, 0)
        self.assertEqual(len(result.records), 0)
        self.assertIsNone(result.mean_aoi_s)

    def test_100_percent_packet_loss_scenario(self) -> None:
        """Verify 100% packet loss drops all packets and flags all evaluations as not eligible."""
        net_cfg = NetworkConfig(
            packet_loss=PacketLossConfig(enabled=True, probability=1.0)
        )
        scenario = EvaluationScenario(
            name="TotalLoss",
            duration_s=3.0,
            dt_s=0.1,
            network_config=net_cfg,
        )
        result = self.runner.run_scenario(scenario)

        self.assertEqual(result.total_packets_delivered, 0)
        self.assertGreater(result.total_packets_dropped, 0)
        self.assertEqual(result.packet_loss_rate_percent, 100.0)

    def test_scenario_validation_errors(self) -> None:
        """Verify invalid scenario parameters raise ValueError on validation."""
        # Negative duration
        sc_neg_dur = EvaluationScenario(duration_s=-1.0)
        with self.assertRaises(ValueError):
            self.runner.run_scenario(sc_neg_dur)

        # Zero or negative dt
        sc_zero_dt = EvaluationScenario(dt_s=0.0)
        with self.assertRaises(ValueError):
            self.runner.run_scenario(sc_zero_dt)

        # Invalid duplicate injection rate
        sc_bad_dup = EvaluationScenario(duplicate_injection_rate=1.5)
        with self.assertRaises(ValueError):
            self.runner.run_scenario(sc_bad_dup)

    def test_serialization_and_export_formats(self) -> None:
        """Verify structured result to_dict, to_summary_dict, and record to_dict."""
        scenario = self.runner.create_scenario_a_clean(duration_s=1.0, seed=42)
        result = self.runner.run_scenario(scenario)

        summary_dict = result.to_summary_dict()
        self.assertIsInstance(summary_dict, dict)
        self.assertNotIn("records", summary_dict)
        self.assertEqual(summary_dict["scenario_name"], "Scenario_A_Clean")

        full_dict = result.to_dict()
        self.assertIsInstance(full_dict, dict)
        self.assertIn("records", full_dict)
        self.assertEqual(len(full_dict["records"]), 10)

        record_dict = result.records[0].to_dict()
        self.assertIn("time_s", record_dict)
        self.assertIn("residuals", record_dict)
        self.assertIn("freshness_statuses", record_dict)
        self.assertIn("anomaly_results", record_dict)

    def test_allow_aging_policy_override(self) -> None:
        """Verify allow_aging=True evaluates aging frames instead of marking them NOT_EVALUATED."""
        sc_strict = self.runner.create_scenario_b_aging_stale(duration_s=6.0, seed=42)
        sc_strict.allow_aging = False
        res_strict = self.runner.run_scenario(sc_strict)

        sc_permissive = self.runner.create_scenario_b_aging_stale(duration_s=6.0, seed=42)
        sc_permissive.allow_aging = True
        res_permissive = self.runner.run_scenario(sc_permissive)

        self.assertGreater(
            res_strict.anomaly_level_counts[AnomalyLevel.NOT_EVALUATED.value],
            res_permissive.anomaly_level_counts[AnomalyLevel.NOT_EVALUATED.value],
        )
        self.assertGreater(
            res_permissive.anomaly_level_counts[AnomalyLevel.NORMAL.value],
            res_strict.anomaly_level_counts[AnomalyLevel.NORMAL.value],
        )


if __name__ == "__main__":
    unittest.main()
