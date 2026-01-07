# Chess-Card-Battle プロジェクト概要

## 📋 プロジェクト基本情報

**プロジェクト名**: Chess-Card-Battle  
**タイプ**: デスクトップゲーム（Python + Pygame）  
**ゲームジャンル**: チェス × カードバトル ハイブリッドゲーム

### ゲームコンセプト
伝統的なチェスにカードゲームの戦略要素を組み合わせた、ターン制の戦略ゲーム。プレイヤーは駒を動かすだけでなく、カードを使って戦況を変化させることができます。

---

## 🎮 ゲームの特徴

### コアメカニクス
1. **チェスの基本ルール** - 標準的なチェスルールに準拠
2. **カードシステム** - プレイポイント（PP）を消費してカードを使用
3. **ターン管理** - 各ターン開始時にPP回復 + カード1枚ドロー
4. **AI対戦** - 4段階の難易度（Easy, Medium, Hard, Expert）
5. **カスタムデッキ** - プレイヤー独自のデッキ作成が可能

### ゲームモード
- **ローカル対戦**: 同じPC上で2人対戦
- **CPU対戦**: AI相手に対戦
- **オンライン対戦**: ネットワーク経由での対戦（実装中）

---

## 🏗️ プロジェクト構造

### ディレクトリ構成
```
chess-card-battle-1/
├── c.c.b/                      # メインソースコード
│   ├── __init__.py
│   ├── CardGame.py             # メインゲームロジック（約7700行）
│   ├── ChessMain.py            # 旧メインエントリーポイント
│   ├── card_core.py            # カードシステムコア（1800行）
│   ├── chess_engine.py         # チェスエンジン（361行）
│   ├── mode_select.py          # ゲームモード選択
│   ├── piece.py                # 駒の基本クラス
│   │
│   ├── ai/                     # AI関連
│   │   ├── ai_logic.py         # AI思考ロジック（449行）
│   │   └── config.py           # AI設定
│   │
│   ├── assets/                 # アセット管理
│   │   ├── animation.py        # GIFアニメーション
│   │   └── image_loader.py     # 画像ロード＆キャッシュ（384行）
│   │
│   ├── audio/                  # サウンド管理
│   │   └── bgm_manager.py      # BGM再生管理（132行）
│   │
│   ├── chess/                  # チェスルール
│   │   └── rules.py            # チェスルール実装
│   │
│   ├── debug/                  # デバッグツール
│   │   └── debug_tools.py      # デバッグ用ユーティリティ
│   │
│   ├── game/                   # ゲーム状態管理
│   │   ├── state.py            # ゲーム状態クラス（171行）
│   │   ├── deck_manager.py     # デッキ管理（386行）
│   │   ├── loop_manager.py     # ゲームループ管理
│   │   └── turn_manager.py     # ターン管理
│   │
│   ├── input/                  # 入力処理
│   │   ├── keyboard_handler.py # キーボード入力
│   │   └── mouse_handler.py    # マウス入力
│   │
│   ├── ui/                     # UI描画
│   │   ├── board_renderer.py   # チェス盤描画（686行）
│   │   ├── card_renderer.py    # カード描画（146行）
│   │   ├── panel_renderer.py   # パネル描画
│   │   ├── overlay.py          # オーバーレイUI
│   │   ├── window.py           # ウィンドウ管理
│   │   ├── layout.py           # レイアウト計算
│   │   ├── config.py           # UI設定
│   │   ├── renderer.py         # 汎用描画ヘルパー
│   │   └── modals/             # モーダルダイアログ
│   │       ├── deck_modals.py  # デッキ関連モーダル
│   │       └── screen_modals.py# 画面モーダル
│   │
│   └── utils/                  # ユーティリティ
│       ├── drawing.py          # 描画ヘルパー
│       └── helpers.py          # 汎用ヘルパー
│
├── images/                     # ゲーム画像
│   ├── Chess_*_*.png           # 駒画像（白黒×6種類）
│   ├── card_*.png              # カード画像
│   ├── Image_*.gif             # エフェクトアニメーション
│   └── *.png                   # その他UI画像
│
├── mugic/                      # BGM音源
│   └── MusMus-BGM-*.mp3
│
├── Noto_Sans_JP/               # 日本語フォント
│
├── scripts/                    # 開発用スクリプト
│   ├── check_image_file.py
│   ├── test_image_loader.py
│   └── ...
│
├── tests/                      # テストファイル
│   ├── test_inspect_deck.py
│   └── check_heat_protection.py
│
├── tools/                      # 開発ツール
│   ├── check_decks.py
│   ├── test_rule_deck_images.py
│   └── ...
│
├── saved_decks.json            # 保存されたデッキデータ
├── feature.md                  # 機能一覧とリファクタリング進捗
├── REFACTOR_PLAN.md            # リファクタリング計画
└── PROJECT_OVERVIEW.md         # このファイル
```

