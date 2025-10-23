#カードゲーム部分実装
import pygame
from pygame import Rect
import sys
import os

try:
    from .card_core import new_game_with_sample_deck, new_game_with_rule_deck
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck


pygame.init()

# 画面設定
W, H = 1200, 800
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("カードゲーム デモ")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)

# ゲーム状態
# ルール表のカードを試したい場合は下を使う
game = new_game_with_rule_deck()
show_grave = False
show_log = False  # ログ表示切替（デフォルト非表示）
log_scroll_offset = 0  # ログスクロール用オフセット（0=最新）
enlarged_card_index = None  # 拡大表示中のカードインデックス（None=非表示）

# 画像の読み込み（カード名と同じファイル名.png を images 配下から探す）
IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
_image_cache = {}
card_rects = []  # カードのクリック判定用矩形リスト
grave_card_rects = []  # 墓地サムネイルのクリック判定用矩形リスト
enlarged_card_name = None  # 墓地など手札以外の拡大表示用カード名
confirm_yes_rect = None  # 確認ダイアログの「はい」ボタン
confirm_no_rect = None   # 確認ダイアログの「いいえ」ボタン
grave_label_rect = None  # 「墓地：n枚」のクリック判定用矩形

def get_card_image(name: str, size=(72, 96)):
    key = (name, size)
    if key in _image_cache:
        return _image_cache[key]
    surf = None
    # 1) 直接候補
    candidates = [f"{name}.png", f"{name}.PNG", f"{name}.jpg", f"{name}.jpeg", f"{name}.webp", f"{name}.bmp"]
    for cand in candidates:
        path = os.path.join(IMG_DIR, cand)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                surf = pygame.transform.smoothscale(img, size)
                break
            except Exception:
                pass
    # 2) 再帰的にベース名一致を探索（拡張子/大文字小文字を無視）
    if surf is None and os.path.isdir(IMG_DIR):
        base_l = name.lower()
        for root, _dirs, files in os.walk(IMG_DIR):
            for f in files:
                fn, ext = os.path.splitext(f)
                if fn.lower() == base_l and ext.lower() in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                    try:
                        path = os.path.join(root, f)
                        img = pygame.image.load(path).convert_alpha()
                        surf = pygame.transform.smoothscale(img, size)
                        break
                    except Exception:
                        continue
            if surf is not None:
                break
    if surf is None:
        # フォールバック: 枠だけのプレースホルダー
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((255, 255, 255, 255))
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
        # タイトルを小さく
        label = SMALL.render(name, True, (0, 0, 0))
        surf.blit(label, (4, 4))
    _image_cache[key] = surf
    return surf

HELP_LINES = [
    "[T] 次のターン開始",
    "[1-7] カード使用",
    "[D] 保留中: 捨て札確定",
    "[L] ログ表示切替",
    "[G] 墓地表示切替",
    "[クリック] カード拡大",
    "[Esc] 終了",
]


def draw_text(surf, text, x, y, color=(20, 20, 20)):
    img = FONT.render(text, True, color)
    surf.blit(img, (x, y))


