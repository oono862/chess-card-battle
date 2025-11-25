"""デバッグモジュール"""
from .debug_tools import (
    DEBUG_COUNTER_CHECK_CARD_MODE,
    _debug_mark_card_played,
    debug_setup_castling,
    debug_setup_en_passant,
    debug_setup_promotion,
    debug_reset_initial,
    debug_setup_checkmate,
    debug_setup_counter_check_white,
    debug_setup_simul_check_start,
    set_debug_counter_check_mode,
    get_debug_counter_check_mode
)

__all__ = [
    'DEBUG_COUNTER_CHECK_CARD_MODE',
    '_debug_mark_card_played',
    'debug_setup_castling',
    'debug_setup_en_passant',
    'debug_setup_promotion',
    'debug_reset_initial',
    'debug_setup_checkmate',
    'debug_setup_counter_check_white',
    'debug_setup_simul_check_start',
    'set_debug_counter_check_mode',
    'get_debug_counter_check_mode'
]
