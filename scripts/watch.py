#!/usr/bin/env python3
"""Real-Time News Watcher Daemon.

Continuously monitors foreign & domestic wire feeds (CNBC, BBC, Bloomberg, Interfax),
deduplicates articles, runs two-stage classification (Branch -> Impact), and displays
actionable market calls in the terminal.
"""
import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import Pipeline, DEMO_ITEMS
from src.storage.dedup import DedupStore
from src.alerts.formatter import format_terminal_call, BOLD, CYAN, RESET, GREEN, YELLOW
from src.alerts.telegram_notifier import TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("news_watcher")


def load_env(env_path: Path = PROJECT_ROOT / ".env") -> None:
    """Load key-value pairs from .env into os.environ if not already present."""
    if not env_path.exists():
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


def load_config():
    load_env()
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            raw_content = os.path.expandvars(f.read())
            # Replace unresolved ${VAR} references with empty string
            raw_content = re.sub(r"\$\{[A-Za-z0-9_]+\}", "", raw_content)
            return yaml.safe_load(raw_content) or {}
    except Exception:
        return {}


def main():
    #flagsss
    parser = argparse.ArgumentParser(description="Real-time News Intelligence Watcher")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval in seconds")
    parser.add_argument("--limit", type=int, default=8, help="Max items per source per poll")
    parser.add_argument("--fast", action="store_true", help="Run in fast keyword-heuristic mode (skip transformers)")
    parser.add_argument("--offline", action="store_true", help="Run offline using demo news items")
    parser.add_argument("--no-translate", action="store_true", help="Disable automatic English to Russian translation")
    parser.add_argument("--max-age", type=int, default=None, help="Max article age in minutes to accept (default: 60)")
    parser.add_argument("--clean-start", action="store_true", help="Sync baseline on start: only alert on new news arriving after start")
    parser.add_argument("--actionable-only", action="store_true", help="Only alert on POSITIVE / NEGATIVE calls (filter out NEUTRAL noise)")
    parser.add_argument("--sound", action="store_true", help="Audible terminal beep on incoming market calls")
    parser.add_argument(
        "--branches", "--branch", "--topic", "--topics",
        dest="branches",
        type=str,
        default=None,
        help="Topics to monitor (e.g. 'finance', 'forex', 'crypto', 'tech,finance'). Overrides config.yaml."
    )
    parser.add_argument("--all-branches", action="store_true", help="Listen to all 10 branches (disables topic filtering)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron/testing)")
    args = parser.parse_args()

    config = load_config()
    watcher_cfg = config.get("watcher", {})
    poll_interval = args.interval or watcher_cfg.get("poll_interval_seconds", 30)
    max_age = args.max_age or watcher_cfg.get("max_age_minutes", 60)
    clean_start = args.clean_start or watcher_cfg.get("clean_start", False)
    actionable_only = args.actionable_only or watcher_cfg.get("actionable_only", False)
    sound_alert = args.sound or watcher_cfg.get("sound_alert", False)
    use_transformers = False if args.fast else config.get("pipeline", {}).get("use_transformers", True)
    translate_en = False if args.no_translate else config.get("translation", {}).get("enabled", True)

    if args.all_branches:
        raw_branches = None
    elif args.branches:
        raw_branches = args.branches
    else:
        raw_branches = config.get("target_branches") or watcher_cfg.get("target_branches")

    telegram_cfg = config.get("telegram", {})
    telegram_enabled = watcher_cfg.get("enable_telegram", False)
    bot_token = str(os.environ.get("TELEGRAM_BOT_TOKEN") or telegram_cfg.get("bot_token") or "").strip()
    chat_id = str(os.environ.get("TELEGRAM_CHAT_ID") or telegram_cfg.get("chat_id") or "").strip()
    notifier = TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        enabled=telegram_enabled,
    )

    dedup = DedupStore()
    pipeline = Pipeline(
        use_transformers=use_transformers,
        dedup_store=dedup,
        translate_en=translate_en,
        target_branches=raw_branches,
        filter_unmatched=True,
    )

    if pipeline.target_branches:
        active_names = ", ".join(b.upper() for b in sorted(pipeline.target_branches))
        preset_hint = f" [PRESET: {args.branches.upper()}]" if args.branches and args.branches.lower() in ("forex", "fx", "crypto", "commodities", "macro", "industry") else ""
        topics_display = f"{YELLOW}{active_names}{preset_hint} (Filtered Mode){RESET}"
    else:
        topics_display = f"{GREEN}ALL 10 SECTORS (Unfiltered){RESET}"

    print("\n" + "=" * 65)
    print(f"{BOLD}{CYAN}📡 REAL-TIME NEWS INTELLIGENCE TERMINAL{RESET}")
    print(f"  • Polling Frequency: {GREEN}Every {poll_interval}s{RESET}")
    print(f"  • Freshness Guard:   {GREEN}<= {max_age} min (Stale news dropped){RESET}")
    print(f"  • Engine Mode:       {GREEN}{'TRANSFORMER (BERT/DeBERTa)' if use_transformers else 'FAST KEYWORD FALLBACK'}{RESET}")
    print(f"  • Listening Topics:  {topics_display}")
    print(f"  • Signal Filter:     {GREEN}{'ACTIONABLE ONLY (No Neutral Noise)' if actionable_only else 'ALL SIGNALS (Incl. Neutral)'}{RESET}")
    print(f"  • Clean Start:       {GREEN}{'ACTIVE (Baseline Synced)' if clean_start else 'OFF'}{RESET}")
    print(f"  • Target Sources:    ForexLive, FXStreet, CNBC, Bloomberg, Interfax")
    print(f"  • Deduplication DB:  {dedup.db_path} ({dedup.count()} seen)")
    print(f"  • Telegram Alerts:   {YELLOW}{'ACTIVE' if notifier.enabled else 'DISABLED (Terminal only)'}{RESET}")
    print("=" * 65)
    print(f"\n{BOLD}Watching for live market wire events){RESET}\n")

    if clean_start and not args.offline:
        print(f"[{time.strftime('%H:%M:%S')}] {CYAN}🔄 Syncing initial baseline to avoid stale news...{RESET}", end="", flush=True)
        initial_items = pipeline.fetch_live(limit_per_source=args.limit, max_age_minutes=max_age)
        for it in initial_items:
            dedup.mark_seen(it.id, it.source, it.title)
        print(f"\r[{time.strftime('%H:%M:%S')}] {GREEN}✓ Baseline synced ({len(initial_items)} articles cataloged). Listening for LIVE breaking news...{RESET}\n")

    history = []
    output_file = PROJECT_ROOT / "output.json"

    try:
        while True:
            t0 = time.time()
            if args.offline:
                raw_items = [i for i in DEMO_ITEMS if not dedup.is_seen(i.id)]
                for i in raw_items:
                    dedup.mark_seen(i.id, i.source, i.title)
            else:
                raw_items = pipeline.fetch_live(
                    limit_per_source=args.limit,
                    filter_seen=True,
                    max_age_minutes=max_age,
                )

            if raw_items:
                matched_items = []
                for item in raw_items:
                    classified = pipeline.classify_item(item)
                    if pipeline.target_branches and not classified.branches:
                        continue
                    if actionable_only:
                        primary_dir = classified.impacts[0].direction if classified.impacts else "neutral"
                        primary_mag = classified.impacts[0].magnitude if classified.impacts else "low"
                        if primary_dir == "neutral" and primary_mag == "low":
                            continue
                    matched_items.append(classified)

                if matched_items:
                    if pipeline.target_branches:
                        print(f"[{time.strftime('%H:%M:%S')}] 🔔 Scanned {len(raw_items)} fresh wire(s) -> {len(matched_items)} matched target topics.")
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] 🔔 Found {len(raw_items)} fresh wire release(s). Classifying...")

                    for classified in matched_items:
                        history.append(classified.to_dict())

                        print(format_terminal_call(classified, use_color=True))
                        if sound_alert:
                            print("\a", end="", flush=True)

                        if notifier.enabled:
                            notifier.send_call(classified)

                    try:
                        output_file.write_text(
                            json.dumps(history[-50:], ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                    except Exception as e:
                        logger.warning(f"Could not write output.json: {e}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Check", flush=True)
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Check", flush=True)

            if args.once:
                print("\n[Done] Run once mode complete.")
                break

            elapsed = time.time() - t0
            sleep_time = max(1.0, poll_interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nStopped")


if __name__ == "__main__":
    main()
