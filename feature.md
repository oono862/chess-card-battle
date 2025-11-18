# B.B.C.py モジュール分割計画

このファイルは、B.B.C.pyのモジュール分割の進捗を管理するためのチェックリストです。

## 📋 機能一覧と分割計画

### 1. ゲーム初期化・設定管理
- [ ] Pygame初期化とウィンドウ設定
- [x] フォント管理（フォントキャッシュ含む）
- [x] グローバル設定（ギミック発動モード、ダブルクリック設定等）
- [ ] 画面サイズ・レイアウト計算

**分割先**: `ui/config.py` ✅(部分完了), `ui/window.py`

---

### 2. カードゲームシステム
- [ ] ゲームインスタンス管理（game, ai_player）
- [x] デッキモード管理（fixed/custom）
- [x] カスタムデッキのロード・保存
- [x] ゲーム作成関数（new_game_with_mode等）
- [x] デッキ構築関数（build_deck_for_mode, build_ai_player）
- [x] カード名からゲーム構築（build_game_from_card_names）
- [x] 保存デッキ管理（load_saved_decks, save_decks_to_file）

**分割先**: `game/deck_manager.py` ✅

---

### 3. AIシステム
- [x] AI思考・行動ロジック（ai_make_move） - ai/ai_logic.pyに移行完了
- [x] AI用ギミックフラグ管理
- [x] AI難易度設定（CPU_DIFFICULTY）
- [x] AIプレイヤー作成（build_ai_player）

**分割先**: `ai/ai_logic.py` ✅
**進捗状況**:
  - ai_make_move関数(約412行)をai/ai_logic.pyに完全移行
  - B.B.C.pyはラッパー関数として新モジュールを呼び出す
  - AIカード判断、駒選択、難易度別ロジックを全て実装
  - グローバル変数の同期処理を実装

---

### 4. BGM・サウンド管理
- [x] BGMモード設定(set_bgm_mode)
- [x] BGM有効化・ボリューム管理
- [x] 音楽ファイル読み込み
- [x] BGM設定の取得・更新関数

**分割先**: `audio/bgm_manager.py` ✅

---

### 5. 画像・GIFアニメーション
- [x] カード画像キャッシュ（get_card_image）
- [x] 駒画像キャッシュ（get_piece_image_surface）
- [x] GIFアニメーションロード・再生
  - [x] Heat GIF（灼熱）
  - [x] Ice GIF（氷結）
  - [x] MG GIF（封鎖タイル）
- [x] 画像キャッシュ管理

**分割先**: `assets/image_loader.py`, `assets/animation.py` ✅

---

### 6. UI描画システム
#### 6.1 メイン描画・レイアウト
- [ ] draw_panel（メイン画面描画）
- [x] レイアウト計算（compute_layout）
- [x] テキスト描画ヘルパー（draw_text, wrap_text）
- [x] BASE UI解像度定数（BASE_UI_W, BASE_UI_H）

**分割先**: `ui/layout.py` ✅

#### 6.2 UI要素描画
- [ ] チェス盤描画
- [ ] 駒描画
- [ ] カード手札描画
- [ ] ログ表示（スクロール対応）
- [ ] 墓地表示オーバーレイ
- [ ] 相手手札表示
- [ ] ハイライト表示（移動可能マス）
- [ ] チェック状態表示
- [ ] ターン表示テロップ
- [ ] プロモーション選択UI
- [ ] カード拡大表示

**分割先候補**: `ui/renderer.py`, `ui/board_renderer.py`, `ui/card_renderer.py`, `ui/overlay.py`

---

### 7. モーダル・ダイアログ
- [x] スタート画面（show_start_screen） - ui/modals/screen_modals.pyに完全移行
- [x] 設定画面（show_settings_screen） - ui/modals/screen_modals.pyに完全移行
- [ ] 難易度選択（show_deck_choice_modal） - モジュール骨格作成済み
- [ ] デッキ管理画面（show_deck_modal） - モジュール骨格作成済み
- [ ] デッキ編集画面（show_deck_editor） - モジュール骨格作成済み
- [ ] デッキ内容確認（show_deck_contents_overlay） - モジュール骨格作成済み
- [ ] デッキバトル確認（show_deck_battle_confirm） - モジュール骨格作成済み
- [ ] デッキアクション選択（show_deck_action_modal） - モジュール骨格作成済み
- [ ] カスタムデッキ選択（show_custom_deck_selection）

