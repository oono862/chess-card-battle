"""Game package for card game system management."""

from .deck_manager import (
    DECK_SAVE_FILE,
    load_saved_decks,
    save_decks_to_file,
    list_custom_decks,
    load_custom_deck_by_name,
    build_deck_for_mode,
    build_ai_player,
    build_game_from_card_names,
)
from .turn_manager import start_player_turn, attempt_start_turn, end_player_chess_move, switch_turn

__all__ = [
    'DECK_SAVE_FILE',
    'load_saved_decks',
    'save_decks_to_file',
    'list_custom_decks',
    'load_custom_deck_by_name',
    'build_deck_for_mode',
    'build_ai_player',
    'build_game_from_card_names',
    'start_player_turn',
    'attempt_start_turn',
    'end_player_chess_move',
    'switch_turn',
]
