"""Renders one run BLOCK for data/autopilot/status.txt.

status.txt is a REVERSE-CHRONOLOGICAL logbook: each run prepends a full,
self-contained snapshot (balance, positions, and the moves + reasons for that
run) to the TOP of the file. The topmost block is therefore always the current
state ("where we are, everything we have now"); scroll down for the full history
of what happened and why. See cmd_execute() in autopilot.py for the prepend.
"""

_SEP = "─" * 60


def _money(x):
    return f"${abs(x):,.2f}"


def _signed_money(x):
    return f"{'+' if x >= 0 else '-'}{_money(x)}"


def _arrow(x):
    return "▲" if x >= 0 else "▼"  # ▲ / ▼


def _short_time(s):
    """Pull the HH:MM token out of a '2026-07-06 16:00 ART' style string."""
    for tok in str(s).split():
        if ":" in tok:
            return tok
    return str(s)


def render_status(marked, brain_label, updated_str, next_run_str, last_moves, halted=False):
    """Render a single run block (newest-on-top logbook entry)."""
    lines = []
    header = f"═══ {updated_str}  ·  {brain_label}  ·  next {_short_time(next_run_str)}"
    if halted:
        header += "  ·  HALTED ≥25% (no new buys)"
    header += " ═══"
    lines.append(header)
    lines.append(
        f"BALANCE   {_money(marked['total_value'])}    "
        f"{_arrow(marked['pnl_abs'])} {_signed_money(marked['pnl_abs'])}  "
        f"({(marked['pnl_pct'] or 0.0):+.2f}%)   since $5,000 start"
    )
    lines.append(f"CASH      {_money(marked['cash'])}    INVESTED {_money(marked['invested'])}")
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
    lines.append("MOVES THIS RUN")
    if last_moves:
        lines.extend(f"  {m}" for m in last_moves)
    else:
        lines.append("  (none)")
    lines.append(_SEP)
    lines.append("")  # blank line between stacked blocks
    return "\n".join(lines) + "\n"
