"""チュートリアルシステム v2

5ターン構成の新しいチュートリアルを提供します。
- Turn 1: 駒を動かす
- Turn 2: カードを使う（2ドロー）
- Turn 3: 状態異常（氷結）
- Turn 4: 灼熱（封鎖）
- Turn 5: チェックと詰み
"""

import pygame
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum, auto


class TutorialPhase(Enum):
    """チュートリアルのフェーズ"""
    WELCOME = auto()       # 開始前画面
    TURN1_MOVE = auto()    # ターン1: 駒を動かす
    TURN2_DRAW = auto()    # ターン2: カードを使う（2ドロー）
    TURN3_FREEZE = auto()  # ターン3: 氷結
    TURN4_HEAT = auto()    # ターン4: 灼熱（封鎖）
    TURN5_CHECKMATE = auto()  # ターン5: チェックメイト
    COMPLETE = auto()      # 完了


class TutorialState:
    """チュートリアルの状態を管理"""
    
    def __init__(self):
        self.phase = TutorialPhase.WELCOME
        self.enabled = False
        self.completed = False
        self.waiting_for_action = False
        
        # UI用の矩形
        self.start_button_rect: Optional[pygame.Rect] = None
        self.cpu_button_rect: Optional[pygame.Rect] = None
        self.retry_button_rect: Optional[pygame.Rect] = None
        
        # 各フェーズでの進行状態
        self.piece_selected = False
        self.piece_moved = False
        self.card_used = False
        self.target_selected = False
        self.tiles_selected: List[Tuple[int, int]] = []
        
        # アクション待機
        self.awaiting_card_effect = False
        self.awaiting_effect_type: Optional[str] = None
        
        # 動的カードハイライト（カードインデックス）
        self.highlight_card_indices: List[int] = []


