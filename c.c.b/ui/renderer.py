"""ゲーム画面の描画を担当するモジュール

draw_panel関数から分離された描画ヘルパー関数を提供します。
"""

import pygame
import os


def draw_background(screen, W, H, play_bg_img, play_bg_surf, PLAY_BG_FILENAME, IMG_DIR):
    """背景を描画する
    
    Args:
        screen: pygame display surface
        W, H: ウィンドウサイズ
        play_bg_img: キャッシュされた元画像
        play_bg_surf: キャッシュされたスケール済み画像
        PLAY_BG_FILENAME: 背景画像ファイル名
        IMG_DIR: 画像ディレクトリパス
        
    Returns:
        tuple: (play_bg_img, play_bg_surf) 更新されたキャッシュ
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


def draw_left_panel_info(screen, game, layout, draw_text, get_opponent_hand_count):
    """左パネルに基本情報を描画する
    
    Returns:
        dict: 描画された要素の矩形情報と次のY座標
    """
    left_margin = layout['left_margin']
    top_margin = layout['board_area_top']
    info_x = left_margin
    info_y = top_margin
    left_line_step = 44
    
    # ターン数
    draw_text(screen, f"ターン: {game.turn}", info_x, info_y, bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # PP
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", info_x, info_y, bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 簡易エフェクト表示
    if getattr(game.player, 'next_move_can_jump', False):
        draw_text(screen, "次：飛越可", info_x, info_y, (10, 40, 180), scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    
    # 迅雷効果の表示
    consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    if consecutive_turns > 0:
        info_y += 6
        label = "次：追加行動" if consecutive_turns == 1 else f"次：追加行動×{consecutive_turns}"
        draw_text(screen, label, info_x, info_y, (10, 120, 10), scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    info_y += left_line_step
    
    # 山札
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", info_x, info_y, (40,40,90), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 墓地表示
    grave_text = f"墓地: {len(game.player.graveyard)}枚"
    grave_label_rect = draw_text(screen, grave_text, info_x, info_y, (90,40,40), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 相手の手札表示
    opponent_hand_text = f"相手の手札: {get_opponent_hand_count()}枚"
    opponent_hand_rect = draw_text(screen, opponent_hand_text, info_x, info_y, (100,50,100), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    return {
        'grave_label_rect': grave_label_rect,
        'opponent_hand_rect': opponent_hand_rect,
        'info_y': info_y,
        'info_x': info_x
    }


def draw_turn_start_button(screen, info_x, info_y, game, chess_current_turn, cpu_wait, game_over, layout, get_font):
    """ターン開始ボタンを描画する
    
    Returns:
        pygame.Rect: ボタンの矩形
    """
    btn_w, btn_h = 160, 36
    start_turn_rect = pygame.Rect(info_x, info_y, btn_w, btn_h)
    
    # 押下可否に応じて色分け
    can_start = (
        getattr(game, 'pending', None) is None and
        not getattr(game, 'turn_active', False) and
        chess_current_turn == 'white' and
        not cpu_wait and
        not game_over
    )
    bg_col = (60, 140, 220) if can_start else (140, 140, 140)
    
    pygame.draw.rect(screen, bg_col, start_turn_rect)
    pygame.draw.rect(screen, (255,255,255), start_turn_rect, 2)
    
    # ボタンラベル
    ui_scale = layout.get('scale', 1.0)
    try:
        btn_font = get_font(max(12, int(18 * ui_scale)), bold=True)
        lab = btn_font.render("バトル開始 (T)", True, (255,255,255))
        screen.blit(lab, (start_turn_rect.x + (btn_w - lab.get_width())//2, start_turn_rect.y + (btn_h - lab.get_height())//2))
    except Exception:
        pass
    
    return start_turn_rect


def draw_pending_info(screen, game, info_x, info_y, draw_text, line_height=35):
    """保留中表示を描画する
    
    Returns:
        int: 更新されたY座標
    """
    if getattr(game, 'pending', None) is not None:
        info_y += line_height + 10
        label = game.pending.kind
        src = game.pending.info.get('source_card_name')
        if src:
            label = f"{src} ({label})"
        draw_text(screen, f"⚠ 保留中:", info_x, info_y, (180, 60, 0))
        info_y += 20
        draw_text(screen, label, info_x, info_y, (180, 60, 0))
    
    return info_y


def draw_help_section(screen, layout, HELP_FONT, HELP_LINES):
    """ヘルプセクションを描画する"""
    help_x = layout['right_panel_x'] + 12
    help_y = layout['board_top']
    
    try:
        header_s = HELP_FONT.render("操作:", True, (60, 60, 100))
        screen.blit(header_s, (help_x, help_y))
    except Exception:
        pass
    
    help_y += 44
    for hl in HELP_LINES:
        try:
            line_s = HELP_FONT.render(hl, True, (30, 30, 90))
            screen.blit(line_s, (help_x, help_y))
        except Exception:
            pass
        help_y += 40


def draw_chess_board_grid(screen, board_left, board_top, square_w, square_h, board_size):
    """チェス盤のグリッドを描画する"""
    light = (235, 248, 240)
    dark = (200, 220, 200)
    
    try:
        pygame.draw.rect(screen, (200, 220, 200), (board_left, board_top, board_size, board_size))
        pygame.draw.rect(screen, (120, 140, 120), (board_left, board_top, board_size, board_size), 2)
    except Exception:
        pass
    
    for rr in range(8):
        for cc in range(8):
            rrect = pygame.Rect(board_left + cc*square_w, board_top + rr*square_h, square_w, square_h)
            pygame.draw.rect(screen, light if (rr+cc)%2==0 else dark, rrect)


def draw_pieces(screen, chess_pieces, board_left, board_top, square_w, square_h, get_piece_image_surface, SMALL):
    """駒を描画する"""
    for p in chess_pieces:
        cell_x = board_left + p.col*square_w
        cell_y = board_top + p.row*square_h
        padding = max(6, int(square_w * 0.08))
        img_w = square_w - padding*2
        img_h = square_h - padding*2
        
        img = get_piece_image_surface(p.name, p.color, (img_w, img_h))
        if img is not None:
            screen.blit(img, (cell_x + padding, cell_y + padding))
        else:
            # フォールバック描画
            cx = cell_x + square_w//2
            cy = cell_y + square_h//2
            radius = min(square_w, square_h)//2 - padding
            if p.color == 'white':
                pygame.draw.circle(screen, (250,250,250), (cx,cy), radius)
                label = SMALL.render(p.name, True, (0,0,0))
            else:
                pygame.draw.circle(screen, (40,40,40), (cx,cy), radius)
                label = SMALL.render(p.name, True, (255,255,255))
            screen.blit(label, (cx - label.get_width()//2, cy - label.get_height()//2))
