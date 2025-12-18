"""ゲーム画面関連のモーダル

このモジュールは、ゲームの主要な画面を提供します。
- スタート画面（難易度選択）
- 設定画面
"""

import pygame
import os
import sys
import logging
from ui.config import get_ui_effects_enabled

logger = logging.getLogger(__name__)


def show_start_screen(screen, get_font, IMG_DIR, set_bgm_mode_func, 
                     show_deck_choice_modal_func, show_deck_modal_func,
                     show_settings_screen_func, new_game_with_mode_func,
                     build_ai_player_func, get_deck_mode_func, SMALL_font):
    """起動時に難易度を選択する簡易メニュー。
    1-4 のキーか、画面上のボタンで選択可能。選択はグローバル CPU_DIFFICULTY に保存される。
    
    Args:
        screen: pygame display surface
        get_font: フォント取得関数
        IMG_DIR: 画像ディレクトリパス
        set_bgm_mode_func: BGMモード設定関数
        show_deck_choice_modal_func: デッキ選択モーダル表示関数
        show_deck_modal_func: デッキモーダル表示関数
        show_settings_screen_func: 設定画面表示関数
        new_game_with_mode_func: ゲーム作成関数
        build_ai_player_func: AIプレイヤー構築関数
        get_deck_mode_func: デッキモード取得関数
        SMALL_font: 小さいフォント
        
    Returns:
        tuple: (CPU_DIFFICULTY, game, ai_player) または None（キャンセル時）
    """
    # 初期ウィンドウサイズを取得
    W, H = screen.get_size()
    
    # Prefer a repo-local background image (if present), otherwise fall back to user's Downloads
    repo_bg_path = os.path.join(IMG_DIR, "ChatGPT Image 2025年10月21日 14_06_32.png")
    user_bg_path = r"c:\Users\Student\Downloads\ChatGPT Image 2025年10月21日 14_06_32.png"
    bg_surf = None
    repo_bg_used = False
    try:
        if os.path.exists(repo_bg_path):
            img = pygame.image.load(repo_bg_path)
            bg_surf = pygame.transform.smoothscale(img, (W, H)).convert()
            repo_bg_used = True
        elif os.path.exists(user_bg_path):
            img = pygame.image.load(user_bg_path)
            bg_surf = pygame.transform.smoothscale(img, (W, H)).convert()
    except Exception:
        bg_surf = None

    # normalize names and prepare UI metrics/fonts used below
    bg = bg_surf
    # keep the original loaded image (if any) for rescaling on resize
    bg_img = locals().get('img', None)

    # Try to play title BGM (non-fatal if audio subsystem or file missing)
    try:
        set_bgm_mode_func('title')
    except Exception:
        pass

    clock = pygame.time.Clock()
    CPU_DIFFICULTY = None
    game = None
    ai_player = None

    while True:
        # Use the actual current surface size from the passed-in screen so the
        # UI aligns correctly when this module is used as an imported UI.
        win_w, win_h = screen.get_size()
        W, H = win_w, win_h
        
        # recompute fonts/layout each frame so start screen responds to VIDEORESIZE
        title_font = get_font(max(32, int(H * 0.05)), bold=True)
        btn_font = get_font(max(20, int(H * 0.03)), bold=True)
        options = [("1 - 簡単", 1), ("2 - ノーマル", 2), ("3 - ハード", 3), ("4 - ベリーハード", 4)]
        # ボタン幅を広げてテキストが見切れないようにする
        btn_w = 240
        btn_h = 80
        # use larger horizontal spacing between buttons to match screenshot
        spacing = 20
        total_h = len(options) * btn_h + (len(options) - 1) * spacing
        # place title near top and move buttons further down to create generous whitespace like reference
        title_y = int(H * 0.08)
        # create a larger vertical gap between title and buttons per user request
        start_y = title_y + title_font.get_height() + 240

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.VIDEORESIZE:
                # update window size and recreate screen surface
                try:
                    W, H = max(200, event.w), max(200, event.h)
                    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                    # rescale background image if we have the original loaded image
                    if bg_img is not None:
                        try:
                            bg = pygame.transform.smoothscale(bg_img, (W, H)).convert()
                        except Exception:
                            bg = bg_surf
                except Exception:
                    pass
            # keyboard selection (1-4)
            if event.type == pygame.KEYDOWN:
                if pygame.K_1 <= event.key <= pygame.K_4:
                    CPU_DIFFICULTY = event.key - pygame.K_0
                    # After difficulty selection, let user pick deck mode
                    try:
                        selected = show_deck_choice_modal_func(screen)
                    except Exception:
                        selected = False
                    # if the user canceled (Esc/×), don't start the game; keep showing menu
                    if not selected:
                        continue
                    # if custom decks were selected, show deck list to pick which deck to use
                    try:
                        DECK_MODE = get_deck_mode_func()
                        if DECK_MODE == 'custom':
                            started = show_deck_modal_func(screen, battle_select_mode=True)
                            if started:
                                # game と ai_player はグローバルに設定されている
                                return (CPU_DIFFICULTY, None, None)
                            else:
                                continue
                        else:
                            game = new_game_with_mode_func(DECK_MODE)
                            ai_player = build_ai_player_func(DECK_MODE)
                    except Exception:
                        pass
                    return (CPU_DIFFICULTY, game, ai_player)
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit(0)

            # mouse click or touch (FINGERDOWN)
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1) or event.type == pygame.FINGERDOWN:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                else:
                    # map normalized touch coords to screen coords
                    mx = int(event.x * W)
                    my = int(event.y * H)

                # check difficulty buttons (horizontal layout)
                btn_x = (W - (btn_w*len(options) + spacing*(len(options)-1)))//2
                for i, (_lab, val) in enumerate(options):
                    bx = btn_x + i * (btn_w + spacing)
                    by = start_y
                    if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
                        CPU_DIFFICULTY = val
                        # deck choice modal
                        try:
                            selected = show_deck_choice_modal_func(screen)
                        except Exception:
                            selected = False
                        if not selected:
                            continue
                        try:
                            DECK_MODE = get_deck_mode_func()
                            if DECK_MODE == 'custom':
                                started = show_deck_modal_func(screen, battle_select_mode=True)
                                if started:
                                    return (CPU_DIFFICULTY, None, None)
                                else:
                                    continue
                            else:
                                game = new_game_with_mode_func(DECK_MODE)
                                ai_player = build_ai_player_func(DECK_MODE)
                                # Ensure AI gets starting hand when created from start screen
                                try:
                                    import __main__ as _m
                                    if hasattr(_m, '_init_ai_start_hand'):
                                        try:
                                            _m._init_ai_start_hand(ai_player, 4, game)
                                        except Exception:
                                            pass
                                    else:
                                        try:
                                            got = len(getattr(ai_player, 'hand').cards or []) if ai_player is not None else 0
                                        except Exception:
                                            got = 0
                                        if got == 0 and ai_player is not None and hasattr(ai_player, 'deck') and getattr(ai_player, 'deck') is not None:
                                            for _ in range(4):
                                                try:
                                                    c = ai_player.deck.draw()
                                                    if c is not None:
                                                        ai_player.hand.add(c)
                                                except Exception:
                                                    pass
                                            try:
                                                if game and hasattr(game, 'log'):
                                                    game.log.append('[注意] AIの初期手札が0枚だったため、デッキから4枚を強制的に配布しました。')
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                                try:
                                    logger.debug("game created (start_screen) id=%s deck_count=%s", id(game), len(getattr(game.player.deck,'cards',[])) if game and hasattr(game,'player') else 'NA')
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return (CPU_DIFFICULTY, game, ai_player)

                # deck button (centered below) - match the drawing coordinates used later
                deck_w = 220  # matches deck_btn_w when drawing
                deck_h = 64   # matches deck_btn_h when drawing
                deck_x = (W - deck_w)//2
                # compute deck_y to match drawing: hint_y = start_y + btn_h + 140; deck_y = hint_y + 100
                deck_y = start_y + btn_h + 240
                # settings button on the left (same vertical position as deck button)
                settings_w = 180
                settings_h = deck_h
                settings_x = 20
                settings_y = deck_y
                if settings_x <= mx <= settings_x + settings_w and settings_y <= my <= settings_y + settings_h:
                    # open settings modal/screen
                    show_settings_screen_func(screen)
                    # consume click and continue the main loop (settings handles its own loop)
                    continue
                if deck_x <= mx <= deck_x + deck_w and deck_y <= my <= deck_y + deck_h:
                    # open deck selection modal (deck editor requires slot context)
                    show_deck_modal_func(screen)

        # draw background (image if available) - prefer sepia image
        if bg is not None:
            screen.blit(bg, (0,0))
            # If repo image is used, it's likely already properly exposed; apply a tiny brighten.
            if repo_bg_used:
                bright = pygame.Surface((W, H), pygame.SRCALPHA)
                bright.fill((255,255,255,20))
                screen.blit(bright, (0,0))
            else:
                # For user-provided images, apply stronger brighten to reach the desired level
                bright = pygame.Surface((W, H), pygame.SRCALPHA)
                bright.fill((255,255,255,100))
                screen.blit(bright, (0,0))
        else:
            # lighter sepia fallback
            screen.fill((150, 100, 50))

        # gentle dark overlay to maintain contrast but keep background visible
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))

        # Title with outline (dark fill with light outline to match screenshot)
        title_text = "CPUの難易度を設定してください"
        title_surf = title_font.render(title_text, True, (30,30,30))
        tx = (W - title_surf.get_width())//2
        ty = title_y
        # subtle outline (light) behind the darker text
        outline_surf = title_font.render(title_text, True, (240,240,240))
        for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            screen.blit(outline_surf, (tx+ox, ty+oy))
        screen.blit(title_surf, (tx, ty))

        # horizontal buttons (4 across) to match provided image
        btn_x = (W - (btn_w*4 + spacing*3))//2
        for i, (lab, val) in enumerate(options):
            bx = btn_x + i * (btn_w + spacing)
            by = start_y
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            # button fill and darker border
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (80,80,80), rect, 4)
            txt = btn_font.render(lab, True, (30,30,30))
            screen.blit(txt, (bx + (btn_w-txt.get_width())//2, by + (btn_h-txt.get_height())//2))

        # hint text and deck button (centered below buttons) - push further down per request
        hint = title_font.render("キー1-4でも選択できます。Escで終了", True, (240,240,240))
        hint_y = start_y + btn_h + 140
        screen.blit(hint, ((W-hint.get_width())//2, hint_y))

        deck_btn_w = 220
        deck_btn_h = 64
        deck_x = (W - deck_btn_w)//2
        deck_y = hint_y + 100
        deck_rect = pygame.Rect(deck_x, deck_y, deck_btn_w, deck_btn_h)
        pygame.draw.rect(screen, (230,230,230), deck_rect)
        pygame.draw.rect(screen, (70,70,70), deck_rect, 3)
        dtxt = btn_font.render("デッキ作成", True, (30,30,30))
        screen.blit(dtxt, (deck_x + (deck_btn_w - dtxt.get_width())//2, deck_y + (deck_btn_h - dtxt.get_height())//2))
        
        # Settings button (left bottom, same vertical as deck button)
        try:
            settings_w = 180
            settings_h = deck_btn_h
            settings_x = 20
            settings_y = deck_y
            settings_rect = pygame.Rect(settings_x, settings_y, settings_w, settings_h)
            pygame.draw.rect(screen, (230,230,230), settings_rect)
            pygame.draw.rect(screen, (70,70,70), settings_rect, 3)
            stxt = btn_font.render("設定", True, (30,30,30))
            screen.blit(stxt, (settings_x + (settings_w - stxt.get_width())//2, settings_y + (settings_h - stxt.get_height())//2))
        except Exception:
            pass
        
        # BGM クレジット表示（右下） 
        try:
            credit_text = "BGM:MusMus様"
            # create a bold variant for slightly thicker text
            try:
                credit_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", SMALL_font.get_height(), bold=True)
            except Exception:
                credit_font = SMALL_font
            # darker fill color for "濃く"
            fill_color = (200, 200, 200)
            outline_color = (10, 10, 10)
            credit_surf = credit_font.render(credit_text, True, fill_color)
            # draw a slightly darker outline for readability
            try:
                outline = credit_font.render(credit_text, True, outline_color)
                x = W - credit_surf.get_width() - 14
                y = H - credit_surf.get_height() - 40
                # outline offset (one pixel) then draw the main text twice to emphasize weight
                screen.blit(outline, (x + 1, y + 1))
            except Exception:
                x = W - credit_surf.get_width() - 14
                y = H - credit_surf.get_height() - 40
            # draw main text twice with tiny offset to make it visually bolder
            try:
                screen.blit(credit_surf, (x, y))
                screen.blit(credit_surf, (x + 1, y))
            except Exception:
                try:
                    screen.blit(credit_surf, (x, y))
                except Exception:
                    pass
        except Exception:
            pass

        pygame.display.flip()
        clock.tick(30)


def show_settings_screen(screen, get_font, W, H, FONT, SMALL, TINY,
                         get_bgm_enabled_func, set_bgm_enabled_func,
                         get_bgm_volume_func, set_bgm_volume_func,
                         get_current_bgm_mode_func, set_bgm_mode_func,
                         get_gimmick_activation_mode_func, set_gimmick_activation_mode_func,
                         get_gimmick_click_submode_func, set_gimmick_click_submode_func,
                         notice_msg_callback=None):
    """Simple settings screen to toggle BGM ON/OFF and adjust volume.

    This is a modal-like loop that returns when the user presses "戻る".
    It updates BGM settings via audio.bgm_manager module.
    
    Args:
        screen: pygame display surface
        get_font: フォント取得関数
        W, H: ウィンドウサイズ
        FONT, SMALL, TINY: フォントオブジェクト
        get_bgm_enabled_func: BGM有効状態取得関数
        set_bgm_enabled_func: BGM有効状態設定関数
        get_bgm_volume_func: BGM音量取得関数
        set_bgm_volume_func: BGM音量設定関数
        get_current_bgm_mode_func: 現在のBGMモード取得関数
        set_bgm_mode_func: BGMモード設定関数
        get_gimmick_activation_mode_func: ギミック発動モード取得関数
        set_gimmick_activation_mode_func: ギミック発動モード設定関数
        get_gimmick_click_submode_func: ギミッククリックサブモード取得関数
        set_gimmick_click_submode_func: ギミッククリックサブモード設定関数
        notice_msg_callback: 通知メッセージコールバック関数(optional)
    """
    import time as _ct_time
    
    clk = pygame.time.Clock()
    dragging = False
    drag_offset = 0

    # layout (enlarged to give more space for options)
    w = 760
    h = 360
    x = (W - w) // 2
    y = (H - h) // 2

    # slider geometry
    slider_x = x + 40
    slider_y = y + 140
    slider_w = w - 80
    slider_h = 6

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # back button
                back_rect = pygame.Rect(x + w - 120, y + h - 56, 100, 40)
                if back_rect.collidepoint(mx, my):
                    return
                # toggle BGM checkbox
                chk_rect = pygame.Rect(x + 40, y + 60, 24, 24)
                if chk_rect.collidepoint(mx, my):
                    set_bgm_enabled_func(not get_bgm_enabled_func())
                    try:
                        # Reapply or stop BGM according to the current logical mode
                        if get_bgm_enabled_func():
                            try:
                                # reapply the currently selected mode (title/game) so proper file is loaded
                                set_bgm_mode_func(get_current_bgm_mode_func())
                            except Exception:
                                pass
                        else:
                            try:
                                set_bgm_mode_func(None)
                            except Exception:
                                pass
                    except Exception:
                        pass
                # slider hit check
                slid_rect = pygame.Rect(slider_x, slider_y - 8, slider_w, 24)
                if slid_rect.collidepoint(mx, my):
                    dragging = True
                    # compute proportion
                    rel = (mx - slider_x) / float(max(1, slider_w))
                    set_bgm_volume_func(rel)
                # Gimmick activation option click areas (relative to modal)
                gimm_x = x + 40
                gimm_y = y + 220
                opt_w = w - 80
                opt_h = 28
                # top-level options
                top_num_rect = pygame.Rect(gimm_x, gimm_y, opt_w, opt_h)
                top_click_rect = pygame.Rect(gimm_x, gimm_y + opt_h + 8, opt_w, opt_h)
                # nested options (shown only when top-click is selected)
                nested_x = gimm_x + 20
                nested_y = top_click_rect.y + opt_h + 8
                nested_rect_1 = pygame.Rect(nested_x, nested_y, opt_w - 20, opt_h)
                nested_rect_2 = pygame.Rect(nested_x, nested_y + (opt_h + 8), opt_w - 20, opt_h)

                if top_num_rect.collidepoint(mx, my):
                    set_gimmick_activation_mode_func('number_key')
                    if notice_msg_callback:
                        try:
                            notice_msg_callback("発動方法: 数字キー", _ct_time.time() + 1.5)
                        except Exception:
                            pass
                elif top_click_rect.collidepoint(mx, my):
                    # Select the click-top mode but keep the chosen submode
                    # If a submode hasn't been chosen yet, default to click_enlarged
                    sub = get_gimmick_click_submode_func()
                    set_gimmick_click_submode_func(sub)
                    set_gimmick_activation_mode_func(sub)
                    if notice_msg_callback:
                        try:
                            notice_msg_callback("発動方法: カードをクリックして発動", _ct_time.time() + 1.5)
                        except Exception:
                            pass
                else:
                    # handle nested option clicks when the click-top area is shown
                    if nested_rect_1.collidepoint(mx, my):
                        set_gimmick_click_submode_func('click_enlarged')
                        set_gimmick_activation_mode_func('click_enlarged')
                        if notice_msg_callback:
                            try:
                                notice_msg_callback("発動方法: 拡大クリック", _ct_time.time() + 1.5)
                            except Exception:
                                pass
                    elif nested_rect_2.collidepoint(mx, my):
                        set_gimmick_click_submode_func('double_click')
                        set_gimmick_activation_mode_func('double_click')
                        if notice_msg_callback:
                            try:
                                notice_msg_callback("発動方法: ダブルクリック", _ct_time.time() + 1.5)
                            except Exception:
                                pass
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False
            elif ev.type == pygame.MOUSEMOTION and dragging:
                mx, my = ev.pos
                rel = (mx - slider_x) / float(max(1, slider_w))
                set_bgm_volume_func(rel)
                

        # draw modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((210,215,220))
        pygame.draw.rect(surf, (70,70,70), (0,0,w,h), 3)

        title = FONT.render("設定", True, (30,30,30))
        surf.blit(title, (20, 12))

        # BGM enabled checkbox
        try:
            chk_rect = pygame.Rect(40, 60, 24, 24)
            pygame.draw.rect(surf, (230,230,230), chk_rect)
            pygame.draw.rect(surf, (80,80,80), chk_rect, 2)
            txt = SMALL.render("BGM を再生する", True, (30,30,30))
            surf.blit(txt, (80, 60))
            if get_bgm_enabled_func():
                # draw a tidy check mark that fits inside the checkbox
                try:
                    cx = chk_rect.x
                    cy = chk_rect.y
                    pts = [
                        (cx + 4, cy + 12),
                        (cx + 10, cy + 18),
                        (cx + 20, cy + 6),
                    ]
                    pygame.draw.lines(surf, (20,20,20), False, pts, 3)
                except Exception:
                    # fallback: small filled rect
                    pygame.draw.rect(surf, (20,20,20), (chk_rect.x+6, chk_rect.y+6, 12, 12))
        except Exception:
            pass

        # Volume slider
        try:
            # slider background
            sx = slider_x - x
            sy = slider_y - y
            pygame.draw.rect(surf, (200,200,200), (sx, sy - slider_h//2, slider_w, slider_h))
            # knob position
            current_volume = get_bgm_volume_func()
            kx = int(sx + current_volume * slider_w)
            ky = sy
            pygame.draw.circle(surf, (80,80,80), (kx, ky), 10)
            vol_txt = SMALL.render(f"音量: {int(current_volume*100)}%", True, (30,30,30))
            # move the volume text slightly upward for better spacing
            surf.blit(vol_txt, (40, sy + 8))
        except Exception:
            pass

        # Back button
        back_rect = pygame.Rect(w - 120, h - 56, 100, 40)
        pygame.draw.rect(surf, (220,220,220), back_rect)
        pygame.draw.rect(surf, (70,70,70), back_rect, 2)
        back_txt = SMALL.render("戻る", True, (30,30,30))
        surf.blit(back_txt, (back_rect.x + (back_rect.w - back_txt.get_width())//2, back_rect.y + (back_rect.h - back_txt.get_height())//2))

        # Gimmick activation method description and options
        try:
            opt_title = SMALL.render("ギミック発動方法", True, (30,30,30))
            # place title a bit lower to avoid overlapping the volume label
            surf.blit(opt_title, (40, 180))
            gimm_x = 40
            gimm_y = 220
            opt_h = 28
            opt_w = w - 80

            # Top-level options: 1) 数字キーで発動  2) カードをクリックして発動
            # Draw top-level radios
            # Top 1: 数字キーで発動
            chk_x = gimm_x
            chk_y = gimm_y
            pygame.draw.circle(surf, (200,200,200), (chk_x+10, chk_y+opt_h//2), 10)
            if get_gimmick_activation_mode_func() == 'number_key':
                pygame.draw.circle(surf, (80,80,80), (chk_x+10, chk_y+opt_h//2), 6)
            txt1 = SMALL.render("数字キーで発動", True, (30,30,30))
            surf.blit(txt1, (chk_x + 28, chk_y + (opt_h - txt1.get_height())//2))

            # Top 2: カードをクリックして発動
            chk_y2 = gimm_y + opt_h + 8
            pygame.draw.circle(surf, (200,200,200), (chk_x+10, chk_y2+opt_h//2), 10)
            # top-click is considered selected when effective mode is not number_key
            if get_gimmick_activation_mode_func() != 'number_key':
                pygame.draw.circle(surf, (80,80,80), (chk_x+10, chk_y2+opt_h//2), 6)
            txt2 = SMALL.render("カードをクリックして発動", True, (30,30,30))
            surf.blit(txt2, (chk_x + 28, chk_y2 + (opt_h - txt2.get_height())//2))

            # If click-top is selected, draw nested options indented
            if get_gimmick_activation_mode_func() != 'number_key':
                nested_x = gimm_x + 20
                nested_y = chk_y2 + opt_h + 8
                # nested 1: 拡大カードをクリックで発動
                pygame.draw.circle(surf, (200,200,200), (nested_x+10, nested_y+opt_h//2), 10)
                if get_gimmick_click_submode_func() == 'click_enlarged':
                    pygame.draw.circle(surf, (80,80,80), (nested_x+10, nested_y+opt_h//2), 6)
                ntxt1 = SMALL.render("拡大カードをクリックして発動", True, (30,30,30))
                surf.blit(ntxt1, (nested_x + 28, nested_y + (opt_h - ntxt1.get_height())//2))

                # nested 2: ダブルクリックで発動
                nested_y2 = nested_y + (opt_h + 8)
                pygame.draw.circle(surf, (200,200,200), (nested_x+10, nested_y2+opt_h//2), 10)
                if get_gimmick_click_submode_func() == 'double_click':
                    pygame.draw.circle(surf, (80,80,80), (nested_x+10, nested_y2+opt_h//2), 6)
                ntxt2 = SMALL.render("ダブルクリックで発動", True, (30,30,30))
                surf.blit(ntxt2, (nested_x + 28, nested_y2 + (opt_h - ntxt2.get_height())//2))
        except Exception:
            pass
        
        # クレジット表示（モーダル左下）
        try:
            credit_text = "フリーBGM・音楽素材:MusMus様"
            try:
                credit_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", max(14, SMALL.get_height()-2), bold=True)
            except Exception:
                credit_font = SMALL
            fill_color = (120, 120, 120)
            outline_color = (30, 30, 30)
            credit_surf = credit_font.render(credit_text, True, fill_color)
            outline = credit_font.render(credit_text, True, outline_color)
            # Place credit at the modal's top-right with a small inset
            cx = w - credit_surf.get_width() - 12
            cy = 12
            # draw outline slightly offset then main text
            surf.blit(outline, (cx + 1, cy + 1))
            surf.blit(credit_surf, (cx, cy))
        except Exception:
            pass

        screen.blit(surf, (x, y))
        pygame.display.flip()
        clk.tick(30)
