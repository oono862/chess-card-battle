"""
チェス盤の描画機能を提供するモジュール

このモジュールは以下の機能を含みます：
- チェス盤の描画（マス目）
- 駒の描画
- カード効果の視覚化（封鎖タイル、凍結駒、GIFアニメーション）
- ハイライト表示（選択可能な移動先）
- チェック状態の表示
"""

import pygame
import time as _ct_time

# 必要なモジュールのインポート
try:
    from assets import image_loader
    get_piece_image_surface = image_loader.get_piece_image_surface
except Exception:
    def get_piece_image_surface(name: str, color: str, size: tuple):
        return None

try:
    from assets import animation
    heat_gif_anim = animation.heat_gif_anim
    ic_gif_anim = animation.ic_gif_anim
    _ensure_mg_gif_loaded = animation._ensure_mg_gif_loaded
    _ensure_mg_gif_2p_loaded = animation._ensure_mg_gif_2p_loaded
    IC_GIF_SCALE = animation.IC_GIF_SCALE
    _animation_module = animation
except Exception:
    heat_gif_anim = {'playing': False}
    ic_gif_anim = {'playing': False}
    def _ensure_mg_gif_loaded():
        pass
    def _ensure_mg_gif_2p_loaded():
        pass
    IC_GIF_SCALE = 1.4
    _animation_module = None

try:
    from utils.drawing import draw_dashed_rect
except Exception:
    def draw_dashed_rect(surf, color, rect, dash=6, gap=4, width=2):
        pass


def draw_chessboard(screen, layout, chess):
    """チェス盤のマス目を描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報（compute_layout()の戻り値）
        chess: チェスエンジンモジュール
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    # 盤面の色（淡い緑色テーマ）
    light = (235, 248, 240)
    dark = (200, 220, 200)
    
    # 盤面背景を描画
    try:
        pygame.draw.rect(screen, (200, 220, 200), (board_left, board_top, board_size, board_size))
        pygame.draw.rect(screen, (120, 140, 120), (board_left, board_top, board_size, board_size), 2)
    except Exception:
        pass
    
    # 8x8のマス目を描画
    for rr in range(8):
        for cc in range(8):
            rrect = pygame.Rect(board_left + cc*square_w, board_top + rr*square_h, square_w, square_h)
            pygame.draw.rect(screen, light if (rr+cc)%2==0 else dark, rrect)
    
    # 盤面の境界線を描画
    left_x = board_left
    right_x = board_left + 8 * square_w
    pygame.draw.rect(screen, (20,20,20), (left_x-3, board_top, 6, 8 * square_h))
    pygame.draw.rect(screen, (20,20,20), (right_x-3, board_top, 6, 8 * square_h))
    pygame.draw.rect(screen, (20,20,20), (board_left, board_top-3, 8 * square_w, 6))
    pygame.draw.rect(screen, (20,20,20), (board_left, board_top + 8 * square_h - 3, 8 * square_w, 6))


def draw_pieces(screen, layout, chess, SMALL):
    """チェス駒を描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        chess: チェスエンジンモジュール
        SMALL: 小さいフォント
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    for p in chess.pieces:
        cell_x = board_left + p.col*square_w
        cell_y = board_top + p.row*square_h
        # パディングを設定（駒画像がマス目の端に触れないように）
        padding = max(6, int(square_w * 0.08))
        img_w = square_w - padding*2
        img_h = square_h - padding*2
        img = get_piece_image_surface(p.name, p.color, (img_w, img_h))
        if img is not None:
            screen.blit(img, (cell_x + padding, cell_y + padding))
        else:
            # フォールバック：円と文字で描画
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


