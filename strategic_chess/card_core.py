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
    # Number of consecutive extra full chess turns for AI (black)
    ai_consecutive_turns: int = 0
    # AI-specific single-move jump flag (暴風) stored here so card effects can set it
    ai_next_move_can_jump: bool = False

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
        # 封鎖タイルや凍結駒の減少処理は相手ターン終了時に行われるため、ここでは行わない

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


    def decay_statuses(self, ended_color: Optional[str] = None) -> None:
        """Decay time-limited statuses (blocked_tiles, frozen_pieces) by 1 turn.

        If `ended_color` is provided ('white' or 'black'), only statuses that
        apply to that color are decremented. This ensures that a freeze applied
        to a player piece is decremented at the end of that player's turn, not
        immediately when the opponent finishes their move.

        If `ended_color` is None, behave like the legacy behavior and decrement
        all status counters.
        """
        # Decay blocked tiles: only decrement tiles that belong to the color
        # whose turn just ended (if provided).
        for k in list(self.blocked_tiles.keys()):
            owner = self.blocked_tiles_owner.get(k)
            if ended_color is not None and owner is not None and owner != ended_color:
                # skip tiles that belong to the other color
                continue
            try:
                self.blocked_tiles[k] -= 1
            except Exception:
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
        # Decay frozen pieces: we need to look up the engine piece for each id
        # and only decrement if its color matches ended_color (when provided).
        for k in list(self.frozen_pieces.keys()):
            try:
                # If ended_color given, find piece and skip if colors don't match
                if ended_color is not None:
                    try:
                        try:
                            from . import chess_engine as chess
                        except Exception:
                            import chess_engine as chess
                        found = None
                        for p in getattr(chess, 'pieces', []) or []:
                            if id(p) == k:
                                found = p
                                break
                        if found is None:
                            # If the id doesn't match, try to skip decrementing
                            # because we can't determine ownership reliably.
                            continue
                        if getattr(found, 'color', None) != ended_color:
                            # not the color whose turn ended -> skip
                            continue
                    except Exception:
                        # conservative: if lookup fails, skip decrement
                        continue
                # decrement
                self.frozen_pieces[k] -= 1
            except Exception:
                continue
            if self.frozen_pieces[k] <= 0:
                # Clear transient attribute on the actual piece object
                try:
                    try:
                        from . import chess_engine as chess
                    except Exception:
                        import chess_engine as chess
                    for p in getattr(chess, 'pieces', []) or []:
                        if id(p) == k and hasattr(p, 'frozen_turns'):
                            try:
                                delattr(p, 'frozen_turns')
                            except Exception:
                                try:
                                    del p.frozen_turns
                                except Exception:
                                    pass
                            break
                except Exception:
                    pass
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

        # 灼熱: カード消費前に二択を表示（カード未消費）
        if card.name == "灼熱":
            self.pending = PendingAction(
                kind="heat_choice",
                info={
                    "turns": 2,
                    "max_tiles": 3,
                    "hand_index": hand_index,  # カードの位置を保存
                    "note": "Choose: unfreeze one own frozen piece OR block 1-3 tiles for opponent.",
                },
            )
            return True, "灼熱: 自分の凍結駒を解除するか、3マス封鎖をするか選択してください。"
        
        # 錬成: まず錬成カードを墓地に送り、1枚ドローして、その後手札から1枚捨てる処理
        if card.name == "錬成":
            # PPを消費して錬成カードを墓地に送る
            assert self.player.spend_pp(card.cost)
            self.player.hand.remove_at(hand_index)
            self.player.graveyard.append(card)
            
            # 1枚ドロー
            drawn_card = self.player.deck.draw()
            if drawn_card:
                self.player.hand.add(drawn_card)
                msg = f"『{card.name}』（コスト{card.cost}）を使用。山札から『{drawn_card.name}』を引きました。PPは{self.player.pp_current}/{self.player.pp_max}。"
            else:
                msg = f"『{card.name}』（コスト{card.cost}）を使用。山札が空です。PPは{self.player.pp_current}/{self.player.pp_max}。"
            
            self.log.append(msg)
            
            # その後、手札から1枚捨てる処理を保留
            self.pending = PendingAction(
                kind="discard",
                info={
                    "count": 1,
                    "is_alchemy": True,  # 錬成の捨てる処理であることを示す
                    "drawn_card_name": drawn_card.name if drawn_card else None,  # 引いたカード名を保存
                    "note": f"錬成で引いたカード『{drawn_card.name if drawn_card else 'なし'}』を含めて手札から1枚選んで墓地に捨ててください。",
                },
            )
            return True, msg + " 手札から1枚選んで墓地に捨ててください。"
        
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

    def play_card_for(self, player, hand_index: int) -> Tuple[bool, str]:
        """Play a card on behalf of `player` (AI). This mirrors play_card but
        uses the provided player object instead of self.player and automatically
        resolves interactive pending choices with reasonable defaults for AI.
        """
        # Basic guards similar to play_card
        if not getattr(self, 'turn_active', False):
            return False, "ターンが開始していません。[T]で開始してください。"
        if self.pending is not None:
            return False, "操作待ちがあるためカードを使用できません。"
        if not (0 <= hand_index < len(player.hand.cards)):
            return False, "手札の番号が不正です。"
        card = player.hand.cards[hand_index]
        if not card.can_play(player):
            return False, f"PPが不足しています（現在{player.pp_current}）。『{card.name}』のコストは{card.cost}です。"

        # For AI, auto-resolve cards that normally create pending actions
        # Handle 墓地ルーレット: if grave empty, AI will cancel use
        if card.name == "墓地ルーレット" and not player.graveyard:  # AIのカード使用度改正
            return False, "AI: 墓地が空のため墓地ルーレットを使いませんでした。"

        # 迅雷: if already active for the side using it, AI will skip using
        if card.name == "迅雷":
            # if AI is the actor, check ai_consecutive_turns; otherwise check player_consecutive_turns
            if player is self.player and getattr(self, 'player_consecutive_turns', 0) >= 1:
                return False, "AI: 迅雷は既に効果があるため使用しませんでした。"
            if player is not self.player and getattr(self, 'ai_consecutive_turns', 0) >= 1:
                return False, "AI: 迅雷は既に効果があるため使用しませんでした。"

        # 暴風: if player's next_move_can_jump already True, skip
        if card.name == "暴風" and getattr(player, 'next_move_can_jump', False):
            return False, "AI: 暴風は既に効果があるため使用しませんでした。"

        # 錬成 special-case: AI will consume PP and perform immediate discard
        if card.name == "錬成":
            assert player.spend_pp(card.cost)
            player.hand.remove_at(hand_index)
            player.graveyard.append(card)
            drawn = player.deck.draw()
            if drawn:
                player.hand.add(drawn)
            # AI discards a random card if hand not empty
            import random
            if player.hand.cards:
                player.hand.remove_at(random.randrange(len(player.hand.cards)))
            self.log.append(f"AI: 錬成を使用しました。")
            return True, "AI: 錬成を使用しました。"

        # Spend PP and resolve general effects
        assert player.spend_pp(card.cost)
        player.hand.remove_at(hand_index)
        # Call effect; many effects expect (game, player)
        msg = card.effect(self, player)
        # If effect created pending (unlikely for AI), try to auto-resolve simple kinds
        if self.pending is not None:
            # Auto-resolve pending actions for AI in sensible ways
            try:
                from . import chess_engine as chess
            except Exception:
                try:
                    import chess_engine as chess
                except Exception:
                    chess = None

            # Determine player color: assume self.player is human (white), others are black
            own_color = 'white' if player is self.player else 'black'
            opp_color = 'black' if own_color == 'white' else 'white'

            if self.pending.kind == 'heat_choice':
                turns = self.pending.info.get('turns', 2)
                max_tiles = self.pending.info.get('max_tiles', 3)

                # If AI has any frozen own pieces, unfreeze the highest-value one; otherwise block tiles
                unfreeze_candidates = []
                if chess is not None:
                    try:
                        for p in chess.pieces:
                            if getattr(p, 'color', None) == own_color and id(p) in self.frozen_pieces:
                                unfreeze_candidates.append(p)
                    except Exception:
                        unfreeze_candidates = []

                if unfreeze_candidates:
                    # choose highest-value by piece type
                    vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
                    best = None
                    best_v = -1
                    for p in unfreeze_candidates:
                        v = vals.get(getattr(p, 'name', ''), 0)
                        if v > best_v:
                            best_v = v
                            best = p
                    if best is not None:
                        try:
                            del self.frozen_pieces[id(best)]
                        except Exception:
                            pass
                        # Also clear transient attribute on the actual piece object
                        try:
                            if hasattr(best, 'frozen_turns'):
                                try:
                                    delattr(best, 'frozen_turns')
                                except Exception:
                                    try:
                                        del best.frozen_turns
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        self.log.append(f"AI: 灼熱で自分の凍結駒 {getattr(best,'name',str(best))} を解除しました。")
                        self.pending = None
                else:
                    # Block up to max_tiles around strongest opponent piece
                    target = None
                    best_val = -1
                    vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
                    if chess is not None:
                        try:
                            for p in chess.pieces:
                                if getattr(p, 'color', None) == opp_color:
                                    v = vals.get(getattr(p, 'name', ''), 0)
                                    if v > best_val:
                                        best_val = v
                                        target = p
                        except Exception:
                            target = None
                    if target is not None:
                        tr, tc = getattr(target, 'row', None), getattr(target, 'col', None)
                        placed = 0
                        # Try to place up to max_tiles empty blocked tiles around the target.
                        # Instead of only checking immediate 8 neighbours, expand search by
                        # increasing Manhattan radius so AI can still place tiles if nearby
                        # squares are occupied.
                        if tr is not None and tc is not None:
                            # Collect candidate empty tiles in deterministic order
                            candidates = []
                            max_radius = 3
                            for radius in range(1, max_radius + 1):
                                # produce ordered offsets for this radius: iterate dr from -radius..radius
                                for dr in range(-radius, radius + 1):
                                    dc_base = radius - abs(dr)
                                    dc_list = [dc_base] if dc_base == 0 else [dc_base, -dc_base]
                                    for dc in dc_list:
                                        nr, nc = tr + dr, tc + dc
                                        if nr is None or nc is None:
                                            continue
                                        if not (0 <= nr < 8 and 0 <= nc < 8):
                                            continue
                                        # ensure empty
                                        empty = True
                                        if chess is not None:
                                            try:
                                                if chess.get_piece_at(nr, nc) is not None:
                                                    empty = False
                                            except Exception:
                                                empty = True
                                        if not empty:
                                            continue
                                        # skip already blocked
                                        if (nr, nc) in self.blocked_tiles:
                                            continue
                                        candidates.append((nr, nc))
                                if len(candidates) >= max_tiles:
                                    break
                            # Apply up to max_tiles from candidates (deterministic order)
                            to_place = candidates[:max_tiles]
                            for (nr, nc) in to_place:
                                try:
                                    self.blocked_tiles[(nr, nc)] = turns
                                    self.blocked_tiles_owner[(nr, nc)] = opp_color
                                except Exception:
                                    self.blocked_tiles[(nr, nc)] = turns
                            placed = len(to_place)
                            if placed:
                                try:
                                    self.log.append(f"AI: 灼熱で封鎖マスを適用しました: {to_place}")
                                except Exception:
                                    pass
                        if placed > 0:
                            self.log.append(f"AI: 灼熱でマスの封鎖を行いました: {placed} マス")
                        else:
                            self.log.append("AI: 灼熱を使用しましたが、有効な封鎖マスが見つかりませんでした。")
                        self.pending = None
            elif self.pending.kind == 'target_piece':
                # AI should pick an opponent piece to freeze for the specified turns
                turns = self.pending.info.get('turns', 1)
                target = None
                best_val = -1
                vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
                if chess is not None:
                    try:
                        for p in chess.pieces:
                            if getattr(p, 'color', None) == opp_color:
                                v = vals.get(getattr(p, 'name', ''), 0)
                                if v > best_val:
                                    best_val = v
                                    target = p
                    except Exception:
                        target = None
                if target is not None:
                    try:
                        self.frozen_pieces[id(target)] = turns
                    except Exception:
                        self.frozen_pieces[id(target)] = turns
                    # Also set a transient attribute on the piece object so
                    # UI/engine code that looks at the piece directly can see
                    # the frozen state even if id-based lookups fail in some
                    # execution paths.
                    try:
                        setattr(target, 'frozen_turns', turns)
                    except Exception:
                        pass
                    # If UI hook present on the Game instance, request GIF playback
                    try:
                        play_hook = getattr(self, 'play_ic_gif', None)
                        tr = getattr(target, 'row', None)
                        tc = getattr(target, 'col', None)
                        if callable(play_hook) and tr is not None and tc is not None:
                            try:
                                play_hook(int(tr), int(tc))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Enhance log to include coordinates when possible
                    try:
                        tr = getattr(target, 'row', None)
                        tc = getattr(target, 'col', None)
                        if tr is not None and tc is not None:
                            self.log.append(f"AI: 氷結で相手の駒 {getattr(target,'name',str(target))} を ({tr},{tc}) に {turns} ターン凍結しました。")
                        else:
                            self.log.append(f"AI: 氷結で相手の駒 {getattr(target,'name',str(target))} を {turns} ターン凍結しました。")
                    except Exception:
                        self.log.append("AI: 氷結で相手の駒を凍結しました。")
                else:
                    # no valid target found, clear pending
                    self.log.append("AI: 氷結を使用しましたが、凍結対象が見つかりませんでした。")
                self.pending = None
            else:
                # Clear any other pending for AI (best-effort)
                self.pending = None
        # move to graveyard
        player.graveyard.append(card)
        self.log.append(f"AI: 『{card.name}』を使用しました。 {msg}")
        return True, f"AI: 『{card.name}』を使用しました。 {msg}"


