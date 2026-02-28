"""ゲーム画面の描画を担当するモジュール

draw_panel関数から分離された描画ヘルパー関数を提供します。
"""

import pygame
import os


def draw_tutorial_overlay(screen, tutorial_manager, layout, draw_text):
    """チュートリアルオーバーレイを描画する
    
    Args:
        screen: pygame display surface
        tutorial_manager: TutorialManager インスタンス
        layout: レイアウト情報
        draw_text: テキスト描画関数
    """
    if not tutorial_manager:
        return
    
    # enabledでなければ何も表示しない（最優先チェック）
    if not getattr(tutorial_manager, 'enabled', False):
        return
    
    # IS_TUTORIAL_MODEをチェック（CPU戦遷移後は描画しない）
    try:
        import sys
        main_mod = sys.modules.get('__main__')
        if main_mod and not getattr(main_mod, 'IS_TUTORIAL_MODE', False):
            return
    except Exception:
        pass
    
    # チュートリアル完了後の完了ボタン表示
    if getattr(tutorial_manager, 'completed', False):
        _draw_tutorial_completion_screen(screen, tutorial_manager, layout, draw_text)
        return
    
    try:
        tutorial_manager.set_start_button_rect(None)
    except Exception:
        pass

    step = tutorial_manager.get_current_step()
    message = tutorial_manager.get_message()
    
    lock_ui = False
    try:
        lock_ui = bool(getattr(step, 'lock_ui', False) or getattr(tutorial_manager, 'waiting_for_start', False))
    except Exception:
        lock_ui = False
    if not message:
        return
    
    # メッセージボックス描画（画面上部中央、テキスト折り返し対応）
    W = layout.get('screen_width', 1600)
    H = layout.get('screen_height', 900)
    
    box_width = min(1000, int(W * 0.8))
    box_x = (W - box_width) // 2

    # 改行に応じた行分割（簡易）
    lines = message.split("\n") if "\n" in message else [message]
    
    # 完了画面（COMPLETE）の場合のみボタン用スペースを確保
    is_complete_step = False
    try:
        if step and step.step_id == 6:  # COMPLETE (step_id=6) のみ
            is_complete_step = True
    except Exception:
        pass
    
    box_height = max(120, len(lines) * 34 + 60)
    if is_complete_step:
        box_height = max(280, len(lines) * 34 + 120)  # 完了ボタン用のスペースを追加
    
    # lock_ui時は画面中央に配置、それ以外は上部
    if lock_ui and is_complete_step:
        box_y = (H - box_height - 80) // 2  # 中央寄り
    else:
        box_y = 40

    # ハイライト（タイル/駒/カード）と重なる場合は位置を調整する
    try:
        highlight_info = tutorial_manager.get_highlight_info()
        board_left = layout.get('board_left', 0)
        board_top = layout.get('board_top', 0)
        board_size = layout.get('board_size', 800)
        square_w = max(1, board_size // 8)

        highlight_rects = []
        for (r, c) in highlight_info.get('tiles', []):
            try:
                rct = pygame.Rect(board_left + c * square_w, board_top + r * square_w, square_w, square_w)
                highlight_rects.append(rct)
            except Exception:
                pass
        for (r, c) in highlight_info.get('pieces', []):
            try:
                rct = pygame.Rect(board_left + c * square_w, board_top + r * square_w, square_w, square_w)
                highlight_rects.append(rct)
            except Exception:
                pass

        # カード矩形が layout に含まれていればカードのハイライトも考慮
        card_rects = layout.get('card_rects') if isinstance(layout, dict) else None
        for ci in highlight_info.get('cards', []):
            try:
                if card_rects and 0 <= ci < len(card_rects):
                    crect = card_rects[ci]
                    if isinstance(crect, tuple) and len(crect) >= 1:
                        crect = crect[0]
                    if isinstance(crect, pygame.Rect):
                        highlight_rects.append(crect)
                    elif hasattr(crect, '__iter__') and len(crect) >= 4:
                        highlight_rects.append(pygame.Rect(crect[0], crect[1], crect[2], crect[3]))
            except Exception:
                pass

        if highlight_rects:
            # 結合矩形を作成
            union = highlight_rects[0].copy()
            for rct in highlight_rects[1:]:
                union.union_ip(rct)

            msg_rect = pygame.Rect(box_x, box_y, box_width, box_height)
            if msg_rect.colliderect(union):
                # まずボックスをハイライトの下に移す
                candidate_y = union.bottom + 12
                # 画面下に収まるか確認
                if candidate_y + box_height < H - 8:
                    box_y = candidate_y
                else:
                    # 下に入らなければ上に移す
                    candidate_y2 = union.top - box_height - 12
                    if candidate_y2 > 8:
                        box_y = candidate_y2
                    else:
                        # どちらにも入らない場合は上寄せ（既存の40より下にならないよう制限）
                        box_y = max(8, min(box_y, H - box_height - 8))
    except Exception:
        pass

    if lock_ui:
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        screen.blit(dim, (0, 0))

    # 半透明背景
    overlay = pygame.Surface((box_width, box_height))
    overlay.set_alpha(230 if lock_ui else 200)
    overlay.fill((40, 60, 120))
    screen.blit(overlay, (box_x, box_y))

    # 描画したメッセージボックス矩形を tutorial_manager に記録しておく
    try:
        # 他の描画関数（通知、テロップ等）が重なり回避を行えるようにする
        tutorial_manager.last_message_rect = pygame.Rect(box_x, box_y, box_width, box_height)
    except Exception:
        pass
    
    # 枠線
    pygame.draw.rect(screen, (200, 220, 255), (box_x, box_y, box_width, box_height), 3)
    
    # メッセージテキスト（複数行対応）
    text_x = box_x + 24
    text_y = box_y + 20
    for line in lines:
        draw_text(screen, line, text_x, text_y, (255, 255, 255), bold=True, scale=1.0)
        text_y += 32

    # 開始前ロック: 開始ボタンを表示
    try:
        if getattr(tutorial_manager, 'waiting_for_start', False):
            btn_w, btn_h = 180, 48
            btn_x = box_x + (box_width - btn_w) // 2
            btn_y = box_y + box_height - btn_h - 18
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            pygame.draw.rect(screen, (90, 180, 90), btn_rect)
            pygame.draw.rect(screen, (240, 255, 240), btn_rect, 2)
            draw_text(screen, "開始", btn_x + (btn_w // 2) - 22, btn_y + 12, (255, 255, 255), bold=True, scale=1.0)
            tutorial_manager.set_start_button_rect(btn_rect)
            return
    except Exception:
        pass

    # スキップボタン（右下）- Turn 5以外で表示
    try:
        if step and step.step_id < 5:  # Turn 5未満の場合のみスキップボタンを表示
            skip_text = "[ESC: スキップ]"
            skip_x = box_x + box_width - 150
            skip_y = box_y + box_height - 25
            draw_text(screen, skip_text, skip_x, skip_y, (180, 180, 180), scale=0.8)
    except Exception:
        pass


def _draw_tutorial_completion_buttons(screen, tutorial_manager, box_x, box_y, box_width, box_height, draw_text):
    """チュートリアル完了時のボタンを描画"""
    btn_w, btn_h = 180, 45
    spacing = 40
    total_width = btn_w * 2 + spacing
    start_x = box_x + (box_width - total_width) // 2
    btn_y = box_y + box_height - btn_h - 25  # ボックスの中のに配置
    
    # CPU戦へボタン
    cpu_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
    pygame.draw.rect(screen, (60, 140, 200), cpu_rect)
    pygame.draw.rect(screen, (200, 220, 255), cpu_rect, 3)
    draw_text(screen, "CPU戦へ", start_x + 45, btn_y + 10, (255, 255, 255), bold=True, scale=1.1)
    
    # もう一度チュートリアルボタン
    retry_rect = pygame.Rect(start_x + btn_w + spacing, btn_y, btn_w, btn_h)
    pygame.draw.rect(screen, (80, 140, 80), retry_rect)
    pygame.draw.rect(screen, (180, 220, 180), retry_rect, 3)
    draw_text(screen, "もう一度", start_x + btn_w + spacing + 40, btn_y + 10, (255, 255, 255), bold=True, scale=1.1)
    
    # ボタン情報を保存
    try:
        tutorial_manager.completion_cpu_rect = cpu_rect
        tutorial_manager.completion_retry_rect = retry_rect
    except Exception:
        pass


def _draw_tutorial_completion_screen(screen, tutorial_manager, layout, draw_text):
    """チュートリアル完了後の完了画面を描画"""
    W = layout.get('screen_width', 1600)
    H = layout.get('screen_height', 900)
    
    # 半透明オーバーレイ
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 200))
    screen.blit(dim, (0, 0))
    
    # 完了メッセージ
    message = "チュートリアル完了！\n次は実戦で遊んでみましょう"
    box_width = 800
    box_height = 250
    box_x = (W - box_width) // 2
    box_y = (H - box_height) // 2
    
    overlay = pygame.Surface((box_width, box_height))
    overlay.set_alpha(240)
    overlay.fill((40, 60, 120))
    screen.blit(overlay, (box_x, box_y))
    pygame.draw.rect(screen, (200, 220, 255), (box_x, box_y, box_width, box_height), 3)
    
    # メッセージテキスト
    lines = message.split("\n")
    text_y = box_y + 40
    for line in lines:
        text_x = box_x + (box_width - len(line) * 16) // 2
        draw_text(screen, line, text_x, text_y, (255, 255, 255), bold=True, scale=1.2)
        text_y += 40
    
    _draw_tutorial_completion_buttons(screen, tutorial_manager, box_x, box_y, box_width, box_height, draw_text)


def draw_tutorial_highlights(screen, tutorial_manager, board_left, board_top, square_w, square_h, 
                             card_rects, layout):
    """チュートリアルハイライトを描画する
    
    Args:
        screen: pygame display surface
        tutorial_manager: TutorialManager インスタンス
        board_left, board_top: チェス盤の左上座標
        square_w, square_h: マスのサイズ
        card_rects: カードの矩形リスト
        layout: レイアウト情報
    """
    if not tutorial_manager or not tutorial_manager.enabled:
        return
    
    highlight_info = tutorial_manager.get_highlight_info()
    
    # Turn 5（チェックメイト）かどうかを判定
    is_checkmate_phase = False
    try:
        from game.tutorial import TutorialPhase
        if hasattr(tutorial_manager, 'state') and tutorial_manager.state.phase == TutorialPhase.TURN5_CHECKMATE:
            is_checkmate_phase = True
    except Exception:
        pass
    
    # マスのハイライト（Turn 5は赤色、それ以外は黄色）
    tile_color = (255, 50, 50) if is_checkmate_phase else (255, 255, 0)
    for (row, col) in highlight_info['tiles']:
        rect = pygame.Rect(
            board_left + col * square_w,
            board_top + row * square_h,
            square_w,
            square_h
        )
        # Turn 5の場合は太い枠と半透明の塗りつぶし
        if is_checkmate_phase:
            # 半透明の赤い塗りつぶし
            highlight_surf = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
            highlight_surf.fill((255, 50, 50, 80))
            screen.blit(highlight_surf, rect.topleft)
            pygame.draw.rect(screen, tile_color, rect, 6)
        else:
            pygame.draw.rect(screen, tile_color, rect, 5)
    
    # 駒のハイライト（緑の枠）
    for (row, col) in highlight_info['pieces']:
        rect = pygame.Rect(
            board_left + col * square_w,
            board_top + row * square_h,
            square_w,
            square_h
        )
        pygame.draw.rect(screen, (0, 255, 100), rect, 5)
    
    # カードのハイライト（青の枠）
    for card_idx in highlight_info['cards']:
        if 0 <= card_idx < len(card_rects):
            rect_data = card_rects[card_idx]
            # card_rectsは (pygame.Rect, インデックス) のタプル形式の場合がある
            try:
                if isinstance(rect_data, tuple) and len(rect_data) >= 1:
                    # タプルの最初の要素がRect
                    rect = rect_data[0]
                else:
                    rect = rect_data
                
                if isinstance(rect, pygame.Rect):
                    pygame.draw.rect(screen, (100, 200, 255), rect, 5)
                elif rect is not None and hasattr(rect, '__iter__') and len(rect) >= 4:
                    r = pygame.Rect(rect[0], rect[1], rect[2], rect[3])
                    pygame.draw.rect(screen, (100, 200, 255), r, 5)
            except Exception as e:
                pass  # エラーは無視


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
