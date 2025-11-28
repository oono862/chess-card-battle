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
    # Iron wall protection: protects from harmful gimmick cards for 1 turn
    player_ironwall_protection_turns: int = 0
    ai_ironwall_protection_turns: int = 0

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
        # Decay ironwall protection turns
        if ended_color is None or ended_color == 'white':
            if getattr(self, 'player_ironwall_protection_turns', 0) > 0:
                try:
                    self.player_ironwall_protection_turns -= 1
                except Exception:
                    pass
        if ended_color is None or ended_color == 'black':
            if getattr(self, 'ai_ironwall_protection_turns', 0) > 0:
                try:
                    self.ai_ironwall_protection_turns -= 1
                except Exception:
                    pass
        
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

    # ---- helpers to apply status effects with iron-wall checks ----
    def apply_blocked_tile(self, coord, turns: int, applies_to: str = 'black', source_color: Optional[str] = None, source_card_name: Optional[str] = None) -> bool:
        """Apply a blocked tile to the board taking iron-wall into account.

        Returns True if the block was applied, False if it was prevented by iron-wall.
        """
        # If the target side is the human player
        try:
            if applies_to == 'white':
                # human side
                human = self.player
                if getattr(human, 'iron_wall_active', False) and source_color is not None and source_color != 'white':
                    # consume iron wall instead of applying
                    human.iron_wall_active = False
                    try:
                        self.log.append(f"鉄壁: 敵の効果 {source_card_name or ''} を防ぎました。")
                    except Exception:
                        pass
                    return False
            else:
                # applies_to == 'black' -> AI side
                if getattr(self, 'ai_iron_wall_active', False) and source_color is not None and source_color != 'black':
                    try:
                        self.ai_iron_wall_active = False
                    except Exception:
                        setattr(self, 'ai_iron_wall_active', False)
                    try:
                        self.log.append(f"鉄壁(敵): プレイヤーの効果 {source_card_name or ''} を防ぎました。")
                    except Exception:
                        pass
                    return False
        except Exception:
            pass

        # Apply the block
        try:
            self.blocked_tiles[coord] = turns
            try:
                self.blocked_tiles_owner[coord] = applies_to
            except Exception:
                pass
        except Exception:
            self.blocked_tiles[coord] = turns
        return True

    def apply_freeze_piece(self, piece_obj, turns: int, target_color: Optional[str] = None, source_color: Optional[str] = None, source_card_name: Optional[str] = None) -> bool:
        """Apply freeze to a piece (engine piece or other) respecting iron-wall.

        Returns True if freeze applied, False if prevented by iron-wall.
        """
        # Determine which side would be affected. Prefer provided target_color.
        try:
            if target_color is None:
                target_color = getattr(piece_obj, 'color', None)
        except Exception:
            target_color = None

        try:
            if target_color == 'white':
                human = self.player
                if getattr(human, 'iron_wall_active', False) and source_color is not None and source_color != 'white':
                    human.iron_wall_active = False
                    try:
                        self.log.append(f"鉄壁: 敵の効果 {source_card_name or ''} を防ぎました。")
                    except Exception:
                        pass
                    return False
            elif target_color == 'black':
                if getattr(self, 'ai_iron_wall_active', False) and source_color is not None and source_color != 'black':
                    try:
                        self.ai_iron_wall_active = False
                    except Exception:
                        setattr(self, 'ai_iron_wall_active', False)
                    try:
                        self.log.append(f"鉄壁(敵): プレイヤーの効果 {source_card_name or ''} を防ぎました。")
                    except Exception:
                        pass
                    return False
        except Exception:
            pass

        # Apply freeze using id-based map
        try:
            self.frozen_pieces[id(piece_obj)] = turns
        except Exception:
            self.frozen_pieces[id(piece_obj)] = turns
        try:
            setattr(piece_obj, 'frozen_turns', turns)
        except Exception:
            pass
        return True

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
            # mark which side originated this pending action so resolution can
            # distinguish incoming vs self-inflicted effects (important for
            # '鉄壁' behavior)
            self.pending.info.setdefault('source_card_name', card.name)
            try:
                self.pending.info.setdefault('source_color', 'white')
            except Exception:
                self.pending.info['source_color'] = 'white'
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
            # ensure pending knows which side caused it
            try:
                self.pending.info.setdefault('source_card_name', card.name)
            except Exception:
                try:
                    self.pending.info['source_card_name'] = card.name
                except Exception:
                    pass
            try:
                self.pending.info.setdefault('source_color', 'white' if player is self.player else 'black')
            except Exception:
                try:
                    self.pending.info['source_color'] = 'white' if player is self.player else 'black'
                except Exception:
                    pass
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
                    # Block up to max_tiles around strategic opponent pieces
                    # Enhanced: consider multiple high-value targets and block escape routes
                    target_candidates = []
                    vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
                    
                    if chess is not None:
                        try:
                            # Collect multiple high-value targets for consideration
                            for p in chess.pieces:
                                if getattr(p, 'color', None) == opp_color:
                                    v = vals.get(getattr(p, 'name', ''), 0)
                                    pr, pc = getattr(p, 'row', None), getattr(p, 'col', None)
                                    if pr is not None and pc is not None and v >= 3:  # Only consider valuable pieces
                                        score = v
                                        # Bonus for pieces near center
                                        center_dist = abs(pr - 3.5) + abs(pc - 3.5)
                                        score += (7 - center_dist) * 0.5
                                        target_candidates.append((p, score))
                        except Exception:
                            pass
                    
                    # Sort by score and pick top target
                    if target_candidates:
                        target_candidates.sort(key=lambda x: x[1], reverse=True)
                        target = target_candidates[0][0]
                    else:
                        target = None
                    
                    if target is not None:
                        tr, tc = getattr(target, 'row', None), getattr(target, 'col', None)
                        placed = 0
                        if tr is not None and tc is not None:
                            # Enhanced blocking strategy: prioritize escape routes and key squares
                            candidates = []
                            max_radius = 3
                            
                            # Calculate scores for each potential blocking square
                            for radius in range(1, max_radius + 1):
                                for dr in range(-radius, radius + 1):
                                    dc_base = radius - abs(dr)
                                    dc_list = [dc_base] if dc_base == 0 else [dc_base, -dc_base]
                                    for dc in dc_list:
                                        nr, nc = tr + dr, tc + dc
                                        if nr is None or nc is None:
                                            continue
                                        if not (0 <= nr < 8 and 0 <= nc < 8):
                                            continue
                                        
                                        # Check if empty
                                        empty = True
                                        if chess is not None:
                                            try:
                                                if chess.get_piece_at(nr, nc) is not None:
                                                    empty = False
                                            except Exception:
                                                empty = True
                                        if not empty:
                                            continue
                                        
                                        # Skip already blocked
                                        if (nr, nc) in self.blocked_tiles:
                                            continue
                                        
                                        # Calculate strategic value of this square
                                        square_score = 10
                                        
                                        # Higher priority for squares closer to target
                                        dist = abs(nr - tr) + abs(nc - tc)
                                        square_score += (4 - dist) * 5
                                        
                                        # Bonus for center squares (more disruptive)
                                        center_dist = abs(nr - 3.5) + abs(nc - 3.5)
                                        square_score += (7 - center_dist) * 2
                                        
                                        # Bonus for blocking key files/ranks
                                        if nc == tc:  # Same column as target
                                            square_score += 8
                                        if nr == tr:  # Same row as target
                                            square_score += 8
                                        
                                        # Bonus for squares that block multiple opponent pieces
                                        try:
                                            blocking_value = 0
                                            for p2 in chess.pieces:
                                                if getattr(p2, 'color', None) == opp_color and p2 != target:
                                                    p2r, p2c = getattr(p2, 'row', None), getattr(p2, 'col', None)
                                                    if p2r is not None and p2c is not None:
                                                        p2_dist = abs(nr - p2r) + abs(nc - p2c)
                                                        if p2_dist <= 2:
                                                            blocking_value += vals.get(getattr(p2, 'name', ''), 0) * 2
                                            square_score += blocking_value
                                        except Exception:
                                            pass
                                        
                                        candidates.append(((nr, nc), square_score))
                                
                                if len(candidates) >= max_tiles * 2:  # Collect enough candidates
                                    break
                            
                            # Sort by strategic value and pick best squares
                            candidates.sort(key=lambda x: x[1], reverse=True)
                            to_place = [pos for pos, score in candidates[:max_tiles]]
                            
                            # Apply blocking
                            applied = []
                            for (nr, nc) in to_place:
                                try:
                                    ok = self.apply_blocked_tile((nr, nc), turns, applies_to=opp_color, source_color=self.pending.info.get('source_color'), source_card_name=self.pending.info.get('source_card_name'))
                                    if ok:
                                        applied.append((nr, nc))
                                except Exception:
                                    try:
                                        self.blocked_tiles[(nr, nc)] = turns
                                        self.blocked_tiles_owner[(nr, nc)] = opp_color
                                        applied.append((nr, nc))
                                    except Exception:
                                        self.blocked_tiles[(nr, nc)] = turns
                                        applied.append((nr, nc))
                            placed = len(applied)
                            if placed:
                                try:
                                    self.log.append(f"AI: 灼熱で封鎖マスを適用しました: {applied}")
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
                best_score = -1
                # Enhanced target selection: consider value, position, and strategic importance
                vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
                
                # Get opponent king position for strategic evaluation
                opp_king_pos = None
                if chess is not None:
                    try:
                        for p in chess.pieces:
                            if getattr(p, 'color', None) == opp_color and getattr(p, 'name', '') == 'K':
                                opp_king_pos = (getattr(p, 'row', 0), getattr(p, 'col', 0))
                                break
                    except Exception:
                        pass
                
                if chess is not None:
                    try:
                        candidates = []
                        # First pass: collect non-king targets with strategic scoring
                        for p in chess.pieces:
                            if getattr(p, 'color', None) == opp_color and getattr(p, 'name', '') != 'K':
                                # Skip already frozen pieces
                                if id(p) in self.frozen_pieces and self.frozen_pieces.get(id(p), 0) > 0:
                                    continue
                                if hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0:
                                    continue
                                
                                v = vals.get(getattr(p, 'name', ''), 0)
                                score = v * 10
                                
                                pr, pc = getattr(p, 'row', None), getattr(p, 'col', None)
                                if pr is not None and pc is not None:
                                    # Bonus for pieces in center (more active)
                                    center_dist = abs(pr - 3.5) + abs(pc - 3.5)
                                    score += (7 - center_dist) * 2
                                    
                                    # Bonus for pieces near opponent's king (defensive target)
                                    if opp_king_pos:
                                        king_dist = abs(pr - opp_king_pos[0]) + abs(pc - opp_king_pos[1])
                                        if king_dist <= 2:
                                            score += 15  # High priority for king's defenders
                                    
                                    # Bonus for advanced pieces (closer to AI's side)
                                    if own_color == 'black':
                                        # Black AI: bonus for white pieces in upper rows (rows 0-3)
                                        if pr <= 3:
                                            score += (4 - pr) * 3
                                    else:
                                        # White AI: bonus for black pieces in lower rows (rows 4-7)
                                        if pr >= 4:
                                            score += (pr - 3) * 3
                                    
                                    # Extra bonus for active pieces (Knights and Bishops in good positions)
                                    pname = getattr(p, 'name', '')
                                    if pname == 'N' and 2 <= pr <= 5 and 2 <= pc <= 5:
                                        score += 8  # Knights in center
                                    elif pname == 'B' and ((pr + pc) % 2 == 0 or (pr + pc) % 2 == 1):
                                        # Bishops on long diagonals
                                        if pr == pc or pr + pc == 7:
                                            score += 6
                                
                                candidates.append((p, score))
                        
                        # Select target with randomization to avoid always picking the same piece
                        if candidates:
                            # Sort by score
                            candidates.sort(key=lambda x: x[1], reverse=True)
                            
                            # Top 40% chance to pick best, 30% for second best, 20% for third, 10% random
                            import random
                            roll = random.random()
                            if roll < 0.40 and len(candidates) >= 1:
                                target = candidates[0][0]
                            elif roll < 0.70 and len(candidates) >= 2:
                                target = candidates[1][0]
                            elif roll < 0.90 and len(candidates) >= 3:
                                target = candidates[2][0]
                            else:
                                # Pick randomly from top half of candidates
                                top_half = candidates[:max(1, len(candidates)//2)]
                                target = random.choice(top_half)[0]
                        
                        # if no non-king targets found, fall back to considering the king
                        if target is None:
                            for p in chess.pieces:
                                if getattr(p, 'color', None) == opp_color and getattr(p, 'name', '') == 'K':
                                    # Only freeze king if not already frozen
                                    if not (id(p) in self.frozen_pieces and self.frozen_pieces.get(id(p), 0) > 0):
                                        target = p
                                    break
                    except Exception:
                        target = None
                if target is not None:
                    try:
                        # Use helper which respects iron-wall
                        applied = self.apply_freeze_piece(target, turns, target_color=opp_color, source_color=self.pending.info.get('source_color'), source_card_name=self.pending.info.get('source_card_name'))
                        # apply_freeze_piece already sets frozen_turns when applied
                    except Exception:
                        try:
                            self.frozen_pieces[id(target)] = turns
                        except Exception:
                            self.frozen_pieces[id(target)] = turns
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
    
    def check_no_lose_trigger(self, player_color: str = 'white') -> bool:
        """「負けるわけないだろwww」カードの発動条件をチェック
        
        発動条件:
        1. 手札に「負けるわけないだろwww」がある
        2. 手札に「摂取」がある
        3. PPが3以上ある
        
        Returns:
            発動可能な場合True
        """
        # プレイヤーかどうかを判定
        if player_color == 'white':
            target_player = self.player
        else:
            # AIの場合は発動しない（プレイヤー専用）
            return False
        
        # 1. PPチェック
        if target_player.pp_current < 3:
            self.log.append(f"[発動失敗] PP不足 (現在: {target_player.pp_current}, 必要: 3)")
            return False
        
        # 2. 手札に「負けるわけないだろwww」があるか
        has_no_lose = any(c.name == "負けるわけないだろwww" for c in target_player.hand.cards)
        if not has_no_lose:
            self.log.append("[発動失敗] 手札に「負けるわけないだろwww」がありません")
            return False
        
        # 3. 手札に「摂取」があるか
        has_leech = any(c.name == "摂取" for c in target_player.hand.cards)
        if not has_leech:
            self.log.append("[発動失敗] 手札に「摂取」がありません")
            return False
        
        self.log.append("[発動可能] 全ての条件を満たしています")
        return True

    def can_auto_no_lose(self, player_color: str = 'white') -> bool:
        """自動発動版の条件チェック。
        仕様: 3PPと手札の『摂取』を消費し、自分が負けるとき自動発動して盤面のみ初期化。

        条件:
        - プレイヤー色がwhite
        - PPが3以上
        - 手札に『負けるわけないだろwww』がある
        - 手札に『摂取』がある
        """
        if player_color != 'white':
            return False
        try:
            if self.player.pp_current < 3:
                self.log.append(f"[自動発動不可] PP不足 (現在: {self.player.pp_current}, 必要: 3)")
                return False
            has_no_lose = any(c.name == "負けるわけないだろwww" for c in self.player.hand.cards)
            if not has_no_lose:
                self.log.append("[自動発動不可] 手札に『負けるわけないだろwww』がありません")
                return False
            has_leech = any(c.name == "摂取" for c in self.player.hand.cards)
            if not has_leech:
                self.log.append("[自動発動不可] 手札に『摂取』がありません")
                return False
            return True
        except Exception:
            return False

    def auto_trigger_no_lose(self, player_color: str = 'white') -> bool:
        """自動発動版『負けるわけないだろwww』。
        3PPと手札の『摂取』を消費し、カードを墓地へ移動、盤面リセット指示（board_reset）を発行する。
        手札・山札・墓地は基本維持（消費した2枚のみ墓地へ）。
        """
        if player_color != 'white':
            return False
        try:
            # 条件確認
            if self.player.pp_current < 3:
                return False
            idx_no_lose = None
            idx_leech = None
            for i, c in enumerate(self.player.hand.cards):
                if c.name == "負けるわけないだろwww" and idx_no_lose is None:
                    idx_no_lose = i
                elif c.name == "摂取" and idx_leech is None:
                    idx_leech = i
                if idx_no_lose is not None and idx_leech is not None:
                    break
            if idx_no_lose is None or idx_leech is None:
                return False
            # 消費（PP→カード2枚を墓地）
            self.player.spend_pp(3)
            card_no_lose = self.player.hand.cards[idx_no_lose]
            self.player.hand.remove_at(idx_no_lose)
            self.player.graveyard.append(card_no_lose)
            # 注意: 摂取のインデックスはズレる可能性があるため再検索
            for j, cj in enumerate(self.player.hand.cards):
                if cj.name == "摂取":
                    idx_leech = j
                    break
            if idx_leech is not None:
                card_leech = self.player.hand.cards[idx_leech]
                self.player.hand.remove_at(idx_leech)
                self.player.graveyard.append(card_leech)
            else:
                # まれに取り違えた場合は失敗扱い
                return False
            # 盤面リセットのpendingを発行
            self.pending = PendingAction(
                kind="board_reset",
                info={"source": "auto_no_lose"}
            )
            self.log.append("★★★ 『負けるわけないだろwww』自動発動！ ★★★")
            self.log.append("盤面を最初の状態にリセットします！")
            return True
        except Exception:
            return False
    
    def trigger_no_lose(self, player_color: str = 'white') -> bool:
        """「負けるわけないだろwww」カードを発動
        
        効果:
        1. 手札から「負けるわけないだろwww」を墓地へ
        2. 手札から「摂取」を墓地へ（発動要件として所持が必要なため消費）
        3. 3PPを消費
        4. 盤面を最初の状態にリセット（手札、山札、墓地はそのまま）をUIへ依頼（pending設定）
        
        Returns:
            発動に成功した場合True
        """
        if player_color == 'white':
            target_player = self.player
        else:
            return False
        
        # カードを手札から探す（両方必要）
        no_lose_idx = None
        leech_idx = None
        for i, c in enumerate(target_player.hand.cards):
            if no_lose_idx is None and c.name == "負けるわけないだろwww":
                no_lose_idx = i
            elif leech_idx is None and c.name == "摂取":
                leech_idx = i
            if no_lose_idx is not None and leech_idx is not None:
                break
        
        if no_lose_idx is None or leech_idx is None:
            # 要件不満足（レースコンディション防止）
            return False
        
        # PPを消費（不足はcheck側で弾くが安全のため再確認）
        if target_player.pp_current < 3:
            self.log.append(f"[発動失敗] PP不足 (現在: {target_player.pp_current}, 必要: 3)")
            return False
        target_player.spend_pp(3)
        
        # カードを墓地に移動（消費）
        try:
            no_lose_card = target_player.hand.cards[no_lose_idx]
            target_player.hand.remove_at(no_lose_idx)
            target_player.graveyard.append(no_lose_card)
        except Exception:
            return False
        # 摂取も消費
        try:
            # インデックスがずれる可能性に注意（no_loseを先に抜いたので再検索）
            leech_idx2 = None
            for i, c in enumerate(target_player.hand.cards):
                if c.name == "摂取":
                    leech_idx2 = i
                    break
            if leech_idx2 is not None:
                leech_card = target_player.hand.cards[leech_idx2]
                target_player.hand.remove_at(leech_idx2)
                target_player.graveyard.append(leech_card)
        except Exception:
            pass
        
        self.log.append(f"★★★ 「負けるわけないだろwww」が発動！ ★★★")
        self.log.append("盤面を最初の状態にリセットします！")
        
        # UIへ盤面リセットのpendingを通知（UI側で安全にボードを初期化・ターン状態を整える）
        try:
            from dataclasses import is_dataclass
            if hasattr(self, 'pending'):
                self.pending = PendingAction(kind='board_reset', info={'source': 'no_lose'})
        except Exception:
            pass
        
        # 発動フラグ（UI側でも参照可能）
        try:
            setattr(self, 'no_lose_triggered', True)
        except Exception:
            pass
        
        return True


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
    # Check if opponent has ironwall protection (暴風 benefits the user, so opponent is affected)
    try:
        if player is game.player:
            # Player using card, AI is affected
            if getattr(game, 'ai_ironwall_protection_turns', 0) > 0:
                return "相手の鉄壁により効果が無効化されました。"
        else:
            # AI using card, player is affected
            if getattr(game, 'player_ironwall_protection_turns', 0) > 0:
                return "鉄壁の保護により効果が無効化されました。"
    except Exception:
        pass
    
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
    # Check if opponent has ironwall protection (迅雷 benefits the user, so opponent is affected)
    try:
        if player is game.player:
            # Player using card, AI is affected
            if getattr(game, 'ai_ironwall_protection_turns', 0) > 0:
                return "相手の鉄壁により効果が無効化されました。"
        else:
            # AI using card, player is affected
            if getattr(game, 'player_ironwall_protection_turns', 0) > 0:
                return "鉄壁の保護により効果が無効化されました。"
    except Exception:
        pass
    
    # Grant one extra full chess turn to the player (so player gets this turn + 1 more).
    # If the effect is played by the human (game.player), set player_consecutive_turns;
    # otherwise (AI) set ai_consecutive_turns so the AI benefits.
    try:
        if player is game.player:
            game.player_consecutive_turns = max(getattr(game, 'player_consecutive_turns', 0), 1)
        else:
            # AIの場合: game属性とglobalsの両方を設定
            game.ai_consecutive_turns = max(getattr(game, 'ai_consecutive_turns', 0), 1)
            # globalsも更新（Card Game.pyで参照される）
            try:
                import sys
                # Card Game.pyのグローバル名前空間を取得
                for module_name, module in sys.modules.items():
                    if hasattr(module, 'ai_consecutive_turns') and module_name.endswith('Card Game'):
                        module.ai_consecutive_turns = game.ai_consecutive_turns
                        break
            except Exception:
                pass
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


def eff_risky_gamble(game: Game, player: PlayerState) -> str:
    """命がけのギャンブル(3): 25%の確率で自分のルーク・キング以外の駒がクイーンに変わる。外れたら相手側が変わる。自ターンスキップ。"""
    import random
    
    # Check if user has ironwall protection (失敗時の不利な効果を防ぐ)
    user_has_protection = False
    # Check if opponent has ironwall protection (成功時の効果を防ぐ)
    opponent_has_protection = False
    try:
        if player is game.player:
            user_has_protection = getattr(game, 'player_ironwall_protection_turns', 0) > 0
            opponent_has_protection = getattr(game, 'ai_ironwall_protection_turns', 0) > 0
        else:
            user_has_protection = getattr(game, 'ai_ironwall_protection_turns', 0) > 0
            opponent_has_protection = getattr(game, 'player_ironwall_protection_turns', 0) > 0
    except Exception:
        pass
    
    success = random.random() < 0.25  # 25%の確率
    
    if success:
        # 当たり: 相手に鉄壁保護があれば無効化
        if opponent_has_protection:
            return "25%の確率に成功！しかし相手の鉄壁により効果は無効化されました。"
        
        # 当たり: 自分のルークとキング以外の駒をクイーンに変更
        game.pending = PendingAction(
            kind="gamble_promote",
            info={
                "target_color": "white",  # プレイヤー側
                "success": True,
            }
        )
        # 成功時はターンスキップを行わない（UI側で判定）
        return "25%の確率に成功！自分のルークとキング以外の駒がクイーンに変わります。"
    else:
        # 外れ: 鉄壁保護があれば失敗効果を無効化
        if user_has_protection:
            # 失敗したが鉄壁により相手への効果は発動しない（ターンスキップは発生）
            return "25%の確率に失敗...しかし鉄壁の保護により相手への効果は無効化されました。自ターンスキップ。"
        
        # 外れ: 相手のルークとキング以外の駒をクイーンに変更
        game.pending = PendingAction(
            kind="gamble_promote",
            info={
                "target_color": "black",  # AI側
                "success": False,
            }
        )
        # 失敗時はターンスキップ
        return "25%の確率に失敗...相手のルークとキング以外の駒がクイーンに変わります。自ターンスキップ。"


def eff_no_lose(game: Game, player: PlayerState) -> str:
    """負けるわけないだろwww(3): 3PPと手札に「摂取」があれば盤面を最初の状態にリセット。
    手動使用時も自動発動と同一処理（カード/摂取/PP消費 + board_reset pending）。"""
    # 使用条件再確認（UI側のprecheck通過後でもレースコンディション対策）
    if not game.check_no_lose_trigger('white'):
        return "条件未達: PP3以上か『摂取』所持が必要です。"
    ok = game.trigger_no_lose('white')
    if ok:
        # trigger_no_loseがpendingを設定済み。手動使用であることをinfoに付加。
        try:
            if game.pending and game.pending.kind == 'board_reset':
                game.pending.info['triggered_by'] = 'manual'
        except Exception:
            pass
        return "「負けるわけないだろwww」発動！盤面を初期状態へリセットします！"
    else:
        return "発動失敗: 手札からカード/摂取を正常に消費できませんでした。"


def precheck_no_lose(game: Game, player: PlayerState) -> dict:
    """「負けるわけないだろwww」の使用条件チェック
    
    使用条件:
    1. 手札に「摂取」がある
    2. PPい3以上ある
    """
    # 1. 手札に「摂取」があるか
    has_leech = any(c.name == "摂取" for c in player.hand.cards)
    if not has_leech:
        return {
            "can_use": False,
            "message": "「負けるわけないだろwww」の使用には\n手札に「摂取」が必要です。"
        }
    
    # 2. PPい3以上あるか（コスト4なので通常はコストチェックで弾かれるが、一応確認）
    if player.pp_current < 3:
        return {
            "can_use": False,
            "message": "「負けるわけないだろwww」の使用には\n3PP以上必要です。"
        }
    
    return {"can_use": True}


def eff_iron_wall(game: Game, player: PlayerState) -> str:
    """鉄壁(2): 二重の防御効果
    1) 次に受ける相手の効果を1回だけ防御（氷結、灼熱など）
    2) 1ターンの間、暴風・迅雷・ハンです☆・命がけギャンブル（成功時/失敗時）の不利な効果を無効化"""
    # プレイヤーに防御フラグを立てる
    if not hasattr(player, 'iron_wall_active'):
        player.iron_wall_active = False
    player.iron_wall_active = True
    
    # Set 1-turn protection from harmful gimmick cards
    try:
        if player is game.player:
            game.player_ironwall_protection_turns = 1
        else:
            game.ai_ironwall_protection_turns = 1
    except Exception:
        pass
    
    # If the effect was applied to the AI's PlayerState, also keep a game-level
    # flag so game-side helpers can check AI iron wall.
    try:
        if player is not game.player:
            setattr(game, 'ai_iron_wall_active', True)
    except Exception:
        pass
    return "鉄壁発動！\n① 次に受ける相手の効果を1回防御\n② 1ターンの間、暴風・迅雷・ハンです☆・命がけギャンブルの効果を無効化"


def eff_hand_discard(game: Game, player: PlayerState) -> str:
    """ハンです☆(2): 相手のカードをランダムで一枚墓地に送る"""
    # Check if opponent has ironwall protection
    try:
        if player is game.player:
            # Player using card, AI is affected
            if getattr(game, 'ai_ironwall_protection_turns', 0) > 0:
                return "相手の鉄壁により効果が無効化されました。"
        else:
            # AI using card, player is affected
            if getattr(game, 'player_ironwall_protection_turns', 0) > 0:
                return "鉄壁の保護により効果が無効化されました。"
    except Exception:
        pass
    
    # pending actionで相手の手札を捨てる処理を保留
    game.pending = PendingAction(
        kind="discard_opponent_hand",
        info={
            "note": "相手の手札からランダムで1枚墓地に送ります",
        }
    )
    return "相手の手札からランダムで1枚墓地に送ります。"


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
        Card("摂取", 1, eff_leech_pp2),
        # ★以下の4枚はデッキビルド専用（ルールデッキには含めない）
        # Card("命がけのギャンブル", 3, eff_risky_gamble),
        Card("負けるわけないだろwww", 3, eff_no_lose, precheck_no_lose),
        Card("鉄壁", 2, eff_iron_wall),
        # Card("ハンです☆", 2, eff_hand_discard),
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