def wrap_text(text: str, max_width: int):
    """Return list of lines wrapped to fit max_width using FONT metrics."""
    lines = []
    cur = ""
    for ch in text:
        test = cur + ch
        w, _ = FONT.size(test)
        if w <= max_width or cur == "":
            cur = test
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def draw_panel():
    screen.fill((240, 240, 245))

    # === 上部エリア: 基本情報バー（縦並び）===
    info_x = 24
    info_y = 20
    line_height = 24
    
    # ターン数
    draw_text(screen, f"ターン: {game.turn}", info_x, info_y)
    info_y += line_height
    
    # PP
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", info_x, info_y)
    info_y += line_height
    
    # 山札
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", info_x, info_y, (40,40,90))
    info_y += line_height
    
    # 墓地表示（クリック可能領域として矩形を保存）
    grave_text = f"墓地: {len(game.player.graveyard)}枚"
    grave_surf = FONT.render(grave_text, True, (90,40,40))
    global grave_label_rect
    grave_label_rect = pygame.Rect(info_x, info_y, grave_surf.get_width(), grave_surf.get_height())
    draw_text(screen, grave_text, info_x, info_y, (90,40,40))
    
    # 保留中表示（右上に移動）
    if getattr(game, 'pending', None) is not None:
        label = game.pending.kind
        src = game.pending.info.get('source_card_name')
        if src:
            label = f"{src} ({label})"
        draw_text(screen, f"⚠ 保留中: {label}", 200, 20, (180, 60, 0))

    # 右上: ヘルプ（簡潔に）
    help_x = W - 250
    help_y = 20
    draw_text(screen, "操作:", help_x, help_y, (60, 60, 100))
    help_y += 24
    for hl in HELP_LINES:  # 全ての操作を表示
        draw_text(screen, hl, help_x, help_y, (30, 30, 90))
        help_y += 20

    # === 中央エリア: チェス盤用の空白エリア ===
    board_area_left = 24
    board_area_top = 120  # 縦並び情報の下に配置
    board_area_width = 750
    board_area_height = 430  # 高さを少し調整
    
    # チェス盤エリアの枠（デバッグ用・実際のチェス盤実装時は削除）
    pygame.draw.rect(screen, (200, 220, 200), 
                     (board_area_left, board_area_top, board_area_width, board_area_height))
    pygame.draw.rect(screen, (120, 140, 120), 
                     (board_area_left, board_area_top, board_area_width, board_area_height), 2)
    draw_text(screen, "チェス盤エリア", board_area_left + 300, board_area_top + 200, (100, 120, 100))

    # === 右側エリア: ログ（切替式）===
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    if show_log:
        log_panel_left = board_area_left + board_area_width + 20
        log_panel_top = board_area_top
        log_panel_width = W - log_panel_left - 24
        log_panel_height = board_area_height

        # ログパネル背景
        pygame.draw.rect(screen, (250, 250, 255),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height))
        pygame.draw.rect(screen, (100, 100, 120),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height), 2)

        draw_text(screen, "ログ履歴 [L]閉じる", log_panel_left + 10, log_panel_top + 8, (60, 60, 100))
        # 見出しのすぐ下にスクロールのヒントを表示
        draw_text(screen, "↑↓ / ホイールでスクロール", log_panel_left + 10, log_panel_top + 30, (100, 100, 120))

        # ログの折り返し処理
        wrapped_lines = []
        max_log_width = log_panel_width - 30
        for line in game.log:
            for wline in wrap_text(f"• {line}", max_log_width):
                wrapped_lines.append(wline)

        # スクロールオフセットの範囲制限
        global log_scroll_offset
        max_lines_visible = (log_panel_height - 50) // 22
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
        log_y = log_panel_top + 56
        for wline in visible_lines:
            if log_y < log_panel_top + log_panel_height - 10:
                draw_text(screen, wline, log_panel_left + 10, log_y, (60, 60, 60))
                log_y += 22

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
    else:
        # ログ非表示時のヒント
        draw_text(screen, "[L] ログ表示", W - 240, board_area_top + board_area_height - 30, (100, 100, 120))

    # === 下部エリア: 手札（横並び最大7枚） ===
    card_area_top = board_area_top + board_area_height + 20
    draw_text(screen, "手札 (1-7で使用 / クリックで拡大):", 24, card_area_top, (40, 40, 40))
    
    card_w = 100
    card_h = 140
    card_spacing = 8
    card_start_x = 30
    card_y = card_area_top + 30
    
    # カード描画とクリック判定用の矩形保存
    global card_rects
    card_rects = []
    
    for i, c in enumerate(game.player.hand.cards[:7]):
        x = card_start_x + i * (card_w + card_spacing)
        rect = pygame.Rect(x, card_y, card_w, card_h)
        card_rects.append((rect, i))
        
        # カード画像のみ表示
        thumb = get_card_image(c.name, size=(card_w, card_h))
        screen.blit(thumb, (x, card_y))
        
        # 錬成で選択中のカードを金色の枠で強調
        if (getattr(game, 'pending', None) is not None and 
            game.pending.kind == 'discard' and 
            game.pending.info.get('selected') == i):
            # 太い金色の枠
            pygame.draw.rect(screen, (255, 215, 0), rect, 5)
            # 外側にもう一層、少し濃い金色
            pygame.draw.rect(screen, (218, 165, 32), rect.inflate(4, 4), 3)
        
        # カード下部にボタン番号を大きく表示
        button_number = f"[{i+1}]"
        # 背景ボックス
        button_bg_width = 35
        button_bg_height = 30
        button_bg_x = x + (card_w - button_bg_width) // 2
        button_bg_y = card_y + card_h - button_bg_height - 5
        
        # PP足りるかで色を変える
        if c.cost <= game.player.pp_current:
            bg_color = (100, 200, 100)  # 緑（使用可能）
        else:
            bg_color = (200, 100, 100)  # 赤（PP不足）
        
        pygame.draw.rect(screen, bg_color, (button_bg_x, button_bg_y, button_bg_width, button_bg_height))
        pygame.draw.rect(screen, (255, 255, 255), (button_bg_x, button_bg_y, button_bg_width, button_bg_height), 2)
        
        # 番号テキスト
        num_surf = FONT.render(button_number, True, (255, 255, 255))
        num_x = button_bg_x + (button_bg_width - num_surf.get_width()) // 2
        num_y = button_bg_y + (button_bg_height - num_surf.get_height()) // 2
        screen.blit(num_surf, (num_x, num_y))


    # === 状態表示（右下）===
    state_x = W - 240
    state_y = card_area_top + 40
    draw_text(screen, f"封鎖: {len(getattr(game, 'blocked_tiles', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    draw_text(screen, f"凍結: {len(getattr(game, 'frozen_pieces', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    draw_text(screen, f"追加行動: {game.player.extra_moves_this_turn}", state_x, state_y, (80, 80, 80))
    state_y += 20
    if game.player.next_move_can_jump:
        draw_text(screen, "次: 飛越可", state_x, state_y, (0, 120, 0))

    # === 墓地オーバーレイ ===
    if show_grave:
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
        global grave_card_rects
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

    # === カード拡大表示オーバーレイ ===
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
        large_img = get_card_image(c.name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))
    elif enlarged_card_name is not None:
        # 手札以外（例: 墓地）からの拡大表示
        enlarged_w = 300
        enlarged_h = 420
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2

        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))

        large_img = get_card_image(enlarged_card_name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))

    # === 保留中の操作説明オーバーレイ ===
    if getattr(game, 'pending', None) is not None:
        # 操作説明テキストを決定
        if game.pending.kind == 'discard':
            instruction_text = "手札から捨てるカードを選択: [1-7]で選択 → [D]で確定"
        elif game.pending.kind == 'target_tile':
            instruction_text = "封鎖するマスを選択してください（未実装）"
        elif game.pending.kind == 'target_piece':
            instruction_text = "凍結する相手コマを選択してください（未実装）"
        else:
            instruction_text = "選択を完了してください"
        
        # ボックスサイズ計算
        box_padding = 30
        
        # confirmの場合は複数行対応
        if game.pending.kind == 'confirm':
            msg = game.pending.info.get('message', '実行してもよろしいですか？ [Y]=はい / [N]=いいえ')
            lines = msg.split('\n')
            # 各行の幅を計算して最大幅を取得
            max_width = 0
            for line in lines:
                line_surface = FONT.render(line, True, (0, 0, 0))
                max_width = max(max_width, line_surface.get_width())
            box_width = max_width + box_padding * 2
            # タイトル + メッセージ行数分の高さ + 下部余白
            box_height = 50 + len(lines) * 22 + 15
        else:
            text_surface = FONT.render(instruction_text, True, (0, 0, 0))
            text_width = text_surface.get_width()
            box_width = text_width + box_padding * 2
            box_height = 80
        
        # カード拡大表示の横に配置（右側）
        if enlarged_card_index is not None:
            box_x = (W - 300) // 2 + 300 + 30  # カードの右側
        else:
            box_x = (W - box_width) // 2  # 中央
        box_y = (H - box_height) // 2
        
        # 背景ボックス
        pygame.draw.rect(screen, (255, 255, 200), (box_x, box_y, box_width, box_height))
        pygame.draw.rect(screen, (180, 60, 0), (box_x, box_y, box_width, box_height), 4)
        
        # タイトル
        draw_text(screen, "⚠ 操作待ち", box_x + box_padding, box_y + 15, (180, 60, 0))
        # 操作説明テキスト
        if game.pending.kind == 'confirm':
            msg = game.pending.info.get('message', '実行してもよろしいですか？ [Y]=はい / [N]=いいえ')
            # 改行対応: \nで分割して複数行描画
            lines = msg.split('\n')
            line_y = box_y + 45
            for line in lines:
                draw_text(screen, line, box_x + box_padding, line_y, (60, 60, 60))
                line_y += 22  # 行間
        else:
            draw_text(screen, instruction_text, box_x + box_padding, box_y + 45, (60, 60, 60))

        # 確認ダイアログのボタン（はい/いいえ）
        global confirm_yes_rect, confirm_no_rect
        confirm_yes_rect = None
        confirm_no_rect = None
        if game.pending.kind == 'confirm':
            btn_w, btn_h = 120, 36
            gap = 20
            btn_y = box_y + box_height + 12
            total_w = btn_w * 2 + gap
            start_x = (W - total_w) // 2
            yes_label = game.pending.info.get('yes_label', 'はい(Y)')
            no_label = game.pending.info.get('no_label', 'いいえ(N)')
            confirm_yes_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
            confirm_no_rect = pygame.Rect(start_x + btn_w + gap, btn_y, btn_w, btn_h)
            pygame.draw.rect(screen, (80, 150, 80), confirm_yes_rect)
            pygame.draw.rect(screen, (160, 80, 80), confirm_no_rect)
            pygame.draw.rect(screen, (255, 255, 255), confirm_yes_rect, 2)
            pygame.draw.rect(screen, (255, 255, 255), confirm_no_rect, 2)
            yes_s = FONT.render(yes_label, True, (255, 255, 255))
            no_s = FONT.render(no_label, True, (255, 255, 255))
            screen.blit(yes_s, (confirm_yes_rect.centerx - yes_s.get_width()//2, confirm_yes_rect.centery - yes_s.get_height()//2))
            screen.blit(no_s, (confirm_no_rect.centerx - no_s.get_width()//2, confirm_no_rect.centery - no_s.get_height()//2))



def handle_keydown(key):
    global log_scroll_offset, show_log, enlarged_card_index
    
    if key == pygame.K_ESCAPE:
        pygame.quit()
        sys.exit(0)
    
    # ログ表示切替
    if key == pygame.K_l:
        show_log = not show_log
        return
    
    # ログスクロール（ログ表示中のみ）
    if show_log:
        if key == pygame.K_UP:
            log_scroll_offset += 1
            return
        if key == pygame.K_DOWN:
            log_scroll_offset = max(0, log_scroll_offset - 1)
            return
    
    if key == pygame.K_t:
        if getattr(game, 'pending', None) is not None:
            game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return
        game.start_turn()
        log_scroll_offset = 0  # 新しいターンで最新ログへ
        return
    
    if key == pygame.K_g:
        # 保留中でも閲覧だけは可能にする
        global show_grave
        show_grave = not show_grave
        return
    
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
        # pending中: discardのみ選択を許可し、それ以外は行動不可
        if getattr(game, 'pending', None) is not None:
            if game.pending.kind == 'discard':
                game.pending.info['selected'] = idx
                game.log.append(f"捨てるカードとして手札{idx+1}番を選択。[D]で確定")
            else:
                game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return
        ok, msg = game.play_card(idx)
        if not ok:
            game.log.append(msg)
        log_scroll_offset = 0  # カード使用後は最新ログへ
        return

    # Y/N: 確認ダイアログへの回答
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'confirm':
        if key in (pygame.K_y, pygame.K_RETURN):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                # 墓地ルーレットの確認「はい」→カードを実際に消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除、墓地へ
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。墓地が空のため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい → 効果なし（墓地が空）")
            else:
                game.log.append("確認: はい")
            game.pending = None
            log_scroll_offset = 0
            return
        if key in (pygame.K_n, pygame.K_ESCAPE):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            log_scroll_offset = 0
            return
    
    # Dキー: discard pending の確定
    if key == pygame.K_d and getattr(game, 'pending', None) is not None and game.pending.kind == 'discard':
        sel = game.pending.info.get('selected')
        if isinstance(sel, int):
            removed = game.player.hand.remove_at(sel)
            if removed:
                game.player.graveyard.append(removed)
                game.log.append(f"『{removed.name}』を捨てました。")
            else:
                game.log.append("捨てるカードを選択してください。")
        else:
            game.log.append("捨てるカードが選択されていません。")
        game.pending = None
        log_scroll_offset = 0  # 保留解決後は最新ログへ
        return


def handle_mouse_click(pos):
    """マウスクリック時の処理"""
    global enlarged_card_index, enlarged_card_name
    
    # 拡大表示中ならどこクリックしても閉じる
    if enlarged_card_index is not None or enlarged_card_name is not None:
        enlarged_card_index = None
        enlarged_card_name = None
        return
    
    # 保留中の確認（ボタン）
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'confirm':
        if confirm_yes_rect and confirm_yes_rect.collidepoint(pos):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                # 墓地ルーレットの確認「はい」→カードを実際に消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除、墓地へ
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。墓地が空のため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい")
            else:
                game.log.append("確認: はい")
            game.pending = None
            return
        if confirm_no_rect and confirm_no_rect.collidepoint(pos):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            return
    
    # 墓地ラベルのクリックで墓地表示切替
    if grave_label_rect and grave_label_rect.collidepoint(pos):
        global show_grave
        show_grave = not show_grave
        return
    
    # 墓地表示中はサムネイルのクリックで拡大表示
    if show_grave:
        for rect, name in grave_card_rects:
            if rect.collidepoint(pos):
                enlarged_card_name = name
                return

    # カードのクリック判定
    for rect, idx in card_rects:
        if rect.collidepoint(pos):
            enlarged_card_index = idx
            return


def main_loop():
    global log_scroll_offset, dragging_scrollbar, drag_start_y, drag_start_offset
    dragging_scrollbar = False
    drag_start_y = 0
    drag_start_offset = 0
    scrollbar_rect = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左クリック
                    # スクロールバーつまみのドラッグ開始判定
                    if show_log and scrollbar_rect and scrollbar_rect.collidepoint(event.pos):
                        dragging_scrollbar = True
                        drag_start_y = event.pos[1]
                        drag_start_offset = log_scroll_offset
                    else:
                        handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging_scrollbar = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging_scrollbar and show_log and scrollbar_rect:
                    # ドラッグ量に応じてスクロールオフセットを変更
                    thumb_top = scrollbar_rect.top
                    thumb_height = scrollbar_rect.height
                    # スクロールバー全体の高さ
                    bar_top = scrollbar_rect.top - (log_scroll_offset / max(1, log_scroll_offset)) * thumb_height
                    bar_height = scrollbar_rect.height / max(1, thumb_height)
                    # ドラッグした距離
                    dy = event.pos[1] - drag_start_y
                    # スクロールバーの移動量をログオフセットに変換
                    # draw_panelで計算したmax_scroll, scrollbar_height, thumb_heightを再利用
                    # ここではスクロールバーの移動量をmax_scrollに比例させる
                    # まずdraw_panelを呼び出して最新の値を取得
                    # ただし、draw_panelは毎フレーム呼ばれるので、ここではlog_scroll_offsetのみ更新
                    # スクロールバーの高さ（draw_panelで定義）
                    # つまみの移動可能範囲 = scrollbar_height - thumb_height
                    # dy / (scrollbar_height - thumb_height) = scroll_ratioの変化
                    # scroll_ratio = log_scroll_offset / max_scroll
                    # 新しいscroll_ratio = (thumb_y + dy - scrollbar_y) / (scrollbar_height - thumb_height)
                    # まずdraw_panelで必要な値を取得
                    # draw_panel()の中でmax_scroll, scrollbar_height, thumb_height, scrollbar_yが定義されている
                    # ここではそれらをグローバル変数にしておくと良い
                    # ただし、draw_panel()の中でしか値が確定しないので、
                    # ここでは簡易的にdyをscroll_offsetに変換
                    # つまみの移動可能範囲
                    move_range = max(1, scrollbar_rect.height * 10)  # 仮の値（実際はdraw_panelの値を使うべき）
                    # 仮のmax_scroll（draw_panelの値を使うべき）
                    max_scroll = 30  # 仮の値（実際はdraw_panelの値を使うべき）
                    # dyをmax_scrollに比例させる
                    new_offset = drag_start_offset + int(dy * max_scroll / move_range)
                    log_scroll_offset = max(0, min(new_offset, max_scroll))
            elif event.type == pygame.MOUSEWHEEL:
                # マウスホイールでログスクロール（ログ表示中のみ）
                if show_log:
                    if event.y > 0:  # 上スクロール
                        log_scroll_offset += 1
                    elif event.y < 0:  # 下スクロール
                        log_scroll_offset = max(0, log_scroll_offset - 1)

        draw_panel()
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main_loop()