**分割先**: `ui/modals/deck_modals.py`, `ui/modals/screen_modals.py` (骨格作成完了)
**進捗状況**:
  - show_start_screen関数をui/modals/screen_modals.pyに完全移行(~270行)
  - show_settings_screen関数をui/modals/screen_modals.pyに完全移行(~290行)
  - B.B.C.pyはラッパー関数として新モジュールを呼び出す
  - 難易度選択、デッキ選択、BGM設定、ギミック発動設定などの全機能を実装
**注意**: デッキ関連モーダルの完全移行は次フェーズで実施。現在はB.B.C.pyに元の実装が残存。

---

### 8. チェスルール・ロジック
#### 8.1 基本ロジック
- [x] 駒の移動可能範囲計算（get_valid_moves） - ラッパー関数として残存
- [x] チェック判定（is_in_check, is_in_check_for_display）
- [ ] チェックメイト判定
- [ ] ステイルメイト判定
- [x] 合法手判定（has_legal_moves_for, has_legal_moves_with_cards）

#### 8.2 特殊ルール
- [ ] キャスリング
- [ ] アンパサン
- [ ] プロモーション
- [ ] 同時チェック管理
- [x] カード効果考慮の合法手計算（has_legal_moves_with_cards）

**分割先**: `chess/rules.py` ✅(コア判定関数完了)
**注意**: get_valid_movesはB.B.C.pyにラッパー関数として残し、chess_rulesモジュールを利用

---

### 9. ゲーム状態管理
- [x] ターン管理（chess_current_turn）
- [x] ゲームオーバー判定
- [x] 選択中の駒管理（selected_piece, highlight_squares）
- [ ] プロモーション待ち状態
- [ ] カード効果の保留状態（pending）
- [ ] 凍結駒管理（frozen_pieces）
- [ ] 封鎖タイル管理（blocked_tiles）

**分割先**: `game/state.py` ✅(基本状態管理完了)
**進捗状況**:
  - GameStateクラス実装完了(20+変数を管理)
  - B.B.C.pyへのインポート完了
  - グローバル変数への参照コメント追加完了
  - restart_game関数で部分的に使用開始
**次フェーズ**: 全関数でのGameState利用への完全移行(draw_panel, handle_mouse_click, main_loop等)

---

### 10. イベント処理
- [x] キーボード入力処理（handle_keydown） - input/keyboard_handler.pyに移行完了
- [ ] マウスクリック処理（handle_mouse_click）
- [ ] ダブルクリック検出
- [ ] スクロールバー操作
- [ ] カード発動処理

**分割先**: `input/keyboard_handler.py` ✅, `input/mouse_handler.py` (候補)
**進捗状況**:
  - handle_keydown関数(271行)をinput/keyboard_handler.pyに移行完了
  - B.B.C.pyは新モジュールを呼び出すラッパー関数に変更
  - ゲーム終了、ログ、ターン開始、墓地表示、デバッグキー、カード使用、確認ダイアログなど全機能を実装

---

### 11. ターン制御
- [x] プレイヤーターン開始（start_player_turn）
- [x] ターン開始試行（attempt_start_turn）
- [x] ターン終了処理（end_player_chess_move）
- [x] ターン切り替え処理（switch_turn）
- [x] ステータス減衰処理（decay_statuses）※card_core.pyに実装済み

**分割先**: `game/turn_manager.py` ✅

---

### 12. デバッグ機能
- [x] デバッグボード設定
  - [x] キャスリング用（debug_setup_castling）
  - [x] アンパサン用（debug_setup_en_passant）
  - [x] プロモーション用（debug_setup_promotion）
  - [x] チェックメイト用（debug_setup_checkmate）
  - [x] 反撃チェック用（debug_setup_counter_check_white）
  - [x] 同時チェック用（debug_setup_simul_check_start）
- [x] デバッグモード管理（DEBUG_COUNTER_CHECK_CARD_MODE）
- [x] カード使用マーク（_debug_mark_card_played）

**分割先**: `debug/debug_tools.py` ✅

---

### 13. ユーティリティ
- [x] 盤面座標チェック（on_board）
- [x] 駒取得（get_piece_at）
- [x] 移動シミュレーション（simulate_move）
- [x] 破線矩形描画（draw_dashed_rect）
- [x] 相手手札数取得（get_opponent_hand_count）

**分割先**: `utils/helpers.py`, `utils/drawing.py` ✅

---

