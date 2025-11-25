"""描画ユーティリティ関数"""
import pygame


def draw_dashed_rect(surf, color, rect, dash=6, gap=4, width=2):
    """Draw a dashed rectangle on surf. rect is pygame.Rect."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    # top
    sx = x
    while sx < x + w:
        ex = min(sx + dash, x + w)
        pygame.draw.line(surf, color, (sx, y), (ex, y), width)
        sx += dash + gap
    # bottom
    sx = x
    by = y + h
    while sx < x + w:
        ex = min(sx + dash, x + w)
        pygame.draw.line(surf, color, (sx, by), (ex, by), width)
        sx += dash + gap
    # left
    sy = y
    while sy < y + h:
        ey = min(sy + dash, y + h)
        pygame.draw.line(surf, color, (x, sy), (x, ey), width)
        sy += dash + gap
    # right
    sy = y
    rx = x + w
    while sy < y + h:
        ey = min(sy + dash, y + h)
        pygame.draw.line(surf, color, (rx, sy), (rx, ey), width)
        sy += dash + gap