---

## 🔧 主要モジュール詳細

### 1. CardGame.py（メインゲームロジック）
**行数**: 約7700行  
**役割**: ゲーム全体の中核

#### 主要機能
- **ゲームループ** (`main_loop()` - 約770行)
  - イベント処理
  - 状態更新
  - 描画処理
  
- **UI描画** (`draw_panel()` - 約1829行)
  - チェス盤描画
  - 手札・墓地表示
  - メッセージ表示
  - エフェクト描画
  
- **入力処理** (`handle_mouse_click()` - 約1000行)
  - 駒の選択・移動
  - カードクリック
  - ボタンクリック
  
- **AI制御** (`ai_make_move()` - 約500行)
  - AI思考ロジック
  - カード判断
  - 駒選択

#### 特記事項
- モノリシックな構造のため、現在リファクタリング中
- 多数のグローバル変数を使用（GameStateクラスへの移行中）

---

### 2. card_core.py（カードシステム）
**行数**: 約1831行  
**役割**: カードゲームシステムの基盤

#### データモデル
```python
@dataclass
class Card:
    name: str           # カード名
    cost: int          # 使用コスト（PP）
    effect: EffectFn   # 効果関数
    precheck: Optional[PrecheckFn]  # 使用前チェック

@dataclass
class PlayerState:
    pp_max: int        # 最大PP（通常3）
    pp_current: int    # 現在のPP
    deck: Deck         # デッキ
    hand: Hand         # 手札
    graveyard: List[Card]  # 墓地
```

#### カードシステムフロー
1. **ゲーム開始時**: 4枚ドロー
2. **ターン開始時**: PP回復 + 1枚ドロー
3. **カード使用**: PP消費 → 効果発動 → 墓地へ
4. **効果処理**: 駒移動、特殊能力、盤面変化など

#### 実装されているカードタイプ
- **攻撃系**: 駒の除去、ダメージ
- **防御系**: 鉄壁（攻撃無効化）
- **移動系**: 迅雷（追加ターン）
- **制御系**: 氷結（駒の凍結）、灼熱（凍結解除/封鎖）
- **リソース系**: ドロー、PP回復

---

### 3. chess_engine.py（チェスエンジン）
**行数**: 361行  
**役割**: チェスルールの実装

#### 主要機能
- **駒クラス** (`Piece`)
  - 各駒の移動可能範囲計算
  - キャスリング判定
  - アンパッサン処理
  - ポーン昇格
  
- **盤面管理**
  - 駒配置状態
  - 移動検証
  - チェック判定
  - チェックメイト判定

#### サポートする特殊ルール
- ✅ キャスリング（王と塔の同時移動）
- ✅ アンパッサン（ポーンの特殊取り方）
- ✅ ポーン昇格（最終列到達時の昇格）
- ✅ チェック・チェックメイト判定
- ✅ ステイルメイト（引き分け）判定

---

### 4. AI System（ai/ai_logic.py）
**行数**: 449行  
**役割**: AI思考・行動ロジック

#### AI難易度レベル
1. **Easy (CPU_DIFFICULTY=1)**
   - ランダム移動
   - カードはランダム使用
   
2. **Medium (CPU_DIFFICULTY=2)**
   - 簡易評価で駒選択
   - カード効果を考慮
   
3. **Hard (CPU_DIFFICULTY=3)**
   - 詳細な盤面評価
   - 戦略的なカード使用
   
4. **Expert (CPU_DIFFICULTY=4)**
   - 高度な先読み
   - 最適なカード選択

#### AI思考フロー
```
1. ターン開始処理（PP回復＋ドロー）
2. カード使用判断
   ├─ 手札を評価
   ├─ 使用可能なカードを選択
   └─ 効果を実行
3. 駒移動判断
   ├─ 全駒の移動可能先を列挙
   ├─ 各移動を評価（盤面評価関数）
   └─ 最良の手を選択
4. 特殊処理
   ├─ 迅雷による連続ターン
   └─ 同時チェック対応
```

