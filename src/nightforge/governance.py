from __future__ import annotations


TICKET_TRANSITIONS: dict[str, frozenset[str]] = {
    "state:open": frozenset({"state:claimed"}),
    "state:claimed": frozenset({"state:open", "state:submitted"}),
    "state:submitted": frozenset({"state:verifying"}),
    "state:verifying": frozenset({"state:accepted", "state:rejected"}),
    "state:rejected": frozenset({"state:claimed"}),
    "state:accepted": frozenset(),
}


def transition_ticket_state(current: str, target: str) -> str:
    if target not in TICKET_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid ticket transition: {current} -> {target}")
    return target
