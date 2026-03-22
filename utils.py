from typing import Any, Optional, Set

from riichienv import ActionType, calculate_shanten
import riichienv.convert as cvt

from chart_data import chart2_row_as_dict


def _obs_attr(obs: Any, name: str, default=None):
    """Read attribute from Observation object or dict."""
    if hasattr(obs, name):
        return getattr(obs, name)
    if isinstance(obs, dict) and name in obs:
        return obs[name]
    return default


def tid_to_mpsz(tid: int) -> str:
    return cvt.tid_to_mpsz(tid)


def get_unavailable_tile_ids(obs) -> Set[int]:
    # `obs.hand` is only the observing (current) player's hand — not opponents'
    # concealed hands. Unaccounted tiles may still be in other players' hands or
    # the wall.
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


# Red fives: tile_types 4 (5m), 13 (5p), 22 (5s). Physical id tile_type * 4 is the
# plain-five copy; aka (red) fives use copy indices 1–3 (tid % 4 != 0).
RED_FIVE_TILE_TYPES = frozenset({4, 13, 22})


def representative_discard_for_tile_type(actions, tile_type, rng):
    """
    Pick one legal discard action to stand in for this tile_type.

    For red-five tile types (4, 13, 22), prefer an action whose tile_id is
    not a multiple of 4 (aka copy). Otherwise pick randomly among equivalent
    physical copies.
    """
    if not actions:
        return None
    if tile_type not in RED_FIVE_TILE_TYPES:
        return rng.choice(actions)
    preferred = [
        a for a in actions
        if getattr(a, "tile", None) is not None and a.tile % 4 != 0
    ]
    if preferred:
        return rng.choice(preferred)
    return rng.choice(actions)


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


def dora_tile_type_from_indicator(indicator_tile_type: int) -> int:
    """
    Tile type of the winning tile indicated by a dora marker (next in sequence).
    Man: 1→2→…→9→1; Pin/Sou same; winds E→S→W→N→E; dragons W→G→R→W (1z–7z order).
    """
    t = indicator_tile_type
    if 0 <= t <= 8:
        return (t + 1) % 9
    if 9 <= t <= 17:
        return ((t - 9 + 1) % 9) + 9
    if 18 <= t <= 26:
        return ((t - 18 + 1) % 9) + 18
    if 27 <= t <= 30:
        return 27 + (t - 27 + 1) % 4
    if 31 <= t <= 33:
        return 31 + (t - 31 + 1) % 3
    return t


def dora_tile_types_from_observation(obs: Any) -> Set[int]:
    """All tile types (0–33) that count as dora from `dora_indicators` tile_ids."""
    out: Set[int] = set()
    for tid in _obs_attr(obs, "dora_indicators", []) or []:
        if tid is None:
            continue
        ind_tt = tid // 4
        out.add(dora_tile_type_from_indicator(ind_tt))
    return out


def round_wind_tile_type(round_wind: Any) -> int:
    """Round wind as honor tile type 27–30 (E,S,W,N)."""
    rw = int(round_wind)
    if 27 <= rw <= 30:
        return rw
    return 27 + (rw % 4)


def seat_wind_tile_type(oya: int, player_id: int) -> int:
    """
    Seat wind for `player_id` given dealer `oya` (0–3).
    oya → East (27), oya+1 → South (28), etc.
    """
    offset = (int(player_id) - int(oya)) % 4
    return 27 + offset


def yakuhai_tile_types(obs: Any, player_id: int) -> Set[int]:
    """Dragons + round wind + seat wind tile types."""
    oya = int(_obs_attr(obs, "oya", 0))
    round_wind = _obs_attr(obs, "round_wind", 0)
    rw_tt = round_wind_tile_type(round_wind)
    sw_tt = seat_wind_tile_type(oya, player_id)
    return {31, 32, 33, rw_tt, sw_tt}


# Tiebreak class for equal ukeire (lower = discard first among ties).
# 1: guest winds   2: 1/9   3: yakuhai   4: 2/8   5: middle   6: value
DISCARD_TIEBREAK_GUEST_WIND = 1
DISCARD_TIEBREAK_19 = 2
DISCARD_TIEBREAK_YAKUHAI = 3
DISCARD_TIEBREAK_28 = 4
DISCARD_TIEBREAK_MIDDLE = 5
DISCARD_TIEBREAK_VALUE = 6


def discard_tiebreak_class(
    tile_type: int,
    rep_tile_id: Optional[int],
    obs: Any,
    player_id: int,
) -> int:
    """
    Classify a discard candidate (tile_type + representative physical tile id)
    for tie-breaking among equal ukeire scores.
    """
    dora_types = dora_tile_types_from_observation(obs)
    yakuhai = yakuhai_tile_types(obs, player_id)

    # 6 — value: dora tile types, or red five (aka copy)
    if tile_type in dora_types:
        return DISCARD_TIEBREAK_VALUE
    if (
        tile_type in RED_FIVE_TILE_TYPES
        and rep_tile_id is not None
        and rep_tile_id % 4 != 0
    ):
        return DISCARD_TIEBREAK_VALUE

    # 1 — guest winds (round/seat winds that are not yakuhai)
    if 27 <= tile_type <= 30 and tile_type not in yakuhai:
        return DISCARD_TIEBREAK_GUEST_WIND

    # 3 — yakuhai (dragons + round wind + seat wind)
    if tile_type in yakuhai:
        return DISCARD_TIEBREAK_YAKUHAI

    # Number tiles: rank 0–8 within man / pin / sou
    if 0 <= tile_type <= 8:
        rank = tile_type
    elif 9 <= tile_type <= 17:
        rank = tile_type - 9
    elif 18 <= tile_type <= 26:
        rank = tile_type - 18
    else:
        return DISCARD_TIEBREAK_MIDDLE

    if rank in (0, 8):
        return DISCARD_TIEBREAK_19
    if rank in (1, 7):
        return DISCARD_TIEBREAK_28
    return DISCARD_TIEBREAK_MIDDLE