### 14. メインループ
- [x] メインゲームループ（main_loop） - game/loop_manager.pyにヘルパー関数を移行完了
- [ ] ゲーム再起動（restart_game）
- [x] フレームレート管理（clock.tick(60)）

**分割先**: `game/loop_manager.py` ✅
**進捗状況**:
  - main_loop関数(573行)からゲームロジック部分をgame/loop_manager.pyに分離完了
  - 9個のヘルパー関数を実装:
    * update_turn_tracking() - ターン追跡とテロップ表示
    * update_simultaneous_check_deadlines() - 同時チェック期限管理
    * check_simultaneous_check_victory() - 同時チェック勝敗判定
    * detect_new_simultaneous_check() - 同時チェック突入検出
    * check_king_capture_victory() - キング取得勝利判定
    * clear_simultaneous_check_state() - 同時チェック状態クリア
    * check_checkmate_and_stalemate() - チェックメイト/ステイルメイト判定
    * process_pending_actions() - 保留中処理の実行
    * process_gamble_promote() - 命がけのギャンブル処理
  - B.B.C.pyのmain_loop関数は主にイベント処理とAI思考管理に集中
  - ゲームロジックの大半をヘルパー関数に委譲済み

---

## 📊 分割モジュール構成案

```
chess-card-battle-1/
├── main.py                    # エントリポイント
├── game/
│   ├── __init__.py
│   ├── state.py              # ゲーム状態管理
│   ├── card_game.py          # カードゲームシステム
│   ├── deck_manager.py       # デッキ管理
│   ├── turn_manager.py       # ターン制御
│   └── effects.py            # カード効果管理
├── chess/
│   ├── __init__.py
│   ├── rules.py              # チェスルール
│   ├── special_moves.py      # 特殊移動
│   └── check_logic.py        # チェック判定
├── ai/
│   ├── __init__.py
│   ├── ai_player.py          # AIプレイヤー
│   └── ai_logic.py           # AI思考ロジック
├── ui/
│   ├── __init__.py
│   ├── config.py             # UI設定
│   ├── window.py             # ウィンドウ管理
│   ├── renderer.py           # メイン描画
│   ├── board_renderer.py     # 盤面描画
│   ├── card_renderer.py      # カード描画
│   ├── overlay.py            # オーバーレイ表示
│   ├── modals/               # モーダルダイアログ
│   │   ├── __init__.py
│   │   ├── start_screen.py
│   │   ├── deck_modal.py
│   │   └── settings.py
│   └── screens/              # 各種画面
│       └── __init__.py
├── input/
│   ├── __init__.py
│   ├── keyboard_handler.py   # キーボード入力
│   └── mouse_handler.py      # マウス入力
├── assets/
│   ├── __init__.py
│   ├── image_loader.py       # 画像読み込み
│   └── animation.py          # アニメーション管理
├── audio/
│   ├── __init__.py
│   └── bgm_manager.py        # BGM管理
├── utils/
│   ├── __init__.py
│   ├── helpers.py            # ヘルパー関数
│   └── drawing.py            # 描画ユーティリティ
└── debug/
    ├── __init__.py
    └── debug_tools.py        # デバッグツール
```

---

## 📝 分割作業の進め方

1. **Phase 1**: ユーティリティと設定の分離
   - utils/, ui/config.py, ui/window.py を作成
   
2. **Phase 2**: 描画システムの分離
   - ui/renderer.py, ui/board_renderer.py, ui/card_renderer.py を作成
   
3. **Phase 3**: ゲームロジックの分離
   - game/, chess/ モジュールを作成
   
4. **Phase 4**: AI・入力処理の分離
   - ai/, input/ モジュールを作成
   
5. **Phase 5**: UI要素の分離
   - ui/modals/, ui/screens/, ui/overlay.py を作成
   
6. **Phase 6**: アセット管理の分離
   - assets/, audio/ モジュールを作成
   
7. **Phase 7**: 統合テスト
   - 全モジュールの動作確認とバグ修正

---

## ✅ 完了基準

各機能について、以下が完了したらチェックマークを付けます：
- [ ] 該当機能を新しいモジュールに移動
- [ ] インポート文を更新
- [ ] 動作確認（既存の機能が正常に動作）
- [ ] グローバル変数の依存関係を整理

---

## 📌 注意事項

- グローバル変数が多く使われているため、段階的に分離すること
- 各モジュール間の依存関係を明確にすること
- 既存の機能を壊さないように、テストしながら進めること
- git でこまめにコミットし、問題があればロールバック可能にすること
