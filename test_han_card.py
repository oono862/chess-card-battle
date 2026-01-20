"""「ハン です☆」カードの特殊演出テスト"""
import sys
import os

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'c.c.b'))

from card_core import Card, Deck

# テスト用の効果関数
def dummy_effect(game, player):
    return "test"

# カード名のバリエーションをテスト
test_names = [
    'ハンです☆',
    'ハン です☆',
    'ハン　です☆',
]

print("=== カード名テスト ===")
for name in test_names:
    print(f"カード名: '{name}'")
    deck = Deck(cards=[Card(name=name, cost=1, effect=dummy_effect) for _ in range(100)])
    
    special_count = 0
    normal_count = 0
    
    # 100回引いてみる
    for _ in range(100):
        card = deck.draw()
        if card and hasattr(card, 'custom_image') and card.custom_image:
            special_count += 1
        else:
            normal_count += 1
    
    print(f"  通常: {normal_count}回, 特殊: {special_count}回")
    print(f"  特殊出現率: {special_count}%")
    print()

print("=== 期待値 ===")
print("5%の確率なので、100回中約5回程度特殊画像が出るはずです")
