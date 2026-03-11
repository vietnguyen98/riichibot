import json
import random

from riichienv import RiichiEnv, calculate_shanten, ActionType
import riichienv.convert as cvt

def tid_to_mpsz(tid):
    return cvt.tid_to_mpsz(tid)

def get_unavailable_tile_ids(obs):
    hand_tile_ids = obs.hand

    # Build the set of tile_ids that are already present somewhere in the game
    # state and thus cannot be drawn.
    unavailable = set(hand_tile_ids)
    
    for player_discards in obs.discards:
        unavailable.update(player_discards)
        for i, meld in enumerate(obs.melds):
            if len(meld) > 0:
                meld = meld[0]
                unavailable.update(meld.tiles)
    unavailable.update(obs.dora_indicators)
    return unavailable

def ukeire_for_discard(hand_tile_ids, unavailable_tile_ids):
    """
    Given:
      - hand_tile_ids: list of physical tile IDs (0–135)
      - unavailable_tile_ids: set of physical tile IDs (0–135) that cannot be drawn
        (e.g. already in hands, discards, melds, dora indicators, etc.)

    Return:
      dict {tile_type_index (0–33): count_of_improving_draws}
    """
    # `hand_tile_ids` is a list of physical tile IDs 0–135, as required
    # by `calculate_shanten`.
    current_shanten = calculate_shanten(hand_tile_ids)
    ukeire = {}

    # Work in tile-type space for the keys: 0–33
    tile_types_in_hand = set(tid // 4 for tid in hand_tile_ids)

    for tile_type_to_discard in tile_types_in_hand:
        # Remove one physical tile of this tile type from the hand
        remaining = hand_tile_ids.copy()
        for i, tid in enumerate(remaining):
            if tid // 4 == tile_type_to_discard:
                del remaining[i]
                break

        improve_count = 0

        # Consider drawing each tile type (0–33). For each type, we:
        # - find all available physical copies (0–4)
        # - run shanten once for a representative copy
        # - if that improves shanten, each available copy counts as 1
        for draw_tile_type in range(34):
            available_copies = [
                draw_tile_type * 4 + copy_idx
                for copy_idx in range(4)
                if (draw_tile_type * 4 + copy_idx) not in unavailable_tile_ids
            ]
            if not available_copies:
                continue

            # Use one representative physical tile for shanten calculation
            repr_tid = available_copies[0]
            new_hand = remaining + [repr_tid]
            new_shanten = calculate_shanten(new_hand)
            if new_shanten < current_shanten:
                improve_count += len(available_copies)

        ukeire[tile_type_to_discard] = improve_count

    return ukeire


class MyAgent:
    def __init__(self, seed: int | None = None):
        # Independent RNG per agent
        self.rng = random.Random(seed)

    def act(self, observation):
        legal_actions = observation.legal_actions()
        if not legal_actions:
            return None

        # Always take high-priority non-discard actions when available.
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

        # Prefer discard actions that maximize ukeire (improve_count)
        discard_actions = [
            a for a in legal_actions if a.action_type == ActionType.Discard
        ]

        if discard_actions and hasattr(observation, "hand"):
            ukeire = ukeire_for_discard(observation.hand, get_unavailable_tile_ids(observation))

            # Group discard actions by tile type (0–33), treating different
            # physical copies of the same tile type as the same choice.
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
                # Randomize between tile types that have the same best score,
                # then randomize between physical copies for that tile type.
                chosen_tile_type = self.rng.choice(best_tile_types)
                chosen_actions = actions_by_tile_type[chosen_tile_type]
                return self.rng.choice(chosen_actions)

        # Fallback: random legal action (including non-discards)
        return self.rng.choice(legal_actions)


def main():
    # Seed here controls only this agent's randomness
    agent = MyAgent(seed=42)
    # Create a game environment
    #   game_mode: 1 = East-only, 2 = East-South (hanchan)
    #   seed: fixed seed for reproducibility (optional)
    env = RiichiEnv(game_mode=2, seed=42)
    # Get initial observations for all players
    observations = env.get_observations()
    print("observations", observations)
    while not env.done():
        # Find the player who needs to act
        for pid, obs in observations.items():
            actions = obs.legal_actions()
            if actions:
                # Your agent decides the action
                action = agent.act(obs)
                if action is None:
                    continue
                # Environment expects a dict of {player_id: action}
                observations = env.step({pid: action})
                break
    # Game finished — check results
    print("Scores:", env.scores())
    print("Ranks:", env.ranks())
    # Full MJAI log is available
    for event in env.mjai_log:
        print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()