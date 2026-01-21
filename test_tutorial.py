"""チュートリアル機能の確認テスト"""

import sys
sys.path.insert(0, r'C:\Users\Student\Desktop\卒研＠本番用資料\chess-card-battle\chess-card-battle\C.C.B')

from game.tutorial import TutorialManager

def test_tutorial():
    """チュートリアル機能の動作確認"""
    
    print("=" * 60)
    print("チュートリアル機能テスト")
    print("=" * 60)
    
    # 1. マネージャー初期化
    print("\n✓ 1. TutorialManager 初期化")
    tm = TutorialManager()
    print(f"  - ステップ数: {len(tm.steps)}")
    print(f"  - 有効化前: enabled={tm.enabled}, current_step={tm.current_step}")
    
    # 2. チュートリアル開始
    print("\n✓ 2. チュートリアル開始")
    tm.start()
    print(f"  - 有効化後: enabled={tm.enabled}, current_step={tm.current_step}")
    
    # 3. 各ステップの確認
    print("\n✓ 3. ステップ詳細確認")
    for i in range(len(tm.steps)):
        step = tm.get_current_step()
        if step:
            print(f"\n  【ステップ {i}】")
            print(f"    メッセージ: {step.message}")
            print(f"    許可操作: {step.allowed_actions}")
            print(f"    ハイライト駒: {step.highlight_pieces}")
            print(f"    ハイライトマス: {step.highlight_tiles}")
            print(f"    ハイライトカード: {step.highlight_cards}")
            print(f"    固定デッキ: {step.fixed_deck}")
            
            # 次ステップへ
            tm.advance_step()
    
    # 4. 操作制限テスト
    print("\n✓ 4. 操作制限テスト")
    tm = TutorialManager()
    tm.start()
    
    print(f"\n  ステップ 0（駒を動かす）:")
    print(f"    - move_piece許可: {tm.is_action_allowed('move_piece')}")
    print(f"    - play_card許可: {tm.is_action_allowed('play_card')}")
    print(f"    - end_turn許可: {tm.is_action_allowed('end_turn')}")
    
    tm.advance_step()
    print(f"\n  ステップ 1（カードを使う）:")
    print(f"    - move_piece許可: {tm.is_action_allowed('move_piece')}")
    print(f"    - play_card許可: {tm.is_action_allowed('play_card')}")
    print(f"    - end_turn許可: {tm.is_action_allowed('end_turn')}")
    
    # 5. ハイライト情報取得テスト
    print("\n✓ 5. ハイライト情報テスト")
    tm = TutorialManager()
    tm.start()
    
    highlight = tm.get_highlight_info()
    print(f"\n  ステップ 0:")
    print(f"    - タイル: {highlight['tiles']}")
    print(f"    - 駒: {highlight['pieces']}")
    print(f"    - カード: {highlight['cards']}")
    
    # 6. コールバックテスト
    print("\n✓ 6. コールバック（自動進行）テスト")
    tm = TutorialManager()
    tm.start()
    
    print(f"\n  初期: step={tm.current_step}, completed={tm.completed}")
    
    # ステップ0: 駒移動でカード強制進行
    tm.on_piece_moved((6, 4), (5, 4))
    print(f"  駒移動後: step={tm.current_step}")
    
    # ステップ1: カード使用で自動進行
    tm.on_card_played(0)
    print(f"  カード使用後: step={tm.current_step}")
    
    # ステップ2: ターン終了で自動進行
    tm.on_turn_ended()
    print(f"  ターン終了後: step={tm.current_step}")
    
    # 7. スキップテスト
    print("\n✓ 7. スキップテスト")
    tm = TutorialManager()
    tm.start()
    print(f"  スキップ前: enabled={tm.enabled}, completed={tm.completed}")
    tm.skip()
    print(f"  スキップ後: enabled={tm.enabled}, completed={tm.completed}")
    
    # 8. メッセージ取得テスト
    print("\n✓ 8. メッセージ取得テスト")
    tm = TutorialManager()
    tm.start()
    print(f"\n  各ステップのメッセージ:")
    for i in range(len(tm.steps)):
        msg = tm.get_message()
        if msg:
            print(f"    Step {i}: {msg[:40]}...")
        tm.advance_step()
    
    print("\n" + "=" * 60)
    print("✓ すべてのテストが完了しました！")
    print("=" * 60)

if __name__ == "__main__":
    test_tutorial()
