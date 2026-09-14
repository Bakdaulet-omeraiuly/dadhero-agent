"""
Terminal demo / presentation-day fallback for DadHero.

  python cli_demo.py            -> interactive chat loop
  python cli_demo.py --scripted -> runs a fixed demo conversation unattended
                                    (recorded backup for the live demo)
"""

from __future__ import annotations

import sys

from dadhero.agent import build_agent

SCRIPTED_TURNS = [
    "My husband Nurlan has short black hair, always wears black-framed glasses "
    "and a red hoodie, and a big warm laugh. I want a 5-page comic where he's a "
    "brave astronaut who rescues a lost baby star, for our 5-year-old daughter Aisha.",
    "Love it! Page 2 feels a little sad -- can you make the baby star look curious "
    "instead of scared? Everything else is perfect.",
    "Save this story please!",
]


def run_turn(agent, text: str) -> None:
    print(f"\n\033[1mPARENT:\033[0m {text}\n")
    print("\033[1mDADHERO:\033[0m")
    result = agent(text)
    print(str(result).strip())

    tool_calls = [
        block["toolUse"]["name"]
        for msg in agent.messages
        for block in msg.get("content", [])
        if isinstance(block, dict) and "toolUse" in block
    ]
    if tool_calls:
        print(f"\n\033[2m[tool calls this turn: {' -> '.join(tool_calls[-10:])}]\033[0m")


def main() -> None:
    agent = build_agent()

    if "--scripted" in sys.argv:
        for turn in SCRIPTED_TURNS:
            run_turn(agent, turn)
        return

    print("DadHero -- tell me your idea for a family comic.")
    print("(Ctrl+C or 'quit' to exit)\n")
    while True:
        try:
            text = input("\033[1mPARENT:\033[0m ")
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if text.strip().lower() in {"quit", "exit"}:
            break
        if not text.strip():
            continue
        print("\n\033[1mDADHERO:\033[0m")
        print(str(agent(text)).strip())
        print()


if __name__ == "__main__":
    main()
