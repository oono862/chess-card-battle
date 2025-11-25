#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chess-Card-Battle ゲームのエントリポイント

このファイルはゲームを起動するためのメインエントリポイントです。
C.C.Bフォルダ内のCard Game.pyを適切にインポートして実行します。
"""
import sys
import os

# プロジェクトルートディレクトリをパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# C.C.Bディレクトリをパスに追加
ccb_dir = os.path.join(project_root, 'C.C.B')
if ccb_dir not in sys.path:
    sys.path.insert(0, ccb_dir)

if __name__ == "__main__":
    # Card Game.pyの内容をインポートして実行
    try:
        # C.C.Bフォルダ内のCard Game.pyを直接実行
        card_game_path = os.path.join(ccb_dir, 'card_game.py')
        with open(card_game_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # __name__を'__main__'に設定して実行
        exec(compile(code, card_game_path, 'exec'), {'__name__': '__main__', '__file__': card_game_path})
    except Exception as e:
        print(f"ゲームの起動中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