# -----------------------------
# Sample effects and a small sample card pool
# -----------------------------

def eff_draw1(game: Game, player: PlayerState) -> str:
    # Draw one card for the specified player (works for both human and AI)
    drawn = player.deck.draw()
    if drawn is None:
        return "山札が空のためドローできません。"
    if len(player.hand.cards) >= player.hand_limit:
        player.graveyard.append(drawn)
        game.log.append(f"手札上限{player.hand_limit}のため『{drawn.name}』は墓地へ。")
        return f"手札上限のため『{drawn.name}』は墓地へ。"
    else:
        player.hand.add(drawn)
        return f"『{drawn.name}』をドロー。"


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
    return "灼熱: 自分の凍結駒を解除するか、3マス封鎖をするか選択してください。"


def eff_freeze_piece(game: Game, player: PlayerState) -> str:
    """氷結(1): 相手コマ1つ選択→次の相手ターン終わりまで行動不能。

    Demo: declare a pending target_piece.
    """
    game.pending = PendingAction(
        kind="target_piece",
        info={"turns": 1, "note": "Freeze enemy piece until end of next opponent turn."},
    )
    return "凍結する相手コマを選択してください。"


def eff_storm_jump_once(game: Game, player: PlayerState) -> str:
    """暴風(1): 駒を一つ飛び越えられる（次の移動1回に有効）。"""
    # Mark the flag on the PlayerState so human benefits immediately.
    player.next_move_can_jump = True
    # If the effect was played by AI (player is not the human player), also mark
    # the game-level AI jump flag so AI movement code can read it.
    try:
        if player is not game.player:
            game.ai_next_move_can_jump = True
    except Exception:
        pass
    return "次の移動で駒を1つ飛び越え可能。"


