"""デッキ関連のモーダルダイアログ（スケルトン）

注意: このモジュールは現在スケルトンのみです。
実際の実装はB.B.C.pyに残されており、完全移行は次フェーズで実施されます。
"""

import pygame


def show_deck_choice_modal(screen, W, H, get_font, FONT, SMALL, load_saved_decks=None):
    """デッキ選択モーダル（スケルトン）"""
    # Placeholder implementation
    return False


def show_deck_modal(screen, W, H, get_font, load_saved_decks, show_deck_action_modal_func, battle_select_mode=False):
    """デッキモーダル（スケルトン）"""
    return None


def show_deck_options(screen, W, H, get_font, deck):
    """デッキオプション（スケルトン）"""
    return None


def show_deck_battle_confirm(screen, W, H, get_font, deck, slot_idx):
    """デッキバトル確認（スケルトン）"""
    return False


def show_deck_editor(screen, W, H, get_font, existing_deck, slot_idx):
    """デッキエディタ（スケルトン）"""
    return None


def show_deck_contents_overlay(screen, W, H, get_font, deck):
    """デッキ内容オーバーレイ（スケルトン）"""
    pass


def show_deck_action_modal(screen, W, H, get_font, deck, slot_idx):
    """デッキアクションモーダル（スケルトン）"""
    return None