def tiebreak_best_tile_types(
    best_tile_types: list,
    actions_by_tile_type: dict,
    observation: Any,
    rng,
    player_id: Optional[int] = None,
):
    """
    Among tile types with equal best ukeire, prefer lower tiebreak class
    (1 = guest wind first, 2 = 1/9, 3 = yakuhai, 4 = 2/8, 5 = middle,
    6 = value last). Random if still tied.
    """
    if not best_tile_types:
        return None
    if len(best_tile_types) == 1:
        return best_tile_types[0]

    if player_id is None:
        player_id = _obs_attr(observation, "player_id", None)
    if player_id is None:
        player_id = 0

    def rep_tid(tt):
        act = actions_by_tile_type.get(tt)
        return getattr(act, "tile", None) if act is not None else None

    classes = [
        (discard_tiebreak_class(tt, rep_tid(tt), observation, player_id), tt)
        for tt in best_tile_types
    ]
    best_c = min(c for c, _ in classes)
    tied = [tt for c, tt in classes if c == best_c]
    return rng.choice(tied)


# --- Deal-in rate (per discard tile type, 0–100 scale) ---------------------------------

def _is_honor_tile_type(tile_type: int) -> bool:
    """Honor tiles: East–North and dragons (tile types 27–33)."""
    return 27 <= int(tile_type) <= 33


def _count_tile_type_in_unavailable(obs: Any, tile_type: int) -> int:
    """
    Count how many physical tiles of `tile_type` appear in `get_unavailable_tile_ids`
    (our hand, discards, melds, dora indicators), reusing the same aggregation logic.

    Does not include tiles in other players' concealed hands — the observation
    only lists our own hand, not theirs.
    """
    tt = int(tile_type)
    unavailable = get_unavailable_tile_ids(obs)
    return sum(
        1
        for tid in unavailable
        if tid is not None and int(tid) // 4 == tt
    )


def calculate_honor_dealinrate(
    observation: Any,
    player_id: int,
    tile_type: int,
    turn_passed: int = 1,
) -> float:
    """
    Estimate deal-in risk (0–100) when discarding this honor tile type.

    - Classifies the tile as yakuhai vs guest wind for the given `player_id`
      (round wind, seat wind, dragons).
    - Counts copies of this tile type in `get_unavailable_tile_ids(observation)`
      (our hand + public info only — not opponents' concealed hands):
      0 = live, 1 / 2 → Chart 2 ``_1_visible`` / ``_2_visible``; 3+ → deal-in 0.
    - Looks up `chart_data.CHART2` row for `turn_passed` (clamped 1–19).
    """
    if not _is_honor_tile_type(tile_type):
        return 0.0

    tt = int(tile_type)
    is_yakuhai = tt in yakuhai_tile_types(observation, int(player_id))
    in_play_count = _count_tile_type_in_unavailable(observation, tt)

    if in_play_count >= 3:
        return 0.0

    # in_play_count is 0, 1, or 2 → live / 1_visible / 2_visible
    turn = max(1, min(19, int(turn_passed)))
    row = chart2_row_as_dict(turn)
    if row is None:
        return 0.0

    if is_yakuhai:
        col = ("yakuhai_live", "yakuhai_1_visible", "yakuhai_2_visible")[
            in_play_count
        ]
    else:
        col = ("guest_wind_live", "guest_wind_1_visible", "guest_wind_2_visible")[
            in_play_count
        ]

    return float(row[col])


def calculate_suji_dealinrate(player_id: int, tile_type: int) -> float:
    """
    Estimate deal-in risk (0–100) when discarding this suited tile type.

    Skeleton: replace with suji / chart_data-based logic.
    """
    _ = player_id, tile_type
    return 0.0


def calculate_dealinrate(
    observation: Any,
    player_id: int,
    discard_actions,
    turn_passed: int = 1,
) -> dict[int, float]:
    """
    For each tile type present in legal discard actions, return an estimated
    deal-in rate on a 0–100 scale.

    Honor tile types (27–33) use `calculate_honor_dealinrate`; all others use
    `calculate_suji_dealinrate`.

    `turn_passed` selects the Chart 2 row (1–19) for honor deal-in rates.
    """
    tile_types: set[int] = set()
    for action in discard_actions:
        at = getattr(action, "action_type", None)
        if at is not None and at != ActionType.Discard:
            continue
        tile_id = getattr(action, "tile", None)
        if tile_id is None:
            continue
        tile_types.add(int(tile_id) // 4)

    out: dict[int, float] = {}
    for tile_type in sorted(tile_types):
        if _is_honor_tile_type(tile_type):
            out[tile_type] = float(
                calculate_honor_dealinrate(
                    observation,
                    player_id,
                    tile_type,
                    turn_passed=turn_passed,
                )
            )
        else:
            out[tile_type] = float(calculate_suji_dealinrate(player_id, tile_type))

    # Clamp to [0, 100] for safety once helpers are implemented
    for k in list(out.keys()):
        out[k] = max(0.0, min(100.0, out[k]))

    return out

