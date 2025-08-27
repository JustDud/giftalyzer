# manager.py
import os, asyncio, argparse, importlib
from datetime import datetime, timezone


def ts(msg: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")


def resolve(entry: str):
    # "pkg.mod:function"
    mod_name, func_name = entry.split(":")
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name)
    return fn


def run_bot():
    from main import main as bot_main
    if asyncio.iscoroutinefunction(bot_main):
        asyncio.run(bot_main())
    else:
        bot_main()


async def run_updater():
    # Default to your updater
    entry = os.getenv("UPDATER_ENTRY", "scripts.db_updater:update_db")
    fn = resolve(entry)
    ts(f"Starting updater {entry} …")
    if asyncio.iscoroutinefunction(fn):
        await fn()
    else:
        await asyncio.to_thread(fn)


async def check_subscriptions_once():
    """
    One-shot daily cleanup; we call a one-shot function from scripts/subscription_checker.py
    """
    ts("Running daily subscription check…")
    # expose run_once() in scripts/subscription_checker.py (see step 2)
    from scripts.subscription_checker import run_once
    if asyncio.iscoroutinefunction(run_once):
        await run_once()
    else:
        await asyncio.to_thread(run_once)
    ts("Check complete.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run-bot")
    sub.add_parser("update-forever")
    sub.add_parser("check-subscriptions")
    args = p.parse_args()

    if args.cmd == "run-bot":
        run_bot()
    elif args.cmd == "update-forever":
        asyncio.run(run_updater())
    elif args.cmd == "check-subscriptions":
        asyncio.run(check_subscriptions_once())


if __name__ == "__main__":
    main()