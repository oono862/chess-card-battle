"""
一時的なスクリプト: 添付画像をdeck_bg.pngとして保存
使用後は削除してください
"""
from PIL import Image
import os

# 画像のパスを指定してください
# このスクリプトを実行する際に、添付画像のパスを引数として渡してください
import sys

if len(sys.argv) > 1:
    input_path = sys.argv[1]
    output_path = os.path.join("images", "deck_bg.png")
    
    # 画像を開いて保存
    img = Image.open(input_path)
    img.save(output_path)
    print(f"背景画像を保存しました: {output_path}")
else:
    print("使い方: python save_deck_bg.py <画像ファイルのパス>")
