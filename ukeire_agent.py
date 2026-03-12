import random

from riichienv import ActionType

from utils import ukeire_for_discard, get_unavailable_tile_ids


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
            ukeire = ukeire_for_discard(
                observation.hand,
                get_unavailable_tile_ids(observation),
            )

            actions_by_tile_type = {}
            for action in discard_actions:
                tile_id = action.tile
                if tile_id is None:
                    continue
                tile_type = tile_id // 4
                actions_by_tile_type.setdefault(tile_type, []).append(action)

            best_tile_types = []
            best_score = None

            for tile_type, actions_for_type in actions_by_tile_type.items():
                score = ukeire.get(tile_type, 0)
                if best_score is None or score > best_score:
                    best_score = score
                    best_tile_types = [tile_type]
                elif score == best_score:
                    best_tile_types.append(tile_type)

            if best_tile_types:
                chosen_tile_type = self.rng.choice(best_tile_types)
                chosen_actions = actions_by_tile_type[chosen_tile_type]
                return self.rng.choice(chosen_actions)

        return self.rng.choice(legal_actions)

