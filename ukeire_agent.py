import random
from collections import defaultdict

from riichienv import ActionType

from utils import (
    get_unavailable_tile_ids,
    representative_discard_for_tile_type,
    tiebreak_best_tile_types,
    ukeire_for_discard,
)


class UkeMaxAgent:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def act(self, observation):
        legal_actions = observation.legal_actions()
        if not legal_actions:
            return None

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
                return self.rng.choice(candidates)

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

            # Group discards by tile_type, then one representative action per type
            # (red fives: prefer aka tile_id % 4 != 0).
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
                return actions_by_tile_type[chosen_tile_type]

        return self.rng.choice(legal_actions)

