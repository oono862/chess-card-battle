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
    "[↑↓] ログスクロール",
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

    # === 上部エリア: 基本情報バー ===
    info_y = 20
    draw_text(screen, f"ターン: {game.turn}", 24, info_y)
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", 160, info_y)
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", 280, info_y, (40,40,90))
    draw_text(screen, f"墓地: {len(game.player.graveyard)}枚", 420, info_y, (90,40,40))
    
    # 保留中表示
    if getattr(game, 'pending', None) is not None:
        label = game.pending.kind
        src = game.pending.info.get('source_card_name')
        if src:
            label = f"{src} ({label})"
        draw_text(screen, f"⚠ 保留中: {label}", 580, info_y, (180, 60, 0))

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
    board_area_top = 70
    board_area_width = 750
    board_area_height = 480
    
    # チェス盤エリアの枠（デバッグ用・実際のチェス盤実装時は削除）
    pygame.draw.rect(screen, (200, 220, 200), 
                     (board_area_left, board_area_top, board_area_width, board_area_height))
    pygame.draw.rect(screen, (120, 140, 120), 
                     (board_area_left, board_area_top, board_area_width, board_area_height), 2)
    draw_text(screen, "チェス盤エリア", board_area_left + 300, board_area_top + 220, (100, 120, 100))

    # === 右側エリア: ログ（切替式）===
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
        
        log_y = log_panel_top + 36
        for wline in visible_lines:
            if log_y < log_panel_top + log_panel_height - 10:
                draw_text(screen, wline, log_panel_left + 10, log_y, (60, 60, 60))
                log_y += 22
        
        # スクロール位置インジケーター
        if max_scroll > 0:
            scroll_info = f"[{log_scroll_offset}/{max_scroll}]"
            draw_text(screen, scroll_info, log_panel_left + 10, 
                     log_panel_top + log_panel_height - 28, (100, 100, 100))
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
        
        # カード背景
        color = (220, 255, 220) if c.cost <= game.player.pp_current else (255, 220, 220)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (80, 80, 80), rect, 2)
        
        # サムネイル画像
        thumb = get_card_image(c.name, size=(card_w - 10, int((card_w - 10) * 1.4)))
        screen.blit(thumb, (x + 5, card_y + 5))
        
        # カード番号
        num_surf = FONT.render(f"[{i+1}]", True, (0, 0, 0))
        screen.blit(num_surf, (x + 5, card_y + 5))
        
        # カード名とコスト（下部）
        name_surf = TINY.render(c.name[:7], True, (0, 0, 0))
        screen.blit(name_surf, (x + 5, card_y + card_h - 35))
        cost_surf = SMALL.render(f"Cost:{c.cost}", True, (60, 60, 180))
        screen.blit(cost_surf, (x + 5, card_y + card_h - 18))

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
        
        counts = {}
        for c in game.player.graveyard:
            counts[c.name] = counts.get(c.name, 0) + 1
        
        gy = overlay_y + 60
        gx = overlay_x + 30
        col_w = 280
        for name, cnt in sorted(counts.items()):
            thumb = get_card_image(name, size=(70, 95))
            screen.blit(thumb, (gx, gy))
            draw_text(screen, f"{name}: {cnt}枚", gx + 80, gy + 35)
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
    global enlarged_card_index
    
    # 拡大表示中ならどこクリックしても閉じる
    if enlarged_card_index is not None:
        enlarged_card_index = None
        return
    
    # カードのクリック判定
    for rect, idx in card_rects:
        if rect.collidepoint(pos):
            enlarged_card_index = idx
            return


def main_loop():
    global log_scroll_offset
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左クリック
                    handle_mouse_click(event.pos)
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