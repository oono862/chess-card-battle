import pygame

def get_font(size, bold=False):
    """日本語対応フォントを取得"""
    font_names = ['Noto Sans JP', 'Meiryo', 'MS Gothic', 'Yu Gothic']
    for font_name in font_names:
        try:
            return pygame.font.SysFont(font_name, size, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, size)

def select_game_mode(screen, font_size=24):
    clock = pygame.time.Clock()
    selected_mode = None
    title_font = get_font(32, bold=True)
    button_font = get_font(font_size)

    buttons = [
        {"label": "チュートリアル", "value": "tutorial"},
        {"label": "ローカル対戦", "value": "local"},
        {"label": "ホスト（オンライン）", "value": "host"},
        {"label": "クライアント（オンライン）", "value": "client"},
        {"label": "CPU対戦", "value": "cpu"},
    ]

    while selected_mode is None:
        screen.fill((240, 240, 240))
        title = title_font.render("モードを選んでください", True, (0, 0, 0))
        screen.blit(title, (100, 60))

        for i, btn in enumerate(buttons):
            rect = pygame.Rect(100, 150 + i * 70, 400, 50)
            # チュートリアルボタンは緑色で目立たせる
            color = (50, 180, 50) if btn["value"] == "tutorial" else (100, 100, 255)
            pygame.draw.rect(screen, color, rect)
            label = button_font.render(btn["label"], True, (255, 255, 255))
            screen.blit(label, (rect.x + 100, rect.y + 10))
            btn["rect"] = rect

        pygame.display.flip()
        clock.tick(30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                for btn in buttons:
                    if btn["rect"].collidepoint(pos):
                        selected_mode = btn["value"]
                        break

    return selected_mode

