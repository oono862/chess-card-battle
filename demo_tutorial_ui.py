"""チュートリアル UI デモ

チュートリアルの画面表示を実際に確認できるシンプルなデモです。
"""

import sys
import pygame

sys.path.insert(0, r'C:\Users\Student\Desktop\卒研＠本番用資料\chess-card-battle\chess-card-battle\C.C.B')

from game.tutorial import TutorialManager
from ui.renderer import draw_tutorial_overlay, draw_tutorial_highlights


def demo_tutorial_ui():
    """チュートリアル UI のデモ表示"""
    
    pygame.init()
    W, H = 1200, 800
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("チュートリアル UI デモ")
    
    clock = pygame.time.Clock()
    
    # チュートリアル初期化
    tutorial = TutorialManager()
    tutorial.start()
    
    # テスト用フォント関数
    def get_font(size, bold=False):
        return pygame.font.Font(None, size)
    
    def draw_text(screen, text, x, y, color=(0, 0, 0), bold=False, scale=1.0, **kwargs):
        """シンプルなテキスト描画"""
        font = pygame.font.Font(None, int(24 * scale))
        surf = font.render(text, True, color)
        screen.blit(surf, (x, y))
        return pygame.Rect(x, y, surf.get_width(), surf.get_height())
    
    # レイアウト情報
    layout = {
        'screen_width': W,
        'screen_height': H,
        'board_area_top': 150,
        'scale': 1.0
    }
    
    # チェス盤パラメータ
    board_left = 100
    board_top = 200
    square_w = 70
    square_h = 70
    
    # ダミーカード矩形
    card_rects = [
        pygame.Rect(100 + i * 140, H - 150, 130, 180)
        for i in range(5)
    ]
    
    # ステップ表示用
    step_start_time = pygame.time.get_ticks()
    step_duration = 3000  # 3秒ごとにステップ進行
    
    running = True
    while running:
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # SPACEキーで次ステップへ
                    tutorial.advance_step()
                    step_start_time = current_time
        
        # 自動進行（3秒ごと）
        if current_time - step_start_time > step_duration:
            if not tutorial.completed:
                tutorial.advance_step()
                step_start_time = current_time
        
        # 画面描画
        screen.fill((240, 240, 245))
        
        # タイトル
        draw_text(screen, "チュートリアル UI デモ (SPACE: 次へ, ESC: 終了)", 50, 20, (0, 0, 0), bold=True, scale=1.5)
        
        # 現在のステップ表示
        if tutorial.enabled and not tutorial.completed:
            step = tutorial.get_current_step()
            draw_text(screen, f"現在のステップ: {step.step_id} / {len(tutorial.steps)-1}", 50, 60, (100, 50, 200), bold=True, scale=1.2)
        else:
            draw_text(screen, "チュートリアル完了！", 50, 60, (50, 200, 50), bold=True, scale=1.2)
        
        # チェス盤描画（グリッド）
        light = (235, 248, 240)
        dark = (200, 220, 200)
        for row in range(8):
            for col in range(8):
                rect = pygame.Rect(
                    board_left + col * square_w,
                    board_top + row * square_h,
                    square_w,
                    square_h
                )
                color = light if (row + col) % 2 == 0 else dark
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, (100, 100, 100), rect, 1)
        
        # カードエリア描画
        draw_text(screen, "カード手札エリア", 50, H - 180, (100, 100, 100), scale=1.1)
        for i, card_rect in enumerate(card_rects):
            pygame.draw.rect(screen, (200, 200, 200), card_rect)
            pygame.draw.rect(screen, (100, 100, 100), card_rect, 2)
            draw_text(screen, f"Card {i}", card_rect.x + 20, card_rect.y + 80)
        
        # ハイライト描画
        draw_tutorial_highlights(
            screen, tutorial,
            board_left, board_top, square_w, square_h,
            card_rects, layout
        )
        
        # メッセージオーバーレイ描画
        draw_tutorial_overlay(screen, tutorial, layout, draw_text)
        
        # ステップ情報表示（左下）
        if tutorial.enabled and not tutorial.completed:
            step = tutorial.get_current_step()
            info_y = H - 120
            draw_text(screen, f"許可操作: {', '.join(step.allowed_actions)}", 50, info_y, (50, 100, 200), scale=0.9)
            draw_text(screen, f"ハイライト駒: {step.highlight_pieces}", 50, info_y + 30, (50, 150, 50), scale=0.9)
            draw_text(screen, f"ハイライトマス: {step.highlight_tiles}", 50, info_y + 60, (200, 200, 0), scale=0.9)
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()


if __name__ == "__main__":
    print("チュートリアル UI デモを起動しています...")
    print("SPACE: 次ステップ、ESC: 終了")
    demo_tutorial_ui()
    print("デモを終了しました。")