---

### 5. Game State Management（game/state.py）
**行数**: 171行  
**役割**: ゲーム状態の一元管理

#### 管理する状態
```python
class GameState:
    # チェス盤の状態
    selected_piece: Optional[Piece]
    highlight_squares: List[Tuple[int, int]]
    chess_current_turn: str  # 'white' or 'black'
    
    # 同時チェック管理
    simul_check_active: bool
    simul_white_result: str
    simul_black_result: str
    
    # ゲーム終了状態
    game_over: bool
    game_over_winner: Optional[str]
    
    # UI表示状態
    show_grave: bool
    show_log: bool
    enlarged_card_index: Optional[int]
    show_opponent_hand: bool
    
    # メッセージ表示
    turn_telop_msg: Optional[str]
    notice_msg: Optional[str]
    
    # ゲームインスタンス
    game: Game  # card_core.Game
    ai_player: PlayerState
```

#### 利点
- グローバル変数の削減
- 状態管理の一元化
- テスト・デバッグの容易化

---

### 6. UI Rendering System（ui/）

#### board_renderer.py（686行）
**チェス盤描画**
- マス目の描画
- 駒の描画
- ハイライト表示（移動可能マス）
- カード効果の視覚化
  - 封鎖タイル（赤枠）
  - 凍結駒（氷アニメーション）
  - エフェクトGIF再生

#### card_renderer.py（146行）
**カード描画**
- 手札表示
- 拡大表示
- カードコスト表示
- クリック判定用矩形管理

#### モーダルシステム（ui/modals/）
**deck_modals.py**
- デッキ選択画面
- デッキ編集画面
- デッキ内容表示
- バトル確認ダイアログ

**screen_modals.py**
- スタート画面
- 設定画面
- 難易度選択

---

### 7. Asset Management（assets/）

#### image_loader.py（384行）
**画像管理システム**
- 画像のロード＆キャッシュ
- カード画像（PNG）
- 駒画像（PNG）
- GIFアニメーション
- リサイズ・最適化

**キャッシュシステム**
```python
_image_cache = {}           # 通常画像
_piece_image_cache = {}     # 駒画像
_gif_animation_cache = {}   # GIFアニメーション
```

#### animation.py
**アニメーション管理**
- GIF読み込み
- フレーム管理
- タイミング制御
- エフェクト再生（灼熱、氷結、魔術など）

---

### 8. Deck Management（game/deck_manager.py）
**行数**: 386行  
**役割**: デッキ管理システム

#### 機能
- **デッキモード**
  - `fixed`: 固定デッキ（バランス調整済み）
  - `custom`: カスタムデッキ（プレイヤー作成）
  
- **デッキ保存/読み込み**
  - JSON形式で保存
  - カード名リストから復元
  - エラーハンドリング
  
- **デッキ構築**
  - AI用デッキ生成
  - カードプールからの選択
  - バランス調整

---

## 🎴 実装済みカード一覧

### 基本カード
| カード名 | コスト | 効果 |
|---------|-------|------|
| **迅雷** | 2 | 追加で1手駒を動かせる |
| **鉄壁** | 2 | 次の相手ターン中、自分の駒が取られない |
| **氷結** | 1 | 相手の駒1つを2ターン凍結（移動不可） |
| **灼熱** | 2 | 凍結解除 or タイル3つを封鎖 |
| **2ドロー** | 1 | カードを2枚引く |
| **暴風** | 1 | カードを1枚引き、相手は1枚捨てる |
| **錬成** | 0 | PP+1（最大3） |

### 特殊カード
| カード名 | コスト | 効果 |
|---------|-------|------|
| **墓地ルーレット** | 1 | 墓地からランダムに1枚手札に戻す |
| **摂取** | 2 | 相手の墓地から1枚選んで使用 |
| **命がけのギャンブル** | 3 | 50%で相手の駒1つ除去、失敗で自駒除去 |

---

## 🔄 リファクタリング状況

