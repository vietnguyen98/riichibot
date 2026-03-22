import json
import re
from typing import Any, Optional, Sequence, Set, Tuple

from riichienv import ActionType, HandEvaluator, calculate_shanten
from riichienv.hand import Conditions
import riichienv.convert as cvt

from chart_data import chart1_row_as_dict, chart2_row_as_dict

_MPSZ_PAI_RE = re.compile(r"^(\d+)([mps])r?$", re.IGNORECASE)


def _obs_attr(obs: Any, name: str, default=None):
    """Read attribute from Observation object or dict."""
    if hasattr(obs, name):
        return getattr(obs, name)
    if isinstance(obs, dict) and name in obs:
        return obs[name]
    return default


def tid_to_mpsz(tid: int) -> str:
    return cvt.tid_to_mpsz(tid)


def _mjai_parse_event(raw: Any) -> Optional[dict]:
    """Parse one MJAI log entry (JSON string or dict)."""
    try:
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
    except json.JSONDecodeError:
        pass
    return None


def last_ron_dahai_from_mjai_events(
    mjai_events: Optional[Sequence[Any]],
    *,
    observing_player_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Walk **chronological** MJAI ``events`` and return ``(actor, pai)`` for the
    most recent ``dahai`` that can be a ron target: ``pai`` is not ``'?'``, and
    if ``observing_player_id`` is set, ``actor`` must differ (ron is off another
    seat's discard).

    Returns ``(None, None)`` if none found.
    """
    if not mjai_events:
        return None, None
    last_actor: Optional[int] = None
    last_pai: Optional[str] = None
    pid = observing_player_id
    for raw in mjai_events:
        ev = _mjai_parse_event(raw)
        if not ev or ev.get("type") != "dahai":
            continue
        actor = ev.get("actor")
        pai = ev.get("pai")
        if actor is None or pai is None:
            continue
        spai = str(pai).strip()
        if spai in ("?", ""):
            continue
        aid = int(actor)
        if pid is not None and aid == int(pid):
            continue
        last_actor, last_pai = aid, spai
    return last_actor, last_pai


def check_for_4th_confirm(
    observation: Any,
    is_hanchan: bool = True,
    *,
    mjai_events: Optional[Sequence[Any]] = None,
) -> bool:
    """
    If ``True``, callers (e.g. ``RuleBasedAgent.act``) should not take Ron/Tsumo
    and should pick another legal action instead (e.g. pending 4th confirm).
    If ``False``, wins may be declared when offered.

    ``is_hanchan`` reflects East–South (hanchan) vs East-only (tonpu); use when
    interpreting ``WinResult`` / conditions (not used in the skeleton yet).

    ``mjai_events``: MJAI-style log (same as ``RuleBasedAgent`` uses). For a
    **13-tile** hand (ron), the winning tile is taken from the latest qualifying
    ``dahai`` via :func:`last_ron_dahai_from_mjai_events`, excluding self-discard
    using ``observation.player_id``.

    Skeleton: builds ``HandEvaluator``, runs ``calc``, always returns ``False``.
    """
    hand = _obs_attr(observation, "hand")
    if not hand:
        return False

    tids = [int(t) for t in list(hand)]

    if len(tids) < 13:
        return False

    ron_from_seat: Optional[int] = None

    # 14 tiles: treat last as drawn winning tile (tsumo-style); 13: need ron tile on obs.
    if len(tids) >= 14:
        body_tids = tids[:-1]
        win_tile = tids[-1]
    else:
        body_tids = tids
        win_tile = _obs_attr(observation, "ron_tile")
        if win_tile is None:
            win_tile = _obs_attr(observation, "win_tile")
        if win_tile is None:
            win_tile = _obs_attr(observation, "agari_tile")
        if win_tile is None:
            pid = _obs_attr(observation, "player_id")
            observing_seat = int(pid) if pid is not None else None
            ron_from_seat, ron_pai = last_ron_dahai_from_mjai_events(
                mjai_events,
                observing_player_id=observing_seat,
            )
            if ron_pai is None:
                return False
            win_tile = int(cvt.mpsz_to_tid(ron_pai))
        else:
            win_tile = int(win_tile)

    hand_text = "".join(cvt.tid_to_mpsz(t) for t in body_tids)
    he = HandEvaluator.hand_from_text(hand_text)

    dora_indicators = list(_obs_attr(observation, "dora_indicators") or [])
    round_wind = _obs_attr(observation, "round_wind")
    player_wind = (int(observation.player_id) - int(observation.oya)) % 4
    riichi_sticks = _obs_attr(observation, "riichi_sticks")
    honba = _obs_attr(observation, "honba")
    ura: list[int] = []

    tsumo = ...
    riichi = ...
    # double_riichi = False
    # ippatsu = False
    # chankan = False
    # haitei = False
    # houtei = False
    # rinshan = False
    # tsumo_first_turn = False
    todo: riichi from observation riichi_declared
    tsumo from action types (Ron, Tsumo)
    ura indicators - calculate based on which ones maximize my potential score, counting dora_indicators
    # let's set the rest to false for now and try and just test if the function works w/out crashing agent

    winres = he.calc(
        int(win_tile),
        dora_indicators=dora_indicators,
        ura_indicators=...,
        conditions=Conditions(tsumo=tsumo, riichi=riichi, double_riichi=double_riichi, ippatsu=ippatsu,
        chankan=chankan, haitei=haitei, houtei=houtei, rinshan=rinshan, tsumo_first_turn=tsumo_first_turn, 
        player_wind=player_wind, round_wind=round_wind, riichi_sticks=riichi_sticks, honba=honba),
    )

    print("condition params: ", "win_tile: ", win_tile, "dora_indicators: ", dora_indicators, 
        "ura_indicators: ", ura, "tsumo: ", tsumo, "riichi: ", riichi, 
        "double_riichi: ", double_riichi, "ippatsu: ", ippatsu, 
        "chankan: ", chankan, "haitei: ", haitei, "houtei: ", houtei, 
        "rinshan: ", rinshan, "tsumo_first_turn: ", tsumo_first_turn, 
        "player_wind: ", player_wind, "round_wind: ", round_wind, 
        "riichi_sticks: ", riichi_sticks, "honba: ", honba)

    _ = (winres, is_hanchan, ron_from_seat)
    print("winres: ", winres.ron_agari)
    print("winres: ", winres.tsumo_agari_oya)
    print("winres: ", winres.tsumo_agari_ko)
    print("is_hanchan: ", is_hanchan)
    print("ron_from_seat: ", ron_from_seat)
    return False


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
      (our hand + public info only — not opponents' concealed hands). Chart column:

      - **0 or 1** visible → ``*_live``
      - **2** visible → ``*_1_visible``
      - **3** visible → ``*_2_visible``
      - **4+** visible → deal-in **0** (all copies accounted for).
    - Looks up `chart_data.CHART2` row for `turn_passed` (clamped 1–19).
    """
    if not _is_honor_tile_type(tile_type):
        return 0.0

    tt = int(tile_type)
    is_yakuhai = tt in yakuhai_tile_types(observation, int(player_id))
    in_play_count = _count_tile_type_in_unavailable(observation, tt)

    if in_play_count >= 4:
        return 0.0

    # 0–1 → live (0), 2 → 1_visible (1), 3 → 2_visible (2)
    if in_play_count <= 1:
        chart_idx = 0
    elif in_play_count == 2:
        chart_idx = 1
    else:
        chart_idx = 2

    turn = max(1, min(19, int(turn_passed)))
    row = chart2_row_as_dict(turn)
    if row is None:
        return 0.0

    if is_yakuhai:
        col = ("yakuhai_live", "yakuhai_1_visible", "yakuhai_2_visible")[
            chart_idx
        ]
    else:
        col = ("guest_wind_live", "guest_wind_1_visible", "guest_wind_2_visible")[
            chart_idx
        ]

    return float(row[col])


def _parse_mpsz_pai(pai: str) -> Optional[tuple[int, str]]:
    """Parse MJAI tile strings like '5m', '5mr', '12p' -> (rank, suit)."""
    m = _MPSZ_PAI_RE.match(str(pai).strip())
    if not m:
        return None
    return (int(m.group(1)), m.group(2).lower())


def _mpsz_pool_from_pairs(
    discards: Sequence[tuple[str, bool]],
    extended: Sequence[tuple[str, bool]],
) -> set[tuple[int, str]]:
    """Unique (rank, suit) seen in this player's discards + extended pond."""
    out: set[tuple[int, str]] = set()
    for seq in (discards, extended):
        for pai, _ in seq:
            pr = _parse_mpsz_pai(pai)
            if pr:
                out.add(pr)
    return out


def _pool_has(pool: set[tuple[int, str]], rank: int, suit: str) -> bool:
    return (rank, suit) in pool


def _tile_type_to_rank_suit(tile_type: int) -> Optional[tuple[int, str]]:
    """Suited tile types only: 0–8 man, 9–17 pin, 18–26 sou."""
    tt = int(tile_type)
    if 0 <= tt <= 8:
        return (tt + 1, "m")
    if 9 <= tt <= 17:
        return (tt - 8, "p")
    if 18 <= tt <= 26:
        return (tt - 17, "s")
    return None


def _chart1_column_for_suji_category(
    rank: int,
    suit: str,
    pool: set[tuple[int, str]],
) -> str:
    """
    Map (rank, suit) discard to a CHART1_COLUMN_LABELS key (non_/half_/full_).
    Pool = (rank, suit) from player's discards + extended_discards (MPSZ).
    """
    # --- 5 : neighbors 2 and 8 ---
    if rank == 5:
        a = _pool_has(pool, 2, suit)
        b = _pool_has(pool, 8, suit)
        if a and b:
            return "full_5"
        if a or b:
            return "half_5"
        return "non_5"

    # --- 4 and 6 : two ±3 neighbors; closer-to-terminal side for 46A/46B ---
    if rank == 4:
        closer, other = 1, 7  # 1m side vs 7m side
        c_ok = _pool_has(pool, closer, suit)
        o_ok = _pool_has(pool, other, suit)
        if c_ok and o_ok:
            return "full_46"
        if c_ok and not o_ok:
            return "half_46A"
        if o_ok and not c_ok:
            return "half_46B"
        return "non_46"

    if rank == 6:
        closer, other = 3, 9
        c_ok = _pool_has(pool, closer, suit)
        o_ok = _pool_has(pool, other, suit)
        if c_ok and o_ok:
            return "full_46"
        if c_ok and not o_ok:
            return "half_46A"
        if o_ok and not c_ok:
            return "half_46B"
        return "non_46"

    # --- 1,2,3,7,8,9 : single tile three steps toward middle ---
    neighbor: Optional[int] = None
    band: str = ""

    if rank == 1:
        neighbor = 4
        band = "19"
    elif rank == 9:
        neighbor = 6
        band = "19"
    elif rank == 2:
        neighbor = 5
        band = "28"
    elif rank == 8:
        neighbor = 5
        band = "28"
    elif rank == 3:
        neighbor = 6
        band = "37"
    elif rank == 7:
        neighbor = 4
        band = "37"
    else:
        # rank 5 and 4,6 handled above
        return "non_5"

    seen = _pool_has(pool, neighbor, suit)
    if band == "19":
        return "half_19" if seen else "non_19"
    if band == "28":
        return "half_28" if seen else "non_28"
    if band == "37":
        return "half_37" if seen else "non_37"
    return "non_5"


# MJAI-style honor tokens in dahai logs (winds / dragons).
_HONOR_TILE_TYPE_MJAI: dict[int, str] = {
    27: "E",
    28: "S",
    29: "W",
    30: "N",
    31: "P",
    32: "F",
    33: "C",
}


def check_safe_tile(
    tile_type: int,
    *,
    discards_mpsz: Sequence[tuple[str, bool]] = (),
    extended_discards_mpsz: Sequence[tuple[str, bool]] = (),
) -> bool:
    """
    True if this tile type already appears in the player's discard lists
    (``discards_mpsz`` or ``extended_discards_mpsz``), i.e. treated as safe → 0 deal-in.
    """
    tt = int(tile_type)
    rs = _tile_type_to_rank_suit(tt)
    if rs is not None:
        pool = _mpsz_pool_from_pairs(discards_mpsz, extended_discards_mpsz)
        return _pool_has(pool, rs[0], rs[1])

    mjai = _HONOR_TILE_TYPE_MJAI.get(tt)
    if mjai is not None:
        for seq in (discards_mpsz, extended_discards_mpsz):
            for pai, _ in seq:
                if str(pai).strip().upper() == mjai:
                    return True
        return False

    return False


def calculate_suji_dealinrate(
    player_id: int,
    tile_type: int,
    turn_passed: int = 1,
    *,
    discards_mpsz: Sequence[tuple[str, bool]] = (),
    extended_discards_mpsz: Sequence[tuple[str, bool]] = (),
) -> float:
    """
    Deal-in rate from Chart 1 for a suited discard, using suji classification
    vs this player's ``discards_mpsz`` + ``extended_discards_mpsz`` (MJAI strings).

    ``player_id`` is reserved for future use (e.g. seat-specific rules).
    """
    _ = player_id
    rs = _tile_type_to_rank_suit(tile_type)
    if rs is None:
        return 0.0

    rank, suit = rs
    pool = _mpsz_pool_from_pairs(discards_mpsz, extended_discards_mpsz)
    col = _chart1_column_for_suji_category(rank, suit, pool)

    turn = max(1, min(19, int(turn_passed)))
    row = chart1_row_as_dict(turn)
    if row is None:
        return 0.0
    val = row.get(col)
    if val is None:
        return 0.0
    return float(val)


def refine_tile_types_by_suji_visibility_tiebreak(
    observation: Any,
    tile_types: list[int],
) -> list[int]:
    """
    When several **suited** tile types share the same suji deal-in rate (e.g. in
    ``fold()``), prefer discarding types with more copies already visible in public
    information. Score is ``min(4, count)`` from ``get_unavailable_tile_ids``, so
    tiers are **0–4** (4 means four or more visible); higher is preferred.

    Honor tile types (27–33) are passed through unchanged; the filter applies only
    among non-honor entries in ``tile_types``.
    """
    if not tile_types:
        return tile_types
    honors = [tt for tt in tile_types if _is_honor_tile_type(tt)]
    suited = [tt for tt in tile_types if not _is_honor_tile_type(tt)]
    if not suited:
        return list(tile_types)
    scores = {
        tt: min(4, _count_tile_type_in_unavailable(observation, tt))
        for tt in suited
    }
    mx = max(scores.values())
    suited_kept = [tt for tt in suited if scores[tt] == mx]
    return honors + suited_kept


def calculate_dealinrate(
    observation: Any,
    player_id: int,
    discard_actions,
    turn_passed: int = 1,
    *,
    rule_agent: Any = None,
    suji_discards_mpsz: Optional[Sequence[tuple[str, bool]]] = None,
    suji_extended_mpsz: Optional[Sequence[tuple[str, bool]]] = None,
) -> dict[int, float]:
    """
    For each tile type present in legal discard actions, return an estimated
    deal-in rate on a 0–100 scale.

    If ``check_safe_tile`` is true for a tile type (already in discards /
    extended discards), the rate is ``0`` before honor/suji charts.

    Honor tile types (27–33) use `calculate_honor_dealinrate`; all others use
    `calculate_suji_dealinrate`.

    `turn_passed` selects chart rows (Chart 2 honors, Chart 1 suji).

    For suji, pass ``rule_agent`` (e.g. ``RuleBasedAgent``) so
    ``discards_by_player`` / ``extended_discards_by_player`` MJAI lists are used,
    or set ``suji_discards_mpsz`` / ``suji_extended_mpsz`` explicitly.
    """
    disc_pairs: Sequence[tuple[str, bool]] = suji_discards_mpsz or ()
    ext_pairs: Sequence[tuple[str, bool]] = suji_extended_mpsz or ()
    if rule_agent is not None:
        if suji_discards_mpsz is None:
            disc_pairs = list(
                getattr(rule_agent, "discards_by_player", {}).get(player_id, [])
            )
        if suji_extended_mpsz is None:
            ext_pairs = list(
                getattr(rule_agent, "extended_discards_by_player", {}).get(
                    player_id, []
                )
            )

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
        if check_safe_tile(
            tile_type,
            discards_mpsz=disc_pairs,
            extended_discards_mpsz=ext_pairs,
        ):
            out[tile_type] = 0.0
            continue

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
            out[tile_type] = float(
                calculate_suji_dealinrate(
                    player_id,
                    tile_type,
                    turn_passed=turn_passed,
                    discards_mpsz=disc_pairs,
                    extended_discards_mpsz=ext_pairs,
                )
            )

    # Clamp to [0, 100] for safety once helpers are implemented
    for k in list(out.keys()):
        out[k] = max(0.0, min(100.0, out[k]))

    return out

