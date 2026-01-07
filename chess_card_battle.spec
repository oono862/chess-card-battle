# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Chess-Card-Battle.
# Build command:
#     cd <project_root>
#     pyinstaller chess_card_battle.spec
# Output: dist/ChessCardBattle.exe

import os

block_cipher = None

# プロジェクトルートディレクトリ
project_root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    # エントリーポイント
    [os.path.join(project_root, 'c.c.b', 'CardGame.py')],
    
    # パス設定
    pathex=[
        project_root,
        os.path.join(project_root, 'c.c.b'),
    ],
    
    # バイナリファイル（DLLなど）
    binaries=[],
    
    # データファイル（画像、音楽、フォントなど）
    # 形式: (source, destination_folder)
    datas=[
        (os.path.join(project_root, 'images'), 'images'),
        (os.path.join(project_root, 'mugic'), 'mugic'),
        (os.path.join(project_root, 'Noto_Sans_JP'), 'Noto_Sans_JP'),
    ],
    
    # PyInstallerが自動検出できないインポート
    # Note: c.c.bディレクトリ内のモジュールは pathex に含まれているので
    # ドットなしの名前で指定
    hiddenimports=[
        # pygame関連
        'pygame',
        'pygame.mixer',
        'pygame.font',
        'pygame.image',
        'pygame.transform',
        
        # Pillow (GIFアニメーション用)
        'PIL',
        'PIL.Image',
        'PIL.GifImagePlugin',
        
        # プロジェクトモジュール（c.c.bディレクトリ内）
        'card_core',
        'chess_engine',
        'gimmick',
        'piece',
        'mode_select',
        'connection',
        'AI',
        
        # assets
        'assets',
        'assets.image_loader',
        'assets.animation',
        
        # audio
        'audio',
        'audio.bgm_manager',
        
        # game
        'game',
        'game.deck_manager',
        'game.state',
        'game.turn_manager',
        'game.loop_manager',
        
        # ui
        'ui',
        'ui.board_renderer',
        'ui.card_renderer',
        'ui.overlay',
        'ui.panel_renderer',
        'ui.renderer',
        'ui.config',
        'ui.layout',
        'ui.window',
        'ui.modals',
        'ui.modals.deck_modals',
        'ui.modals.screen_modals',
        
        # ai
        'ai',
        'ai.ai_logic',
        'ai.config',
        
        # utils
        'utils',
        'utils.path_resolver',
        'utils.font_loader',
        'utils.helpers',
        'utils.drawing',
        
        # debug
        'debug',
        'debug.debug_tools',
        
        # input
        'input',
        'input.keyboard_handler',
        'input.mouse_handler',
        
        # chess
        'chess',
        'chess.rules',
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
