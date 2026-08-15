# Usage: python scripts/run_agent.py "<goal>"
#
# Runs the agent once on a goal. It reasons about whether the task needs a
# paid resource and, if so, pays for it via x402 in real USDC on Base,
# subject to the spending caps in .env. Every step is written to the audit
# log - view it with: uvicorn agentic_payments.ui.app:app --reload

import sys

from dotenv import load_dotenv

from agentic_payments.net import force_ipv4

force_ipv4()
load_dotenv()

from agentic_payments.agent.loop import run_agent  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/run_agent.py "<goal>"')
        sys.exit(1)

    goal = sys.argv[1]
    print(f"Goal: {goal}\n")
    answer = run_agent(goal)
    print("\n--- Final answer ---")
    print(answer)


if __name__ == "__main__":
    main()
