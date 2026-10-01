"""Terminal formatter for real-time news intelligence alerts (calls)."""
from datetime import datetime
from src.models import ClassifiedNews

# ANSI Colors
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"
WHITE = "\033[37m"


def format_terminal_call(news: ClassifiedNews, use_color: bool = True) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine primary impact direction
    if news.impacts:
        primary_impact = news.impacts[0]
        direction = primary_impact.direction.upper()
        score = primary_impact.score
        magnitude = primary_impact.magnitude.upper()
        explanation = primary_impact.explanation
    else:
        direction = "NEUTRAL"
        score = 0.0
        magnitude = "LOW"
        explanation = "no impact calculated"

    if direction == "POSITIVE":
        dir_color = GREEN
        emoji = "🟢 [CALL: POSITIVE / BULLISH]"
    elif direction == "NEGATIVE":
        dir_color = RED
        emoji = "🔴 [CALL: NEGATIVE / BEARISH]"
    else:
        dir_color = YELLOW
        emoji = "⚪ [CALL: NEUTRAL / MIXED]"

    branches_str = ", ".join(
        f"{b.branch.upper()} ({int(b.confidence * 100)}%)" for b in news.branches
    ) if news.branches else "GENERAL / UNCLASSIFIED"

    pub_str = news.item.published_at or now_str
    age = news.item.age_minutes
    if age < 5:
        freshness_badge = f"⚡ JUST IN ({int(age)}m ago)"
        badge_color = RED
    elif age < 30:
        freshness_badge = f"⚡ FRESH ({int(age)}m ago)"
        badge_color = YELLOW
    elif age < 60:
        freshness_badge = f"🕒 ({int(age)}m ago)"
        badge_color = GRAY
    else:
        hours = int(age // 60)
        mins = int(age % 60)
        freshness_badge = f"🕒 ({hours}h {mins}m ago)"
        badge_color = GRAY

    is_flash = any(w in news.item.title.upper() for w in ["BREAKING", "FLASH", "ALERT", "JUST IN", "URGENT"])
    flash_tag = "🚨 " if is_flash else ""

    if not use_color:
        lines = [
            "=" * 65,
            f"{flash_tag}{emoji} | {now_str} | Source: {news.item.source.upper()}",
            f"🕒 Published: {pub_str} [{freshness_badge}]",
            f"📌 Title:     {news.item.title}",
        ]
        if news.item.lang == "en" and news.item.title_ru:
            lines.append(f"🇷🇺 Перевод:   {news.item.title_ru}")
        lines.extend([
            f"🏢 Branch:    {branches_str}",
            f"📊 Impact:    {direction} (score: {score:+.2f}, magnitude: {magnitude})",
            f"💡 Reason:    {explanation}",
            f"🔗 Link:      {news.item.url or 'N/A'}",
            "=" * 65,
        ])
        return "\n".join(lines)

    lines = [
        f"{GRAY}{'=' * 65}{RESET}",
        f"{flash_tag}{BOLD}{dir_color}{emoji}{RESET} {GRAY}| {now_str} | Source: {CYAN}{news.item.source.upper()}{RESET}",
        f"{BOLD}🕒 Published:{RESET} {GRAY}{pub_str}{RESET} {BOLD}{badge_color}[{freshness_badge}]{RESET}",
        f"{BOLD}📌 Title:{RESET}     {news.item.title}",
    ]
    if news.item.lang == "en" and news.item.title_ru:
        lines.append(f"{BOLD}🇷🇺 Перевод:{RESET}   {CYAN}{news.item.title_ru}{RESET}")
    lines.extend([
        f"{BOLD}🏢 Branch:{RESET}    {CYAN}{branches_str}{RESET}",
        f"{BOLD}📊 Impact:{RESET}    {dir_color}{BOLD}{direction}{RESET} (score: {BOLD}{score:+.2f}{RESET}, mag: {YELLOW}{magnitude}{RESET})",
        f"{BOLD}💡 Reason:{RESET}    {GRAY}{explanation}{RESET}",
        f"{BOLD}🔗 Link:{RESET}      {GRAY}{news.item.url or 'N/A'}{RESET}",
        f"{GRAY}{'=' * 65}{RESET}",
    ])
    return "\n".join(lines)
