"""
Card system core for the chess-card-battle project.

This module provides a minimal, composable model for cards, deck/hand management,
play points (PP), and turn flow based on the provided rules:

- At battle start: draw 4 cards.
- At the start of each turn: draw 1 card and restore PP to max (max PP is 3).
- Using a card consumes PP equal to its cost; you cannot play a card without enough PP.

Notes:
- Effects are represented as callables that accept (game, player) and return a short log string.
- Integration points with the chess board are left as placeholders (e.g., grant extra move).

This file is pure Python and UI-agnostic so it can be tested independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Literal, Dict, Any
import random


# -----------------------------
# Data models
# -----------------------------

EffectFn = Callable[["Game", "PlayerState"], str]
PrecheckFn = Callable[["Game", "PlayerState"], Optional[str]]  # None: OK, str: error message


@dataclass
class PendingAction:
    """Represents a UI-required follow-up action (e.g., choose a card to discard).

    Extended to include several target kinds used by the UI:
    - 'heat_choice': ask the player to choose between unfreezing one own piece or blocking tiles
    - 'target_tiles_multi': collect multiple tile targets (e.g. up to 3)
    - 'target_piece_unfreeze': select one own frozen piece to unfreeze
    - legacy kinds: 'discard', 'target_tile', 'target_piece', 'confirm'
    """
    kind: Literal[
        "discard",
        "target_tile",
        "target_piece",
        "confirm",
        "heat_choice",
        "target_tiles_multi",
        "target_piece_unfreeze",
    ]
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PrePlayCheck:
    """カード使用前の確認が必要な場合の情報を保持"""
    hand_index: int
    card: Card
    needs_confirmation: bool = False
    confirmation_message: str = ""


@dataclass
class Card:
    name: str
    cost: int
    effect: EffectFn
    precheck: Optional[PrecheckFn] = None

    def can_play(self, player: "PlayerState") -> bool:
        return self.cost <= player.pp_current


@dataclass
class Deck:
    cards: List[Card] = field(default_factory=list)

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self) -> Optional[Card]:
        if not self.cards:
            return None
        return self.cards.pop(0)


@dataclass
class Hand:
    cards: List[Card] = field(default_factory=list)

    def add(self, card: Optional[Card]) -> None:
        if card is not None:
            self.cards.append(card)

    def remove_at(self, idx: int) -> Optional[Card]:
        if 0 <= idx < len(self.cards):
            return self.cards.pop(idx)
        return None


@dataclass
class PlayerState:
    deck: Deck
    hand: Hand = field(default_factory=Hand)
    graveyard: List[Card] = field(default_factory=list)
    pp_max: int = 3
    pp_current: int = 3
    hand_limit: int = 7
    # Hooks for chess integration / movement modifiers
    next_move_can_jump: bool = False
    extra_moves_this_turn: int = 0

    def reset_pp(self) -> None:
        self.pp_current = self.pp_max

    def spend_pp(self, amount: int) -> bool:
        if amount <= self.pp_current:
            self.pp_current -= amount
            return True
        return False


@dataclass
class Game:
    player: PlayerState
    turn: int = 0
    log: List[str] = field(default_factory=list)
    pending: Optional[PendingAction] = None
    # Placeholders for chess integration
    blocked_tiles: Dict[Any, int] = field(default_factory=dict)  # tile -> turns left
    frozen_pieces: Dict[Any, int] = field(default_factory=dict)  # piece_id -> turns left
    # which color the blocked tile applies to (tile -> 'white'|'black')
    blocked_tiles_owner: Dict[Any, str] = field(default_factory=dict)
    # Whether the player has already moved a chess piece this card-game turn.
    player_moved_this_turn: bool = False
    # Whether the player's card-game turn is currently active (started via start_turn)
    turn_active: bool = False
    # Number of consecutive extra full chess turns the player may take (skip opponent moves)
    player_consecutive_turns: int = 0

    # ---- draw helper with hand limit ----
    def draw_to_hand(self, n: int = 1) -> List[Tuple[Optional[Card], bool]]:
        """Draw up to n cards to hand respecting hand_limit.

        Returns a list of (card, added) where added=False means the card
        could not be added due to hand limit and was sent to graveyard.
        """
        results: List[Tuple[Optional[Card], bool]] = []
        for _ in range(n):
            c = self.player.deck.draw()
            if c is None:
                results.append((None, False))
                continue
            if len(self.player.hand.cards) >= self.player.hand_limit:
                # overflow -> send to graveyard
                self.player.graveyard.append(c)
                self.log.append(f"手札上限{self.player.hand_limit}のため『{c.name}』は墓地へ。")
                results.append((c, False))
            else:
                self.player.hand.add(c)
                results.append((c, True))
        return results

    def setup_battle(self) -> None:
        """Initial draw of 4 cards at battle start and PP reset."""
        self.player.reset_pp()
        self.draw_to_hand(4)
        self.log.append("バトル開始: 手札を4枚引き、PPを最大まで回復しました。")

    def start_turn(self) -> None:
        """At the start of each turn: draw 1 and restore PP to max."""
        self.turn += 1 if self.turn > 0 else 1
        # Mark the card-game turn as active; player must press start_turn to enable actions
        self.turn_active = True
        self.player.reset_pp()
        # Decay board statuses (done via helper so opponent-turn-only decay can be applied separately)
        self.decay_statuses()

        self.player.extra_moves_this_turn = 0
        self.player.next_move_can_jump = False
        # Reset per-turn movement flag so player can move once this new turn
        self.player_moved_this_turn = False

        res = self.draw_to_hand(1)
        if not res or res[0][0] is None:
            self.log.append(f"ターン{self.turn}開始: 山札が空。PPを{self.player.pp_max}に回復。")
        else:
            c, added = res[0]
            if added:
                self.log.append(f"ターン{self.turn}開始: 『{c.name}』を1枚ドロー。PPを{self.player.pp_max}に回復。")
            else:
                self.log.append(f"ターン{self.turn}開始: 手札上限のため『{c.name}』は墓地へ。PPを{self.player.pp_max}に回復。")

    def decay_statuses(self) -> None:
        """Decay time-limited statuses (blocked_tiles, frozen_pieces) by 1 turn.

        This function is intended to be called once per opponent turn end so that
        effects like 封鎖 (灼熱) which last N opponent turns are decremented.
        It only decrements the counters and removes expired entries; it does not
        perform start-of-turn actions like drawing cards or restoring PP.
        """
        # Decay blocked tiles
        for k in list(self.blocked_tiles.keys()):
            try:
                self.blocked_tiles[k] -= 1
            except Exception:
                # If value is not numeric, ignore
                continue
            if self.blocked_tiles[k] <= 0:
                try:
                    del self.blocked_tiles_owner[k]
                except Exception:
                    pass
                try:
                    del self.blocked_tiles[k]
                except Exception:
                    pass
        # Decay frozen pieces
        for k in list(self.frozen_pieces.keys()):
            try:
                self.frozen_pieces[k] -= 1
            except Exception:
                continue
            if self.frozen_pieces[k] <= 0:
                try:
                    del self.frozen_pieces[k]
                except Exception:
                    pass

    def play_card(self, hand_index: int) -> Tuple[bool, str]:
        """Attempt to play a card from hand; returns (success, message)."""
        # Block play unless the player's card-game turn is active
        if not getattr(self, 'turn_active', False):
            return False, "ターンが開始していません。[T]で開始してください。"
        if self.pending is not None:
            return False, "操作待ち: 先に保留中の選択を完了してください。"
        if not (0 <= hand_index < len(self.player.hand.cards)):
            return False, "手札の番号が不正です。"
        card = self.player.hand.cards[hand_index]
        if not card.can_play(self.player):
            return False, f"PPが不足しています（現在{self.player.pp_current}）。『{card.name}』のコストは{card.cost}です。"
        
        # 墓地ルーレット専用: 墓地が空なら確認を先に出す（カード未消費）
        if card.name == "墓地ルーレット" and not self.player.graveyard:
            self.pending = PendingAction(
                kind="confirm",
                info={
                    "id": "confirm_grave_roulette_empty",
                    "message": "墓地から回収できるカードがありません。\n使用しますか？",
                    "yes_label": "はい(Y)",
                    "no_label": "いいえ(N)",
                    "hand_index": hand_index,  # カードの位置を保存
                },
            )
            return True, "確認待ち"

        # 迅雷: 2回目以降の使用は上書きで追加ターン数が増えないため、警告を出す（カード未消費）
        if card.name == "迅雷" and getattr(self, 'player_consecutive_turns', 0) >= 1:
            self.pending = PendingAction(
                kind="confirm",
                info={
                    "id": "confirm_second_lightning_overwrite",
                    "message": "すでに『迅雷』は使用しています。\n再度使用しても何も起きません。\nそれでも使用しますか？",
                    "yes_label": "はい(Y)",
                    "no_label": "いいえ(N)",
                    "hand_index": hand_index,
                },
            )
            return True, "確認待ち"

        # 暴風: 2回目以降の使用は上書きで効果が増えないため、警告を出す（カード未消費）
        if card.name == "暴風" and getattr(self.player, 'next_move_can_jump', False):
            self.pending = PendingAction(
                kind="confirm",
                info={
                    "id": "confirm_second_storm_overwrite",
                    "message": "すでに『暴風』の効果が有効です。\n再度使用しても効果を上書きするだけです。\nそれでも使用しますか？",
                    "yes_label": "はい(Y)",
                    "no_label": "いいえ(N)",
                    "hand_index": hand_index,
                },
            )
            return True, "確認待ち"
        
        # Optional precheck (e.g., cannot play if graveyard empty)
        if card.precheck is not None:
            err = card.precheck(self, self.player)
            if err:
                return False, err
        # Spend PP and resolve effect
        assert self.player.spend_pp(card.cost)
        self.player.hand.remove_at(hand_index)
        # Resolve effect BEFORE sending the card itself to graveyard
        msg = card.effect(self, self.player)
        # If the effect created a pending action, remember which card caused it
        if self.pending is not None:
            self.pending.info.setdefault('source_card_name', card.name)
        # After resolution, move the used card to graveyard
        self.player.graveyard.append(card)
        msg_full = f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{self.player.pp_current}/{self.player.pp_max}。"
        self.log.append(msg_full)
        return True, msg_full


# -----------------------------
# Sample effects and a small sample card pool
# -----------------------------

def eff_draw1(game: Game, player: PlayerState) -> str:
    res = game.draw_to_hand(1)
    if not res or res[0][0] is None:
        return "山札が空のためドローできません。"
    c, added = res[0]
    return f"『{c.name}』をドロー。" if added else f"手札上限のため『{c.name}』は墓地へ。"


def eff_gain_pp1(game: Game, player: PlayerState) -> str:
    before = player.pp_current
    player.pp_current = min(player.pp_current + 1, player.pp_max)
    return f"PP+1（{before}→{player.pp_current}）。"


def eff_placeholder_extra_move(game: Game, player: PlayerState) -> str:
    # Placeholder for chess integration, e.g., grant an extra move this turn
    return "チェスの追加手番を付与（仮）。"


def make_sample_deck() -> Deck:
    """Create a tiny sample deck for demo purposes."""
    pool = [
        Card("Quick Draw", 0, eff_draw1),
        Card("Meditate", 1, eff_gain_pp1),
        Card("Tactical Surge", 2, eff_placeholder_extra_move),
        Card("Quick Draw", 0, eff_draw1),
        Card("Meditate", 1, eff_gain_pp1),
        Card("Tactical Surge", 2, eff_placeholder_extra_move),
        Card("Quick Draw", 0, eff_draw1),
        Card("Meditate", 1, eff_gain_pp1),
    ]
    random.shuffle(pool)
    return Deck(pool)


def new_game_with_sample_deck() -> Game:
    deck = make_sample_deck()
    deck.shuffle()
    player = PlayerState(deck=deck)
    game = Game(player=player)
    game.setup_battle()
    return game


# -------------------------------------------------------
# Extended effects based on provided card table (Japanese)
# -------------------------------------------------------

def eff_heat_block_tile(game: Game, player: PlayerState) -> str:
    """灼熱(1): 盤面の駒のいないマスを1つ選択→相手は次の相手ターンから2ターン通れない。

    Demo: declare a pending target. Real board integration should apply
    'blocked_tiles[tile] = turns'.
    """
    # If the player has any frozen own pieces, offer the choice to unfreeze
    # one of them instead of blocking tiles. The UI will present the choice.
    game.pending = PendingAction(
        kind="heat_choice",
        info={
            "turns": 2,
            "max_tiles": 3,
            "note": "Choose: unfreeze one own frozen piece OR block 1-3 tiles for opponent.",
        },
    )
    return "灼熱: 自分の凍結駒を解除するか、1～3マスを封鎖するか選択してください。"


def eff_freeze_piece(game: Game, player: PlayerState) -> str:
    """氷結(1): 相手コマ1つ選択→次の相手ターン終わりまで行動不能。

    Demo: declare a pending target_piece.
    """
    game.pending = PendingAction(
        kind="target_piece",
        info={"turns": 1, "note": "Freeze enemy piece until end of next opponent turn."},
    )
    return "凍結する相手コマを選択してください（デモでは選択のみ）。"


def eff_storm_jump_once(game: Game, player: PlayerState) -> str:
    """暴風(1): 駒を一つ飛び越えられる（次の移動1回に有効）。"""
    player.next_move_can_jump = True
    return "次の移動で駒を1つ飛び越え可能。"


def eff_lightning_two_actions(game: Game, player: PlayerState) -> str:
    """迅雷(1): このターンに1回だけ追加の全行動（合計で2ターン分）。"""
    # Grant one extra full chess turn to the player (so player gets this turn + 1 more).
    try:
        game.player_consecutive_turns = max(getattr(game, 'player_consecutive_turns', 0), 1)
    except Exception:
        setattr(game, 'player_consecutive_turns', 1)
    return "このターンに追加で1ターン分行動できます（合計2ターン）。"


def eff_draw2(game: Game, player: PlayerState) -> str:
    """2ドロー(1): 山札から2枚引く。"""
    res = game.draw_to_hand(2)
    items: List[str] = []
    for c, added in res:
        if c is None:
            continue
        items.append(c.name if added else f"{c.name}(墓地)")
    return "ドロー: " + (", ".join(items) if items else "なし")


def eff_alchemy(game: Game, player: PlayerState) -> str:
    """錬成(0): 山札から1枚引き、その後手札から1枚選んで捨てる（保留アクション）。"""
    # New behavior: require the player to discard first; ONLY after discard is confirmed
    # the effect draws 1 card. We capture this as an execute_after_discard instruction
    # so the UI can perform the draw after the discard completes.
    game.pending = PendingAction(kind="discard", info={
        "count": 1,
        "execute_after_discard": {"draw": 1},
        "note": "錬成: 先に手札から1枚捨てると、その後1枚ドローします。",
    })
    return "錬成: まず手札から1枚を捨ててください。捨てると1枚ドローします。"


def eff_graveyard_roulette(game: Game, player: PlayerState) -> str:
    """墓地ルーレット(1): ランダムで墓地のカードを回収して手札へ。"""
    if not player.graveyard:
        # 墓地が空の場合は何もしない（確認はplay_card内で行われる）
        return "墓地が空です。"
    idx = random.randrange(len(player.graveyard))
    card = player.graveyard.pop(idx)
    player.hand.add(card)
    return f"墓地から『{card.name}』を回収。"


def pre_graveyard_not_empty(game: Game, player: PlayerState) -> Optional[str]:
    """墓地が空ならエラーを返し、カードを使用不可にする。"""
    if not player.graveyard:
        return "墓地が空のため『墓地ルーレット』は発動できません。"
    return None


def eff_leech_pp2(game: Game, player: PlayerState) -> str:
    """\u6442\u53d6(1): PPを2回復（上限あり）。"""
    before = player.pp_current
    player.pp_current = min(player.pp_current + 2, player.pp_max)
    return f"PP+2（{before}→{player.pp_current}）。"


# ---- name normalization to avoid legacy/encoding variants ----
def _normalize_card_name(name: str) -> str:
    """Normalize legacy or variant names to canonical ones.

    Currently consolidates '掠取' -> '摂取'.
    """
    mapping = {
        "掠取": "\u6442\u53d6",  # ensure canonical '摂取'
    }
    return mapping.get(name, name)


def make_rule_cards_deck() -> Deck:
    """Create a deck containing the cards listed in the provided table."""
    kinds = [
        Card("灼熱", 1, eff_heat_block_tile),
        Card("氷結", 1, eff_freeze_piece),
        Card("暴風", 1, eff_storm_jump_once),
        Card("迅雷", 1, eff_lightning_two_actions),
        Card("2ドロー", 1, eff_draw2),
    Card("錬成", 0, eff_alchemy),
    # 墓地ルーレットは空でも使用可能にし、UIで確認を促す
    Card("墓地ルーレット", 1, eff_graveyard_roulette),
        Card("\u6442\u53d6", 1, eff_leech_pp2),
    ]
    pool = []
    for c in kinds:
        pool.extend([Card(c.name, c.cost, c.effect, getattr(c, 'precheck', None)) for _ in range(3)])
    # Normalize any legacy variants just in case
    for c in pool:
        c.name = _normalize_card_name(c.name)
    random.shuffle(pool)
    return Deck(pool)


def new_game_with_rule_deck() -> Game:
    deck = make_rule_cards_deck()
    deck.shuffle()
    player = PlayerState(deck=deck)
    game = Game(player=player)
    game.setup_battle()
    return game


__all__ = [
    "Card",
    "Deck",
    "Hand",
    "PlayerState",
    "Game",
    "new_game_with_sample_deck",
    "new_game_with_rule_deck",
]
