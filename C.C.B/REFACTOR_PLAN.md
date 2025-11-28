# Card Game.py リファクタリング計画

## 現状

Card Game.pyは7105行のモノリシックファイルで、以下を含んでいます:
- ゲームループとメインロジック
- UI描画処理
- モーダルダイアログ(10個以上)
- チェスロジックの一部
- AIロジックの呼び出し
- 入力ハンドリング

## 段階的リファクタリング計画

### Phase 1: モジュール構造の整理 ✅ (完了)

- [x] ui/modalsモジュールにモーダル関数を実装
- [x] 重複ファイルの削除(11ファイル)
- [x] Card Game.pyにui.modalsのインポートを追加

### Phase 2: モーダル関数の置き換え (TODO)

Card Game.py内の以下の関数は、ui.modalsに完全実装が存在します:

#### デッキ関連モーダル (ui/modals/deck_modals.py)
- `show_deck_choice_modal()` (行445) - 固定/カスタムデッキ選択
- `show_deck_modal()` (行1149) - デッキリスト表示(3x3グリッド)
- `show_deck_options()` (行1331) - デッキオプション
- `show_deck_battle_confirm()` (行1394) - バトル確認
- `show_deck_editor()` (行1479) - デッキ作成/編集
- `show_deck_action_modal()` (行2015) - デッキアクション選択
- `show_deck_contents_overlay()` (行2232) - デッキ内容表示

#### 画面モーダル (ui/modals/screen_modals.py)
- `show_start_screen()` (行853) - スタート画面と難易度選択
- `show_settings_screen()` (行2309) - 設定画面

**問題点:**
- Card Game.py内の関数とui.modalsの関数でシグネチャが異なる
- グローバル変数への依存が強い
- 直接置き換えには大規模な変更が必要

**推奨アプローチ:**
1. 新しいゲーム機能ではui.modalsを直接使用
2. 既存のコードは段階的に移行
3. グローバル変数を減らし、引数として渡す設計に変更

### Phase 3: 大型関数の分割 (TODO)

以下の関数は非常に大きく、複数の責務を持っています:

#### 1. `draw_panel()` (行3525, 約1829行)
- **責務:** ゲーム画面全体の描画
- **問題:** 複数の描画処理が1つの関数に集約されている
- **提案:** ui/renderer.pyに分割
  - `draw_board()` - チェス盤描画
  - `draw_hand()` - 手札描画
  - `draw_log()` - ログ描画
  - `draw_status()` - ステータス表示
  - `draw_buttons()` - ボタン描画

#### 2. `handle_mouse_click()` (行5354, 約985行)
- **責務:** マウスクリックイベント処理
- **問題:** 多数のクリック対象を1つの関数で処理
- **提案:** input/mouse_handler.pyに機能分割
  - `handle_board_click()` - チェス盤クリック
  - `handle_card_click()` - カード選択
  - `handle_button_click()` - ボタンクリック
  - `handle_modal_click()` - モーダル内クリック

#### 3. `ai_make_move()` (行3033, 約492行)
- **責務:** AI思考とアクション実行
- **問題:** AI判断とゲームロジックが混在
- **提案:** ai/ai_logic.pyに完全移行
  - 既にai/ai_logic.pyが存在するため、そこに統合

#### 4. `main_loop()` (行6339, 約742行)
- **責務:** メインゲームループ
- **問題:** イベント処理とゲーム更新が混在
- **提案:** game/loop_manager.pyに機能分割
  - `handle_events()` - イベント処理
  - `update_game_state()` - ゲーム状態更新
  - `render_frame()` - フレーム描画

### Phase 4: グローバル変数の削減 (TODO)

現在、多数のグローバル変数が使用されています:
```python
game, ai_player, chess, screen, W, H, FONT, SMALL, TINY, 
CPU_DIFFICULTY, DECK_MODE, card_rects, selected_piece, 
highlight_squares, chess_current_turn, game_over, 
game_over_winner, cpu_wait, log_scroll_offset, ...
```

**提案:**
1. `GameState`クラスを作成し、ゲーム状態を集約
2. `UIState`クラスを作成し、UI状態を管理
3. 関数の引数として必要な状態を渡す設計に変更

### Phase 5: テストの追加 (TODO)

リファクタリングの安全性を保証するため、テストを追加:
- 単体テスト: 個別関数のテスト
- 統合テスト: モーダル表示とゲームフローのテスト
- リグレッションテスト: 既存機能が壊れていないことを確認

## 実施優先順位

1. **高優先度:** Phase 2 (モーダル関数の置き換え)
   - 影響範囲が限定的
   - ui.modalsモジュールが既に完成している
   
2. **中優先度:** Phase 3 (大型関数の分割)
   - draw_panel()とhandle_mouse_click()は特に複雑
   - 段階的に分割可能

3. **低優先度:** Phase 4 (グローバル変数の削減)
   - 大規模な変更が必要
   - 全体の設計変更を伴う

4. **継続的:** Phase 5 (テストの追加)
   - リファクタリングと並行して実施

## 注意事項

- **ブランチで作業:** 各フェーズは個別のブランチで実施
- **段階的にマージ:** 小さな変更を頻繁にマージ
- **動作確認:** 各変更後にゲームが正常に動作することを確認
- **ペアプログラミング:** 複雑な変更はチームで実施

## 完了したタスク

- [x] デッキ数の修正(24枚総数維持)
- [x] 重複ファイルの削除(11ファイル)
- [x] ui.modalsモジュールのインポート追加
- [x] リファクタリング計画の文書化