### 完了した項目 ✅
- [x] UI/config.py - UI設定管理
- [x] UI/window.py - ウィンドウ管理
- [x] UI/layout.py - レイアウト計算
- [x] game/state.py - ゲーム状態一元管理
- [x] game/deck_manager.py - デッキ管理システム
- [x] ai/ai_logic.py - AI思考ロジック
- [x] audio/bgm_manager.py - BGM管理
- [x] ui/modals/ - モーダルダイアログ（10個以上）
- [x] assets/image_loader.py - 画像管理システム

### 進行中の項目 🚧
- [ ] CardGame.py の関数分割
  - draw_panel() の機能別分割
  - handle_mouse_click() のリファクタリング
  - グローバル変数の削減

### 今後の予定 📋
- [ ] テストコードの充実
- [ ] パフォーマンス最適化
- [ ] オンライン対戦機能の完成
- [ ] UIの改善（アニメーション強化）

---

## 🎯 主要な技術課題

### 1. モノリシックな構造
**問題**: CardGame.py が7700行と巨大  
**対策**: 段階的なモジュール化（現在進行中）  
**方針**: 
- 新機能は必ずモジュールに配置
- 既存コードは最小限の変更
- セクションコメントで可読性向上

### 2. グローバル変数の乱立
**問題**: 多数のグローバル変数による管理の複雑化  
**対策**: GameStateクラスへの統合  
**進捗**: 主要な状態変数は移行完了

### 3. 同時チェック機能
**複雑性**: 両プレイヤーが同時にチェック状態になった場合の処理  
**実装**: 専用の状態管理と判定ロジック  
**状態**: 基本実装完了、調整中

---

## 🛠️ 開発環境

### 必須要件
- **Python**: 3.8以上
- **Pygame**: 2.0以上
- **OS**: Windows / macOS / Linux

### 推奨スペック
- **メモリ**: 4GB以上
- **ストレージ**: 500MB以上（画像アセット含む）
- **画面解像度**: 1200x800以上

### 依存ライブラリ
```python
pygame       # ゲームエンジン
dataclasses  # データモデル（Python 3.7+は標準）
typing       # 型ヒント
json         # デッキ保存/読み込み
random       # ランダム処理
logging      # ログ出力
```

---

## 🚀 起動方法

### 基本起動
```bash
cd c.c.b
python CardGame.py
```

### デバッグモード
```bash
python CardGame.py --debug
```

### 旧エントリーポイント（ChessMain.py）
```bash
python ChessMain.py
```

---

## 📝 開発ドキュメント

### プロジェクト内ドキュメント
- [feature.md](feature.md) - 機能一覧とリファクタリング進捗（925行）
- [REFACTOR_PLAN.md](c.c.b/REFACTOR_PLAN.md) - リファクタリング計画（198行）
- [修正ドキュメント_デッキ詳細からのバトル開始.md](修正ドキュメント_デッキ詳細からのバトル開始.md) - 機能追加履歴

### コード内ドキュメント
各モジュールには詳細なdocstringとコメントが含まれています。

---

## 🧪 テスト構成

### テストファイル
```
tests/
├── test_inspect_deck.py        # デッキ検証テスト
├── check_heat_protection.py    # 灼熱カード保護機能テスト

c.c.b/
├── test_card_integration.py    # カード統合テスト
├── test_ironwall.py            # 鉄壁カードテスト
├── test_lightning.py           # 迅雷カードテスト
├── verify_turn_consumption.py  # ターン消費検証
├── chess_engine_smoketests.py  # チェスエンジンテスト
└── smoke_headless_test.py      # ヘッドレステスト
```

---

## 🎨 アセット構成

### 画像アセット（images/）
- **駒画像**: 12ファイル（白黒 × 6種類）
  - `Chess_k_white.png` / `Chess_k_black.png` (王)
  - `Chess_q_white.png` / `Chess_q_black.png` (女王)
  - `Chess_r_white.png` / `Chess_r_black.png` (塔)
  - `Chess_b_white.png` / `Chess_b_black.png` (司教)
  - `Chess_n_white.png` / `Chess_n_black.png` (騎士)
  - `Chess_p_white.png` / `Chess_p_black.png` (ポーン)

- **カード画像**: 約15ファイル
  - `2ドロー.png`
  - `迅雷.png`
  - `鉄壁.png`
  - `氷結.png`
  - `灼熱.png`
  - `暴風.png`
  - `錬成.png`
  - その他特殊カード

