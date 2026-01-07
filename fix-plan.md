# PyInstaller exe化 修正計画

## 📋 概要

このドキュメントは、Chess-Card-Battle プロジェクトを PyInstaller で exe 化する際に発生する問題点と、その修正方法をまとめたものです。

---

## 🔴 優先度：高（必須修正）

### 1. リソースパス解決の問題

**問題点**: 
現在、`__file__` を使用してリソースパスを解決しているが、PyInstaller でパッケージングすると `__file__` の動作が変わり、リソースが見つからなくなる。

**影響箇所**:
- [c.c.b/assets/image_loader.py](c.c.b/assets/image_loader.py#L19-L26) - 画像ディレクトリ
- [c.c.b/audio/bgm_manager.py](c.c.b/audio/bgm_manager.py#L102-L107) - BGMディレクトリ
- [c.c.b/game/deck_manager.py](c.c.b/game/deck_manager.py#L22-L28) - デッキ保存ファイル
- [c.c.b/CardGame.py](c.c.b/CardGame.py#L82-L88) - 各種パス設定

**修正方法**:
共通のパス解決ユーティリティを作成し、`sys.frozen` 属性をチェックして PyInstaller 環境かどうかを判定する。

```python
# c.c.b/utils/path_resolver.py (新規作成)
import os
import sys

def get_base_path():
    """PyInstaller でパッケージ化された場合と開発環境で適切なベースパスを返す"""
    if getattr(sys, 'frozen', False):
        # PyInstaller でパッケージ化された場合
        return sys._MEIPASS
    else:
        # 開発環境の場合
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_resource_path(relative_path):
    """リソースへの絶対パスを取得"""
    return os.path.join(get_base_path(), relative_path)

def get_writable_path(relative_path):
    """書き込み可能なパス（exe と同じディレクトリ）を取得"""
    if getattr(sys, 'frozen', False):
        # exe と同じディレクトリに保存
        return os.path.join(os.path.dirname(sys.executable), relative_path)
    else:
        return os.path.join(get_base_path(), relative_path)
```

---

### 2. ハードコードされた絶対パス

**問題点**:
特定のユーザー環境のパスがハードコードされており、他の環境では動作しない。

**影響箇所**:

| ファイル | 行 | 内容 |
|---------|------|------|
| [CardGame.py](c.c.b/CardGame.py#L1809) | 1809 | `c:\Users\Student\Downloads\...` |
| [CardGame.py](c.c.b/CardGame.py#L2888-L2890) | 2888-2890 | `C:\Windows\Fonts\*.ttf` |
| [ChessMain.py](c.c.b/ChessMain.py#L200) | 200 | `c:\Users\Student\Desktop\...` |
| [screen_modals.py](c.c.b/ui/modals/screen_modals.py#L45) | 45 | `c:\Users\Student\Downloads\...` |
| [deck_modals.py](c.c.b/ui/modals/deck_modals.py#L1336-L1338) | 1336-1338 | `C:\Windows\Fonts\*.ttf` |

**修正方法**:
- フォールバック画像パスはリポジトリ内のリソースのみを使用するよう変更
- フォントは同梱の `Noto_Sans_JP` を優先使用し、システムフォントはフォールバックとして残す
- Windows 以外の OS でも動作するよう、フォントパスの存在チェックを追加

---

### 3. 書き込み可能ファイルの配置

**問題点**:
`saved_decks.json` と `user_settings.json` がリソースディレクトリに保存されるが、PyInstaller の一時展開ディレクトリは読み取り専用。

**影響箇所**:
- [c.c.b/CardGame.py](c.c.b/CardGame.py#L134) - `user_settings.json`
- [c.c.b/game/deck_manager.py](c.c.b/game/deck_manager.py#L27) - `saved_decks.json`

**修正方法**:
- 書き込みが必要なファイルは exe と同じディレクトリ、または `%APPDATA%` に保存
- `get_writable_path()` 関数を使用して書き込み可能なパスを取得

```python
# 例: user_settings.json の保存場所
def get_user_data_dir():
    """ユーザーデータ保存ディレクトリを取得"""
    if getattr(sys, 'frozen', False):
        # exe と同じディレクトリ
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))
```

---

### 4. PyInstaller spec ファイルの作成

**問題点**:
spec ファイルが存在しないため、リソースファイルが自動的に含まれない。

**修正方法**:
以下の spec ファイルを作成する。

```python
# chess_card_battle.spec (新規作成)
# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# プロジェクトルート
project_root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['c.c.b/CardGame.py'],
    pathex=[project_root, os.path.join(project_root, 'c.c.b')],
    binaries=[],
    datas=[
        ('images', 'images'),
        ('mugic', 'mugic'),
        ('Noto_Sans_JP', 'Noto_Sans_JP'),
    ],
    hiddenimports=[
        'pygame',
        'c.c.b.card_core',
        'c.c.b.chess_engine',
        'c.c.b.assets.image_loader',
        'c.c.b.assets.animation',
        'c.c.b.audio.bgm_manager',
        'c.c.b.game.deck_manager',
        'c.c.b.game.state',
        'c.c.b.ui.board_renderer',
        'c.c.b.ui.card_renderer',
        'c.c.b.ui.overlay',
        'c.c.b.ui.modals.deck_modals',
        'c.c.b.ui.modals.screen_modals',
        'c.c.b.ai.ai_logic',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChessCardBattle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUIアプリなのでコンソール非表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # アイコンがあれば指定: icon='icon.ico'
)
```

---

## 🟡 優先度：中（推奨修正）

### 5. requirements.txt の作成

**問題点**:
依存パッケージの定義ファイルが存在しない。

**修正方法**:
```
# requirements.txt (新規作成)
pygame>=2.0.0
```

---

### 6. フォント同梱と読み込み優先順位

**問題点**:
システムフォント（`SysFont`）に依存しているため、フォントがない環境で文字化けする可能性。

**影響箇所**:
- [CardGame.py](c.c.b/CardGame.py#L245-L248) 等、多数の `pygame.font.SysFont` 呼び出し

**修正方法**:
同梱の `Noto_Sans_JP` フォントを優先使用する共通フォント読み込み関数を作成。

```python
# c.c.b/utils/font_loader.py (新規作成)
import os
import pygame
from .path_resolver import get_resource_path

_font_cache = {}

def get_font(size, bold=False):
    """同梱フォントを優先して読み込む"""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    
    # 同梱フォントを試す
    font_paths = [
        get_resource_path('Noto_Sans_JP/NotoSansJP-VariableFont_wght.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Regular.ttf'),
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font = pygame.font.Font(font_path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    
    # フォールバック: システムフォント
    font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", size, bold=bold)
    _font_cache[key] = font
    return font
```

---

### 7. 動的インポートの整理

**問題点**:
`sys.path` の動的操作や複数のインポートフォールバックがあり、PyInstaller がモジュールを検出できない可能性。

**影響箇所**:
- [CardGame.py](c.c.b/CardGame.py#L84-L88) - sys.path 操作
- [CardGame.py](c.c.b/CardGame.py#L129) - sys.path 操作
- [deck_modals.py](c.c.b/ui/modals/deck_modals.py#L956) - sys.path 操作

**修正方法**:
- spec ファイルの `hiddenimports` に必要なモジュールを明示的に追加（上記 spec ファイル参照）
- 可能であれば、インポート構造を整理して一貫性を持たせる

---

## 🟢 優先度：低（任意）

### 8. アイコンファイルの作成

**問題点**:
exe ファイルにアイコンが設定されていない。

**修正方法**:
- `.ico` 形式のアイコンファイルを作成
- spec ファイルの `icon=` パラメータに指定

---

### 9. バージョン情報の埋め込み

**問題点**:
exe ファイルにバージョン情報がない。

**修正方法**:
PyInstaller の `--version-file` オプションを使用してバージョン情報を埋め込む。

---

## 📁 修正対象ファイル一覧

### 新規作成
| ファイル | 説明 |
|----------|------|
| `c.c.b/utils/path_resolver.py` | パス解決ユーティリティ |
| `c.c.b/utils/font_loader.py` | フォント読み込みユーティリティ |
| `chess_card_battle.spec` | PyInstaller spec ファイル |
| `requirements.txt` | 依存パッケージ定義 |

### 修正が必要
| ファイル | 修正内容 |
|----------|----------|
| `c.c.b/assets/image_loader.py` | path_resolver を使用 |
| `c.c.b/audio/bgm_manager.py` | path_resolver を使用 |
| `c.c.b/game/deck_manager.py` | path_resolver を使用、書き込みパス変更 |
| `c.c.b/CardGame.py` | path_resolver, font_loader を使用、ハードコードパス削除 |
| `c.c.b/ui/modals/screen_modals.py` | ハードコードパス削除 |
| `c.c.b/ui/modals/deck_modals.py` | ハードコードパス削除 |

---

## 🚀 ビルド手順

修正完了後、以下の手順で exe を作成できます。

```bash
# 1. PyInstaller をインストール
pip install pyinstaller

# 2. spec ファイルを使用してビルド
cd c:\Users\Student\Desktop\chess-card-battle\chess-card-battle-1
pyinstaller chess_card_battle.spec

# 3. dist/ChessCardBattle.exe が生成される
```

---

## ⚠️ 注意事項

1. **初回ビルド時のテスト**
   - exe 起動時にリソースが正しく読み込まれるか確認
   - BGM が再生されるか確認
   - デッキ保存/読み込みが正常に動作するか確認
   - 日本語が正しく表示されるか確認

2. **ファイルサイズ**
   - 画像、BGM、フォントを同梱するため、exe サイズは 50-100MB 程度になる可能性あり
   - UPX 圧縮で多少削減可能

3. **アンチウイルスソフト / Windows Defender SmartScreen**
   - PyInstaller で作成した exe はアンチウイルスソフトに誤検知される場合あり
   - 署名付き証明書での署名を検討

---

## 🛡️ 配布時の注意事項（SmartScreen 警告対応）

### 問題
PyInstaller で作成した exe ファイルはデジタル署名がないため、別の PC で実行しようとすると **Windows Defender SmartScreen** が起動をブロックします。

> 「Windows によって PC が保護されました」
> 「Microsoft Defender SmartScreen は認識されないアプリの起動を停止しました」

### 解決方法

#### 方法1: 実行時に許可する（ユーザー側の対応）

1. 警告画面で **「詳細情報」** をクリック
2. 表示される **「実行」** ボタンをクリック

※ これで exe を実行できます。初回のみ必要な操作です。

#### 方法2: 事前に Windows Defender の除外設定（組織内配布向け）

配布先 PC で事前に設定：
1. Windows セキュリティを開く
2. 「ウイルスと脅威の防止」→「設定の管理」
3. 「除外の追加」→「ファイル」→ `ChessCardBattle.exe` を選択

#### 方法3: コード署名証明書を取得（推奨だが有料）

デジタル署名を付けることで SmartScreen 警告を回避：
- **費用**: 年間 $100〜$500 程度
- **効果**: 警告が表示されなくなる
- **取得先**: DigiCert, Sectigo, GlobalSign 等

### 配布時に同梱する説明文（README に記載推奨）

```markdown
## ⚠️ 初回起動時の注意

Windows Defender SmartScreen が警告を表示する場合があります。
これは署名されていないプログラムに対する標準的な警告であり、
ウイルスではありません。

### 実行方法
1. 「Windows によって PC が保護されました」画面で「詳細情報」をクリック
2. 「実行」ボタンをクリック

※ 2回目以降は警告なしで起動できます。
```

---

## 📅 作業スケジュール（推奨）

1. **Phase 1**: path_resolver.py 作成 + 各モジュールへの適用
2. **Phase 2**: spec ファイル作成 + 初回ビルドテスト
3. **Phase 3**: font_loader.py 作成 + フォント読み込み統一
4. **Phase 4**: ハードコードパス削除 + 最終テスト

---

**作成日**: 2026年1月7日  
**対象プロジェクト**: Chess-Card-Battle
