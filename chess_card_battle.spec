# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Chess-Card-Battle.

Build command:
    cd c:\Users\Student\Desktop\chess-card-battle\chess-card-battle-1
    pyinstaller chess_card_battle.spec

Output:
    dist/ChessCardBattle.exe
"""

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
    hiddenimports=[
        # pygame関連
        'pygame',
        'pygame.mixer',
        'pygame.font',
        'pygame.image',
        'pygame.transform',
        
        # プロジェクトモジュール - c.c.bパッケージ
        'c.c.b',
        'c.c.b.card_core',
        'c.c.b.chess_engine',
        'c.c.b.gimmick',
        'c.c.b.piece',
        
        # assets
        'c.c.b.assets',
        'c.c.b.assets.image_loader',
        'c.c.b.assets.animation',
        
        # audio
        'c.c.b.audio',
        'c.c.b.audio.bgm_manager',
        
        # game
        'c.c.b.game',
        'c.c.b.game.deck_manager',
        'c.c.b.game.state',
        'c.c.b.game.turn_manager',
        'c.c.b.game.loop_manager',
        
        # ui
        'c.c.b.ui',
        'c.c.b.ui.board_renderer',
        'c.c.b.ui.card_renderer',
        'c.c.b.ui.overlay',
        'c.c.b.ui.panel_renderer',
        'c.c.b.ui.renderer',
        'c.c.b.ui.config',
        'c.c.b.ui.layout',
        'c.c.b.ui.window',
        'c.c.b.ui.modals',
        'c.c.b.ui.modals.deck_modals',
        'c.c.b.ui.modals.screen_modals',
        
        # ai
        'c.c.b.ai',
        'c.c.b.ai.ai_logic',
        'c.c.b.ai.config',
        
        # utils
        'c.c.b.utils',
        'c.c.b.utils.path_resolver',
        'c.c.b.utils.font_loader',
        'c.c.b.utils.helpers',
        'c.c.b.utils.drawing',
        
        # debug
        'c.c.b.debug',
        'c.c.b.debug.debug_tools',
        
        # input
        'c.c.b.input',
        'c.c.b.input.keyboard_handler',
        'c.c.b.input.mouse_handler',
        
        # chess
        'c.c.b.chess',
        'c.c.b.chess.rules',
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
