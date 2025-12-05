"""デッキ関連のモーダルダイアログ

このモジュールは、デッキ選択、デッキ編集、デッキ管理などの
モーダルダイアログを提供します。
"""

import pygame
import sys
import time as _ct_time
import logging

logger = logging.getLogger(__name__)


# Debounce tracking for deck choice modal
_last_deck_choice_open_time = None


def show_deck_choice_modal(screen, W, H, get_font, FONT, SMALL, DECK_MODE_getter, DECK_MODE_setter, load_saved_decks=None):
    """デッキ選択モーダル（fixed/custom選択）
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        get_font: フォント取得関数
        FONT, SMALL: フォントオブジェクト
        DECK_MODE_getter: 現在のデッキモードを取得する関数
        DECK_MODE_setter: デッキモードを設定する関数
        load_saved_decks: (未使用) デッキ読み込み関数
    
    Returns:
        bool: True=選択完了, False=キャンセル
    """
    global _last_deck_choice_open_time
    
    clk = pygame.time.Clock()
    
    # Debounce: prevent immediate re-entry from multiple callers/clicks
    try:
        now = _ct_time.time()
        if _last_deck_choice_open_time and (now - _last_deck_choice_open_time) < 0.5:
            return False
        _last_deck_choice_open_time = now
    except Exception:
        pass
    
    # Flush any pending click/touch events that opened this modal so the
    # same event doesn't immediately trigger inner buttons (prevents
    # duplicate modal/action when called from click handlers).
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass
    
    w, h = 560, 240
    x = (W - w)//2
    y = (H - h)//2

    # Button geometry
    btn_w = 220
    btn_h = 80
    left_x = x + 32
    right_x = x + w - btn_w - 32
    by = y + 80

    while True:
        # get current window size each frame so UI components position correctly
        win_w, win_h = screen.get_size()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                # ユーザーがEscを押したら、前の画面に戻る（何も選択しない）
                return False
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                # close icon (top-right of modal) — screen coordinates
                close_rect = pygame.Rect(x + w - 34, y + 8, 26, 26)
                if close_rect.collidepoint(mx, my):
                    return False
                # fixed deck
                if left_x <= mx <= left_x + btn_w and by <= my <= by + btn_h:
                    DECK_MODE_setter('fixed')
                    return True
                # created deck
                if right_x <= mx <= right_x + btn_w and by <= my <= by + btn_h:
                    # User chose created decks. Do not open the extra modal overlay;
                    # instead mark DECK_MODE as 'custom' and return so the main
                    # deck-list screen remains interactive and in front.
                    DECK_MODE_setter('custom')
                    return True

        # draw overlay/modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        # make overlay darker so underlying UI (前の画面) is not visible/clickable
        overlay.fill((0,0,0,220))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((245,245,250))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)

        title = FONT.render("デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        # fixed deck button
        fixed_rect = pygame.Rect(left_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), fixed_rect)
        pygame.draw.rect(surf, (70,70,70), fixed_rect, 2)
        t1 = SMALL.render("固定デッキ （デフォルト）", True, (30,30,30))
        t2 = SMALL.render("カード数: 24 / 24", True, (80,80,80))
        surf.blit(t1, (fixed_rect.x + (btn_w - t1.get_width())//2, fixed_rect.y + 12))
        surf.blit(t2, (fixed_rect.x + (btn_w - t2.get_width())//2, fixed_rect.y + 40))

        # custom deck button
        custom_rect = pygame.Rect(right_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), custom_rect)
        pygame.draw.rect(surf, (70,70,70), custom_rect, 2)
        c1 = SMALL.render("作成したデッキ（暫定）", True, (30,30,30))
        c2 = SMALL.render("カード数: 20 / 20", True, (80,80,80))
        surf.blit(c1, (custom_rect.x + (btn_w - c1.get_width())//2, custom_rect.y + 12))
        surf.blit(c2, (custom_rect.x + (btn_w - c2.get_width())//2, custom_rect.y + 40))

        # close icon at top-right of modal
        pygame.draw.rect(surf, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(surf, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            surf.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass

        screen.blit(surf, (x,y))
        pygame.display.flip()
        clk.tick(30)


# Debounce tracking for deck modal
_last_deck_modal_open_time = None


def show_deck_modal(screen, W, H, get_font, FONT, SMALL, load_saved_decks, save_decks_to_file,
                    show_deck_action_modal_func, show_deck_battle_confirm_func, show_deck_editor_func,
                    new_game_with_mode_func, build_ai_player_func, build_game_from_card_names_func,
                    DECK_MODE_getter, DECK_MODE_setter, battle_select_mode=False):
    """デッキリスト画面（3x3グリッド表示）
    
    既存の saved_decks.json を読み込み、9スロットを表示します。
    空スロットは「作成」ボタンでデッキ作成へ移動。既存デッキをクリックすると
    小さなアクションモーダルを開きます。
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        get_font: フォント取得関数
        FONT, SMALL: フォントオブジェクト
        load_saved_decks: デッキ読み込み関数
        save_decks_to_file: デッキ保存関数
        show_deck_action_modal_func: アクションモーダル表示関数
        show_deck_battle_confirm_func: バトル確認モーダル表示関数
        show_deck_editor_func: デッキエディタ表示関数
        new_game_with_mode_func: ゲーム作成関数
        build_ai_player_func: AIプレイヤー作成関数
        build_game_from_card_names_func: カード名からゲーム作成関数
        DECK_MODE_getter: デッキモード取得関数
        DECK_MODE_setter: デッキモード設定関数
        battle_select_mode: バトル選択モードかどうか
    
    Returns:
        bool or None: バトル開始時はTrue、それ以外はNone
    """
    global _last_deck_modal_open_time
    
    # Present the deck-selection screen as a fullscreen view (non-blocking overlay)
    clk = pygame.time.Clock()
    
    # Debounce: prevent immediate re-entry when called twice by the same click
    try:
        now = _ct_time.time()
        if _last_deck_modal_open_time and (now - _last_deck_modal_open_time) < 0.5:
            return False
        _last_deck_modal_open_time = now
    except Exception:
        pass
    
    # Flush the click/touch that opened the modal to avoid immediate
    # double-activation of the selected slot (same rationale as above).
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass
    
    while True:
        # keep current window size in local variables for positioning dialogs/buttons
        win_w, win_h = screen.get_size()
        # load saved decks each frame so external edits are reflected immediately
        decks = load_saved_decks()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # Back button click (画面下部の「戻る」)
                back_chk = pygame.Rect(20, H - 70, 120, 50)
                if back_chk.collidepoint(mx, my):
                    return
                # compute grid geometry (centered)
                w = 720
                h = 480
                x = (W - w)//2
                y = (H - h)//2
                slot_w = (w - 40) // 3
                slot_h = (h - 80) // 3
                rel_x = mx - x - 10
                rel_y = my - y - 40
                if rel_x < 0 or rel_y < 0:
                    continue
                col = rel_x // (slot_w + 10)
                row = rel_y // (slot_h + 10)
                if col < 0 or col > 2 or row < 0 or row > 2:
                    continue
                slot_idx = int(row * 3 + col)
                if slot_idx < 0 or slot_idx >= len(decks):
                    continue
                if decks[slot_idx]:
                    # existing deck -> either action modal or battle-select flow
                    if battle_select_mode:
                        # ask user to confirm starting battle with this deck
                        start = show_deck_battle_confirm_func(screen, decks[slot_idx], slot_idx)
                        # reload decks in case of edits
                        decks = load_saved_decks()
                        if start:
                            # user chose to start battle with this deck
                            names = []
                            if decks[slot_idx]:
                                cards_field = decks[slot_idx].get('cards', [])
                                # saved format may be list of card-name strings or list of dicts
                                if isinstance(cards_field, list):
                                    if cards_field and isinstance(cards_field[0], dict):
                                        names = [str(c.get('name')) for c in cards_field if c and 'name' in c]
                                    else:
                                        names = [str(x) for x in cards_field]
                            try:
                                logger.debug("show_deck_modal starting battle, names=%s", names)
                                # Remember that user explicitly chose a custom deck so future
                                # rematches or returning to menus should preserve this choice.
                                DECK_MODE_setter('custom')
                                try:
                                    # Persist the selected deck for rematches (CardGame.py globals)
                                    __main__._selected_deck_card_names = names
                                    __main__._selected_deck_slot_idx = slot_idx
                                except Exception:
                                    pass
                                # Create game using state (caller will retrieve these)
                                import __main__
                                if names and build_game_from_card_names_func:
                                    __main__.state.game = build_game_from_card_names_func(names)
                                else:
                                    __main__.state.game = new_game_with_mode_func('custom')
                                __main__.state.ai_player = build_ai_player_func('custom')
                                # グローバルエイリアスを同期
                                __main__.game = __main__.state.game
                                __main__.ai_player = __main__.state.ai_player
                                # debug: print resulting deck composition if possible
                                try:
                                    g = __main__.state.game
                                    if g and hasattr(g, 'player') and hasattr(g.player, 'deck'):
                                        cards = getattr(g.player.deck, 'cards', None)
                                        if cards is not None:
                                            logger.debug("created game deck count=%d; first_cards=%s", len(cards), [c.name for c in cards[:8]])
                                except Exception as _e:
                                    logger.debug("error inspecting created game: %s", _e)
                            except Exception as e:
                                logger.debug("exception when creating game from names: %s", e)
                                # fallback to a safe default
                                import __main__
                                __main__.state.game = new_game_with_mode_func('custom')
                                __main__.state.ai_player = build_ai_player_func('custom')
                                # グローバルエイリアスを同期
                                __main__.game = __main__.state.game
                                __main__.ai_player = __main__.state.ai_player
                            # cleanly exit; outer finally will clear in-progress flag
                            return True
                        continue
                    else:
                        # normal browsing: show small action modal
                        res = show_deck_action_modal_func(screen, decks[slot_idx], slot_idx)
                        decks = load_saved_decks()
                        continue
                else:
                    # empty slot -> open editor to create new deck
                    new_deck = show_deck_editor_func(screen, None, slot_idx)
                    if new_deck:
                        decks[slot_idx] = new_deck
                        save_decks_to_file(decks)
                    continue

        # draw full-screen deck grid
        screen.fill((240, 235, 230))
        title_font = get_font(36, bold=True)
        title = title_font.render("作成デッキを選択してください", True, (30,30,30))
        screen.blit(title, ((W - title.get_width()) // 2, 24))

        w = 720
        h = 480
        x = (W - w)//2
        y = (H - h)//2
        slot_w = (w - 40) // 3
        slot_h = (h - 80) // 3
        sx = x + 10
        sy = y + 40
        idx = 0
        slot_font = get_font(20, bold=True)
        for r in range(3):
            for c in range(3):
                rx = sx + c * (slot_w + 10)
                ry = sy + r * (slot_h + 10)
                rect = pygame.Rect(rx, ry, slot_w, slot_h)
                # 既存デッキは青系で、未作成スロットはグレーで表示
                deck = decks[idx] if idx < len(decks) else None
                if deck:
                    # 背景は薄い青、枠は濃い青
                    pygame.draw.rect(screen, (220, 240, 255), rect)
                    pygame.draw.rect(screen, (60, 100, 160), rect, 4)
                    nm = deck.get('name', f'デッキ{idx+1}')
                    txt = SMALL.render(nm, True, (30,30,30))
                    screen.blit(txt, (rect.x + 12, rect.y + 12))
                    cnt = ''
                    if 'cards' in deck:
                        cnt = f"{len(deck['cards'])} 枚"
                    if cnt:
                        ctxt = SMALL.render(cnt, True, (60,60,60))
                        screen.blit(ctxt, (rect.right - ctxt.get_width() - 8, rect.y + 12))
                else:
                    pygame.draw.rect(screen, (245,245,250), rect)
                    pygame.draw.rect(screen, (80,80,80), rect, 3)
                    screen.blit(SMALL.render("デッキ作成", True, (100,100,100)), (rect.x + (rect.w - 100)//2, rect.y + (rect.h - 24)//2))
                idx += 1

        # back button
        back_rect = pygame.Rect(20, H - 70, 120, 50)
        pygame.draw.rect(screen, (200, 200, 200), back_rect)
        pygame.draw.rect(screen, (80, 80, 80), back_rect, 3)
        back_text = FONT.render("戻る", True, (30, 30, 30))
        screen.blit(back_text, (back_rect.x + (back_rect.width - back_text.get_width()) // 2,
                               back_rect.y + (back_rect.height - back_text.get_height()) // 2))

        pygame.display.flip()
        clk.tick(30)
    # end of modal


def show_deck_options(screen, W, H, get_font, deck):
    """デッキオプション（スケルトン）"""
    return None


def show_deck_battle_confirm(screen, W, H, get_font, deck, slot_idx):
    """デッキバトル確認（スケルトン）"""
    return False


# Debounce tracking for deck battle confirm
_last_deck_battle_confirm_open_time = None


def show_deck_battle_confirm(screen, W, H, get_font, FONT, SMALL, deck, slot_idx, show_deck_contents_overlay_func):
    """バトル確認ダイアログ
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        get_font: フォント取得関数
        FONT, SMALL: フォントオブジェクト
        deck: デッキ辞書
        slot_idx: スロット番号
        show_deck_contents_overlay_func: デッキ内容表示関数
    
    Returns:
        bool: True=バトル開始, False=キャンセル
    """
    global _last_deck_battle_confirm_open_time
    
    clk = pygame.time.Clock()
    w, h = 560, 240
    x = (W - w)//2
    y = (H - h)//2
    title_font = get_font(28)

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                if ev.key == pygame.K_y:
                    return True
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # compute local coords
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return False
                lx = mx - x
                ly = my - y
                # buttons
                btn_w = 160
                btn_h = 48
                gap = 24
                bx = (w - (btn_w*2 + gap)) // 2
                by = h - 80
                confirm_rect = pygame.Rect(bx, by, btn_w, btn_h)
                start_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
                # close icon (inside modal, top-right)
                close_rect = pygame.Rect(w-34, 8, 26, 26)
                if confirm_rect.collidepoint(lx, ly):
                    # show deck contents
                    show_deck_contents_overlay_func(screen, deck)
                    continue
                if close_rect.collidepoint(lx, ly):
                    return False
                if start_rect.collidepoint(lx, ly):
                    return True

        # draw
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))
        box = pygame.Surface((w, h))
        box.fill((245,245,250))
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render("このデッキでバトルしますか？", True, (30,30,30))
        box.blit(title, (20, 18))

        # buttons: デッキ確認, バトルスタート
        btn_w = 160
        btn_h = 48
        gap = 24
        bx = (w - (btn_w*2 + gap)) // 2
        by = h - 80
        confirm_rect = pygame.Rect(bx, by, btn_w, btn_h)
        start_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
        pygame.draw.rect(box, (200,220,255), confirm_rect)
        pygame.draw.rect(box, (200,255,200), start_rect)
        # close icon at top-right of modal
        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            box.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass
        pygame.draw.rect(box, (80,80,80), confirm_rect, 2)
        pygame.draw.rect(box, (80,80,80), start_rect, 2)
        t_confirm = SMALL.render("デッキ確認", True, (30,30,30))
        t_start = SMALL.render("バトルスタート", True, (30,30,30))
        box.blit(t_confirm, (confirm_rect.x + (btn_w - t_confirm.get_width())//2, confirm_rect.y + (btn_h - t_confirm.get_height())//2))
        box.blit(t_start, (start_rect.x + (btn_w - t_start.get_width())//2, start_rect.y + (btn_h - t_start.get_height())//2))

        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


def show_deck_action_modal(screen, W, H, get_font, FONT, SMALL, TINY, deck, slot_idx,
                           load_saved_decks, save_decks_to_file,
                           show_deck_editor_func, show_deck_contents_overlay_func):
    """デッキアクションモーダル（編集/詳細/削除選択）
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        get_font: フォント取得関数
        FONT, SMALL, TINY: フォントオブジェクト
        deck: デッキ辞書
        slot_idx: スロット番号
        load_saved_decks: デッキ読み込み関数
        save_decks_to_file: デッキ保存関数
        show_deck_editor_func: デッキエディタ表示関数
        show_deck_contents_overlay_func: デッキ内容表示関数
    
    Returns:
        str or None: アクション種別またはNone
    """
    clk = pygame.time.Clock()
    w, h = 420, 200
    x = (W - w) // 2
    y = (H - h) // 2
    # Use Japanese-capable fonts to avoid tofu (□) when rendering deck names
    title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28)
    btn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 22)
    deck_name = deck.get('name', f'デッキ{slot_idx+1}')

    # build short preview lines for the deck (first few card names)
    preview_lines = []
    for c in deck.get('cards', [])[:8]:
        if isinstance(c, dict):
            preview_lines.append(str(c.get('name', '不明')))
        else:
            preview_lines.append(str(c))

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return None
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # outside click closes
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return None

                # close (×) button
                close_rect = pygame.Rect(x + w - 34, y + 8, 26, 26)
                if close_rect.collidepoint(mx, my):
                    return None

                # buttons: left=edit, mid=view, right=delete
                btn_w = 110
                gap = 20
                bx = x + (w - (btn_w*3 + gap*2)) // 2
                by = y + h - 70
                edit_rect = pygame.Rect(bx, by, btn_w, 40)
                view_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, 40)
                delete_rect = pygame.Rect(bx + (btn_w + gap)*2, by, btn_w, 40)

                if edit_rect.collidepoint(mx, my):
                    # open deck editor and save if edited
                    try:
                        decks = load_saved_decks()
                    except Exception:
                        decks = None
                    if decks is not None:
                        edited = show_deck_editor_func(screen, decks[slot_idx], slot_idx)
                        if edited:
                            decks[slot_idx] = edited
                            save_decks_to_file(decks)
                    return None

                if view_rect.collidepoint(mx, my):
                    show_deck_contents_overlay_func(screen, deck)
                    continue

                if delete_rect.collidepoint(mx, my):
                    # confirmation loop
                    while True:
                        # draw confirm dialog
                        confirm_w, confirm_h = 420, 160
                        cx = x + (w - confirm_w)//2
                        cy = y + (h - confirm_h)//2
                        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                        # darken fully so the background deck list is not visible
                        overlay.fill((0,0,0,220))
                        screen.blit(overlay, (0,0))

                        # redraw modal box under confirm
                        box = pygame.Surface((w, h))
                        box.fill((250,250,250))
                        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
                        title = title_font.render(deck_name, True, (30,30,30))
                        box.blit(title, (20, 18))
                        info = SMALL.render("このデッキをどうしますか？", True, (60,60,60))
                        box.blit(info, (20,56))

                        # buttons under modal — ensure they fit inside the box and center text
                        btn_h = 40
                        padding = 20
                        gap2 = 20
                        max_btn_w = (w - padding*2 - gap2*2) // 3
                        btn_w2 = min(140, max_btn_w)
                        bx2 = (w - (btn_w2*3 + gap2*2)) // 2
                        by2 = h - padding - btn_h
                        edit_rect_local = pygame.Rect(bx2, by2, btn_w2, btn_h)
                        view_rect_local = pygame.Rect(bx2 + btn_w2 + gap2, by2, btn_w2, btn_h)
                        delete_rect_local = pygame.Rect(bx2 + (btn_w2 + gap2)*2, by2, btn_w2, btn_h)
                        pygame.draw.rect(box, (220,220,255), edit_rect_local)
                        pygame.draw.rect(box, (200,240,200), view_rect_local)
                        pygame.draw.rect(box, (255,200,200), delete_rect_local)
                        pygame.draw.rect(box, (80,80,80), edit_rect_local, 2)
                        pygame.draw.rect(box, (80,80,80), view_rect_local, 2)
                        pygame.draw.rect(box, (80,80,80), delete_rect_local, 2)
                        # center button labels
                        et = btn_font.render("デッキ編集", True, (30,30,30))
                        vt = btn_font.render("デッキ詳細", True, (30,30,30))
                        dt = btn_font.render("デッキ削除", True, (30,30,30))
                        box.blit(et, (edit_rect_local.x + (btn_w2 - et.get_width())//2, edit_rect_local.y + (btn_h - et.get_height())//2))
                        box.blit(vt, (view_rect_local.x + (btn_w2 - vt.get_width())//2, view_rect_local.y + (btn_h - vt.get_height())//2))
                        box.blit(dt, (delete_rect_local.x + (btn_w2 - dt.get_width())//2, delete_rect_local.y + (btn_h - dt.get_height())//2))

                        # draw confirm box
                        confirm_surf = pygame.Surface((confirm_w, confirm_h))
                        confirm_surf.fill((250,250,250))
                        pygame.draw.rect(confirm_surf, (80,80,80), (0,0,confirm_w,confirm_h), 3)
                        q_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
                        qtxt = q_font.render("本当にこのデッキを削除しますか？", True, (30,30,30))
                        confirm_surf.blit(qtxt, ((confirm_w - qtxt.get_width())//2, 20))
                        yes_rect = pygame.Rect(60, confirm_h - 64, 120, 44)
                        no_rect = pygame.Rect(confirm_w - 180, confirm_h - 64, 120, 44)
                        pygame.draw.rect(confirm_surf, (200,255,200), yes_rect)
                        pygame.draw.rect(confirm_surf, (255,200,200), no_rect)
                        pygame.draw.rect(confirm_surf, (80,80,80), yes_rect, 2)
                        pygame.draw.rect(confirm_surf, (80,80,80), no_rect, 2)
                        confirm_surf.blit(q_font.render("はい (Y)", True, (30,30,30)), (yes_rect.x + 16, yes_rect.y + 10))
                        confirm_surf.blit(q_font.render("いいえ (N)", True, (30,30,30)), (no_rect.x + 16, no_rect.y + 10))

                        screen.blit(box, (x,y))
                        screen.blit(confirm_surf, (cx, cy))
                        pygame.display.flip()

                        # wait for confirm events
                        done = False
                        for cev in pygame.event.get():
                            if cev.type == pygame.QUIT:
                                pygame.quit()
                                sys.exit(0)
                            if cev.type == pygame.KEYDOWN:
                                if cev.key == pygame.K_y:
                                    try:
                                        decks = load_saved_decks()
                                        decks[slot_idx] = None
                                        save_decks_to_file(decks)
                                    except Exception:
                                        pass
                                    return None
                                if cev.key == pygame.K_n or cev.key == pygame.K_ESCAPE:
                                    done = True
                                    break
                            if cev.type == pygame.MOUSEBUTTONDOWN and cev.button == 1:
                                mx2, my2 = cev.pos
                                if cx <= mx2 <= cx + confirm_w and cy <= my2 <= cy + confirm_h:
                                    rx = mx2 - cx
                                    ry = my2 - cy
                                    if yes_rect.collidepoint(rx, ry):
                                        try:
                                            decks = load_saved_decks()
                                            decks[slot_idx] = None
                                            save_decks_to_file(decks)
                                        except Exception:
                                            pass
                                        return None
                                    if no_rect.collidepoint(rx, ry):
                                        done = True
                                        break
                        if done:
                            break
                    # end confirmation loop

        # 描画
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        box = pygame.Surface((w, h))
        box.fill((250, 250, 250))
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render(deck_name, True, (30,30,30))
        box.blit(title, (20, 18))
        info = SMALL.render("このデッキをどうしますか？", True, (60,60,60))
        box.blit(info, (20, 56))

        # close icon
        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        box.blit(btn_font.render("×", True, (60,60,60)), (w-30, 6))

        # ボタン: 左=デッキ編集, 中=デッキ詳細, 右=デッキ削除
        btn_h = 40
        padding = 20
        gap = 20
        max_btn_w = (w - padding*2 - gap*2) // 3
        btn_w = min(140, max_btn_w)
        bx = (w - (btn_w*3 + gap*2)) // 2
        by = h - padding - btn_h
        edit_rect_local = pygame.Rect(bx, by, btn_w, btn_h)
        view_rect_local = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
        delete_rect_local = pygame.Rect(bx + (btn_w + gap)*2, by, btn_w, btn_h)
        pygame.draw.rect(box, (220, 220, 255), edit_rect_local)
        pygame.draw.rect(box, (200, 240, 200), view_rect_local)
        pygame.draw.rect(box, (255, 200, 200), delete_rect_local)
        pygame.draw.rect(box, (80,80,80), edit_rect_local, 2)
        pygame.draw.rect(box, (80,80,80), view_rect_local, 2)
        pygame.draw.rect(box, (80,80,80), delete_rect_local, 2)
        # center labels
        et = btn_font.render("デッキ編集", True, (30,30,30))
        vt = btn_font.render("デッキ詳細", True, (30,30,30))
        dt = btn_font.render("デッキ削除", True, (30,30,30))
        box.blit(et, (edit_rect_local.x + (btn_w - et.get_width())//2, edit_rect_local.y + (btn_h - et.get_height())//2))
        box.blit(vt, (view_rect_local.x + (btn_w - vt.get_width())//2, view_rect_local.y + (btn_h - vt.get_height())//2))
        box.blit(dt, (delete_rect_local.x + (btn_w - dt.get_width())//2, delete_rect_local.y + (btn_h - dt.get_height())//2))

        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


def show_deck_contents_overlay(screen, W, H, FONT, SMALL, TINY, deck):
    """デッキ内容オーバーレイ表示（画像ベース、重複カードは×n表示）
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        FONT, SMALL, TINY: フォントオブジェクト
        deck: デッキ辞書
    """
    # カード画像ローダーをインポート
    get_card_image = None
    try:
        from ..assets.image_loader import get_card_image
    except Exception:
        try:
            from assets.image_loader import get_card_image
        except Exception:
            try:
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                ccb_dir = os.path.dirname(os.path.dirname(current_dir))
                assets_dir = os.path.join(ccb_dir, 'assets')
                if assets_dir not in sys.path:
                    sys.path.insert(0, assets_dir)
                from image_loader import get_card_image
            except Exception:
                get_card_image = None
    
    clk = pygame.time.Clock()
    w = min(800, W - 100)
    h = min(600, H - 100)
    x = (W - w)//2
    y = (H - h)//2
    # Use a Japanese-capable font for the title to avoid garbled text
    try:
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28)
        count_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18, bold=True)
    except Exception:
        title_font = pygame.font.SysFont(None, 28)
        count_font = pygame.font.SysFont(None, 18)

    # カードを集計（重複をカウント）
    card_counts = {}
    for c in deck.get('cards', []):
        if isinstance(c, dict):
            name = str(c.get('name', '不明'))
        else:
            name = str(c)
        card_counts[name] = card_counts.get(name, 0) + 1
    
    # ユニークなカードリストを作成
    unique_cards = list(card_counts.keys())

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # クリックがモーダル外なら閉じる
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return
                # 内部クリック -> ローカル座標で閉じるボタンをチェック
                lx = mx - x
                ly = my - y
                # close icon rect (same as drawn below)
                if (w - 34) <= lx <= (w - 8) and 8 <= ly <= 34:
                    return
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0,0))

        box = pygame.Surface((w, h))
        box.fill((245,245,250))
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render(deck.get('name', 'デッキ'), True, (30,30,30))
        box.blit(title, (20, 12))

        # close icon inside the modal (top-right)
        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            box.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass

        # カード画像を表示（グリッド形式）
        card_w = 90
        card_h = 120
        margin = 15
        start_x = 20
        start_y = 55
        cols = (w - start_x * 2) // (card_w + margin)
        
        for idx, card_name in enumerate(unique_cards):
            col = idx % cols
            row = idx // cols
            cx = start_x + col * (card_w + margin)
            cy = start_y + row * (card_h + margin + 10)
            
            # 描画領域チェック
            if cy + card_h > h - 40:
                break
            
            # カード画像を描画
            if get_card_image:
                try:
                    card_img = get_card_image(card_name, size=(card_w, card_h))
                    if card_img is None:
                        raise Exception("card_img is None")
                    box.blit(card_img, (cx, cy))
                except Exception:
                    # フォールバック: テキスト表示
                    pygame.draw.rect(box, (255, 255, 255), (cx, cy, card_w, card_h))
                    pygame.draw.rect(box, (100, 100, 100), (cx, cy, card_w, card_h), 2)
                    # カード名を複数行に分割して表示
                    name_lines = []
                    if len(card_name) > 8:
                        name_lines.append(card_name[:8])
                        name_lines.append(card_name[8:])
                    else:
                        name_lines.append(card_name)
                    
                    name_y = cy + 10
                    for line in name_lines:
                        name_surf = TINY.render(line, True, (30, 30, 30))
                        name_rect = name_surf.get_rect(center=(cx + card_w // 2, name_y))
                        box.blit(name_surf, name_rect)
                        name_y += 16
            else:
                # get_card_imageが使えない場合のフォールバック
                pygame.draw.rect(box, (255, 255, 255), (cx, cy, card_w, card_h))
                pygame.draw.rect(box, (100, 100, 100), (cx, cy, card_w, card_h), 2)
                name_surf = TINY.render(card_name, True, (30, 30, 30))
                name_rect = name_surf.get_rect(center=(cx + card_w // 2, cy + card_h // 2))
                box.blit(name_surf, name_rect)
            
            # 重複数を右下に表示（2枚以上の場合）
            count = card_counts[card_name]
            if count > 1:
                # 半透明の背景
                count_bg = pygame.Surface((30, 22), pygame.SRCALPHA)
                count_bg.fill((0, 0, 0, 180))
                box.blit(count_bg, (cx + card_w - 32, cy + card_h - 24))
                
                # ×n テキスト
                count_text = count_font.render(f"×{count}", True, (255, 255, 255))
                box.blit(count_text, (cx + card_w - 30, cy + card_h - 22))

        hint = TINY.render("外側をクリックすると閉じる", True, (80,80,80))
        box.blit(hint, (w - hint.get_width() - 12, h - 28))
        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


def show_deck_editor(screen, W, H, get_font, FONT, SMALL, existing_deck, slot_idx):
    """デッキ作成/編集画面
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        get_font: フォント取得関数
        FONT, SMALL: フォントオブジェクト
        existing_deck: 既存のデッキ（編集時）またはNone（新規作成時）
        slot_idx: デッキスロット番号（0-8）
    
    Returns:
        作成/編集されたデッキ辞書、またはNone（キャンセル時）
    """
    import pygame
    import sys
    from datetime import datetime
    
    # 利用可能な全カード（ゲーム内で使用されるカードリスト）
    available_cards = [
        {'name': '灼熱', 'cost': 2},
        {'name': '氷結', 'cost': 2},
        {'name': '暴風', 'cost': 3},
        {'name': '迅雷', 'cost': 3},
        {'name': '2ドロー', 'cost': 1},
        {'name': '錬成', 'cost': 0},
        {'name': '墓地ルーレット', 'cost': 1},
        {'name': '摂取', 'cost': 1},
        {'name': '命がけのギャンブル', 'cost': 3},
        {'name': '負けるわけないだろwww', 'cost': 4},
        {'name': '鉄壁', 'cost': 2},
        {'name': 'ハンです☆', 'cost': 2},
    ]
    
    # 現在のデッキカード
    if existing_deck:
        deck_cards = existing_deck.get('cards', []).copy()
        deck_name = existing_deck.get('name', f'デッキ{slot_idx + 1}')
    else:
        deck_cards = []
        deck_name = f'デッキ{slot_idx + 1}'
    
    clock = pygame.time.Clock()
    scroll_offset = 0
    input_active = False
    input_text = deck_name
    
    # 日本語入力を有効化
    pygame.key.start_text_input()
    # initialize local window size variables (static analyzer friendly)
    win_w, win_h = screen.get_size()
    
    while True:
        # update current window size each frame (used for layout)
        win_w, win_h = screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            
            # TEXTINPUT イベントで日本語・英数字入力を受け取る（Pygame 2.x以降）
            if event.type == pygame.TEXTINPUT and input_active:
                if len(input_text) < 20:
                    input_text += event.text
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.key.stop_text_input()
                    return None
                if input_active:
                    if event.key == pygame.K_RETURN:
                        input_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                
                # 保存ボタン
                save_rect = pygame.Rect(win_w - 250, win_h - 70, 120, 50)
                if save_rect.collidepoint(mx, my):
                    # デッキ枚数チェック
                    if len(deck_cards) < 20:
                        logger.debug("save clicked with %d cards (<20) - entering confirmation dialog", len(deck_cards))
                        # 20枚未満でも保存を許可するか確認するダイアログに変更
                        # 「破棄する」-> 変更を破棄して戻る
                        # 「保存する」-> 20枚未満だが保存してデッキリストに戻る
                        show_warning = True
                        while show_warning:
                            for warn_ev in pygame.event.get():
                                if warn_ev.type == pygame.QUIT:
                                    pygame.quit(); sys.exit(0)
                                if warn_ev.type == pygame.MOUSEBUTTONDOWN and warn_ev.button == 1:
                                    wmx, wmy = warn_ev.pos
                                    dialog_w, dialog_h = 500, 220
                                    dialog_x = (win_w - dialog_w) // 2
                                    dialog_y = (win_h - dialog_h) // 2

                                    # 破棄ボタン
                                    discard_rect = pygame.Rect(dialog_x + 60, dialog_y + 140, 160, 50)
                                    if discard_rect.collidepoint(wmx, wmy):
                                        logger.debug("user selected DISCARD in low-deck dialog")
                                        pygame.key.stop_text_input()
                                        return None  # 変更破棄してデッキリストへ

                                    # 保存するボタン
                                    save_anyway_rect = pygame.Rect(dialog_x + 280, dialog_y + 140, 160, 50)
                                    if save_anyway_rect.collidepoint(wmx, wmy):
                                        logger.debug("user selected SAVE ANYWAY in low-deck dialog")
                                        # 20枚未満だが保存して戻る
                                        pygame.key.stop_text_input()
                                        return {
                                            'name': input_text if input_text.strip() else f'デッキ{slot_idx + 1}',
                                            'cards': deck_cards,
                                            'created_at': existing_deck.get('created_at', datetime.now().isoformat()) if existing_deck else datetime.now().isoformat()
                                        }

                            # 警告ダイアログ描画
                            overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
                            overlay.fill((0, 0, 0, 160))
                            screen.blit(overlay, (0, 0))

                            dialog_surf = pygame.Surface((dialog_w, dialog_h))
                            dialog_surf.fill((245, 245, 250))
                            pygame.draw.rect(dialog_surf, (200, 100, 100), (0, 0, dialog_w, dialog_h), 4)

                            # メッセージ
                            warn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18, bold=True)
                            msg1 = warn_font.render("20枚未満なのでバトルで使用できません。", True, (30, 30, 30))
                            msg2 = warn_font.render("このまま保存しますか？ (バトルでは使用不可)", True, (30, 30, 30))
                            dialog_surf.blit(msg1, ((dialog_w - msg1.get_width()) // 2, 40))
                            dialog_surf.blit(msg2, ((dialog_w - msg2.get_width()) // 2, 70))

                            # 破棄ボタン
                            discard_rect = pygame.Rect(60, 140, 160, 50)
                            pygame.draw.rect(dialog_surf, (255, 200, 200), discard_rect)
                            pygame.draw.rect(dialog_surf, (160, 60, 60), discard_rect, 3)
                            discard_text = FONT.render("破棄する", True, (30, 30, 30))
                            dialog_surf.blit(discard_text, (discard_rect.x + (discard_rect.width - discard_text.get_width()) // 2,
                                                            discard_rect.y + (discard_rect.height - discard_text.get_height()) // 2))

                            # 保存するボタン
                            save_anyway_rect = pygame.Rect(280, 140, 160, 50)
                            pygame.draw.rect(dialog_surf, (200, 255, 200), save_anyway_rect)
                            pygame.draw.rect(dialog_surf, (60, 160, 60), save_anyway_rect, 3)
                            save_anyway_text = FONT.render("保存する", True, (30, 30, 30))
                            dialog_surf.blit(save_anyway_text, (save_anyway_rect.x + (save_anyway_rect.width - save_anyway_text.get_width()) // 2,
                                                                save_anyway_rect.y + (save_anyway_rect.height - save_anyway_text.get_height()) // 2))

                            screen.blit(dialog_surf, (dialog_x, dialog_y))
                            pygame.display.flip()
                            clock.tick(30)
                    
                    # 20枚以上なら保存
                    pygame.key.stop_text_input()
                    return {
                        'name': input_text if input_text.strip() else f'デッキ{slot_idx + 1}',
                        'cards': deck_cards,
                        'created_at': existing_deck.get('created_at', datetime.now().isoformat()) if existing_deck else datetime.now().isoformat()
                    }
                
                # キャンセルボタン
                cancel_rect = pygame.Rect(win_w - 140, win_h - 70, 120, 50)
                if cancel_rect.collidepoint(mx, my):
                    pygame.key.stop_text_input()
                    return None
                
                # 名前入力欄
                name_rect = pygame.Rect(150, 20, 400, 40)
                if name_rect.collidepoint(mx, my):
                    input_active = True
                else:
                    input_active = False
                
                # カードリストクリック（追加）
                list_start_y = 110  # 描画と同じ位置に修正
                card_h = 50
                for i, card in enumerate(available_cards):
                    card_y = list_start_y + i * card_h - scroll_offset
                    if 110 <= card_y < H - 100:  # 範囲も修正
                        card_rect = pygame.Rect(20, card_y, 500, card_h - 5)
                        if card_rect.collidepoint(mx, my):
                            # 同じカードが最大3枚まで
                            count = sum(1 for c in deck_cards if c['name'] == card['name'])
                            if count < 3:
                                deck_cards.append(card.copy())
                            break
                
                # デッキカードクリック（削除）- 集計表示に対応
                deck_start_x = win_w - 420
                # カードを集計
                card_counts = {}
                for card in deck_cards:
                    key = card['name']
                    if key not in card_counts:
                        card_counts[key] = {'name': card['name'], 'cost': card['cost'], 'count': 0}
                    card_counts[key]['count'] += 1
                
                display_idx = 0
                for card_info in card_counts.values():
                    card_y = list_start_y + display_idx * card_h
                    if 110 <= card_y < win_h - 100:
                        card_rect = pygame.Rect(deck_start_x, card_y, 400, card_h - 5)
                        if card_rect.collidepoint(mx, my):
                            # このカードを1枚削除
                            for i, c in enumerate(deck_cards):
                                if c['name'] == card_info['name']:
                                    deck_cards.pop(i)
                                    break
                            break
                    display_idx += 1
            
            if event.type == pygame.MOUSEWHEEL:
                scroll_offset -= event.y * 30
                scroll_offset = max(0, min(scroll_offset, len(available_cards) * 50 - 400))
        
        # 背景
        screen.fill((240, 235, 230))
        
        # タイトル
        title_font = get_font(28, bold=True)
        title = title_font.render("デッキ作成/編集", True, (30, 30, 30))
        screen.blit(title, (20, 25))
        
        # 名前入力欄
        name_rect = pygame.Rect(150, 20, 400, 40)
        pygame.draw.rect(screen, (255, 255, 255) if input_active else (240, 240, 240), name_rect)
        pygame.draw.rect(screen, (100, 150, 255) if input_active else (100, 100, 100), name_rect, 2)
        # 日本語対応フォントを直接ファイル指定で取得
        try:
            # Windowsの標準日本語フォントを直接読み込み
            import os
            font_paths = [
                "C:\\Windows\\Fonts\\msgothic.ttc",  # MSゴシック
                "C:\\Windows\\Fonts\\meiryo.ttc",    # メイリオ
                "C:\\Windows\\Fonts\\yugothic.ttf",  # 遊ゴシック
            ]
            name_font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    name_font = pygame.font.Font(font_path, 24)
                    break
            if name_font is None:
                # フォールバック: システムフォント
                name_font = pygame.font.SysFont("msgothic,meiryo", 24)
        except:
            # 最終フォールバック
            name_font = pygame.font.Font(None, 24)
        
        name_text = name_font.render(input_text if input_text else "", True, (30, 30, 30))
        screen.blit(name_text, (name_rect.x + 10, name_rect.y + 8))
        
        # カーソル表示（点滅）
        if input_active:
            import time
            if int(time.time() * 2) % 2 == 0:  # 0.5秒ごとに点滅
                cursor_x = name_rect.x + 10 + name_text.get_width()
                cursor_y = name_rect.y + 8
                pygame.draw.line(screen, (30, 30, 30), 
                               (cursor_x, cursor_y), 
                               (cursor_x, cursor_y + name_text.get_height()), 2)
        
        # 全カードリスト
        list_title = FONT.render("全カード（クリックで追加）", True, (30, 30, 30))
        screen.blit(list_title, (20, 70))
        
        card_h = 50
        list_start_y = 110
        for i, card in enumerate(available_cards):
            card_y = list_start_y + i * card_h - scroll_offset
            if 80 <= card_y < H - 100:
                card_rect = pygame.Rect(20, card_y, 500, card_h - 5)
                pygame.draw.rect(screen, (220, 240, 255), card_rect)
                pygame.draw.rect(screen, (100, 120, 180), card_rect, 2)
                
                card_text = SMALL.render(f"{card['name']} (コスト: {card['cost']})", True, (30, 30, 30))
                screen.blit(card_text, (card_rect.x + 10, card_rect.y + 15))
                
                # デッキ内の枚数表示
                count = sum(1 for c in deck_cards if c['name'] == card['name'])
                if count > 0:
                    count_text = SMALL.render(f"{count}/3", True, (160, 60, 60) if count >= 3 else (60, 160, 60))
                    screen.blit(count_text, (card_rect.x + 450, card_rect.y + 15))
        
        # デッキ内カードリスト（画像表示、重複をまとめて表示）
        deck_start_x = W - 420
        deck_title = FONT.render(f"デッキ内カード（{len(deck_cards)}枚）", True, (30, 30, 30))
        screen.blit(deck_title, (deck_start_x, 70))
        
        # カードを集計（重複をまとめる）
        card_counts = {}
        for card in deck_cards:
            key = card['name']
            if key not in card_counts:
                card_counts[key] = {'name': card['name'], 'cost': card['cost'], 'count': 0}
            card_counts[key]['count'] += 1
        
        # 画像表示用の設定
        card_img_width = 120
        card_img_height = 160
        cards_per_row = 3
        card_spacing = 10
        
        # 集計結果を画像で表示
        display_idx = 0
        for card_info in card_counts.values():
            row = display_idx // cards_per_row
            col = display_idx % cards_per_row
            
            card_x = deck_start_x + col * (card_img_width + card_spacing)
            card_y = list_start_y + row * (card_img_height + card_spacing)
            
            if 110 <= card_y < H - 100:
                # カード画像を取得・表示
                try:
                    # image_loaderからget_card_imageをインポート
                    try:
                        from assets.image_loader import get_card_image
                    except:
                        from ..assets.image_loader import get_card_image
                    
                    card_img = get_card_image(card_info['name'])
                    if card_img:
                        # 画像をリサイズ
                        card_img_resized = pygame.transform.scale(card_img, (card_img_width, card_img_height))
                        screen.blit(card_img_resized, (card_x, card_y))
                        
                        # 枚数表示（右下に×n）
                        if card_info['count'] > 1:
                            # 半透明の背景
                            count_bg = pygame.Surface((40, 25), pygame.SRCALPHA)
                            count_bg.fill((0, 0, 0, 180))
                            screen.blit(count_bg, (card_x + card_img_width - 45, card_y + card_img_height - 30))
                            
                            # ×n表示
                            count_font = pygame.font.SysFont("arial", 18, bold=True)
                            count_text = count_font.render(f"×{card_info['count']}", True, (255, 255, 255))
                            screen.blit(count_text, (card_x + card_img_width - 40, card_y + card_img_height - 28))
                    else:
                        # 画像が取得できない場合はフォールバック（テキスト表示）
                        card_rect = pygame.Rect(card_x, card_y, card_img_width, card_img_height)
                        pygame.draw.rect(screen, (255, 240, 220), card_rect)
                        pygame.draw.rect(screen, (180, 120, 100), card_rect, 2)
                        
                        # カード名を表示（テキストを複数行に分割）
                        small_font = pygame.font.SysFont("msgothic,meiryo", 14)
                        name_lines = []
                        name = card_info['name']
                        # 長い名前は折り返し
                        if len(name) > 10:
                            name_lines = [name[i:i+10] for i in range(0, len(name), 10)]
                        else:
                            name_lines = [name]
                        
                        y_offset = 10
                        for line in name_lines:
                            line_surf = small_font.render(line, True, (30, 30, 30))
                            screen.blit(line_surf, (card_x + 5, card_y + y_offset))
                            y_offset += 20
                        
                        # コストと枚数
                        cost_text = small_font.render(f"PP:{card_info['cost']}", True, (60, 60, 160))
                        screen.blit(cost_text, (card_x + 5, card_y + card_img_height - 40))
                        
                        count_text = small_font.render(f"×{card_info['count']}", True, (160, 60, 60))
                        screen.blit(count_text, (card_x + 5, card_y + card_img_height - 20))
                except Exception as e:
                    # エラー時のフォールバック
                    card_rect = pygame.Rect(card_x, card_y, card_img_width, card_img_height)
                    pygame.draw.rect(screen, (255, 240, 220), card_rect)
                    pygame.draw.rect(screen, (180, 120, 100), card_rect, 2)
                    small_font = pygame.font.SysFont("arial", 12)
                    err_text = small_font.render(card_info['name'][:15], True, (30, 30, 30))
                    screen.blit(err_text, (card_x + 5, card_y + 70))
            
            display_idx += 1
        
        # ボタン類
        save_rect = pygame.Rect(W - 250, H - 70, 120, 50)
        pygame.draw.rect(screen, (200, 255, 200), save_rect)
        pygame.draw.rect(screen, (60, 160, 60), save_rect, 3)
        save_text = FONT.render("保存", True, (30, 30, 30))
        screen.blit(save_text, (save_rect.x + (save_rect.width - save_text.get_width()) // 2,
                               save_rect.y + (save_rect.height - save_text.get_height()) // 2))
        
        cancel_rect = pygame.Rect(W - 140, H - 70, 120, 50)
        pygame.draw.rect(screen, (255, 200, 200), cancel_rect)
        pygame.draw.rect(screen, (160, 60, 60), cancel_rect, 3)
        cancel_text = FONT.render("戻る", True, (30, 30, 30))
        screen.blit(cancel_text, (cancel_rect.x + (cancel_rect.width - cancel_text.get_width()) // 2,
                                 cancel_rect.y + (cancel_rect.height - cancel_text.get_height()) // 2))
        
        pygame.display.flip()
        clock.tick(30)


def show_custom_deck_selection(screen, W, H, FONT, SMALL, load_saved_decks, show_deck_modal, 
                                build_game_from_card_names, new_game_with_mode, build_ai_player,
                                DECK_MODE_setter, game_setter):
    """保存された作成デッキを一覧表示して選択する画面。
    
    saved_decks.json に保存されたデッキ（存在するもの）を表示し、
    選択されるとそのデッキでゲームを開始します。
    作成済みデッキがない場合は「作る」ボタンでデッキ作成画面へ移動できます。
    
    Args:
        screen: pygame surface
        W, H: ウィンドウサイズ
        FONT, SMALL: フォントオブジェクト
        load_saved_decks: 保存デッキ読み込み関数
        show_deck_modal: デッキモーダル表示関数
        build_game_from_card_names: カード名リストからゲーム構築関数
        new_game_with_mode: デッキモードでゲーム作成関数
        build_ai_player: AIプレイヤー作成関数
        DECK_MODE_setter: デッキモード設定関数
        game_setter: ゲームインスタンス設定関数
    """
    clk = pygame.time.Clock()

    # saved_decks に格納されたデッキ群（9スロット）を読み込む
    saved = load_saved_decks()
    # 表示用の (slot_idx, name) リストを作る（None のスロットは除外）
    choices = []
    for i, d in enumerate(saved):
        if d:
            choices.append((i, d.get('name', f'デッキ{i+1}')))

    # Flush the click/touch that opened the modal so it doesn't immediately
    # register here and cause an accidental selection.
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass

    w = 640
    h = 360
    x = (W - w)//2
    y = (H - h)//2
    entry_h = 56
    pad = 20
    start_y = y + 64

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                if not (x <= mx <= x + w and y <= my <= y + h):
                    continue
                rel_y = my - start_y
                idx = rel_y // (entry_h + pad)
                if 0 <= idx < max(1, len(choices)):
                    # choices が空ならメッセージ領域のボタン（作る/戻る）を処理
                    if not choices:
                        # ボタン領域を計算
                        btn_w = 120
                        make_rect = pygame.Rect(x + 80, y + h - 90, btn_w, 50)
                        back_rect = pygame.Rect(x + w - 200, y + h - 90, btn_w, 50)
                        if make_rect.collidepoint(mx, my):
                            # デッキ作成画面（グリッド）へ移動
                            show_deck_modal(screen)
                            # 再読み込み
                            saved = load_saved_decks()
                            choices = [(i, d.get('name', f'デッキ{i+1}')) for i, d in enumerate(saved) if d]
                            continue
                        if back_rect.collidepoint(mx, my):
                            return
                        continue

                    # choices から選択されたスロットを特定
                    if idx < len(choices):
                        slot_idx = choices[idx][0]
                        deck = saved[slot_idx]
                        # deck のカード名リストを取得。保存形式がオブジェクト一覧の場合は名前列に変換する
                        names = None
                        if deck:
                            cards_field = deck.get('cards')
                            if isinstance(cards_field, list):
                                if cards_field and isinstance(cards_field[0], dict):
                                    names = [str(c.get('name')) for c in cards_field if c and 'name' in c]
                                else:
                                    names = [str(x) for x in cards_field]
                        DECK_MODE_setter('custom')
                        # ゲーム作成ロジックは既存の関数を再利用（存在確認）
                        try:
                            logger.debug("selection modal starting battle, names=%s", names)
                            if names and build_game_from_card_names:
                                game_setter(build_game_from_card_names(names))
                            else:
                                game_setter(new_game_with_mode('custom'))
                            # Note: ai_player is not set here; caller must handle it
                            try:
                                logger.debug("created game deck from custom selection")
                            except Exception as _e:
                                logger.debug("error inspecting created game: %s", _e)
                        except Exception as e:
                            logger.debug("exception when creating game from names: %s", e)
                            game_setter(new_game_with_mode('custom'))
                        return

        # draw overlay and modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((245,245,250))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)
        title = FONT.render("作成デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        ty = 0
        if not choices:
            # 作成済みデッキがない場合の案内表示
            info = SMALL.render("作成済みのデッキがありません。デッキ作成で新しいデッキを作成してください。", True, (60,60,60))
            surf.blit(info, (20, 80))
            # 作る / 戻る ボタン
            make_rect = pygame.Rect(80, h - 90, 120, 50)
            back_rect = pygame.Rect(w - 200, h - 90, 120, 50)
            pygame.draw.rect(surf, (200, 240, 200), make_rect)
            pygame.draw.rect(surf, (80, 120, 80), make_rect, 3)
            pygame.draw.rect(surf, (240, 200, 200), back_rect)
            pygame.draw.rect(surf, (120, 80, 80), back_rect, 3)
            surf.blit(SMALL.render("作る", True, (30,30,30)), (make_rect.x + 36, make_rect.y + 14))
            surf.blit(SMALL.render("戻る", True, (30,30,30)), (back_rect.x + 36, back_rect.y + 14))
        else:
            for i, (slot_idx, name) in enumerate(choices):
                ex = pygame.Rect(pad, start_y - y + ty, w - pad*2, entry_h)
                pygame.draw.rect(surf, (220,220,220), ex)
                pygame.draw.rect(surf, (70,70,70), ex, 2)
                ntxt = SMALL.render(name, True, (30,30,30))
                surf.blit(ntxt, (ex.x + 12, ex.y + (entry_h - ntxt.get_height())//2))
                # 枚数表示
                deck = saved[slot_idx]
                cnt_txt = ""
                if deck and 'cards' in deck:
                    cnt_txt = f"{len(deck['cards'])} 枚"
                if cnt_txt:
                    ctxt = SMALL.render(cnt_txt, True, (80,80,80))
                    surf.blit(ctxt, (ex.right - ctxt.get_width() - 12, ex.y + (entry_h - ctxt.get_height())//2))
                ty += entry_h + pad

        screen.blit(surf, (x,y))
        pygame.display.flip()
        clk.tick(30)


