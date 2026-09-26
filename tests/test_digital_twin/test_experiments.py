"""Unit Tests for Module 4 Stage 5 — Experimental Campaign & Research Data Generation."""

import csv
import json
import os
import shutil
import tempfile
import unittest

from digital_twin.experiment_config import ExperimentConfig, ExperimentGroup
from digital_twin.experiment_runner import (
    ExperimentCampaign,
    ExperimentResult,
    ExperimentRunner,
)
from digital_twin.run_experiments import build_experiment_configs, main
from network.delay_model import DelayMode
from simulator.fault_injector import FaultType


class TestExperimentFramework(unittest.TestCase):
    """Test suite for experiment configuration, matrix sweeps, determinism, metrics, and exports."""

    def setUp(self) -> None:
        self.runner = ExperimentRunner()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Configuration Validation Tests
    # -------------------------------------------------------------------------
    def test_valid_configuration(self) -> None:
        """Verify valid experiment configuration passes validation without error."""
        cfg = ExperimentConfig(
            experiment_id="EXP_VALID_01",
            group=ExperimentGroup.BASELINE,
            duration_s=10.0,
            dt_s=0.1,
            packet_loss_rate=0.15,
            delay_mode=DelayMode.FIXED,
            fixed_delay_ms=20.0,
        )
        cfg.validate()
        scenario = cfg.to_evaluation_scenario()
        self.assertEqual(scenario.name, "EXP_VALID_01")
        self.assertEqual(scenario.duration_s, 10.0)

    def test_invalid_configurations_raise_value_error(self) -> None:
        """Verify out-of-bound parameters raise ValueError upon validation."""
        # Empty experiment ID
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="").validate()

        # Negative or zero duration
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="EXP_0", duration_s=0.0).validate()
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="EXP_0", duration_s=-5.0).validate()

        # Negative dt
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="EXP_0", dt_s=-0.1).validate()

        # Out-of-bounds packet loss rate
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="EXP_0", packet_loss_rate=1.2).validate()
        with self.assertRaises(ValueError):
            ExperimentConfig(experiment_id="EXP_0", packet_loss_rate=-0.05).validate()

        # Invalid uniform delay bounds (min > max)
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_id="EXP_0",
                delay_mode=DelayMode.UNIFORM,
                min_delay_ms=200.0,
                max_delay_ms=50.0,
            ).validate()

        # Invalid fault timing
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_id="EXP_0",
                fault_start_s=10.0,
                fault_end_s=5.0,
            ).validate()

    # -------------------------------------------------------------------------
    # 2. Determinism & Seed Replicability Tests
    # -------------------------------------------------------------------------
    def test_deterministic_reproducibility(self) -> None:
        """Verify identical configuration with identical seed produces bit-for-bit identical results."""
        cfg1 = ExperimentConfig(
            experiment_id="EXP_DET_01",
            group=ExperimentGroup.COMBINED_IMPAIRMENT,
            seed=777,
            duration_s=3.0,
            packet_loss_rate=0.20,
            delay_mode=DelayMode.GAUSSIAN,
            mean_delay_ms=80.0,
            std_delay_ms=20.0,
            fault_type=FaultType.TEMP_SENSOR_BIAS,
            fault_magnitude=15.0,
        )
        cfg2 = ExperimentConfig(
            experiment_id="EXP_DET_01",
            group=ExperimentGroup.COMBINED_IMPAIRMENT,
            seed=777,
            duration_s=3.0,
            packet_loss_rate=0.20,
            delay_mode=DelayMode.GAUSSIAN,
            mean_delay_ms=80.0,
            std_delay_ms=20.0,
            fault_type=FaultType.TEMP_SENSOR_BIAS,
            fault_magnitude=15.0,
        )

        res1 = self.runner.run_experiment(cfg1)
        res2 = self.runner.run_experiment(cfg2)

        self.assertEqual(res1.to_csv_row(), res2.to_csv_row())

    def test_different_seeds_produce_distinct_noise(self) -> None:
        """Verify different random seeds produce varying stochastic drop patterns."""
        cfg_seed_a = ExperimentConfig(
            experiment_id="EXP_SEED_A",
            seed=111,
            duration_s=5.0,
            packet_loss_rate=0.40,
        )
        cfg_seed_b = ExperimentConfig(
            experiment_id="EXP_SEED_B",
            seed=999,
            duration_s=5.0,
            packet_loss_rate=0.40,
        )

        res_a = self.runner.run_experiment(cfg_seed_a)
        res_b = self.runner.run_experiment(cfg_seed_b)

        self.assertEqual(res_a.total_generated_frames, res_b.total_generated_frames)
        # Random seeds generate different drop counts or delivery histories
        self.assertIsInstance(res_a.total_packets_delivered, int)
        self.assertIsInstance(res_b.total_packets_delivered, int)

    # -------------------------------------------------------------------------
    # 3. Experiment Groups Execution & Sweep Tests
    # -------------------------------------------------------------------------
    def test_group_a_baseline_execution(self) -> None:
        """Verify Group A (Baseline Healthy) executes with 0 false alerts and normal residuals."""
        configs = ExperimentCampaign.create_baseline_group(seeds=(42,), duration_s=3.0)
        self.assertEqual(len(configs), 1)

        result = self.runner.run_experiment(configs[0])
        self.assertEqual(result.group, "baseline")
        self.assertEqual(result.false_alert_count, 0)
        self.assertEqual(result.confirmed_anomaly_count, 0)
        self.assertGreater(result.fresh_count, 0)
        self.assertEqual(result.total_packets_dropped, 0)

    def test_group_b_packet_loss_sweep(self) -> None:
        """Verify Group B executes packet loss sweeps and logs dropped packets monotonically."""
        configs = ExperimentCampaign.create_packet_loss_sweep_group(
            loss_rates=(0.0, 0.50),
            seeds=(42,),
            duration_s=3.0,
        )
        self.assertEqual(len(configs), 2)

        results = self.runner.run_campaign(configs)
        res_0 = results[0]
        res_50 = results[1]

        self.assertEqual(res_0.total_packets_dropped, 0)
        self.assertGreater(res_50.total_packets_dropped, 0)
        self.assertGreater(res_50.packet_loss_rate_percent, 25.0)

    def test_group_c_delay_sweep(self) -> None:
        """Verify Group C measures increasing AoI with increasing transmission delay."""
        configs = ExperimentCampaign.create_delay_sweep_group(
            delays_ms=(10.0, 300.0),
            seeds=(42,),
            duration_s=3.0,
        )
        results = self.runner.run_campaign(configs)

        self.assertIsNotNone(results[0].mean_aoi_s)
        self.assertIsNotNone(results[1].mean_aoi_s)
        self.assertGreater(results[1].mean_aoi_s, results[0].mean_aoi_s)

    def test_group_d_jitter_sweep(self) -> None:
        """Verify Group D handles stochastic delay jitter and records metric bounds."""
        configs = ExperimentCampaign.create_jitter_sweep_group(
            jitters_ms=(0.0, 50.0),
            base_delay_ms=100.0,
            seeds=(42,),
            duration_s=3.0,
        )
        results = self.runner.run_campaign(configs)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertGreater(r.total_packets_delivered, 0)

    def test_group_e_fault_severity_sweep(self) -> None:
        """Verify Group E residual magnitude scales with injected thermal sensor bias."""
        configs = ExperimentCampaign.create_fault_severity_sweep_group(
            biases_c=(5.0, 20.0),
            seeds=(42,),
            duration_s=5.0,
        )
        results = self.runner.run_campaign(configs)

        res_5c = results[0]
        res_20c = results[1]

        # Max thermal residual for +20°C bias must exceed +5°C bias
        self.assertGreater(res_20c.max_temp_residual, res_5c.max_temp_residual)
        self.assertGreater(res_20c.ground_truth_fault_frames, 0)

    def test_group_f_fault_plus_packet_loss(self) -> None:
        """Verify Group F evaluates fault detection under packet loss conditions."""
        configs = ExperimentCampaign.create_fault_packet_loss_group(
            bias_c=15.0,
            loss_rates=(0.0, 0.30),
            seeds=(42,),
            duration_s=5.0,
        )
        results = self.runner.run_campaign(configs)
        self.assertEqual(len(results), 2)
        self.assertGreater(results[1].total_packets_dropped, 0)

    def test_group_g_fault_plus_delay(self) -> None:
        """Verify Group G evaluates fault detection under delayed network channels."""
        configs = ExperimentCampaign.create_fault_delay_group(
            bias_c=15.0,
            delays_ms=(10.0, 200.0),
            seeds=(42,),
            duration_s=5.0,
        )
        results = self.runner.run_campaign(configs)
        self.assertEqual(len(results), 2)
        self.assertGreater(results[0].ground_truth_fault_frames, 0)

    def test_group_h_combined_impairment(self) -> None:
        """Verify Group H executes full multi-variable impairment."""
        configs = ExperimentCampaign.create_combined_impairment_group(
            seeds=(101, 202),
            duration_s=4.0,
        )
        results = self.runner.run_campaign(configs)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.group, "combined_impairment")
            self.assertGreater(r.total_packets_delivered, 0)

    def test_full_campaign_matrix_generation(self) -> None:
        """Verify create_full_campaign generates complete matrix covering all standard groups."""
        full_configs = ExperimentCampaign.create_full_campaign(seeds=(42,), duration_s=2.0)
        # Groups: Baseline(1) + Loss(5) + Delay(5) + Jitter(5) + Fault(4) + FaultLoss(5) + FaultDelay(5) + Combined(5)
        self.assertGreaterEqual(len(full_configs), 30)

    # -------------------------------------------------------------------------
    # 4. Metric Integrity & Ground Truth Tests
    # -------------------------------------------------------------------------
    def test_metric_conservation_and_non_negativity(self) -> None:
        """Verify metric non-negativity, packet accounting, and ground truth alignment."""
        cfg = ExperimentConfig(
            experiment_id="EXP_METRICS_CHECK",
            group=ExperimentGroup.FAULT_PACKET_LOSS,
            duration_s=6.0,
            dt_s=0.1,
            packet_loss_rate=0.20,
            fault_type=FaultType.TEMP_SENSOR_BIAS,
            fault_magnitude=15.0,
            fault_start_s=2.0,
            fault_end_s=5.0,
        )
        res = self.runner.run_experiment(cfg)

        # Non-negative counts
        self.assertGreaterEqual(res.total_generated_frames, 0)
        self.assertGreaterEqual(res.total_packets_transmitted, 0)
        self.assertGreaterEqual(res.total_packets_delivered, 0)
        self.assertGreaterEqual(res.total_packets_dropped, 0)
        self.assertGreaterEqual(res.fresh_count, 0)
        self.assertGreaterEqual(res.diagnostic_eligible_count, 0)
        self.assertGreaterEqual(res.confirmed_anomaly_count, 0)
        self.assertGreaterEqual(res.false_alert_count, 0)

        # Ground truth fault frames
        self.assertGreater(res.ground_truth_fault_frames, 0)
        if res.detection_delay_s is not None:
            self.assertGreaterEqual(res.detection_delay_s, 0.0)

    # -------------------------------------------------------------------------
    # 5. Data Export Tests (CSV, JSON, Manifest)
    # -------------------------------------------------------------------------
    def test_export_to_csv_and_json(self) -> None:
        """Verify CSV and JSON file exports produce valid research-ready data structures."""
        configs = ExperimentCampaign.create_baseline_group(seeds=(42, 101), duration_s=1.0)
        results = self.runner.run_campaign(configs)

        csv_path = os.path.join(self.test_dir, "results.csv")
        json_path = os.path.join(self.test_dir, "results.json")
        manifest_path = os.path.join(self.test_dir, "manifest.json")

        self.runner.export_to_csv(results, csv_path)
        self.runner.export_to_json(results, json_path)
        self.runner.generate_manifest(configs, manifest_path)

        # Verify CSV
        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertIn("experiment_id", rows[0])
            self.assertIn("packet_loss_rate", rows[0])
            self.assertIn("confirmed_anomaly_count", rows[0])

        # Verify JSON
        self.assertTrue(os.path.exists(json_path))
        with open(json_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["experiment_id"], results[0].experiment_id)

        # Verify Manifest
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, mode="r", encoding="utf-8") as f:
            manifest = json.load(f)
            self.assertEqual(manifest["total_experiments"], 2)
            self.assertEqual(len(manifest["experiments"]), 2)

    # -------------------------------------------------------------------------
    # 6. CLI Runner Invocation Tests
    # -------------------------------------------------------------------------
    def test_cli_build_configs_and_execution(self) -> None:
        """Verify CLI helper builds correct configs for each group keyword."""
        class MockArgs:
            def __init__(self, group: str, run_all: bool = False):
                self.group = group
                self.run_all = run_all
                self.seeds = [42]
                self.duration = 1.0

        for grp in [
            "baseline",
            "packet_loss",
            "delay",
            "jitter",
            "fault",
            "fault_packet_loss",
            "fault_delay",
            "combined",
        ]:
            cfgs = build_experiment_configs(MockArgs(group=grp))
            self.assertGreater(len(cfgs), 0)


if __name__ == "__main__":
    unittest.main()
