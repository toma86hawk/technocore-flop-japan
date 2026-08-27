#!/usr/bin/env python3
"""FLOP airdrop allocation simulator.

Models the published Flop Network genesis-pool rules (flop.finance/teaser) so you can
compare the three participant roles before the Q4 2026 testnet and decide where to
put your compute and time. All figures are the project's published targets, not
promises: nothing here guarantees any allocation.

Usage:
  python flop_calc.py                       # compare all roles with default assumptions
  python flop_calc.py --agent-spend 9000    # agent: testnet FLOP spent on inference
  python flop_calc.py --gpu-hours 2160 --gpu-cost 0.74   # miner: 90 days of one GPU
  python flop_calc.py --json                # machine-readable output
"""
import argparse, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Published genesis-pool figures (flop.finance/teaser, as read 2026-08-27).
GENESIS_POOL = 3_500_000_000        # total testnet genesis pool, FLOP
MINER_POOL = 1_200_000_000          # miner share of the genesis pool
VALIDATOR_POOL = 305_000_000        # validator share of the genesis pool
VALIDATOR_SLOTS = 1_000             # only the top N validators by uptime/accuracy
AGENT_SPEND_RATIO = 3               # 3 FLOP spent on inference -> 1 FLOP airdropped
TESTNET_DAYS = 90                   # testnet runs roughly 90 days


def agent_reward(spend):
    """Agents earn 1 airdropped FLOP per AGENT_SPEND_RATIO spent on inference.
    Testnet FLOP comes from the faucet, so the input cost is time, not capital."""
    return spend / AGENT_SPEND_RATIO


def miner_reward(my_gpu_hours, network_gpu_hours):
    """Miners split MINER_POOL in proportion to compute delivered."""
    if network_gpu_hours <= 0:
        return 0.0
    return MINER_POOL * (my_gpu_hours / network_gpu_hours)


def validator_reward(rank):
    """VALIDATOR_POOL is split across the top VALIDATOR_SLOTS operators.
    Outside the cut-off the allocation is zero, which is what makes uptime decisive."""
    if rank < 1 or rank > VALIDATOR_SLOTS:
        return 0.0
    return VALIDATOR_POOL / VALIDATOR_SLOTS


def main():
    p = argparse.ArgumentParser(description="Simulate FLOP genesis-pool allocation by role.")
    p.add_argument("--agent-spend", type=float, default=9_000,
                   help="testnet FLOP an agent spends on inference over the testnet")
    p.add_argument("--gpu-hours", type=float, default=24 * TESTNET_DAYS,
                   help="GPU-hours you serve as a miner (default: one GPU for the whole testnet)")
    p.add_argument("--network-gpu-hours", type=float, default=5_000_000,
                   help="assumed total GPU-hours served by the whole network")
    p.add_argument("--gpu-cost", type=float, default=0.74,
                   help="your GPU cost per hour in USD (RTX 4090 spot is around 0.74)")
    p.add_argument("--validator-rank", type=int, default=500,
                   help="the rank you expect to hold by uptime and accuracy")
    p.add_argument("--json", action="store_true", help="print JSON instead of a table")
    a = p.parse_args()

    agent = agent_reward(a.agent_spend)
    miner = miner_reward(a.gpu_hours, a.network_gpu_hours)
    miner_cost = a.gpu_hours * a.gpu_cost
    validator = validator_reward(a.validator_rank)

    rows = [
        {"role": "agent", "flop": agent, "usd_cost": 0.0,
         "note": f"spend {a.agent_spend:,.0f} faucet FLOP at {AGENT_SPEND_RATIO}:1"},
        {"role": "miner", "flop": miner, "usd_cost": miner_cost,
         "note": f"{a.gpu_hours:,.0f} of {a.network_gpu_hours:,.0f} network GPU-hours"},
        {"role": "validator", "flop": validator, "usd_cost": 0.0,
         "note": (f"rank {a.validator_rank} of {VALIDATOR_SLOTS}"
                  if validator else f"rank {a.validator_rank} is outside the top {VALIDATOR_SLOTS}")},
    ]

    if a.json:
        print(json.dumps({"assumptions": vars(a), "results": rows}, indent=2))
        return

    print(f"FLOP genesis pool {GENESIS_POOL:,} — testnet ~{TESTNET_DAYS} days\n")
    print(f"{'role':<11}{'FLOP':>14}{'USD cost':>11}   note")
    print("-" * 72)
    for r in rows:
        print(f"{r['role']:<11}{r['flop']:>14,.0f}{r['usd_cost']:>11,.0f}   {r['note']}")
    print()
    print("Reading the table: the agent row needs no capital because testnet FLOP comes")
    print("from the faucet, so its cost is the time spent keeping inference running.")
    print("The miner row is the only one with a real USD bill attached, and the validator")
    print("row collapses to zero the moment you fall outside the top 1,000 by uptime.")
    print()
    print("Figures are the project's published targets. No allocation is guaranteed.")


if __name__ == "__main__":
    main()
