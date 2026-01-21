"""CardGame.py との統合テスト - チュートリアル簡易版

CardGame.py を直接実行するのは複雑なため、
ここではチュートリアルモード検出とUI表示をテストします。
"""

import sys
sys.path.insert(0, r'C:\Users\Student\Desktop\卒研＠本番用資料\chess-card-battle\chess-card-battle\C.C.B')

import pygame
from game.tutorial import TutorialManager
from ui.renderer import draw_tutorial_overlay, draw_tutorial_highlights
from mode_select import select_game_mode

def get_font(size, bold=False):
    """日本語対応フォントを取得"""
    font_names = ['Noto Sans JP', 'Meiryo', 'MS Gothic', 'Yu Gothic']
    for font_name in font_names:
        try:
            return pygame.font.SysFont(font_name, size, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, size)

def test_integration():
    """チュートリアル機能の統合テスト"""
    
    pygame.init()
    W, H = 1200, 800
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("チュートリアル統合テスト")
    
    # モード選択
    mode = select_game_mode(screen, font_size=20)
    
    if mode == 'tutorial':
        print("✓ チュートリアルモードが選択されました")
        
        # チュートリアル初期化
        tutorial = TutorialManager()
        tutorial.start()
        
        # UI描画テスト
        print("✓ チュートリアルUI描画テスト開始")
        
        def draw_text(screen, text, x, y, color=(0, 0, 0), bold=False, scale=1.0, **kwargs):
            font_obj = get_font(int(24 * scale), bold=bold)
            surf = font_obj.render(text, True, color)
            screen.blit(surf, (x, y))
            return pygame.Rect(x, y, surf.get_width(), surf.get_height())
        
        layout = {'screen_width': W, 'screen_height': H, 'scale': 1.0}
        board_left, board_top = 100, 200
        square_w, square_h = 70, 70
        card_rects = [pygame.Rect(100 + i*140, H-150, 130, 180) for i in range(5)]
        
        clock = pygame.time.Clock()
        running = True
        
        while running and tutorial.enabled:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        tutorial.skip()
                    elif event.key == pygame.K_SPACE:
                        tutorial.advance_step()
            
            screen.fill((240, 240, 245))
            
            # タイトル
            draw_text(screen, f"チュートリアル統合テスト - ステップ {tutorial.current_step}/{len(tutorial.steps)-1}", 
                     50, 20, (0, 0, 0), bold=True, scale=1.5)
            draw_text(screen, "(SPACE: 次へ, ESC: スキップ)", 50, 60)
            
            # チェス盤グリッド
            light = (235, 248, 240)
            dark = (200, 220, 200)
            for row in range(8):
                for col in range(8):
                    rect = pygame.Rect(board_left + col*square_w, board_top + row*square_h, square_w, square_h)
                    pygame.draw.rect(screen, light if (row+col)%2==0 else dark, rect)
                    pygame.draw.rect(screen, (100,100,100), rect, 1)
            
            # カード
            draw_text(screen, "カード手札エリア", 50, H-180, scale=1.1)
            for i, card_rect in enumerate(card_rects):
                pygame.draw.rect(screen, (200,200,200), card_rect)
                pygame.draw.rect(screen, (100,100,100), card_rect, 2)
                draw_text(screen, f"Card {i}", card_rect.x + 20, card_rect.y + 80)
            
            # チュートリアルハイライト
            draw_tutorial_highlights(screen, tutorial, board_left, board_top, square_w, square_h, card_rects, layout)
            
            # チュートリアルメッセージ
            draw_tutorial_overlay(screen, tutorial, layout, draw_text)
            
            # ステップ情報
            if tutorial.enabled:
                step = tutorial.get_current_step()
                info_y = H - 120
                draw_text(screen, f"許可操作: {', '.join(step.allowed_actions)}", 50, info_y, scale=0.9)
                draw_text(screen, f"ハイライト: {step.highlight_pieces} / {step.highlight_tiles}", 50, info_y+30, scale=0.9)
            
            pygame.display.flip()
            clock.tick(60)
        
        print("✓ チュートリアル描画完了")
        print(f"✓ 最終ステップ: {tutorial.current_step}, 完了: {tutorial.completed}")
    
    elif mode == 'cpu':
        print("✓ CPU対戦モードが選択されました")
        print("✓ (実際の CPU対戦ロジックはここに続きます)")
    
    else:
        print(f"✓ {mode} モードが選択されました")
    
    pygame.quit()
    print("\n✓ テスト完了！")

if __name__ == "__main__":
    test_integration()
