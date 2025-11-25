"""UI オーバーレイ表示（ログ、墓地、拡大カードなど）"""
import pygame


# スクロールバー関連のグローバル状態
scrollbar_rect = None
dragging_scrollbar = False
drag_start_y = 0
drag_start_offset = 0


def draw_log_panel(screen, game, show_log, log_scroll_offset, layout, W, H, board_area_top, board_area_height, board_top, board_size, board_right):
    """ログパネルを描画する
    
    Args:
        screen: pygame surface
        game: Game instance
        show_log: ログを表示するかどうか
        log_scroll_offset: スクロールオフセット
        layout: compute_layout()で計算されたレイアウト情報
        W, H: ウィンドウサイズ
        board_area_top: ボードエリアのトップ位置
        board_area_height: ボードエリアの高さ
        board_top: ボードのトップ位置
        board_size: ボードのサイズ
        board_right: ボードの右端位置
        
    Returns:
        tuple: (log_scroll_offset, log_toggle_rect or None)
    """
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    
    # Import dependencies
    try:
        from .layout import draw_text, wrap_text
        from .config import FONT, HELP_FONT
    except ImportError:
        try:
            from CCB.ui.layout import draw_text, wrap_text
            from CCB.ui.config import FONT, HELP_FONT
        except ImportError:
            # Fallback for direct execution
            import sys
            if 'B.B.C' in sys.modules:
                main = sys.modules['B.B.C']
                draw_text = main.draw_text
                wrap_text = main.wrap_text
                FONT = main.FONT
                HELP_FONT = main.HELP_FONT
            else:
                raise
    
    board_area_left = layout.get('board_area_left', layout['left_margin'])
    board_area_width = layout.get('board_area_width', board_size)
    
    if show_log:
        # Preferred log panel sits to the right of the board when enough room exists.
        # Make the preferred width a bit larger so normal windows get a readable panel.
        preferred_w = max(360, min(520, layout.get('right_panel_width', 360)))
        # If this is a scaled / fullscreen (拡大画面) UI, allow a wider preferred width
        ui_scale = layout.get('scale', 1.0)
        if ui_scale > 1.15:
            # only increase preferred_w for expanded screens; keep standard screens unchanged
            # grow the log to use at least ~75% of the right-side available area (without overlapping the board)
            gap_exp = int(28 * ui_scale)
            right_margin_exp = 12
            max_right_space = max(0, W - (board_right + gap_exp) - right_margin_exp)
            # safety subtract to avoid 1px overlaps
            safety = 8
            if max_right_space > 200:
                # target to occupy ~75% of the available right-side space, clamped so it never exceeds the space
                target75 = int(max_right_space * 0.75)
                use_w = max(target75, 420)
                use_w = min(use_w, max(0, max_right_space - safety))
                preferred_w = max(preferred_w, use_w)
            else:
                # if not much room, fall back to the scaled target but don't change standard behavior
                preferred_w = max(preferred_w, min(912, int(520 * ui_scale * 1.2)))
        
        scale = layout.get('scale', 1.0)
        gap = int(28 * scale)
        right_margin = 12
        available_right_space = W - (board_right + gap) - right_margin

        # Default: try to place on the right with preferred width
        if available_right_space >= preferred_w:
            log_panel_left = board_right + gap
            log_panel_top = board_area_top
            log_panel_width = preferred_w
            log_panel_height = min(board_area_height, max(220, H - log_panel_top - 24))
        else:
            # Not enough horizontal room: attempt to place below the board between board and hand
            space_below_board = max(0, layout.get('card_area_top', H) - (board_top + board_size))
            if space_below_board >= 160:
                log_panel_left = layout['left_margin']
                log_panel_top = board_top + board_size + int(12 * scale)
                log_panel_width = min(preferred_w, W - 2 * layout['left_margin'] - 24)
                log_panel_height = min(space_below_board - 12, 420)
            else:
                # fallback: try to sit to the right but shrink width to the available space
                use_w = max(220, min(preferred_w, available_right_space)) if available_right_space > 0 else 0
                if use_w > 0 and (board_right + gap + use_w + right_margin) <= W:
                    log_panel_left = board_right + gap
                    log_panel_top = board_area_top
                    log_panel_width = use_w
                    log_panel_height = min(board_area_height, max(200, H - log_panel_top - 24))
                else:
                    # last resort: force fit the panel to the far right and reduce width to avoid overlap
                    forced_w = max(200, W - board_right - gap - right_margin)
                    if forced_w >= 200:
                        log_panel_left = board_right + gap
                        log_panel_top = board_area_top
                        log_panel_width = forced_w
                        log_panel_height = min(board_area_height, max(180, H - log_panel_top - 24))
                    else:
                        # give up on right side, place below the board full-width within margins
                        log_panel_left = layout['left_margin']
                        log_panel_top = board_top + board_size + int(12 * scale)
                        log_panel_width = min(preferred_w, W - 2 * layout['left_margin'] - 24)
                        log_panel_height = min(space_below_board - 12 if 'space_below_board' in locals() else 200, 420)

        # clamp to absolute maxima so huge monitors don't create gigantic panels
        MAX_LOG_W = 640
        MAX_LOG_H = 600
        log_panel_width = min(log_panel_width, MAX_LOG_W)
        log_panel_height = min(log_panel_height, MAX_LOG_H)

        # Ensure the panel is nudged right and fully visible (avoid overlapping board and prevent clipping).
        # Increase the desired gap so the log is pushed farther right (as the user requested),
        # then shrink the panel a bit so it can sit as far right as possible without being cut off.
        # push a bit more to the right as requested (try to keep the current width)
        desired_right_gap = int(112 * layout.get('scale', 1.0))
        right_margin = 12
        min_gap_to_board = int(8 * layout.get('scale', 1.0))
        desired_left = max(log_panel_left, board_right + desired_right_gap)

        # Prefer moving the panel to desired_left WITHOUT shrinking width
        if desired_left + log_panel_width + right_margin <= W:
            log_panel_left = desired_left
        else:
            # Can't place at desired_left with current width. Try to push it as far right as possible while keeping width.
            max_left = W - log_panel_width - right_margin
            if max_left >= board_right + min_gap_to_board:
                # push to the far right but keep width
                log_panel_left = max_left
            else:
                # As a last resort (very narrow window), allow minimal shrinking so it can sit at desired_left
                shrink_w = W - desired_left - right_margin
                if shrink_w >= min_gap_to_board and shrink_w >= 180:
                    log_panel_width = shrink_w
                    log_panel_left = desired_left
                else:
                    # fallback: place at max_left (may overlap slightly if window is too narrow)
                    log_panel_left = max(layout['left_margin'], max_left)

        # Final safety clamp to ensure we never draw off-screen
        if log_panel_left + log_panel_width + right_margin > W:
            log_panel_left = max(layout['left_margin'], W - log_panel_width - right_margin)

        # Force the log panel to be flush-right: try to keep its width but if that would overlap
        # shrink the width until it can be right-aligned without covering the board.
        try:
            scale = layout.get('scale', 1.0)
            right_margin = 12
            min_gap = int(8 * scale)
            # target fixed width (a bit narrower for safety)
            # increase fixed width on expanded/fullscreen to make the log bigger there only
            if layout.get('scale', 1.0) > 1.15:
                # larger fixed width for expanded screens; try to use most of the right space
                gap_exp = int(28 * layout.get('scale', 1.0))
                right_margin_exp = 12
                max_right_space = max(0, W - (board_right + gap_exp) - right_margin_exp)
                if max_right_space > 360:
                    # use ~75% of right space for fixed width, leave a small safety gap
                    FIXED_LOG_W = int(max_right_space * 0.75)
                    FIXED_LOG_W = max(FIXED_LOG_W, 420)
                    FIXED_LOG_W = min(FIXED_LOG_W, max_right_space - 8)
                else:
                    FIXED_LOG_W = int(520 * 1.2)
            else:
                FIXED_LOG_W = 300
            target_w = min(log_panel_width, FIXED_LOG_W)
            # maximum width allowed so the panel's left edge is at least `min_gap` from the board
            max_allowed_w = W - (board_right + min_gap) - right_margin
            if max_allowed_w < 20:
                max_allowed_w = 20
            # choose the smaller of target and allowed
            final_w = min(target_w, max_allowed_w)
            # ensure final width is at least a small readable minimum when possible
            if max_allowed_w >= 160:
                final_w = max(160, final_w)
            else:
                final_w = max(20, final_w)

            # set width and right-align (flush to right_margin)
            log_panel_width = int(final_w)
            log_panel_left = max(layout['left_margin'], W - log_panel_width - right_margin)
        except Exception:
            pass

        # ログパネル背景
        pygame.draw.rect(screen, (250, 250, 255),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height))
        pygame.draw.rect(screen, (100, 100, 120),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height), 2)

        # タイトル（クリックで閉じる）
        # 1行分の余白をタイトル上部に入れる（視認性向上）
        top_line_h = FONT.get_height()
        log_toggle_rect = draw_text(screen, "ログ履歴 [L]閉じる", log_panel_left + 10, log_panel_top + 8 + top_line_h, (60, 60, 100))
        # 見出しのすぐ下にスクロールのヒントを表示
        draw_text(screen, "↑↓ / ホイールでスクロール", log_panel_left + 10, log_panel_top + 30 + top_line_h, (100, 100, 120))

        # ログの折り返し処理
        wrapped_lines = []
        max_log_width = log_panel_width - 30
        for line in game.log:
            for wline in wrap_text(f"• {line}", max_log_width):
                wrapped_lines.append(wline)

        # スクロールオフセットの範囲制限
        # 行高さは現在のフォントから取得し、各文章ごとに1行分の余白を入れる
        line_h = FONT.get_height()
        # 表示行のステップはテキスト行 + 空行分（＝行高 * 2）
        line_step = line_h * 2
        # 下部に余白を設けて見やすくする（最後の行が枠にくっつかないように）
        bottom_padding_px = 28  # ここを調整すると余白サイズを変更できます
        max_lines_visible = max(0, (log_panel_height - 50 - bottom_padding_px) // line_step)
        max_scroll = max(0, len(wrapped_lines) - max_lines_visible)
        log_scroll_offset = max(0, min(log_scroll_offset, max_scroll))

        # 表示範囲を計算（最新が下）
        if len(wrapped_lines) <= max_lines_visible:
            visible_lines = wrapped_lines
        else:
            start_idx = len(wrapped_lines) - max_lines_visible - log_scroll_offset
            start_idx = max(0, start_idx)
            visible_lines = wrapped_lines[start_idx:start_idx + max_lines_visible]

        # ログ描画開始位置（見出しとヒントの下）
        # 先ほどタイトルの上に1行分の余白を入れたので、描画開始位置も同じ分だけ下げる
        log_y = log_panel_top + 56 + top_line_h
        for wline in visible_lines:
            if log_y < log_panel_top + log_panel_height - bottom_padding_px:
                draw_text(screen, wline, log_panel_left + 10, log_y, (60, 60, 60))
                # 次の文章は空行を挟んで描画する
                log_y += line_step

        # スクロールバー表示
        if max_scroll > 0:
            # スクロールバーのエリア
            scrollbar_x = log_panel_left + log_panel_width - 15
            scrollbar_y = log_panel_top + 56
            scrollbar_height = log_panel_height - 66
            scrollbar_width = 8
            # 背景（グレー）
            pygame.draw.rect(screen, (200, 200, 200), 
                           (scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height))
            # スクロール位置を計算
            total_lines = len(wrapped_lines)
            scroll_ratio = log_scroll_offset / max_scroll if max_scroll > 0 else 0
            # つまみのサイズと位置
            thumb_height = max(20, scrollbar_height * max_lines_visible / total_lines)
            thumb_y = scrollbar_y + (scrollbar_height - thumb_height) * (1 - scroll_ratio)
            # つまみ（濃いグレー）
            pygame.draw.rect(screen, (100, 100, 100), 
                           (scrollbar_x, thumb_y, scrollbar_width, thumb_height))
            # スクロールバーの矩形を保存（ドラッグ用）
            scrollbar_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        else:
            scrollbar_rect = None
            
        return log_scroll_offset, log_toggle_rect
    else:
        # ログ非表示時のヒント (右パネルに寄せる)
        # Make the label more visible by using a bolder font if available.
        try:
            lbl_font = HELP_FONT if HELP_FONT else pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
            lbl_s = lbl_font.render("[L] ログ表示", True, (80, 80, 110))
            screen.blit(lbl_s, (layout['right_panel_x'] + 12, board_area_top + board_area_height - 30))
        except Exception:
            draw_text(screen, "[L] ログ表示", layout['right_panel_x'] + 12, board_area_top + board_area_height - 30, (100, 100, 120))
        
        return log_scroll_offset, None


def get_scrollbar_state():
    """スクロールバーの状態を取得する
    
    Returns:
        tuple: (scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset)
    """
    return scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset


def set_scrollbar_state(rect, dragging, start_y, start_offset):
    """スクロールバーの状態を設定する
    
    Args:
        rect: スクロールバーの矩形
        dragging: ドラッグ中かどうか
        start_y: ドラッグ開始Y座標
        start_offset: ドラッグ開始時のオフセット
    """
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    scrollbar_rect = rect
    dragging_scrollbar = dragging
    drag_start_y = start_y
    drag_start_offset = start_offset


# 墓地カード矩形のグローバル状態
grave_card_rects = []


def draw_grave_overlay(screen, game, show_grave, W, H):
    """墓地オーバーレイを描画する
    
    Args:
        screen: pygame surface
        game: Game instance
        show_grave: 墓地を表示するかどうか
        W, H: ウィンドウサイズ
        
    Returns:
        list: 墓地カード矩形のリスト [(rect, card_name), ...]
    """
    global grave_card_rects
    
    if not show_grave:
        grave_card_rects = []
        return grave_card_rects
    
    # Import dependencies
    try:
        from .layout import draw_text
        from ..assets.image_loader import get_card_image
    except ImportError:
        try:
            from CCB.ui.layout import draw_text
            from CCB.assets.image_loader import get_card_image
        except ImportError:
            # Fallback for direct execution
            import sys
            if 'B.B.C' in sys.modules:
                main = sys.modules['B.B.C']
                draw_text = main.draw_text
                get_card_image = main.get_card_image
            else:
                raise
    
    overlay_w = 600
    overlay_h = 500
    overlay_x = (W - overlay_w) // 2
    overlay_y = (H - overlay_h) // 2
    
    overlay = pygame.Surface((overlay_w, overlay_h))
    overlay.fill((255, 255, 255))
    overlay.set_alpha(245)
    screen.blit(overlay, (overlay_x, overlay_y))
    
    pygame.draw.rect(screen, (100, 100, 100), (overlay_x, overlay_y, overlay_w, overlay_h), 3)
    
    draw_text(screen, "墓地のカード一覧 [G]で閉じる", overlay_x + 20, overlay_y + 20, (120, 0, 0))
    draw_text(screen, "カードをクリックで拡大表示", overlay_x + 320, overlay_y + 20, (80, 80, 80))
    
    counts = {}
    for c in game.player.graveyard:
        counts[c.name] = counts.get(c.name, 0) + 1
    
    gy = overlay_y + 60
    gx = overlay_x + 30
    col_w = 280
    grave_card_rects = []
    for name, cnt in sorted(counts.items()):
        thumb = get_card_image(name, size=(70, 95))
        screen.blit(thumb, (gx, gy))
        draw_text(screen, f"{name}: {cnt}枚", gx + 80, gy + 35)
        # クリック用の矩形を保存
        grave_card_rects.append((pygame.Rect(gx, gy, 70, 95), name))
        gy += 110
        if gy > overlay_y + overlay_h - 80:
            gy = overlay_y + 60
            gx += col_w
            if gx > overlay_x + overlay_w - 100:
                break
    
    return grave_card_rects


def draw_opponent_hand_overlay(screen, get_opponent_hand_count, show_opponent_hand, W, H):
    """相手の手札オーバーレイを描画する
    
    Args:
        screen: pygame surface
        get_opponent_hand_count: 相手の手札数を取得する関数
        show_opponent_hand: 相手の手札を表示するかどうか
        W, H: ウィンドウサイズ
    """
    if not show_opponent_hand:
        return
    
    # Import dependencies
    try:
        from .layout import draw_text
    except ImportError:
        try:
            from CCB.ui.layout import draw_text
        except ImportError:
            # Fallback for direct execution
            import sys
            if 'B.B.C' in sys.modules:
                main = sys.modules['B.B.C']
                draw_text = main.draw_text
            else:
                raise
    
    overlay_w = 600
    overlay_h = 500
    overlay_x = (W - overlay_w) // 2
    overlay_y = (H - overlay_h) // 2
    
    overlay = pygame.Surface((overlay_w, overlay_h))
    overlay.fill((230, 230, 240))
    overlay.set_alpha(245)
    screen.blit(overlay, (overlay_x, overlay_y))
    
    pygame.draw.rect(screen, (100, 100, 120), (overlay_x, overlay_y, overlay_w, overlay_h), 3)
    
    draw_text(screen, f"相手の手札 ({get_opponent_hand_count()}枚) [H]で閉じる", overlay_x + 20, overlay_y + 20, (100, 50, 100))
    
    # カード裏面を横並びで表示（画像未実装のため仮の矩形）
    card_back_w = 70
    card_back_h = 95
    start_x = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count(), 7) + 10 * (min(get_opponent_hand_count(), 7) - 1))) // 2
    cy = overlay_y + 80

    for i in range(get_opponent_hand_count()):
        if i >= 7:  # 1行に7枚まで
            cy += card_back_h + 20
            start_x = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count() - 7, 7) + 10 * (min(get_opponent_hand_count() - 7, 7) - 1))) // 2
            if i == 7:
                pass  # 2行目の開始位置を再計算済み

        row = i // 7
        col = i % 7
        if row > 0:
            cx = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count() - 7, 7) + 10 * (min(get_opponent_hand_count() - 7, 7) - 1))) // 2 + col * (card_back_w + 10)
        else:
            cx = start_x + col * (card_back_w + 10)

        actual_cy = overlay_y + 80 + row * (card_back_h + 20)
        
        # カード裏面（仮実装：グレーの矩形とパターン）
        card_rect = pygame.Rect(cx, actual_cy, card_back_w, card_back_h)
        pygame.draw.rect(screen, (150, 150, 160), card_rect)
        pygame.draw.rect(screen, (80, 80, 90), card_rect, 2)
        # 裏面パターン（斜線）
        for d in range(-card_back_h, card_back_w, 10):
            sx = cx + d
            sy = actual_cy
            ex = cx + d + card_back_h
            ey = actual_cy + card_back_h
            if sx < cx:
                sy += (cx - sx)
                sx = cx
            if ex > cx + card_back_w:
                ey -= (ex - (cx + card_back_w))
                ex = cx + card_back_w
            if sy < actual_cy + card_back_h and ey > actual_cy:
                pygame.draw.line(screen, (100, 100, 110), (sx, sy), (ex, ey), 1)


