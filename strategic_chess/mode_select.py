import pygame

def select_game_mode(screen, font):
    clock = pygame.time.Clock()
    selected_mode = None

    buttons = [
        {"label": "ローカル対戦", "value": "local"},
        {"label": "ホスト（オンライン）", "value": "host"},
        {"label": "クライアント（オンライン）", "value": "client"},
        {"label": "CPU対戦", "value": "cpu"},
    ]

    while selected_mode is None:
        screen.fill((240, 240, 240))
        title = font.render("モードを選んでください", True, (0, 0, 0))
        screen.blit(title, (100, 60))

        for i, btn in enumerate(buttons):
            rect = pygame.Rect(100, 150 + i * 70, 400, 50)
            pygame.draw.rect(screen, (100, 100, 255), rect)
            label = font.render(btn["label"], True, (255, 255, 255))
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
