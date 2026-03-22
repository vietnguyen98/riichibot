"""
Rule-based agent: same behavior as UkeMaxAgent (ukeire discards, tiebreaks, priorities).

Use this class when extending or swapping logic without changing ukeire_agent.py.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from typing import Any, Optional

from riichienv import ActionType

from utils import (
    get_unavailable_tile_ids,
    representative_discard_for_tile_type,
    tid_to_mpsz,
    tiebreak_best_tile_types,
    ukeire_for_discard,
)


class RuleBasedAgent:
    def __init__(self, seed: int | None = None, *, debug: bool = False):
        self.rng = random.Random(seed)
        self.debug = debug
        """Estimated turn index: max discard pile lengths + 1 (updated each act())."""
        self.turn_number: int = 1
        self._processed_event_count: int = 0

    def _compute_turn_number(self, observation: Any) -> int:
        discards = getattr(observation, "discards", None) or []
        if not discards:
            return 1
        return max(len(d) for d in discards) + 1

    def _process_new_events_for_debug(self, observation: Any) -> None:
        if not self.debug:
            return
        events = getattr(observation, "events", None)
        if not events:
            return
        n = len(events)
        for i in range(self._processed_event_count, n):
            raw = events[i]
            try:
                if isinstance(raw, str):
                    ev = json.loads(raw)
                elif isinstance(raw, dict):
                    ev = raw
                else:
                    continue
            except json.JSONDecodeError:
                continue
            et = ev.get("type")
            if et in ("start_game", "start_kyoku"):
                print(f"[RuleBasedAgent] event: {et} {ev}")
                scores = ev.get("scores")
                if scores is not None:
                    print(f"[RuleBasedAgent] scores: {scores}")
        self._processed_event_count = n

    def act(self, observation: Any) -> Optional[Any]:
        self._process_new_events_for_debug(observation)
        self.turn_number = self._compute_turn_number(observation)
        if self.debug:
            print(f"[RuleBasedAgent] turn_number={self.turn_number}")

        legal_actions = observation.legal_actions()
        if not legal_actions:
            return None

        chosen: Any = None

        # High-priority non-discard actions
        priority_order = [
            ActionType.Ron,
            ActionType.Tsumo,
            ActionType.Riichi,
            ActionType.Pass,
        ]

        for atype in priority_order:
            candidates = [a for a in legal_actions if a.action_type == atype]
            if candidates:
                chosen = self.rng.choice(candidates)
                break

        if chosen is None:
            # Ukeire-based discard selection
            discard_actions = [
                a for a in legal_actions if a.action_type == ActionType.Discard
            ]

            if discard_actions and hasattr(observation, "hand"):
                player_id = getattr(observation, "player_id", None)
                if player_id is None and discard_actions:
                    player_id = getattr(discard_actions[0], "actor", None)

                ukeire = ukeire_for_discard(
                    observation.hand,
                    get_unavailable_tile_ids(observation),
                )

                groups_by_tile_type = defaultdict(list)
                for action in discard_actions:
                    tile_id = action.tile
                    if tile_id is None:
                        continue
                    tile_type = tile_id // 4
                    groups_by_tile_type[tile_type].append(action)

                actions_by_tile_type = {
                    tile_type: representative_discard_for_tile_type(
                        acts, tile_type, self.rng
                    )
                    for tile_type, acts in groups_by_tile_type.items()
                }

                best_tile_types = []
                best_score = None

                for tile_type, _rep_action in actions_by_tile_type.items():
                    score = ukeire.get(tile_type, 0)
                    if best_score is None or score > best_score:
                        best_score = score
                        best_tile_types = [tile_type]
                    elif score == best_score:
                        best_tile_types.append(tile_type)

                if best_tile_types:
                    chosen_tile_type = tiebreak_best_tile_types(
                        best_tile_types,
                        actions_by_tile_type,
                        observation,
                        self.rng,
                        player_id=player_id,
                    )
                    chosen = actions_by_tile_type[chosen_tile_type]

        if chosen is None:
            chosen = self.rng.choice(legal_actions)

        if self.debug and chosen is not None:
            if getattr(chosen, "action_type", None) == ActionType.Discard:
                tid = getattr(chosen, "tile", None)
                if tid is not None:
                    try:
                        mpsz = tid_to_mpsz(tid)
                    except Exception:
                        mpsz = "?"
                    print(
                        f"[RuleBasedAgent] discard: tile_id={tid} ({mpsz}) "
                        f"actor={getattr(chosen, 'actor', None)}"
                    )

        return chosen
