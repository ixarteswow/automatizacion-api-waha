MIN_STATE = 1
MAX_STATE = 6
FINAL_STATE = 99
ERROR_STATE = -1
MAX_ATTEMPTS = 3


def is_active_state(state: int) -> bool:
    return MIN_STATE <= state <= MAX_STATE


def is_terminal_state(state: int) -> bool:
    return state in (FINAL_STATE, ERROR_STATE)


def next_state(state: int) -> int:
    if state < MAX_STATE:
        return state + 1
    return FINAL_STATE


def should_finalize_on_invalid(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS
