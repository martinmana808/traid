"""Renders data/autopilot/status.txt — the file the user opens to check in."""


def _money(x):
    return f"${abs(x):,.2f}"


def _signed_money(x):
    return f"{'+' if x >= 0 else '-'}{_money(x)}"


def _arrow(x):
    return "▲" if x >= 0 else "▼"  # ▲ / ▼


def render_status(marked, brain_label, updated_str, next_run_str, last_moves, halted=False):
    lines = []
    header = f"TRaid Autopilot — paper       brain today: {brain_label}"
    if halted:
        header += "   [HALTED: down ≥ 25%, no new buys]"
    lines.append(header)
    lines.append(f"Updated: {updated_str}   (next run: {next_run_str})")
    lines.append("")
    lines.append(
        f"BALANCE   {_money(marked['total_value'])}    "
        f"{_arrow(marked['pnl_abs'])} {_signed_money(marked['pnl_abs'])}  "
        f"({(marked['pnl_pct'] or 0.0):+.2f}%)   since $5,000 start"
    )
    lines.append(f"CASH      {_money(marked['cash'])}    INVESTED {_money(marked['invested'])}")
    lines.append("")
    lines.append("POSITIONS")
    if marked["positions"]:
        for p in marked["positions"]:
            lines.append(
                f"  {p['ticker']:<5} {p['shares']:>4} sh  @ {_money(p['avg_cost'])} avg   "
                f"now {_money(p['price'])}   {_arrow(p['pnl_pct'])} {p['pnl_pct']:+.1f}%   "
                f"{_money(p['value'])}"
            )
    else:
        lines.append("  (all cash — no open positions)")
    lines.append("")
    lines.append("LAST MOVES")
    if last_moves:
        lines.extend(f"  {m}" for m in last_moves)
    else:
        lines.append("  (none yet)")
    return "\n".join(lines) + "\n"
