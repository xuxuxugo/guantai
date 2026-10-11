PULSE_KINDS = ("swing_up", "volume", "breakout", "swing_down")


def choose_pulse(tick_index: int, codes: list[str], held: set[str]) -> tuple[str, str] | None:
    """Pick a demo shock. Tick 1 and every 5th scan fire; codes already holding a shock are skipped."""
    if not codes or (tick_index != 1 and tick_index % 5 != 0):
        return None
    available = [code for code in codes if code not in held]
    if not available:
        return None
    step = tick_index // 5
    return available[step % len(available)], PULSE_KINDS[step % len(PULSE_KINDS)]
