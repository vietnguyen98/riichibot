from typing import Iterable, Set

from riichienv import calculate_shanten
import riichienv.convert as cvt


def tid_to_mpsz(tid: int) -> str:
    return cvt.tid_to_mpsz(tid)


def get_unavailable_tile_ids(obs) -> Set[int]:
    hand_tile_ids = obs.hand

    # Build the set of tile_ids that are already present somewhere in the game
    # state and thus cannot be drawn.
    unavailable: Set[int] = set(hand_tile_ids)

    # Discards: list of per-player discard lists
    for player_discards in getattr(obs, "discards", []):
        unavailable.update(player_discards)

    # Melds: list of per-player meld lists; take tiles from each meld object
    for player_melds in getattr(obs, "melds", []):
        for meld in player_melds:
            if hasattr(meld, "tiles"):
                unavailable.update(meld.tiles)

    # Dora indicators
    unavailable.update(getattr(obs, "dora_indicators", []))

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
    current_shanten = calculate_shanten(hand_tile_ids)
    ukeire = {}

    tile_types_in_hand = set(tid // 4 for tid in hand_tile_ids)

    for tile_type_to_discard in tile_types_in_hand:
        remaining = hand_tile_ids.copy()
        for i, tid in enumerate(remaining):
            if tid // 4 == tile_type_to_discard:
                del remaining[i]
                break

        improve_count = 0

        # For each tile type, evaluate shanten once and weight by
        # the number of available physical copies.
        for draw_tile_type in range(34):
            available_copies = [
                draw_tile_type * 4 + copy_idx
                for copy_idx in range(4)
                if (draw_tile_type * 4 + copy_idx) not in unavailable_tile_ids
            ]
            if not available_copies:
                continue

            repr_tid = available_copies[0]
            new_hand = remaining + [repr_tid]
            new_shanten = calculate_shanten(new_hand)
            if new_shanten < current_shanten:
                improve_count += len(available_copies)

        ukeire[tile_type_to_discard] = improve_count

    return ukeire