def draw_card_effects(screen, layout, game, chess, TINY):
    """カード効果の視覚化オーバーレイを描画する
    
    封鎖タイル、凍結駒、保留中の選択タイルなどを表示
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        game: カードゲームオブジェクト
        chess: チェスエンジンモジュール
        TINY: 極小フォント
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    # 封鎖タイルの描画（赤の半透明）
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
                draw_dashed_rect(screen, (200, 30, 30), rrect, dash=6, gap=4, width=3)
                # small tentative label at bottom-right
                try:
                    ttxt = TINY.render(f"仮{idx+1}/{tmax}", True, (200,30,30))
                    screen.blit(ttxt, (bx + square_w - ttxt.get_width() - 4, by + square_h - ttxt.get_height() - 4))
                except Exception:
                    pass
    except Exception:
        pass
    
    # 凍結駒の表示（青の半透明に「凍」マーク）
    try:
        for p in chess.pieces:
            try:
                frozen_map = getattr(game, 'frozen_pieces', {})
                is_frozen = (id(p) in frozen_map and frozen_map.get(id(p), 0) > 0) or (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0)
            except Exception:
                is_frozen = id(p) in getattr(game, 'frozen_pieces', {})
            if is_frozen:
                fx = board_left + p.col * square_w
                fy = board_top + p.row * square_h
                s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                s.fill((30, 120, 200, 90))
                screen.blit(s, (fx, fy))
                # 凍結マーク
                mark_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
                mark = mark_font.render('凍', True, (255,255,255))
                screen.blit(mark, (fx + square_w - mark.get_width() - 4, fy + 4))
    except Exception:
        pass


def draw_gif_animations(screen, layout):
    """GIFアニメーション（灼熱・氷結・封鎖）を描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
    """
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    # 灼熱GIFアニメーション
    try:
        if heat_gif_anim.get('playing') and heat_gif_anim.get('frames'):
            elapsed = _ct_time.time() - heat_gif_anim.get('start_time', 0.0)
            total = heat_gif_anim.get('total_duration', 0.0)
            frames = heat_gif_anim.get('frames')
            durations = heat_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                heat_gif_anim['playing'] = False
            else:
                acc = 0.0
                elapsed_ms = elapsed * 1000.0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if elapsed_ms < acc:
                        idx = i
                        break
                frame = frames[idx]
                pos = heat_gif_anim.get('pos')
                if pos is not None:
                    r, c = pos
                    fx = board_left + c * square_w
                    fy = board_top + r * square_h
                    try:
                        fw = int(square_w)
                        fh = int(square_h)
                        f_surf = pygame.transform.smoothscale(frame, (fw, fh))
                    except Exception:
                        f_surf = frame
                    screen.blit(f_surf, (fx, fy))
    except Exception:
        pass
    
    # 氷結GIFアニメーション
    try:
        if ic_gif_anim.get('playing') and ic_gif_anim.get('frames'):
            elapsed = _ct_time.time() - ic_gif_anim.get('start_time', 0.0)
            total = ic_gif_anim.get('total_duration', 0.0)
            frames = ic_gif_anim.get('frames')
            durations = ic_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                ic_gif_anim['playing'] = False
            else:
                acc = 0.0
                elapsed_ms = elapsed * 1000.0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if elapsed_ms < acc:
                        idx = i
                        break
                frame = frames[idx]
                pos = ic_gif_anim.get('pos')
                if pos is not None:
                    r, c = pos
                    try:
                        fw0, fh0 = frame.get_width(), frame.get_height()
                        max_w = max(1, square_w)
                        max_h = max(1, square_h)
                        scale_bound = IC_GIF_SCALE
                        sf_w = max_w / fw0
                        sf_h = max_h / fh0
                        sf = min(sf_w, sf_h, scale_bound)
                        if sf <= 0:
                            sf = 1.0
                        fw = max(1, int(fw0 * sf))
                        fh = max(1, int(fh0 * sf))
                        f_surf = pygame.transform.smoothscale(frame, (fw, fh))
                    except Exception:
                        f_surf = frame
                        fw = f_surf.get_width()
                        fh = f_surf.get_height()
                    fx = board_left + c * square_w + (square_w - fw) // 2
                    fy = board_top + r * square_h + (square_h - fh) // 2
                    screen.blit(f_surf, (fx, fy))
    except Exception:
        pass
    
    # 封鎖タイルでのループ再生：Image_MG.gif（プレイヤー）/ Image_MG_2P.gif（AI）
    try:
        _ensure_mg_gif_loaded()
        _ensure_mg_gif_2p_loaded()

        mg_frames = getattr(_animation_module, 'mg_gif_frames_cache', None) if _animation_module else None
        mg_2p_frames = getattr(_animation_module, 'mg_gif_2p_frames_cache', None) if _animation_module else None
        if not (mg_frames or mg_2p_frames):
            raise Exception("no mg gif available")

        now_ms = int(_ct_time.time() * 1000)

        # game オブジェクトが必要なので、グローバルから取得
        import builtins
        game = getattr(builtins, 'game', None)
        if not game:
            return

        for (br, bc), raw in getattr(game, 'blocked_tiles', {}).items():
            try:
                if isinstance(raw, list):
                    entries = raw
                elif isinstance(raw, dict):
                    entries = [raw]
                else:
                    entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]
            except Exception:
                entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]

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

            owner = getattr(game, 'blocked_tiles_owner', {}).get((br, bc))
            use_2p = False
            try:
                if owner == 'white' and mg_2p_frames:
                    use_2p = True
            except Exception:
                use_2p = False

            frames_cache = mg_2p_frames if use_2p and mg_2p_frames else mg_frames
            mg_dur = getattr(_animation_module, 'mg_gif_durations', None) if _animation_module else None
            mg_2p_dur = getattr(_animation_module, 'mg_gif_2p_durations', None) if _animation_module else None
            durations = mg_2p_dur if use_2p and mg_2p_dur else mg_dur

            if not frames_cache or not durations:
                continue

            try:
                total_ms = int(sum(durations))
            except Exception:
                mg_total = getattr(_animation_module, 'mg_gif_total_duration', 0.0) if _animation_module else 0.0
                mg_2p_total = getattr(_animation_module, 'mg_gif_2p_total_duration', 0.0) if _animation_module else 0.0
                total_ms = max(1, int((mg_2p_total if use_2p else mg_total) * 1000))

            if total_ms > 0:
                tmod = now_ms % total_ms
                acc = 0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if tmod < acc:
                        idx = i
                        break
            else:
                idx = 0

            frame = frames_cache[idx]
            try:
                f_surf = pygame.transform.smoothscale(frame, (square_w, square_h))
            except Exception:
                f_surf = frame
            screen.blit(f_surf, (bx, by))
    except Exception:
        pass


def draw_turn_telop(screen, layout, turn_telop_msg, turn_telop_until):
    """ターン表示テロップ（中央・1秒表示）を描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        turn_telop_msg: テロップメッセージ
        turn_telop_until: テロップ表示期限
    """
    try:
        if turn_telop_msg and _ct_time.time() < turn_telop_until:
            board_left = layout['board_left']
            board_top = layout['board_top']
            board_size = layout['board_size']
            telop_font_size = max(28, board_size // 8)
            telop_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", telop_font_size, bold=True)
            # 強めの白文字
            telop_surf = telop_font.render(turn_telop_msg, True, (255, 255, 255))
            shadow = telop_font.render(turn_telop_msg, True, (0, 0, 0))
            tx = board_left + (board_size - telop_surf.get_width()) // 2
            ty = board_top + (board_size - telop_surf.get_height()) // 2

            # 'YOUR TURN' の場合は背景を描かず、テキストのみ表示する
            draw_bg = True
            try:
                if isinstance(turn_telop_msg, str) and turn_telop_msg.strip().upper() == 'YOUR TURN':
                    draw_bg = False
            except Exception:
                draw_bg = True

            if draw_bg:
                try:
                    pad_x = max(10, telop_font_size // 5)
                    pad_y = max(6, telop_font_size // 8)
                    bx = tx - pad_x
                    by = ty - pad_y
                    bw = telop_surf.get_width() + pad_x * 2
                    bh = telop_surf.get_height() + pad_y * 2
                    bg = pygame.Surface((bw, bh))
                    bg.fill((28, 28, 28))
                    screen.blit(bg, (bx, by))
                    # 境界線で強調
                    pygame.draw.rect(screen, (220, 180, 60), (bx, by, bw, bh), 2)
                except Exception:
                    pass

            # 影と文字を描画
            try:
                # チュートリアルのメッセージ矩形と重なる場合は位置調整
                try:
                    import sys
                    main_mod = sys.modules.get('__main__')
                    tm = getattr(main_mod, '_current_tutorial', None)
                    tut_rect = getattr(tm, 'last_message_rect', None) if tm is not None else None
                except Exception:
                    tut_rect = None

                adj_tx, adj_ty = tx, ty
                if tut_rect:
                    # テロップの背景矩形を計算して衝突判定
                    pad_x = max(10, telop_font_size // 5)
                    pad_y = max(6, telop_font_size // 8)
                    bw_local = telop_surf.get_width() + pad_x * 2
                    bh_local = telop_surf.get_height() + pad_y * 2
                    telop_rect = pygame.Rect(tx - pad_x, ty - pad_y, bw_local, bh_local)
                    if telop_rect.colliderect(tut_rect):
                        # チュートリアルボックスの下に移動
                        adj_ty = tut_rect.bottom + 8
                        # 画面下にはみ出さないように調整
                        max_y = layout.get('board_top', 0) + layout.get('board_size', 0) - bh_local - 8
                        if adj_ty > max_y:
                            adj_ty = max_y

                screen.blit(shadow, (adj_tx + 3, adj_ty + 3))
            except Exception:
                pass
            try:
                screen.blit(telop_surf, (adj_tx, adj_ty))
            except Exception:
                pass
    except Exception:
        pass


def draw_notice_message(screen, layout, notice_msg, notice_until):
    """短時間表示用の警告メッセージを描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        notice_msg: 警告メッセージ
        notice_until: 表示期限
    """
    try:
        if notice_msg and _ct_time.time() < notice_until:
            board_left = layout['board_left']
            board_top = layout['board_top']
            board_size = layout['board_size']
            box_w = min(500, board_size - 40)
            notice_font_size = max(16, board_size // 24)
            notice_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", notice_font_size, bold=True)
            notice_surf = notice_font.render(notice_msg, True, (255, 230, 180))
            shadow = notice_font.render(notice_msg, True, (0,0,0))
            bx = board_left + (board_size - notice_surf.get_width()) // 2
            by = board_top + 8
            # チュートリアルのメッセージ矩形があれば重なりを避ける
            try:
                import sys
                main_mod = sys.modules.get('__main__')
                tm = getattr(main_mod, '_current_tutorial', None)
                tut_rect = getattr(tm, 'last_message_rect', None) if tm is not None else None
            except Exception:
                tut_rect = None
            # 常に不透明な背景で表示（半透明にしない）
            try:
                bw = notice_surf.get_width() + 20
                bh = notice_surf.get_height() + 12
                tmp = pygame.Surface((bw, bh))
                tmp.fill((28, 28, 28))
                # 衝突判定用の矩形
                notice_rect = pygame.Rect(bx-10, by-6, bw, bh)
                if tut_rect and notice_rect.colliderect(tut_rect):
                    # チュートリアルボックスの下に移動
                    by = tut_rect.bottom + 8
                    notice_rect.y = by - 6
                screen.blit(tmp, (bx-10, by-6))
                pygame.draw.rect(screen, (220, 180, 60), (bx-10, by-6, bw, bh), 2)
                screen.blit(shadow, (bx+2, by+2))
            except Exception:
                try:
                    pygame.draw.rect(screen, (28,28,28), (bx-10, by-6, notice_surf.get_width()+20, notice_surf.get_height()+12))
                    pygame.draw.rect(screen, (220,180,60), (bx-10, by-6, notice_surf.get_width()+20, notice_surf.get_height()+12), 2)
                    screen.blit(shadow, (bx+2, by+2))
                except Exception:
                    pass
            screen.blit(notice_surf, (bx, by))
    except Exception:
        pass


def draw_highlights(screen, layout, selected_piece, highlight_squares, chess, game, is_in_check, simulate_move):
    """選択可能な移動先のハイライトを描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        selected_piece: 選択中の駒
        highlight_squares: ハイライトするマスのリスト
        chess: チェスエンジンモジュール
        game: カードゲームオブジェクト
        is_in_check: チェック判定関数
        simulate_move: 移動シミュレーション関数
    """
    if not selected_piece:
        return
    
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w
    
    # 反撃チェック判定の準備
    try:
        sp_color = getattr(selected_piece, 'color', selected_piece.get('color'))
    except Exception:
        sp_color = 'white'
    try:
        pre_self_in_check = is_in_check(chess.pieces, sp_color)
    except Exception:
        pre_self_in_check = False
    try:
        if sp_color == 'white':
            lightning_active_for_highlight = getattr(game, 'player_consecutive_turns', 0) > 0
        else:
            import builtins
            lightning_active_for_highlight = getattr(builtins, 'ai_consecutive_turns', 0) > 0
    except Exception:
        lightning_active_for_highlight = False
    try:
        import builtins
        debug_card_gate_hl = getattr(builtins, 'DEBUG_COUNTER_CHECK_CARD_MODE', False) and getattr(game, '_debug_last_action_was_card', False)
    except Exception:
        debug_card_gate_hl = False
    
    for hr, hc in highlight_squares:
        hrect = pygame.Rect(board_left + hc*square_w, board_top + hr*square_h, square_w, square_h)
        
        # 移動先の色分け判定
        is_en_passant = False
        is_castling = False
        is_checkmate = False
        is_counter_check = False
        
        # アンパサン判定
        if selected_piece.name == 'P' and chess.en_passant_target is not None:
            if (hr, hc) == chess.en_passant_target:
                if ((selected_piece.color == 'white' and selected_piece.row == 3) or
                    (selected_piece.color == 'black' and selected_piece.row == 4)):
                    is_en_passant = True
        
        # キャスリング判定
        if selected_piece.name == 'K' and abs(hc - selected_piece.col) == 2:
            is_castling = True
        
        # チェックメイト/キング捕獲判定
        target_piece = chess.get_piece_at(hr, hc)
        if target_piece and target_piece.name == 'K' and target_piece.color != selected_piece.color:
            is_checkmate = True
        else:
            # 相手を詰ませる手かどうかを判定
            temp_pieces = chess.simulate_move(selected_piece, hr, hc)
            next_turn = 'black' if selected_piece.color == 'white' else 'white'
            if any(p.name == 'K' and p.color == next_turn for p in temp_pieces):
                is_mate = is_in_check(temp_pieces, next_turn)
                if is_mate:
                    has_moves = False
                    for tp in temp_pieces:
                        if tp.color == next_turn:
                            moves = tp.get_valid_moves(temp_pieces)
                            for mv in moves:
                                test = simulate_move(tp, mv[0], mv[1])
                                if not is_in_check(test, next_turn):
                                    has_moves = True
                                    break
                        if has_moves:
                            break
                    if not has_moves:
                        is_checkmate = True
        
        # 反撃チェック判定
        try:
            if (lightning_active_for_highlight or debug_card_gate_hl):
                post_sim = simulate_move(selected_piece, hr, hc)
                opp_color = 'black' if sp_color == 'white' else 'white'
                if pre_self_in_check and is_in_check(post_sim, sp_color) and is_in_check(post_sim, opp_color):
                    is_counter_check = True
                elif not pre_self_in_check and is_in_check(post_sim, sp_color) and is_in_check(post_sim, opp_color):
                    is_counter_check = True
        except Exception:
            pass

        # 色決定
        if is_checkmate:
            highlight_color = (255, 0, 0, 100)  # 赤: チェックメイト/キング捕獲
        elif is_en_passant:
            highlight_color = (0, 0, 255, 100)  # 青: アンパサン
        elif is_castling:
            highlight_color = (255, 215, 0, 100)  # 金: キャスリング
        elif is_counter_check:
            highlight_color = (255, 165, 0, 110)  # オレンジ: 反撃チェック
        else:
            highlight_color = (0, 255, 0, 80)  # 緑: 通常移動
        
        s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
        s.fill(highlight_color)
        screen.blit(s, hrect.topleft)


def draw_check_indicator(screen, layout, game_over, chess, is_in_check_for_display, can_attack_king_with_cards, W, H):
    """チェック状態の表示を描画する
    
    Args:
        screen: pygame surface
        layout: レイアウト情報
        game_over: ゲームオーバーフラグ
        chess: チェスエンジンモジュール
        is_in_check_for_display: チェック判定関数（表示用）
        can_attack_king_with_cards: カード効果でキング攻撃可能か判定
        W: 画面幅
        H: 画面高さ
    """
    if game_over:
        return
    
    check_colors = []
    if is_in_check_for_display(chess.pieces, 'white') or can_attack_king_with_cards(chess.pieces, 'white'):
        check_colors.append('white')
    if is_in_check_for_display(chess.pieces, 'black') or can_attack_king_with_cards(chess.pieces, 'black'):
        check_colors.append('black')
    
    if not check_colors:
        return
    
    # チェック状態の変化を追跡
    if not hasattr(draw_check_indicator, "last_check_colors"):
        draw_check_indicator.last_check_colors = []
    if check_colors != draw_check_indicator.last_check_colors:
        draw_check_indicator.last_check_colors = check_colors.copy()
    
    # 左パネルの中央付近に表示
    left_margin = layout['left_margin']
    check_x = left_margin + 10
    check_y = H // 2 - 50
    
    for idx, color in enumerate(draw_check_indicator.last_check_colors):
        msg = f"{'白' if color == 'white' else '黒'}チェック中"
        check_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
        check_text = check_font.render(msg, True, (255, 165, 0))
        
        text_w = check_text.get_width()
        text_h = check_text.get_height()
        
        # 背景を半透明の黒で塗りつぶして視認性を向上
        bg_rect = pygame.Rect(check_x - 5, check_y - 3 + idx * (text_h + 10), text_w + 10, text_h + 6)
        try:
            tmp = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            tmp.fill((0, 0, 0, 160))
            screen.blit(tmp, (bg_rect.x, bg_rect.y))
        except Exception:
            pygame.draw.rect(screen, (0, 0, 0), bg_rect)
        pygame.draw.rect(screen, (255, 165, 0), bg_rect, 2)
        screen.blit(check_text, (check_x, check_y + idx * (text_h + 10)))
