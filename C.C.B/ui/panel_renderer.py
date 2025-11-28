"""パネル描画モジュール

このモジュールは、ゲームの主要なUIパネル（ボード、カード、ログなど）の
描画処理を担当します。元々Card Game.py内にあった巨大なdraw_panel()関数を
モジュール化したものです。
"""

import pygame
import os
import sys

# このモジュールは Card Game.py から呼び出されるため、
# グローバル変数への参照が必要です。
# 将来的にはこれらを引数として渡す設計に変更することが望ましいです。

def draw_panel(
    screen,
    W, H,
    game,
    chess,
    selected_piece,
    highlight_squares,
    chess_current_turn,
    game_over,
    game_over_winner,
    confirm_yes_rect,
    confirm_no_rect,
    start_turn_rect,
    grave_label_rect,
    opponent_hand_rect,
    grave_card_rects,
    scrollbar_rect,
    log_scroll_offset,
    _max_scroll,
    show_log,
    show_grave,
    show_opp_hand,
    heat_choice_unfreeze_rect,
    heat_choice_block_rect,
    card_rects,
    FONT,
    SMALL,
    TINY,
    get_font,
    IMG_DIR,
    PLAY_BG_FILENAME,
    play_bg_img,
    play_bg_surf,
    log_toggle_rect,
    HELP_LINES,
    turn_telop_msg,
    turn_telop_until,
    notice_msg,
    notice_until,
    # 追加のグローバル変数参照
):
    """メインゲーム画面の描画処理
    
    NOTE: この関数は元々Card Game.py内に約1590行の巨大関数として存在していました。
    TODO: 将来的にはさらに細分化し、以下のような小さな関数に分割することが望ましいです:
        - draw_background()
        - draw_chess_board()
        - draw_cards()
        - draw_log_panel()
        - draw_grave_panel()
        - draw_ui_controls()
        - draw_turn_indicators()
    """
    # 元のdraw_panel()の実装をここに移動予定
    # 現時点では、Card Game.pyから段階的に移行していきます
    pass


def draw_background(screen, W, H, IMG_DIR, PLAY_BG_FILENAME, play_bg_img, play_bg_surf):
    """背景画像の描画
    
    Args:
        screen: pygame display surface
        W, H: ウィンドウサイズ
        IMG_DIR: 画像ディレクトリパス
        PLAY_BG_FILENAME: 背景画像ファイル名
        play_bg_img: キャッシュされた元画像
        play_bg_surf: スケール済みサーフェス
        
    Returns:
        tuple: (play_bg_img, play_bg_surf) 更新された画像キャッシュ
    """
    try:
        # 初回: 画像ファイルがあればロードしてキャッシュ
        if play_bg_img is None and play_bg_surf is None:
            try:
                bg_path = os.path.join(IMG_DIR, PLAY_BG_FILENAME)
                if os.path.exists(bg_path):
                    play_bg_img = pygame.image.load(bg_path)
            except Exception:
                play_bg_img = None

        # play_bg_img が存在すれば現在のウィンドウサイズに合わせてスケールして描画
        if play_bg_img is not None:
            try:
                play_bg_surf = pygame.transform.smoothscale(play_bg_img, (W, H)).convert()
                screen.blit(play_bg_surf, (0, 0))
            except Exception:
                # スケーリングや描画に失敗した場合は単色で塗りつぶす
                screen.fill((240, 240, 245))
        else:
            screen.fill((240, 240, 245))
    except Exception:
        # どこかで例外が出ても UI が壊れないようにフォールバック
        try:
            screen.fill((240, 240, 245))
        except Exception:
            pass
    
    return play_bg_img, play_bg_surf
