"""
Rule-based agent: same behavior as UkeMaxAgent (ukeire discards, tiebreaks, priorities).

Use this class when extending or swapping logic without changing ukeire_agent.py.
"""

from __future__ import annotations

import json
import pprint
import random
from collections import defaultdict
from typing import Any, Optional

from riichienv import ActionType, calculate_shanten

from utils import (
    RED_FIVE_TILE_TYPES,
    calculate_dealinrate,
    get_unavailable_tile_ids,
    refine_tile_types_by_suji_visibility_tiebreak,
    representative_discard_for_tile_type,
    tid_to_mpsz,
    tiebreak_best_tile_types,
    ukeire_for_discard,
)


class RuleBasedAgent:
    def __init__(
        self,
        seed: int | None = None,
        *,
        debug: bool = False,
        debug_kyoku: Optional[int] = None,
        debug_honba: Optional[int] = None,
        debug_print_obs_dict: bool = False,
    ):
        self.rng = random.Random(seed)
        self.debug = debug
        #: When True (with ``debug`` and kyoku/honba filters passing), print
        #: ``observation.to_dict()`` once per ``act()``.
        self.debug_print_obs_dict = debug_print_obs_dict
        # If set, debug logs only apply when current hand matches (from start_kyoku).
        # None = no filter on that axis; both None = print all debug (default).
        self.debug_kyoku = debug_kyoku
        self.debug_honba = debug_honba
        self._debug_current_kyoku: Optional[int] = None
        self._debug_current_honba: Optional[int] = None
        """Estimated turn index: max discard pile lengths + 1 (updated each act())."""
        self.turn_number: int = 1
        self._processed_event_count: int = 0
        # Per player: list of (pai_mpsz, tsumogiri) from MJAI dahai events.
        self.discards_by_player: dict[int, list[tuple[str, bool]]] = defaultdict(list)
        # Chronological (actor, pai, tsumogiri) for every dahai this hand.
        self._global_dahai_seq: list[tuple[int, str, bool]] = []
        # Last tedashi (tsumogiri=False) per player: tile string and index in _global_dahai_seq.
        self.last_tedashi_by_player: dict[int, Optional[tuple[str, bool]]] = {}
        self._last_tedashi_seq_index_by_player: dict[int, Optional[int]] = {}
        # For each player P: ordered (pai, tsumogiri) of all discards after P's last tedashi
        # (any seat); same tuple shape as discards_by_player entries.
        self.extended_discards_by_player: dict[int, list[tuple[str, bool]]] = {
            i: [] for i in range(4)
        }
        # Caller waiting to discard after a meld (for debug line).
        self._pending_call_actor: Optional[int] = None
        # First real fold() vs riichi this hand (for one-shot debug line).
        self._fold_debug_printed_this_hand: bool = False

    def act(self, observation: Any) -> Optional[Any]:
        self._process_new_events(observation)
        self.turn_number = self._compute_turn_number(observation)
        if self._should_debug_log():
            print(f"[RuleBasedAgent] turn_number={self.turn_number}")
            self._maybe_print_obs_dict(observation)

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
            discard_actions = [
                a for a in legal_actions if a.action_type == ActionType.Discard
            ]

            if discard_actions and hasattr(observation, "hand"):
                player_id = getattr(observation, "player_id", None)
                if player_id is None and discard_actions:
                    player_id = getattr(discard_actions[0], "actor", None)
                if player_id is None:
                    player_id = 0
                player_id = int(player_id)

                rd = self._get_riichi_declared_list(observation)
                any_riichi = bool(rd) and any(x for x in rd)
                if not any_riichi:
                    chosen = self.make_efficient_discard(
                        observation, discard_actions, player_id
                    )
                else:
                    shanten = calculate_shanten(observation.hand)
                    if shanten == 0:
                        chosen = self.make_efficient_discard(
                            observation, discard_actions, player_id
                        )
                    elif shanten >= 1:
                        chosen = self.fold(
                            observation, discard_actions, player_id
                        )

        if chosen is None:
            chosen = self.rng.choice(legal_actions)

        if self._should_debug_log() and chosen is not None:
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

    def _reset_hand_state(self) -> None:
        self.discards_by_player = defaultdict(list)
        self._global_dahai_seq = []
        self.last_tedashi_by_player = {}
        self._last_tedashi_seq_index_by_player = {}
        self.extended_discards_by_player = {i: [] for i in range(4)}
        self._pending_call_actor = None
        self._fold_debug_printed_this_hand = False

    def _rebuild_extended_discards_by_player(self) -> None:
        """
        For each seat P, collect every global discard strictly after P's last tedashi
        (tsumogiri=False), in table order, as (pai, tsumogiri).
        If P has never tedashi-discarded, use the full global sequence.
        """
        for pid in range(4):
            idx = self._last_tedashi_seq_index_by_player.get(pid)
            if idx is None:
                tail = self._global_dahai_seq
            else:
                tail = self._global_dahai_seq[idx + 1 :]
            self.extended_discards_by_player[pid] = [(p, ts) for (_a, p, ts) in tail]

    @staticmethod
    def _parse_event(raw: Any) -> Optional[dict]:
        try:
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, dict):
                return raw
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _gather_event_list_candidates(observation: Any) -> list[list]:
        """Collect every non-empty event log attached to the observation."""
        out: list[list] = []
        for attr in ("mjai_log", "full_events", "events"):
            v = getattr(observation, attr, None)
            if v:
                out.append(list(v))
        to_dict = getattr(observation, "to_dict", None)
        if callable(to_dict):
            try:
                d = to_dict()
                if isinstance(d, dict):
                    for key in ("mjai_log", "full_events", "events"):
                        v = d.get(key)
                        if v:
                            out.append(list(v))
            except Exception:
                pass
        return out

    @classmethod
    def _get_observation_events(cls, observation: Any) -> Optional[list]:
        """
        Prefer the **longest** MJAI-style log (often ``mjai_log`` is full history while
        ``events`` is a short rolling window). Using only the short list makes the log
        appear to "shrink", which used to reset discard state and drop earlier discards.
        """
        candidates = cls._gather_event_list_candidates(observation)
        if not candidates:
            return None
        return max(candidates, key=len)

    @staticmethod
    def _get_riichi_declared_list(observation: Any) -> list:
        """
        RiichiEnv often puts ``riichi_declared`` on the dict from ``to_dict()`` only,
        not as a direct attribute on the Observation wrapper — same pattern as
        ``events``. Without this fallback, ``any_riichi`` is always false and we
        never fold vs riichi.
        """
        rd = getattr(observation, "riichi_declared", None)
        if rd is None:
            to_dict = getattr(observation, "to_dict", None)
            if callable(to_dict):
                try:
                    d = to_dict()
                    if isinstance(d, dict):
                        rd = d.get("riichi_declared")
                except Exception:
                    pass
        if rd is None:
            return []
        try:
            return [bool(x) for x in list(rd)]
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _dahai_tuple_from_event(ev: dict) -> Optional[tuple[int, str, bool]]:
        if ev.get("type") != "dahai":
            return None
        actor = ev.get("actor")
        pai = ev.get("pai")
        if actor is None or pai is None:
            return None
        return (int(actor), str(pai), bool(ev.get("tsumogiri", False)))

    @classmethod
    def _dahai_tuple_seq_from_events(cls, events: list) -> list[tuple[int, str, bool]]:
        seq: list[tuple[int, str, bool]] = []
        for raw in events:
            ev = cls._parse_event(raw)
            if not ev:
                continue
            t = cls._dahai_tuple_from_event(ev)
            if t:
                seq.append(t)
        return seq

    @classmethod
    def _last_hand_boundary_index(cls, events: list) -> int:
        """Index of the last ``start_game`` / ``start_kyoku`` in the snapshot, or -1."""
        last = -1
        for i, raw in enumerate(events):
            ev = cls._parse_event(raw)
            if ev and ev.get("type") in ("start_game", "start_kyoku"):
                last = i
        return last

    @classmethod
    def _dahai_tuple_seq_from_slice(
        cls, events: list, start_idx: int
    ) -> list[tuple[int, str, bool]]:
        seq: list[tuple[int, str, bool]] = []
        for raw in events[start_idx:]:
            ev = cls._parse_event(raw)
            if not ev:
                continue
            t = cls._dahai_tuple_from_event(ev)
            if t:
                seq.append(t)
        return seq

    @staticmethod
    def _overlap_merge_len(
        G: list[tuple[int, str, bool]], seq_hand: list[tuple[int, str, bool]]
    ) -> int:
        """
        Largest L such that ``G[-L:] == seq_hand[:L]``.
        Used when the env replaces the log with a shorter tail: new discards continue
        the hand, so we append ``seq_hand[L:]`` without dropping earlier ``G``.
        """
        max_l = min(len(G), len(seq_hand))
        for L in range(max_l, -1, -1):
            if L == 0:
                return 0
            if G[-L:] == seq_hand[:L]:
                return L
        return 0

    def _rebuild_pond_state_from_global_dahai(self) -> None:
        """Rebuild per-player rivers and tedashi indices from ``_global_dahai_seq``."""
        self.discards_by_player = defaultdict(list)
        self.last_tedashi_by_player = {}
        self._last_tedashi_seq_index_by_player = {}
        for seq_idx, (aid, spai, tsumogiri) in enumerate(self._global_dahai_seq):
            self.discards_by_player[aid].append((spai, tsumogiri))
            if not tsumogiri:
                self.last_tedashi_by_player[aid] = (spai, False)
                self._last_tedashi_seq_index_by_player[aid] = seq_idx
        self._rebuild_extended_discards_by_player()

    def _compute_turn_number(self, observation: Any) -> int:
        discards = getattr(observation, "discards", None) or []
        if not discards:
            return 1
        return max(len(d) for d in discards) + 1

    def _should_debug_log(self) -> bool:
        """True when debug is on and kyoku/honba filters match (if any are set)."""
        if not self.debug:
            return False
        if self.debug_kyoku is None and self.debug_honba is None:
            return True
        if self.debug_kyoku is not None:
            if self._debug_current_kyoku != self.debug_kyoku:
                return False
        if self.debug_honba is not None:
            if self._debug_current_honba != self.debug_honba:
                return False
        return True

    def _maybe_print_obs_dict(self, observation: Any) -> None:
        if not self.debug_print_obs_dict or not self._should_debug_log():
            return
        to_dict = getattr(observation, "to_dict", None)
        if not callable(to_dict):
            return
        try:
            d = to_dict()
        except Exception as ex:
            print(f"[RuleBasedAgent] observation.to_dict() failed: {ex}")
            return
        print("[RuleBasedAgent] observation.to_dict():")
        pprint.pprint(d, width=120, compact=True)

    def _process_new_events(self, observation: Any) -> None:
        """
        Rebuild discard ponds from the current MJAI snapshot.

        The env often **replaces** the whole ``events`` list each step (rolling window).
        Using ``_processed_event_count`` as an index into that list is wrong when length
        grows (e.g. 8→10): indices 0–7 can contain new ``dahai`` that would be skipped.

        Instead, every step: take all ``dahai`` after the last hand boundary, merge onto
        ``_global_dahai_seq`` via longest tail/head overlap, then rebuild rivers.
        """
        events = self._get_observation_events(observation)
        if not events:
            return
        n = len(events)
        prev_n = self._processed_event_count
        boundary = self._last_hand_boundary_index(events)

        if boundary >= 0:
            evb = self._parse_event(events[boundary])
            if self._should_debug_log() and evb:
                et = evb.get("type")
                print(f"[RuleBasedAgent] event: {et} {evb}")
                scores = evb.get("scores")
                if scores is not None:
                    print(f"[RuleBasedAgent] scores: {scores}")
            self._reset_hand_state()
            if evb and evb.get("type") == "start_game":
                self._debug_current_kyoku = None
                self._debug_current_honba = None
            elif evb and evb.get("type") == "start_kyoku":
                k = evb.get("kyoku")
                h = evb.get("honba")
                self._debug_current_kyoku = int(k) if k is not None else None
                self._debug_current_honba = int(h) if h is not None else None
            seq_hand = self._dahai_tuple_seq_from_slice(events, boundary + 1)
            self._global_dahai_seq = list(seq_hand)
        else:
            seq_hand = self._dahai_tuple_seq_from_slice(events, 0)
            G = list(self._global_dahai_seq)
            Lm = self._overlap_merge_len(G, seq_hand)
            self._global_dahai_seq = G + seq_hand[Lm:]

        self._rebuild_pond_state_from_global_dahai()

        # Meld calls (pon / chi / kan / …): last ``consumed`` wins.
        for raw in events:
            ev = self._parse_event(raw)
            if not ev or "consumed" not in ev:
                continue
            actor = ev.get("actor")
            if actor is not None:
                self._pending_call_actor = int(actor)
            if self._should_debug_log():
                print(
                    f"[RuleBasedAgent] call: player={actor} type={ev.get('type')} "
                    f"pai={ev.get('pai')} consumed={ev.get('consumed')} "
                    f"target={ev.get('target')}"
                )

        self._processed_event_count = n

        if self._should_debug_log():
            turn_number = self._compute_turn_number(observation)
            delta = ""
            if n < prev_n:
                delta = f" log_len {prev_n}→{n} (shrunk)"
            elif n > prev_n:
                delta = f" log_len {prev_n}→{n} (grew)"
            # print(
            #     f"[RuleBasedAgent] _process_new_events turn_number={turn_number}"
            #     f"{delta}"
            # )
            # print(f"  raw_events ({len(events)}): {events}")
            # print(f"  discards_by_player: {dict(self.discards_by_player)}")
            # print(
            #     f"  extended_discards_by_player: "
            #     f"{dict(self.extended_discards_by_player)}"
            # )

    @staticmethod
    def _opponent_riichi_seats(
        observation: Any, player_id: int
    ) -> list[int]:
        """Seat indices (other than ``player_id``) with riichi_declared True."""
        rd = RuleBasedAgent._get_riichi_declared_list(observation)
        pid = int(player_id)
        return [i for i in range(len(rd)) if i != pid and rd[i]]

    def make_efficient_discard(
        self,
        observation: Any,
        discard_actions: list,
        player_id: int,
    ) -> Optional[Any]:
        """Ukeire-max discard with red-five representative and tiebreak."""
        return self._efficient_discard_subset(
            observation, discard_actions, player_id
        )

    def _efficient_discard_subset(
        self,
        observation: Any,
        discard_actions: list,
        player_id: int,
    ) -> Optional[Any]:
        """
        Same logic as ``make_efficient_discard``, restricted to the given discard
        actions (used when folding among zero deal-in candidates).
        """
        if not discard_actions or not hasattr(observation, "hand"):
            return None

        ukeire = ukeire_for_discard(
            observation.hand,
            get_unavailable_tile_ids(observation),
        )

        groups_by_tile_type = defaultdict(list)
        for action in discard_actions:
            tile_id = action.tile
            if tile_id is None:
                continue
            tile_type = int(tile_id) // 4
            groups_by_tile_type[tile_type].append(action)

        actions_by_tile_type = {
            tile_type: representative_discard_for_tile_type(
                acts, tile_type, self.rng
            )
            for tile_type, acts in groups_by_tile_type.items()
        }

        best_tile_types: list[int] = []
        best_score: Optional[int] = None

        for tile_type, _rep_action in actions_by_tile_type.items():
            score = ukeire.get(tile_type, 0)
            if best_score is None or score > best_score:
                best_score = score
                best_tile_types = [tile_type]
            elif score == best_score:
                best_tile_types.append(tile_type)

        if not best_tile_types:
            return None

        chosen_tile_type = tiebreak_best_tile_types(
            best_tile_types,
            actions_by_tile_type,
            observation,
            self.rng,
            player_id=player_id,
        )
        return actions_by_tile_type[chosen_tile_type]

    @staticmethod
    def _fold_prefer_plain_five_over_red(
        actions: list, tile_type: int, rng: random.Random
    ) -> Any:
        """
        When summed deal-in for this tile type is > 0, prefer discarding the plain
        five (``tile_id % 4 == 0``) over red/aka copies — opposite of efficient play.
        """
        if not actions:
            raise ValueError("fold tiebreak: empty actions")
        if tile_type not in RED_FIVE_TILE_TYPES:
            return rng.choice(actions)
        plain = [
            a
            for a in actions
            if getattr(a, "tile", None) is not None and int(a.tile) % 4 == 0
        ]
        if plain:
            return rng.choice(plain)
        return rng.choice(actions)

    def fold(
        self,
        observation: Any,
        discard_actions: list,
        player_id: int,
    ) -> Any:
        """
        Against riichi: sum deal-in rates from each riichi opponent's perspective,
        then minimize total risk.         Among tied suited types, prefer more copies visible (tiers 0–4 via
        ``refine_tile_types_by_suji_visibility_tiebreak``). Then: if
        min risk > 0, prefer plain 5 over red 5; if min risk ~= 0, use ukeire +
        same tiebreak as ``make_efficient_discard``.
        """
        riichi_opponents = self._opponent_riichi_seats(observation, player_id)
        if not riichi_opponents:
            out = self.make_efficient_discard(
                observation, discard_actions, player_id
            )
            if out is not None:
                return out
            return self.rng.choice(discard_actions)

        if self._should_debug_log() and not self._fold_debug_printed_this_hand:
            print("[RuleBasedAgent] folding (defensive discard vs riichi)")
            print(f"  discards_by_player: {dict(self.discards_by_player)}")
            print(
                f"  extended_discards_by_player: "
                f"{dict(self.extended_discards_by_player)}"
            )
            print(f"  last_tedashi_by_player: {dict(self.last_tedashi_by_player)}")
            self._fold_debug_printed_this_hand = True

        def _fmt_dealinrates(rates: dict[int, float]) -> str:
            parts: list[str] = []
            for tt in sorted(rates.keys(), key=int):
                try:
                    label = tid_to_mpsz(int(tt) * 4)
                except Exception:
                    label = str(tt)
                parts.append(f"{label}={float(rates[tt]):.2f}")
            return ", ".join(parts)

        totals: dict[int, float] = defaultdict(float)
        per_opp: dict[int, dict[int, float]] = {}
        for rpid in riichi_opponents:
            rates = calculate_dealinrate(
                observation,
                rpid,
                discard_actions,
                turn_passed=self.turn_number,
                rule_agent=self,
            )
            per_opp[rpid] = rates
            if self._should_debug_log():
                print(
                    f"  dealinrate vs riichi seat {rpid}: "
                    f"{_fmt_dealinrates(rates)}"
                )
            for tt, v in rates.items():
                totals[int(tt)] += float(v)

        if self._should_debug_log() and totals:
            print(
                "  dealinrate summed (all riichi): "
                f"{_fmt_dealinrates(dict(totals))}"
            )

        if not totals:
            return self.rng.choice(discard_actions)

        _EPS = 1e-6
        min_rate = min(float(v) for v in totals.values())
        best_tile_types = [
            int(tt)
            for tt, v in totals.items()
            if abs(float(v) - min_rate) <= _EPS
        ]
        # Suited tiles tied on summed suji rate: prefer more copies visible (genbutsu).
        best_tile_types = refine_tile_types_by_suji_visibility_tiebreak(
            observation, best_tile_types
        )
        pool = [
            a
            for a in discard_actions
            if a.tile is not None and (int(a.tile) // 4) in best_tile_types
        ]
        if not pool:
            return self.rng.choice(discard_actions)

        if min_rate > _EPS:
            groups: dict[int, list] = defaultdict(list)
            for a in pool:
                groups[int(a.tile) // 4].append(a)
            reps: list = []
            for tt in best_tile_types:
                acts = groups.get(tt, [])
                if acts:
                    reps.append(
                        self._fold_prefer_plain_five_over_red(
                            acts, tt, self.rng
                        )
                    )
            return self.rng.choice(reps) if reps else self.rng.choice(pool)

        out = self._efficient_discard_subset(
            observation, pool, player_id
        )
        if out is not None:
            return out
        return self.rng.choice(pool)
