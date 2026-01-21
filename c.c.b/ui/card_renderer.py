# -*- coding: utf-8 -*-
"""
C.C.B/ui/card_renderer.py
カード描画関連のUI処理を担当
"""

import pygame
from typing import List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..game.state import GameState

# カードクリック判定用の矩形を保存するグローバル変数
card_rects: List[Tuple[pygame.Rect, int]] = []


def draw_hand_cards(
    screen: pygame.Surface,
    game: 'GameState',
    hand_title_x: int,
    hand_title_y: int,
    layout: dict,
    scale: float,
    W: int,
    H: int,
    FONT: pygame.font.Font,
    get_card_image_func,
    get_gimmick_activation_mode_func
) -> List[Tuple[pygame.Rect, int]]:
    """
    プレイヤーの手札カードを描画する
    
    Args:
        screen: 描画対象のサーフェス
        game: ゲーム状態オブジェクト
        hand_title_x: 手札タイトルのX座標
        hand_title_y: 手札タイトルのY座標
        layout: レイアウト情報の辞書
        scale: UIスケール係数
        W: 画面幅
        H: 画面高さ
        FONT: フォントオブジェクト
        get_card_image_func: カード画像取得関数
        get_gimmick_activation_mode_func: ギミック発動モード取得関数
    
    Returns:
        List[Tuple[pygame.Rect, int]]: カードの矩形とインデックスのリスト
    """
    global card_rects
    
    # カードの基本サイズ計算
    base_card_h = layout.get('card_h', max(72, int(175 * scale)))
    
    # UIスケールに応じてカードサイズを調整
    # 通常ウィンドウ: クリッピングを防ぐため縮小
    # フルスクリーン: より大きなスケールを許可
    try:
        ui_scale = layout.get('scale', 1.0)
        if ui_scale <= 1.0:
            # 通常ウィンドウ: クリッピング防止のため縮小なし
            VISUAL_CARD_SCALE = 0.9
        elif ui_scale <= 1.15:
            VISUAL_CARD_SCALE = 1.0
        else:
            VISUAL_CARD_SCALE = 1.15
    except Exception:
        VISUAL_CARD_SCALE = 1.05
    
    card_h = max(48, int(base_card_h * VISUAL_CARD_SCALE))

    # カード高さをクランプ（ボードや他のUIと重ならないように）
    try:
        bottom_slack = H - (layout['board_top'] + layout['board_size'])
        # 通常のウィンドウで下部がクリップされないように大きめのパディングを残す
        avail_for_card = max(48, bottom_slack - int(64 * scale))
        max_by_board = int(layout['board_size'] * 0.75)
        allowed = max(48, min(max_by_board, avail_for_card))
        if card_h > allowed:
            card_h = allowed
    except Exception:
        pass

    # 元のアスペクト比（130x175）を維持して幅を計算
    card_w = max(48, int(card_h * (130.0 / 175.0)))
    card_spacing = max(8, int(8 * scale))
    card_start_x = hand_title_x  # 左マージンから開始
    card_y = hand_title_y + 30
    
    # カード描画とクリック判定用の矩形をリセット
    card_rects = []
    
    # 手札の最大7枚を描画
    for i, c in enumerate(game.player.hand.cards[:7]):
        x = card_start_x + i * (card_w + card_spacing)
        rect = pygame.Rect(x, card_y, card_w, card_h)
        card_rects.append((rect, i))
        
        # カード画像を描画（custom_imageがあればそれを優先）
        image_name = c.custom_image if hasattr(c, 'custom_image') and c.custom_image else c.name
        # デバッグ出力
        if 'ハン' in c.name:
            print(f"[CARD_RENDERER] Card: {c.name}, custom_image: {getattr(c, 'custom_image', None)}, using: {image_name}")
        thumb = get_card_image_func(image_name, size=(card_w, card_h))
        screen.blit(thumb, (x, card_y))

        # 日本語エイリアスをカード下部に表示（画像の有無に関わらず）
        try:
            alias_map = {
                'Quick Draw': '引く',
                'Meditate': '瞑想',
                'Tactical Surge': '戦術急襲',
                '2ドロー': '2ドロー',
            }
            alias = alias_map.get(getattr(c, 'name', ''), None)
            if alias:
                label_surf = FONT.render(alias, True, (40, 40, 60))
                lx = x + (card_w - label_surf.get_width()) // 2
                ly = card_y + card_h - label_surf.get_height() - 4
                # 背景を少し明るくして読めるように
                bg_rect = pygame.Rect(lx - 6, ly - 2, label_surf.get_width() + 12, label_surf.get_height() + 4)
                pygame.draw.rect(screen, (245, 245, 248), bg_rect)
                pygame.draw.rect(screen, (200, 200, 210), bg_rect, 1)
                screen.blit(label_surf, (lx, ly))
        except Exception:
            pass
        
        # 錬成で選択中のカードを金色の枠で強調
        if (getattr(game, 'pending', None) is not None and 
            game.pending.kind == 'discard' and 
            game.pending.info.get('selected') == i):
            # 太い金色の枠
            pygame.draw.rect(screen, (255, 215, 0), rect, 5)
            # 外側にもう一層、少し濃い金色
            pygame.draw.rect(screen, (218, 165, 32), rect.inflate(4, 4), 3)
        
        # カード下部にボタン番号を表示（数字キーで発動が有効なときのみ）
        if get_gimmick_activation_mode_func() == 'number_key':
            button_number = f"[{i+1}]"
            # 背景ボックス
            button_bg_width = 35
            button_bg_height = 30
            button_bg_x = x + (card_w - button_bg_width) // 2
            button_bg_y = card_y + card_h - button_bg_height - 5
            
            # PPが足りるかで色を変える
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
    
    return card_rects


def get_card_rects() -> List[Tuple[pygame.Rect, int]]:
    """
    現在のカード矩形リストを取得
    
    Returns:
        List[Tuple[pygame.Rect, int]]: カードの矩形とインデックスのリスト
    """
    return card_rects
