from src.domain import fsm


def test_next_state_advances():
    assert fsm.next_state(1) == 2
    assert fsm.next_state(6) == 99


def test_should_finalize_on_invalid():
    assert fsm.should_finalize_on_invalid(3) is True
    assert fsm.should_finalize_on_invalid(2) is False


def test_is_active_state():
    assert fsm.is_active_state(1) is True
    assert fsm.is_active_state(6) is True
    assert fsm.is_active_state(99) is False