def get_grave_card_rects():
    """墓地カード矩形のリストを取得する
    
    Returns:
        list: [(rect, card_name), ...]
    """
    return grave_card_rects


# プロモーション選択UI用のグローバル変数
promo_rects = []


def draw_promotion_overlay(screen, chess, layout, W, H, FONT, get_piece_image_surface_func):
    """プロモーション（駒の昇格）選択オーバーレイを描画する
    
    Args:
        screen: pygame surface
        chess: チェスエンジンモジュール
        layout: compute_layout()で計算されたレイアウト情報
        W: ウィンドウ幅
        H: ウィンドウ高さ
        FONT: フォントオブジェクト
        get_piece_image_surface_func: 駒画像取得関数
    
    Returns:
        list: [(rect, piece_type), ...] プロモーション選択肢の矩形とタイプのリスト
    """
    global promo_rects
    
    if chess.promotion_pending is None:
        promo_rects = []
        return promo_rects
    
    promot = chess.promotion_pending
    opts = ['Q', 'R', 'B', 'N']  # Queen, Rook, Bishop, Knight
    
    # ボックスサイズ・配置
    box_w = 460
    box_h = 160
    
    board_left = layout.get('board_left', 220)
    board_top = layout.get('board_top', 20)
    board_size = layout.get('board_size', 600)
    
    # プロモーション選択ボックスをチェスボード内に配置
    # 可能であれば昇格マスの上に配置、そうでなければボード中央にクランプ
    try:
        piece = promot.get('piece')
        # タイル原点（左上）を駒の位置から計算
        pr = getattr(piece, 'row', None)
        pc = getattr(piece, 'col', None)
        tile_x = board_left + (pc * (board_size // 8)) if pc is not None else None
        tile_y = board_top + (pr * (board_size // 8)) if pr is not None else None
    except Exception:
        tile_x = None
        tile_y = None

    # プロモーションボックスをチェスボードエリア内の中央に配置
    try:
        box_x = board_left + (board_size - box_w) // 2
        box_y = board_top + (board_size - box_h) // 2
    except Exception:
        # ボードメトリクスが利用できない場合は画面中央にフォールバック
        box_x = (W - box_w) // 2
        box_y = (H - box_h) // 2
    
    # 背景ボックス描画
    pygame.draw.rect(screen, (245, 245, 245), (box_x, box_y, box_w, box_h))
    pygame.draw.rect(screen, (80, 80, 80), (box_x, box_y, box_w, box_h), 2)
    
    # ヘッダテキスト
    header_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28)
    hdr = header_font.render("昇格する駒を選択", True, (40, 40, 40))
    screen.blit(hdr, (box_x + (box_w - hdr.get_width()) // 2, box_y + 8))

    # 選択肢を横並びに描画（駒画像を使用）
    opt_w = 96
    spacing = (box_w - 24 - len(opts) * opt_w) // (len(opts) - 1)
    ox = box_x + 12
    oy = box_y + 48
    promo_rects = []
    
    for i, o in enumerate(opts):
        r = pygame.Rect(ox + i * (opt_w + spacing), oy, opt_w, opt_w)
        pygame.draw.rect(screen, (230, 230, 230), r)
        pygame.draw.rect(screen, (120, 120, 120), r, 2)
        
        # 駒画像を描画
        img = get_piece_image_surface_func(o, promot['color'], (opt_w - 8, opt_w - 8))
        if img is not None:
            screen.blit(img, (r.x + 4, r.y + 4))
        else:
            # 画像がない場合はテキストで表示
            lab = FONT.render(o, True, (0, 0, 0))
            screen.blit(lab, (r.x + (r.w - lab.get_width()) // 2, r.y + (r.h - lab.get_height()) // 2))
        
        promo_rects.append((r, o))
    
    return promo_rects


def get_promo_rects():
    """プロモーション選択矩形のリストを取得する
    
    Returns:
        list: [(rect, piece_type), ...]
    """
    return promo_rects


def handle_promotion_click(pos, chess, game):
    """プロモーション選択のクリック処理
    
    Args:
        pos: マウス位置 (x, y)
        chess: チェスエンジンモジュール
        game: ゲームインスタンス
    
    Returns:
        bool: クリックが処理されたかどうか
    """
    global promo_rects
    
    if chess.promotion_pending is None or not promo_rects:
        return False
    
    for r, o in promo_rects:
        if r.collidepoint(pos):
            # 選択された昇格駒で置き換え
            piece = chess.promotion_pending.get('piece')
            if piece is not None:
                piece.name = o
                game.log.append(f"昇格: ポーンを{o}に昇格させました。")
            chess.promotion_pending = None
            promo_rects = []
            return True
    
    return False


def draw_enlarged_card(screen, game, enlarged_card_index, enlarged_card_name, W, H, get_card_image_func):
    """カード拡大表示オーバーレイを描画する
    
    Args:
        screen: pygame surface
        game: ゲームインスタンス
        enlarged_card_index: 拡大表示する手札カードのインデックス（None=非表示）
        enlarged_card_name: 拡大表示するカード名（墓地など手札以外用、None=非表示）
        W: ウィンドウ幅
        H: ウィンドウ高さ
        get_card_image_func: カード画像取得関数
    """
    # 手札カードの拡大表示
    if enlarged_card_index is not None and 0 <= enlarged_card_index < len(game.player.hand.cards):
        c = game.player.hand.cards[enlarged_card_index]
        
        # 拡大カードサイズ
        enlarged_w = 300
        enlarged_h = 420
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2
        
        # 背景暗転
        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))
        
        # 拡大画像のみ表示
        large_img = get_card_image_func(c.name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))
    
    # 手札以外（例: 墓地）からの拡大表示
    elif enlarged_card_name is not None:
        enlarged_w = 300
        enlarged_h = 420
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2

        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))

        large_img = get_card_image_func(enlarged_card_name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))


def draw_tile_effects_overlay(screen, game, layout, TINY, draw_dashed_rect_func):
    """封鎖タイル・凍結駒・仮選択の視覚化オーバーレイを描画
    
    Args:
        screen: pygame surface
        game: Gameインスタンス
        layout: レイアウト情報
        TINY: 小さいフォント
        draw_dashed_rect_func: 点線矩形描画関数
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    # 封鎖タイル表示（赤の半透明）
    try:
        for (br, bc), raw in getattr(game, 'blocked_tiles', {}).items():
            # raw may be legacy int or new list of entries
            try:
                if isinstance(raw, list):
                    entries = raw
                elif isinstance(raw, dict):
                    entries = [raw]
                else:
                    entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]
            except Exception:
                entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]

            # only show overlay if any entry has turns > 0
            any_active = False
            for e in entries:
                try:
                    if int(e.get('turns', 0)) > 0:
                        any_active = True
                        break
                except Exception:
                    continue
            if not any_active:
                continue

            bx = board_left + bc * square_w
            by = board_top + br * square_h
            s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
            s.fill((200, 30, 30, 120))
            screen.blit(s, (bx, by))
            # ターン数を小さく表示
            try:
                turns_text = ','.join(str(int(e.get('turns', 0))) for e in entries if int(e.get('turns', 0)) > 0)
            except Exception:
                turns_text = str(getattr(game, 'blocked_tiles_owner', {}).get((br, bc)) or '')
            ttxt = TINY.render(turns_text, True, (255,255,255))
            screen.blit(ttxt, (bx + 4, by + 4))
            # 所有者表示（白/黒の頭文字）
            owner = getattr(game, 'blocked_tiles_owner', {}).get((br, bc))
            if owner:
                ot = TINY.render(owner[0].upper(), True, (255,255,255))
                screen.blit(ot, (bx + 4, by + 18))
    except Exception:
        pass

    # 仮決定中の選択表示（点線）
    try:
        if getattr(game, 'pending', None) is not None and game.pending.kind == 'target_tiles_multi':
            sel = game.pending.info.get('selected', [])
            tmax = game.pending.info.get('max_tiles', 3)
            for idx, (br, bc) in enumerate(sel):
                bx = board_left + bc * square_w
                by = board_top + br * square_h
                rrect = pygame.Rect(bx, by, square_w, square_h)
                draw_dashed_rect_func(screen, (200, 30, 30), rrect, dash=6, gap=4, width=3)
                # small tentative label at bottom-right
                try:
                    ttxt = TINY.render(f"仮{idx+1}/{tmax}", True, (200,30,30))
                    screen.blit(ttxt, (bx + square_w - ttxt.get_width() - 4, by + square_h - ttxt.get_height() - 4))
                except Exception:
                    pass
    except Exception:
        pass


def draw_frozen_pieces_overlay(screen, game, chess, layout, SMALL):
    """凍結駒の視覚化オーバーレイを描画
    
    Args:
        screen: pygame surface
        game: Gameインスタンス
        chess: chess_engineモジュール
        layout: レイアウト情報
        SMALL: フォント
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    try:
        for p in chess.pieces:
            # consider both the game.frozen_pieces mapping and a transient per-piece attribute
            try:
                frozen_map = getattr(game, 'frozen_pieces', {})
                is_frozen = (id(p) in frozen_map and frozen_map.get(id(p), 0) > 0) or \
                           (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0)
            except Exception:
                is_frozen = id(p) in getattr(game, 'frozen_pieces', {})
            if is_frozen:
                fx = board_left + p.col * square_w
                fy = board_top + p.row * square_h
                s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                s.fill((30, 120, 200, 90))
                screen.blit(s, (fx, fy))
                # 凍結マーク
                mark = SMALL.render('凍', True, (255,255,255))
                screen.blit(mark, (fx + square_w - mark.get_width() - 4, fy + 4))
    except Exception:
        pass


def handle_scrollbar_drag_start(pos, show_log, scrollbar_rect_arg, log_scroll_offset):
    """スクロールバーのドラッグ開始を処理する
    
    Args:
        pos: マウス位置 (x, y)
        show_log: ログを表示しているかどうか
        scrollbar_rect_arg: スクロールバーのRect（draw_log_panelから取得）
        log_scroll_offset: 現在のスクロールオフセット
        
    Returns:
        bool: ドラッグを開始した場合True、それ以外はFalse
    """
    global dragging_scrollbar, drag_start_y, drag_start_offset
    
    if show_log and scrollbar_rect_arg and scrollbar_rect_arg.collidepoint(pos):
        dragging_scrollbar = True
        drag_start_y = pos[1]
        drag_start_offset = log_scroll_offset
        return True
    return False


def handle_scrollbar_drag_end():
    """スクロールバーのドラッグ終了を処理する"""
    global dragging_scrollbar
    dragging_scrollbar = False


def handle_scrollbar_motion(pos, show_log, scrollbar_rect_arg, log_scroll_offset, max_scroll):
    """スクロールバーのドラッグ中のマウス移動を処理する
    
    Args:
        pos: マウス位置 (x, y)
        show_log: ログを表示しているかどうか
        scrollbar_rect_arg: スクロールバーのRect（draw_log_panelから取得）
        log_scroll_offset: 現在のスクロールオフセット
        max_scroll: 最大スクロール値
        
    Returns:
        int: 新しいスクロールオフセット
    """
    global dragging_scrollbar, drag_start_y, drag_start_offset
    
    if not dragging_scrollbar or not show_log or not scrollbar_rect_arg:
        return log_scroll_offset
    
    # ドラッグした距離
    dy = pos[1] - drag_start_y
    
    # スクロールバーの高さに応じてスクロール量を計算
    # scrollbar_rectの高さをベースに、max_scrollに対する比率を計算
    scrollbar_height = scrollbar_rect_arg.height
    if scrollbar_height > 0 and max_scroll > 0:
        # ドラッグ量をスクロールオフセットに変換
        scroll_delta = -dy * max_scroll / scrollbar_height
        new_offset = drag_start_offset + scroll_delta
        # クランプ（0からmax_scrollの範囲内）
        new_offset = max(0, min(max_scroll, new_offset))
        return int(new_offset)
    
    return log_scroll_offset


def get_scrollbar_state():
    """スクロールバーの状態を取得する
    
    Returns:
        tuple: (scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset)
    """
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    return (scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset)
