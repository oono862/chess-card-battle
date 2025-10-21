#カードゲーム部分実装
import pygame
from pygame import Rect
import sys

try:
    from .card_core import new_game_with_sample_deck, new_game_with_rule_deck
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck


pygame.init()

# 画面設定
W, H = 960, 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("カードゲーム デモ")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)

# ゲーム状態
# ルール表のカードを試したい場合は下を使う
game = new_game_with_rule_deck()
show_grave = False

HELP_LINES = [
    "[T] 次のターン開始（PP全回復＋山札から1枚ドロー）",
    "[1-7] 対応する手札のカードを使用（PP消費）",
    "[D] 保留中: 捨てるカードを1枚選択（錬成の後）→ 1-9で選び[D]で確定",
    "※保留中は次の行動はできません",
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

    # PP表示と各種カウント
    draw_text(screen, f"ターン: {game.turn}", 24, 20)
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", 24, 50)
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", 24, 80, (40,40,90))
    draw_text(screen, f"墓地: {len(game.player.graveyard)}枚", 180, 80, (90,40,40))

    # 手札表示
    y = 130
    draw_text(screen, "手札 (1-9で使用):", 24, y)
    y += 30
    for i, c in enumerate(game.player.hand.cards[:9]):
        key = i + 1
        label = f"{key}. {c.name} (Cost {c.cost})"
        color = (0, 120, 0) if c.cost <= game.player.pp_current else (150, 0, 0)
        draw_text(screen, label, 40, y, color)
        y += 26

    # ログ表示（下部・自動折返し）
    draw_text(screen, "ログ:", 24, H - 200)
    log_y = H - 170
    max_w = W - 48
    # 末尾から最大6件を描画。ただし各行は自動折返し
    for line in game.log[-6:]:
        for wline in wrap_text(f"- {line}", max_w - 36):
            draw_text(screen, wline, 36, log_y, (60, 60, 60))
            log_y += 24
            if log_y > H - 20:
                break
        if log_y > H - 20:
            break

    # ヘルプ（右上）
    help_x = W - 420
    help_y = 20
    for hl in HELP_LINES + ["[G] 墓地の内容を表示/非表示"]:
        draw_text(screen, hl, help_x, help_y, (30, 30, 90))
        help_y += 24

    # 状態（簡易）: ヘルプの下から開始して重なりを回避
    state_y = help_y + 12
    if getattr(game, 'pending', None) is not None:
        label = game.pending.kind
        src = game.pending.info.get('source_card_name') if getattr(game, 'pending', None) else None
        if src:
            label = f"{src} ({label})"
        draw_text(screen, f"保留中: {label}", help_x, state_y, (120, 60, 0))
        state_y += 24
    # Chess連携用の簡易表示
    draw_text(screen, f"封鎖マス: {len(getattr(game, 'blocked_tiles', {}))}", help_x, state_y); state_y += 24
    draw_text(screen, f"凍結コマ: {len(getattr(game, 'frozen_pieces', {}))}", help_x, state_y); state_y += 24
    draw_text(screen, f"このターンの追加行動: {game.player.extra_moves_this_turn}", help_x, state_y); state_y += 24
    if game.player.next_move_can_jump:
        draw_text(screen, "次の移動は障害物を飛越可", help_x, state_y, (0, 100, 0))
        state_y += 24

    # 墓地オーバーレイ
    if show_grave:
        overlay = pygame.Surface((W - 80, H - 160))
        overlay.fill((255, 255, 255))
        overlay.set_alpha(235)
        screen.blit(overlay, (40, 120))
        draw_text(screen, "墓地のカード一覧（Gで閉じる）", 60, 130, (80, 0, 0))
        # 枚数集計
        counts = {}
        for c in game.player.graveyard:
            counts[c.name] = counts.get(c.name, 0) + 1
        gy = 160
        for name, cnt in sorted(counts.items()):
            draw_text(screen, f"{name}: {cnt}枚", 70, gy)
            gy += 24


def handle_keydown(key):
    if key == pygame.K_ESCAPE:
        pygame.quit()
        sys.exit(0)
    if key == pygame.K_t:
        if getattr(game, 'pending', None) is not None:
            game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return
        game.start_turn()
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
            return
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
        return


def main_loop():
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                handle_keydown(event.key)

        draw_panel()
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main_loop()