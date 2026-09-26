"""CLI Entrypoint for Connected Vehicle Digital Twin Experimental Campaigns.

Usage:
    python -m digital_twin.run_experiments --group baseline
    python -m digital_twin.run_experiments --group packet_loss --seeds 42 101 202
    python -m digital_twin.run_experiments --all --output-dir experiments/results
"""

import argparse
import os
import sys
import time
from typing import List

from digital_twin.experiment_config import ExperimentConfig, ExperimentGroup
from digital_twin.experiment_runner import ExperimentCampaign, ExperimentRunner


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for the experiment campaign runner."""
    parser = argparse.ArgumentParser(
        description="Execute controlled Digital Twin diagnostic experimental campaigns.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--group",
        type=str,
        default="all",
        choices=[
            "all",
            "baseline",
            "packet_loss",
            "delay",
            "jitter",
            "fault",
            "fault_packet_loss",
            "fault_delay",
            "combined",
        ],
        help="Experiment group to execute.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="run_all",
        help="Execute all experimental groups in a full research campaign.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[42, 101, 202],
        help="Deterministic random seeds for repeated replicate runs.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="Simulation duration in seconds for each scenario.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="experiments/results",
        help="Directory to save generated CSV/JSON research datasets.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="experiments/experiment_manifest.json",
        help="File path to save the experiment manifest JSON.",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="all",
        choices=["csv", "json", "all"],
        help="Export format for experimental results.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-experiment progress logging.",
    )

    return parser.parse_args()


def build_experiment_configs(args: argparse.Namespace) -> List[ExperimentConfig]:
    """Assemble the list of ExperimentConfigs based on command-line arguments."""
    group_arg = "all" if args.run_all else args.group.lower()

    if group_arg == "all":
        return ExperimentCampaign.create_full_campaign(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "baseline":
        return ExperimentCampaign.create_baseline_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "packet_loss":
        return ExperimentCampaign.create_packet_loss_sweep_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "delay":
        return ExperimentCampaign.create_delay_sweep_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "jitter":
        return ExperimentCampaign.create_jitter_sweep_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "fault":
        return ExperimentCampaign.create_fault_severity_sweep_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "fault_packet_loss":
        return ExperimentCampaign.create_fault_packet_loss_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "fault_delay":
        return ExperimentCampaign.create_fault_delay_group(seeds=args.seeds, duration_s=args.duration)
    elif group_arg == "combined":
        return ExperimentCampaign.create_combined_impairment_group(seeds=args.seeds, duration_s=args.duration)
    else:
        raise ValueError(f"Unknown experiment group: {group_arg}")


def main() -> int:
    """Main execution routine for the CLI runner."""
    args = parse_arguments()
    configs = build_experiment_configs(args)

    if not args.quiet:
        print("=" * 70)
        print("  CONNECTED VEHICLE DIGITAL TWIN - EXPERIMENTAL CAMPAIGN RUNNER")
        print("=" * 70)
        print(f"  Selected Group:  {args.group if not args.run_all else 'all'}")
        print(f"  Total Runs:      {len(configs)}")
        print(f"  Seeds:           {args.seeds}")
        print(f"  Duration/run:    {args.duration:.1f}s")
        print(f"  Output Dir:      {args.output_dir}")
        print(f"  Manifest:        {args.manifest}")
        print("-" * 70)

    # 1. Export Experiment Manifest
    runner = ExperimentRunner()
    runner.generate_manifest(configs, args.manifest)
    if not args.quiet:
        print(f"[OK] Experiment manifest generated -> {args.manifest}")

    # 2. Execute Experiments
    start_time = time.time()
    results = []
    for idx, cfg in enumerate(configs, start=1):
        if not args.quiet:
            print(f"  [{idx}/{len(configs)}] Running {cfg.experiment_id} ...", end="", flush=True)
        res = runner.run_experiment(cfg)
        results.append(res)
        if not args.quiet:
            print(
                f" Done. (Loss: {res.packet_loss_rate_percent:.1f}%, "
                f"Eligible: {res.diagnostic_eligible_count}, "
                f"Confirmed: {res.confirmed_anomaly_count})"
            )

    elapsed_s = time.time() - start_time

    # 3. Export Results
    os.makedirs(args.output_dir, exist_ok=True)
    group_label = "all" if args.run_all else args.group.lower()

    if args.format in ("csv", "all"):
        csv_path = os.path.join(args.output_dir, f"campaign_{group_label}_results.csv")
        runner.export_to_csv(results, csv_path)
        if not args.quiet:
            print(f"[OK] Results exported to CSV -> {csv_path}")

    if args.format in ("json", "all"):
        json_path = os.path.join(args.output_dir, f"campaign_{group_label}_results.json")
        runner.export_to_json(results, json_path)
        if not args.quiet:
            print(f"[OK] Results exported to JSON -> {json_path}")

    if not args.quiet:
        print("=" * 70)
        print(f"Campaign complete. {len(results)} experiments finished in {elapsed_s:.2f}s.")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
