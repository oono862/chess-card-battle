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
from typing import Callable, List, Optional, Tuple
import random


# -----------------------------
# Data models
# -----------------------------

EffectFn = Callable[["Game", "PlayerState"], str]


@dataclass
class Card:
    name: str
    cost: int
    effect: EffectFn

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
    turn: int = 1
    log: List[str] = field(default_factory=list)

    def setup_battle(self) -> None:
        """Initial draw of 4 cards at battle start and PP reset."""
        self.player.reset_pp()
        for _ in range(4):
            drawn = self.player.deck.draw()
            if drawn:
                self.player.hand.add(drawn)
        self.log.append("Battle start: drew 4 cards, PP reset to max.")

    def start_turn(self) -> None:
        """At the start of each turn: draw 1 and restore PP to max."""
        self.turn += 1 if self.turn > 0 else 1
        self.player.reset_pp()
        drawn = self.player.deck.draw()
        if drawn:
            self.player.hand.add(drawn)
            self.log.append(f"Turn {self.turn} start: drew '{drawn.name}', PP restored to {self.player.pp_max}.")
        else:
            self.log.append(f"Turn {self.turn} start: deck empty, PP restored to {self.player.pp_max}.")

    def play_card(self, hand_index: int) -> Tuple[bool, str]:
        """Attempt to play a card from hand; returns (success, message)."""
        if not (0 <= hand_index < len(self.player.hand.cards)):
            return False, "Invalid hand index."
        card = self.player.hand.cards[hand_index]
        if not card.can_play(self.player):
            return False, f"Not enough PP ({self.player.pp_current}) for '{card.name}' (cost {card.cost})."
        # Spend PP and resolve effect
        assert self.player.spend_pp(card.cost)
        self.player.hand.remove_at(hand_index)
        self.player.graveyard.append(card)
        msg = card.effect(self, self.player)
        msg_full = f"Played '{card.name}' (cost {card.cost}). {msg} PP now {self.player.pp_current}/{self.player.pp_max}."
        self.log.append(msg_full)
        return True, msg_full


# -----------------------------
# Sample effects and a small sample card pool
# -----------------------------

def eff_draw1(game: Game, player: PlayerState) -> str:
    c = player.deck.draw()
    if c is None:
        return "Deck empty: could not draw."
    player.hand.add(c)
    return f"Drew '{c.name}'."


def eff_gain_pp1(game: Game, player: PlayerState) -> str:
    before = player.pp_current
    player.pp_current = min(player.pp_current + 1, player.pp_max)
    return f"PP +1 ({before}->{player.pp_current})."


def eff_placeholder_extra_move(game: Game, player: PlayerState) -> str:
    # Placeholder for chess integration, e.g., grant an extra move this turn
    return "Grant an extra chess move (placeholder)."


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


__all__ = [
    "Card",
    "Deck",
    "Hand",
    "PlayerState",
    "Game",
    "new_game_with_sample_deck",
]
