#カードゲーム部分実装
import pygame
from pygame import Rect
import sys

try:
    from .card_core import new_game_with_sample_deck
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck


pygame.init()

# 画面設定
W, H = 960, 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("カードゲーム デモ")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)

# ゲーム状態
game = new_game_with_sample_deck()

HELP_LINES = [
    "[T] 次のターン開始 (PP全回復 + 山札から1枚ドロー)",
    "[1-9] 対応する手札のカードを使用 (PP消費)",
    "[Esc] 終了",
]


def draw_text(surf, text, x, y, color=(20, 20, 20)):
    img = FONT.render(text, True, color)
    surf.blit(img, (x, y))


def draw_panel():
    screen.fill((240, 240, 245))

    # PP表示
    draw_text(screen, f"Turn: {game.turn}", 24, 20)
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", 24, 50)

    # 手札表示
    y = 120
    draw_text(screen, "手札 (1-9で使用):", 24, y)
    y += 30
    for i, c in enumerate(game.player.hand.cards[:9]):
        key = i + 1
        label = f"{key}. {c.name} (Cost {c.cost})"
        color = (0, 120, 0) if c.cost <= game.player.pp_current else (150, 0, 0)
        draw_text(screen, label, 40, y, color)
        y += 26

    # ログ表示（下部）
    draw_text(screen, "Log:", 24, H - 200)
    log_y = H - 170
    for line in game.log[-6:]:
        draw_text(screen, f"- {line}", 36, log_y, (60, 60, 60))
        log_y += 24

    # ヘルプ
    help_y = 20
    for hl in HELP_LINES:
        draw_text(screen, hl, W - 420, help_y, (30, 30, 90))
        help_y += 24


def handle_keydown(key):
    if key == pygame.K_ESCAPE:
        pygame.quit()
        sys.exit(0)
    if key == pygame.K_t:
        game.start_turn()
        return
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
        ok, msg = game.play_card(idx)
        if not ok:
            game.log.append(msg)


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