def eff_lightning_two_actions(game: Game, player: PlayerState) -> str:
    """迅雷(1): このターンに1回だけ追加の全行動（合計で2ターン分）。"""
    # Grant one extra full chess turn to the player (so player gets this turn + 1 more).
    # If the effect is played by the human (game.player), set player_consecutive_turns;
    # otherwise (AI) set ai_consecutive_turns so the AI benefits.
    try:
        if player is game.player:
            game.player_consecutive_turns = max(getattr(game, 'player_consecutive_turns', 0), 1)
        else:
            game.ai_consecutive_turns = max(getattr(game, 'ai_consecutive_turns', 0), 1)
    except Exception:
        if player is game.player:
            setattr(game, 'player_consecutive_turns', 1)
        else:
            setattr(game, 'ai_consecutive_turns', 1)
    return "このターンに追加で1ターン分行動できます（合計2ターン）。"


def eff_draw2(game: Game, player: PlayerState) -> str:
    """2ドロー(1): 山札から2枚引く。"""
    # Draw two cards for the specified player (works for both human and AI)
    items: List[str] = []
    for _ in range(2):
        c = player.deck.draw()
        if c is None:
            continue
        if len(player.hand.cards) >= player.hand_limit:
            player.graveyard.append(c)
            game.log.append(f"手札上限{player.hand_limit}のため『{c.name}』は墓地へ。")
            items.append(f"{c.name}(墓地)")
        else:
            player.hand.add(c)
            items.append(c.name)
    return "ドロー: " + (", ".join(items) if items else "なし")


def eff_alchemy(game: Game, player: PlayerState) -> str:
    """錬成(0): 山札から1枚引き、その後手札から1枚選んで捨てる（保留アクション）。"""
    # 実際の処理はplay_card内で行われる（カード消費前に処理）
    return "錬成の効果を実行中..."


def eff_graveyard_roulette(game: Game, player: PlayerState) -> str:
    """墓地ルーレット(1): ランダムで墓地のカードを回収して手札へ。"""
    if not player.graveyard:
        # 墓地が空の場合は何もしない（確認はplay_card内で行われる）
        return "墓地が空です。"
    idx = random.randrange(len(player.graveyard))
    card = player.graveyard.pop(idx)
    player.hand.add(card)
    return f"墓地から『{card.name}』を回収。"





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
        Card("灼熱", 2, eff_heat_block_tile),
        Card("氷結", 2, eff_freeze_piece),
        Card("暴風", 3, eff_storm_jump_once),
        Card("迅雷", 3, eff_lightning_two_actions),
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
