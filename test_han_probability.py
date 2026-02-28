"""「ハン です☆」カードの特殊演出テスト（大量試行）"""
import sys
import os

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'c.c.b'))

from card_core import Card, Deck

# テスト用の効果関数
def dummy_effect(game, player):
    return "test"

# 1000回試行して確率を検証
test_count = 1000
card_name = 'ハン です☆'

print(f"=== {card_name} を{test_count}回引いてテスト ===\n")

deck = Deck(cards=[Card(name=card_name, cost=1, effect=dummy_effect) for _ in range(test_count)])

special_count = 0
normal_count = 0

for _ in range(test_count):
    card = deck.draw()
    if card and hasattr(card, 'custom_image') and card.custom_image:
        special_count += 1
    else:
        normal_count += 1

percentage = (special_count / test_count) * 100

print(f"通常画像: {normal_count}回")
print(f"特殊画像: {special_count}回")
print(f"\n特殊出現率: {percentage:.2f}%")
print(f"理論値: 5.00%")
print(f"誤差: {abs(percentage - 5.0):.2f}%")

if 3.0 <= percentage <= 7.0:
    print("\n✅ 正常に動作しています！")
else:
    print("\n⚠ 確率が理論値から大きく外れています")