- **エフェクトGIF**: 5ファイル
  - `Image_F.gif` (炎エフェクト)
  - `Image_ic (1).gif` (氷エフェクト)
  - `Image_MG.gif` / `Image_MG_2P.gif` (魔術エフェクト)
  - `card_you_lose.gif` (敗北エフェクト)

### 音楽アセット（mugic/）
- `MusMus-BGM-162.mp3` - バトルBGM
- `MusMus-BGM-173.mp3` - メニューBGM

### フォント（Noto_Sans_JP/）
- Noto Sans JP - 日本語表示用フォント

---

## 🐛 既知の問題

### 高優先度
- [ ] 一部のモーダルでスクロールが機能しない
- [ ] 同時チェック状態での挙動が不安定な場合がある

### 中優先度
- [ ] AI難易度Expertで思考時間が長い
- [ ] 一部のカード効果でアニメーションが遅延する

### 低優先度
- [ ] ウィンドウリサイズ時に一時的にレイアウトが崩れる
- [ ] 長時間プレイでメモリ使用量が増加

---

## 🌟 今後の拡張予定

### 短期目標
- [ ] カードバランス調整
- [ ] UI/UXの改善
- [ ] チュートリアルモードの追加
- [ ] リプレイ機能

### 中期目標
- [ ] 新カードの追加（10種類以上）
- [ ] オンライン対戦の完成
- [ ] ランキングシステム
- [ ] 実績システム

### 長期目標
- [ ] トーナメントモード
- [ ] カスタムルール設定
- [ ] モバイル版の検討
- [ ] マルチプレイヤー（4人対戦）

---

## 👥 チーム開発ルール

### ブランチ運用
- **必須**: 各メンバーは個人ブランチで作業
- **禁止**: mainブランチへの直接編集
- **命名規則**: `[メンバー名]/[機能名]`

### Git フロー
1. 個人ブランチを作成
2. 作業を行う
3. コミット＆プッシュ
4. プルリクエストを作成
5. レビュー後にマージ

### 参考
詳細は [.github/copilot-instructions.md](.github/copilot-instructions.md) を参照

---

## 📊 コード統計

### ファイル数
- **Pythonファイル**: 約50ファイル
- **画像アセット**: 約40ファイル
- **音楽ファイル**: 2ファイル
- **ドキュメント**: 5ファイル

### 総行数（概算）
- **メインロジック**: 約15,000行
- **UI関連**: 約2,500行
- **テストコード**: 約1,000行
- **ドキュメント**: 約1,500行

---

## 📚 参考情報

### 使用している主要パターン
- **MVC パターン**: 状態（Model）、描画（View）、入力処理（Controller）の分離
- **データクラス**: Pythonのdataclassesを活用した型安全なデータモデル
- **コールバックパターン**: カード効果の実装
- **キャッシュパターン**: 画像の遅延ロード＆キャッシュ

### 設計の特徴
- **モジュラー設計**: 機能ごとにモジュール分割（進行中）
- **状態管理の一元化**: GameStateクラスによる集中管理
- **UI非依存のコアロジック**: card_core.pyは純粋なPython

---

## 📞 トラブルシューティング

### 起動しない場合
1. Python バージョンを確認（3.8以上）
2. Pygame をインストール: `pip install pygame`
3. カレントディレクトリを確認: `cd c.c.b`

### 画像が表示されない場合
1. `images/` フォルダの存在を確認
2. パスの設定を確認（image_loader.py）
3. Pygame の画像ロード機能を確認

### BGMが再生されない場合
1. `mugic/` フォルダの存在を確認
2. Pygame の mixer 初期化を確認
3. 設定画面でBGM有効化を確認

---

## 🎓 学習リソース

### チェスルールの参考
- 公式FIDEルール
- chess_engine.py のコメント

### Pygame 学習
- [Pygame公式ドキュメント](https://www.pygame.org/docs/)
- プロジェクト内の実装例

### Python 型ヒント
- card_core.py の dataclass 実装
- typing モジュールの活用例

---

## 📜 ライセンス

（プロジェクトのライセンス情報を記載）

---

## 🎉 クレジット

### 使用アセット
- **BGM**: MusMus様
- **フォント**: Noto Sans JP（Google Fonts）
- **画像**: プロジェクト独自作成

### 開発チーム
- 3人チーム開発プロジェクト

---

**最終更新**: 2026年1月7日  
**ドキュメントバージョン**: 1.0