class TutorialManager:
    """チュートリアル進行を管理するメインクラス"""
    
    # 各フェーズの設定
    PHASE_CONFIG = {
        TutorialPhase.WELCOME: {
            'message': (
                "ようこそ Chess-Card-Battle へ\n\n"
                "このチュートリアルでは\n"
                "・駒の動かし方\n"
                "・カードの使い方\n"
                "を実際に体験します"
            ),
            'show_start_button': True,
            'lock_ui': True,
        },
        TutorialPhase.TURN1_MOVE: {
            'message': (
                "【Turn 1】まずは駒を動かしてみましょう\n\n"
                "光っているポーンを選択してください"
            ),
            'highlight_pieces': [(6, 4)],  # e2のポーン
            'highlight_tiles': [(5, 4), (4, 4)],  # e3, e4
            'allowed_actions': ['select_piece', 'move_piece'],
            'restrict_piece': True,
        },
        TutorialPhase.TURN2_DRAW: {
            'message': (
                "駒操作完了です！\n\n"
                "【Turn 2】次はカードを使います\n\n"
                "「2ドロー」を使ってみましょう\n"
                "（青い枠のカードをクリック）"
            ),
            'highlight_cards': ['2ドロー'],
            'allowed_actions': ['play_card'],
        },
        TutorialPhase.TURN3_FREEZE: {
            'message': (
                "良いカードが出てきましたか？\n\n"
                "【Turn 3】このカードは相手の駒を止めます\n\n"
                "「氷結」を使い、光っている敵の駒を\n"
                "選んでください"
            ),
            'highlight_pieces': [(0, 6)],  # g8のナイト
            'highlight_cards': ['氷結'],
            'allowed_actions': ['play_card', 'select_piece'],
        },
        TutorialPhase.TURN4_HEAT: {
            'message': (
                "妨害成功です！\n\n"
                "【Turn 4】マスを封鎖すると\n"
                "相手の逃げ道を塞ぐことができます\n\n"
                "「灼熱」を使い、光っている3マスを\n"
                "クリックしてください"
            ),
            'highlight_tiles': [(3, 3), (3, 4), (3, 5)],  # d5, e5, f5
            'highlight_cards': ['灼熱'],
            'allowed_actions': ['play_card', 'select_tile'],
        },
        TutorialPhase.TURN5_CHECKMATE: {
            'message': (
                "お疲れ様でした！それでは最後です！\n\n"
                "【Turn 5】チェックメイト！\n\n"
                "逃げる・守る・取る\n"
                "すべて不可能な状態です\n\n"
                "カードを駆使して相手を追い詰める\n"
                "これが Chess-Card-Battle の醍醐味です！"
            ),
            'lock_ui': True,
            'auto_advance': True,
        },
        TutorialPhase.COMPLETE: {
            'message': (
                "チュートリアル完了！\n\n"
                "次は実戦で遊んでみましょう"
            ),
            'show_complete_buttons': True,
            'lock_ui': True,
        },
    }
    
    def __init__(self):
        self.state = TutorialState()
        self._board_setup = None
        self._should_auto_start_turn = False
        self._should_auto_end_turn = False
        
    @property
    def enabled(self) -> bool:
        return self.state.enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self.state.enabled = value
        
    @property
    def completed(self) -> bool:
        return self.state.completed
    
    @property
    def current_step(self) -> int:
        """現在のステップ番号を返す（互換性用）"""
        return list(TutorialPhase).index(self.state.phase)
    
    @property
    def waiting_for_start(self) -> bool:
        return self.state.phase == TutorialPhase.WELCOME and self.state.enabled
    
    @property
    def start_button_rect(self):
        return self.state.start_button_rect
    
    @start_button_rect.setter
    def start_button_rect(self, value):
        self.state.start_button_rect = value
        
    @property
    def completion_cpu_rect(self):
        return self.state.cpu_button_rect
    
    @completion_cpu_rect.setter
    def completion_cpu_rect(self, value):
        self.state.cpu_button_rect = value
        
    @property
    def completion_retry_rect(self):
        return self.state.retry_button_rect
    
    @completion_retry_rect.setter
    def completion_retry_rect(self, value):
        self.state.retry_button_rect = value
        
    def start(self):
        """チュートリアルを開始"""
        self.state = TutorialState()
        self.state.enabled = True
        self.state.phase = TutorialPhase.WELCOME
        self.state.completed = False
        
    def skip(self):
        """チュートリアルをスキップ"""
        self.state.enabled = False
        self.state.completed = True
        self.state.phase = TutorialPhase.COMPLETE
        
    def begin_after_intro(self):
        """開始ボタン押下後、Turn 1へ進む"""
        if self.state.phase == TutorialPhase.WELCOME:
            self._advance_to_phase(TutorialPhase.TURN1_MOVE)
            
    def get_current_step(self):
        """互換性のため: 現在のステップ情報を返す"""
        return self._get_step_wrapper()
    
    def get_message(self) -> str:
        """現在のメッセージを取得"""
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        return config.get('message', '')
    
    def get_highlight_info(self) -> Dict[str, List]:
        """ハイライト情報を取得"""
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        return {
            'tiles': config.get('highlight_tiles', []),
            'pieces': config.get('highlight_pieces', []),
            'cards': self.state.highlight_card_indices,
        }
    
    def set_highlight_card_indices(self, indices: List[int]):
        """ハイライトするカードインデックスを設定"""
        self.state.highlight_card_indices = indices
    
    def get_card_name_hints(self) -> List[str]:
        """ハイライトするカード名を取得"""
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        return config.get('highlight_cards', [])
    
    def is_action_allowed(self, action: str) -> bool:
        """指定されたアクションが許可されているか"""
        if not self.state.enabled:
            return True
            
        if self.state.phase == TutorialPhase.WELCOME:
            return False
            
        if self.state.phase == TutorialPhase.COMPLETE:
            return False
            
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        
        if config.get('lock_ui'):
            return False
            
        allowed = config.get('allowed_actions', [])
        
        # アクション名を正規化
        normalized = self._normalize_action(action)
        
        return normalized in allowed or action in allowed
    
    def _normalize_action(self, action: str) -> str:
        """アクション名を正規化"""
        if action in ('use_card', 'card', 'play_card'):
            return 'play_card'
        if action in ('select_piece', 'target_piece'):
            return 'select_piece'
        if action in ('select_tile', 'target_tile'):
            return 'select_tile'
        return action
    
    def is_piece_selection_allowed(self, pos: Tuple[int, int]) -> bool:
        """駒の選択が許可されているか"""
        if not self.state.enabled:
            return True
            
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        
        if not config.get('restrict_piece'):
            return True
            
        highlight_pieces = config.get('highlight_pieces', [])
        return pos in highlight_pieces
    
    def is_tile_selection_allowed(self, pos: Tuple[int, int]) -> bool:
        """タイルの選択が許可されているか"""
        if not self.state.enabled:
            return True
            
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        highlight_tiles = config.get('highlight_tiles', [])
        
        if not highlight_tiles:
            return True
            
        return pos in highlight_tiles
    
    def is_card_allowed(self, card_name: str) -> bool:
        """指定されたカードの使用が許可されているか"""
        if not self.state.enabled:
            return True
            
        if self.state.phase == TutorialPhase.WELCOME:
            return False
            
        if self.state.phase == TutorialPhase.COMPLETE:
            return False
        
        if self.state.phase == TutorialPhase.TURN5_CHECKMATE:
            return False
            
        # カード使用が許可されているフェーズかチェック
        config = self.PHASE_CONFIG.get(self.state.phase, {})
        allowed_actions = config.get('allowed_actions', [])
        
        if 'play_card' not in allowed_actions:
            return False
            
        # highlight_cardsを取得（カード名のヒント）
        hints = config.get('highlight_cards', [])
        if not hints:
            # ヒントがない場合はカード使用不可
            return False
            
        # ヒントに含まれるカードのみ許可
        for hint in hints:
            if hint in card_name:
                return True
                
        return False
    
    def on_piece_moved(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]):
        """駒移動時のコールバック"""
        if not self.state.enabled:
            return
            
        if self.state.phase == TutorialPhase.TURN1_MOVE:
            config = self.PHASE_CONFIG[self.state.phase]
            highlight_pieces = config.get('highlight_pieces', [])
            highlight_tiles = config.get('highlight_tiles', [])
            
            # 正しい駒が正しいマスに移動した
            if from_pos in highlight_pieces and to_pos in highlight_tiles:
                self._advance_to_phase(TutorialPhase.TURN2_DRAW)
    
    def on_card_played(self, card_index: int, card_name: str = ''):
        """カード使用時のコールバック"""
        if not self.state.enabled:
            return
            
        if self.state.phase == TutorialPhase.TURN2_DRAW:
            # 2ドローは即座に効果発動
            if '2ドロー' in card_name or 'ドロー' in card_name:
                self._advance_to_phase(TutorialPhase.TURN3_FREEZE)
                
        elif self.state.phase == TutorialPhase.TURN3_FREEZE:
            # 氷結はターゲット選択後
            if '氷結' in card_name:
                self.state.awaiting_card_effect = True
                self.state.awaiting_effect_type = 'freeze'
                
        elif self.state.phase == TutorialPhase.TURN4_HEAT:
            # 灼熱はタイル選択後
            if '灼熱' in card_name:
                self.state.awaiting_card_effect = True
                self.state.awaiting_effect_type = 'heat'
    
    def on_effect_resolved(self, effect_type: str):
        """カード効果解決時のコールバック"""
        if not self.state.enabled:
            return
            
        if not self.state.awaiting_card_effect:
            return
            
        if self.state.phase == TutorialPhase.TURN3_FREEZE and effect_type == 'freeze':
            self.state.awaiting_card_effect = False
            self._advance_to_phase(TutorialPhase.TURN4_HEAT)
            
        elif self.state.phase == TutorialPhase.TURN4_HEAT and effect_type == 'heat':
            self.state.awaiting_card_effect = False
            self._advance_to_phase(TutorialPhase.TURN5_CHECKMATE)
    
    def on_turn_ended(self):
        """ターン終了時のコールバック"""
        pass  # 新しいチュートリアルではターン終了で自動進行しない
    
    def _advance_to_phase(self, phase: TutorialPhase):
        """指定フェーズへ進む"""
        self.state.phase = phase
        self.state.piece_selected = False
        self.state.piece_moved = False
        self.state.card_used = False
        self.state.target_selected = False
        self.state.tiles_selected = []
        self.state.awaiting_card_effect = False
        self.state.awaiting_effect_type = None
        
        # 自動ターン開始フラグ（Turn 2以降で使用）
        if phase in (TutorialPhase.TURN2_DRAW, TutorialPhase.TURN3_FREEZE, 
                     TutorialPhase.TURN4_HEAT, TutorialPhase.TURN5_CHECKMATE):
            self._should_auto_start_turn = True
        else:
            self._should_auto_start_turn = False
        
        # Turn 5は自動的に完了へ進む（表示後）
        if phase == TutorialPhase.TURN5_CHECKMATE:
            # 短い遅延後に完了へ
            pass  # UIで処理
            
        if phase == TutorialPhase.COMPLETE:
            self.state.completed = True
    
    def advance_to_complete(self):
        """完了画面へ進む（外部から呼び出し用）"""
        self._advance_to_phase(TutorialPhase.COMPLETE)
    
    def set_start_button_rect(self, rect):
        """開始ボタンの矩形を設定"""
        self.state.start_button_rect = rect
    
    def _get_step_wrapper(self):
        """互換性のためのステップラッパー"""
        class StepWrapper:
            def __init__(self, manager):
                self._manager = manager
                config = manager.PHASE_CONFIG.get(manager.state.phase, {})
                self.step_id = list(TutorialPhase).index(manager.state.phase)
                self.message = config.get('message', '')
                self.lock_ui = config.get('lock_ui', False)
                self.highlight_tiles = config.get('highlight_tiles', [])
                self.highlight_pieces = config.get('highlight_pieces', [])
                self.highlight_cards = manager.state.highlight_card_indices
                self.allowed_actions = set(config.get('allowed_actions', []))
                
        return StepWrapper(self)
    
    def get_fixed_deck(self) -> List[str]:
        """チュートリアル用の固定デッキを返す"""
        return [
            '2ドロー',
            '氷結', 
            '灼熱',
            '錬成',
            '暴風',
            '迅雷',
            '墓地ルーレット',
            '摂取',
            '2ドロー',
        ]


def get_tutorial_board_setup() -> Dict[str, Any]:
    """チュートリアル用の盤面設定を返す
    
    シンプルな盤面で詰みの概念を教える
    """
    # 標準の初期配置を使用
    # （必要に応じてカスタム配置に変更可能）
    return {
        'use_standard': True,
    }
