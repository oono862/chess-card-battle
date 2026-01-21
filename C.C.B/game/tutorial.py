"""チュートリアルシステム

最小構成でチュートリアルを実装します:
- tutorial_step で進行管理
- allowed_actions で操作制限
- highlight 情報で UI ガイド
- 固定カード順で 3〜5 ターンで完了
"""

from typing import List, Tuple, Optional, Set


class TutorialStep:
    """チュートリアルの各ステップを定義"""
    
    def __init__(self, step_id: int, message: str, 
                 allowed_actions: Set[str],
                 highlight_tiles: List[Tuple[int, int]] = None,
                 highlight_pieces: List[Tuple[int, int]] = None,
                 highlight_cards: List[int] = None,
                 fixed_deck: List[str] = None):
        """
        Args:
            step_id: ステップ番号
            message: 表示するメッセージ
            allowed_actions: 許可される操作 {'move_piece', 'play_card', 'end_turn'}
            highlight_tiles: ハイライトするマス [(row, col), ...]
            highlight_pieces: ハイライトする駒 [(row, col), ...]
            highlight_cards: ハイライトするカードインデックス [0, 1, ...]
            fixed_deck: 固定デッキ（カード名リスト）
        """
        self.step_id = step_id
        self.message = message
        self.allowed_actions = allowed_actions
        self.highlight_tiles = highlight_tiles or []
        self.highlight_pieces = highlight_pieces or []
        self.highlight_cards = highlight_cards or []
        self.fixed_deck = fixed_deck or []


class TutorialManager:
    """チュートリアル進行を管理"""
    
    def __init__(self):
        self.enabled = False
        self.current_step = 0
        self.steps = self._create_tutorial_steps()
        self.completed = False
        
    def _create_tutorial_steps(self) -> List[TutorialStep]:
        """チュートリアルステップを定義
        
        3〜5ターンで基本操作を学べる最小構成
        """
        return [
            # ステップ0: 開始説明
            TutorialStep(
                step_id=0,
                message="チェスカードバトルへようこそ！まずはポーンを動かしてみましょう",
                allowed_actions={'move_piece'},
                highlight_pieces=[(6, 4)],  # e2のポーン
                highlight_tiles=[(5, 4), (4, 4)],  # e3, e4
                fixed_deck=['draw', 'attack', 'shield', 'move_boost', 'heal']
            ),
            
            # ステップ1: カードプレイ
            TutorialStep(
                step_id=1,
                message="良いですね！次はカードを使ってみましょう。「引く」カードを使用してください",
                allowed_actions={'play_card'},
                highlight_cards=[0],  # 最初のカード（draw）
                fixed_deck=['draw', 'attack', 'shield', 'move_boost', 'heal']
            ),
            
            # ステップ2: PP管理とターン終了
            TutorialStep(
                step_id=2,
                message="カードを使うとPPを消費します。PPが足りない時はこのターンを終了し、次のターンでPPを回復しましょう",
                allowed_actions={'end_turn'},
                fixed_deck=['draw', 'attack', 'shield', 'move_boost', 'heal']
            ),
            
            # ステップ3: 駒とカードの組み合わせ
            TutorialStep(
                step_id=3,
                message="ターンが進むとPPが回復します。駒を動かしてカードを使う、この流れが基本です",
                allowed_actions={'move_piece', 'play_card', 'end_turn'},
                highlight_pieces=[(6, 3)],  # d2のポーン
                fixed_deck=['draw', 'attack', 'shield', 'move_boost', 'heal']
            ),
            
            # ステップ4: チュートリアル完了
            TutorialStep(
                step_id=4,
                message="完璧です！基本操作をマスターしました。実戦で試してみましょう！",
                allowed_actions={'move_piece', 'play_card', 'end_turn'},
                fixed_deck=['draw', 'attack', 'shield', 'move_boost', 'heal']
            ),
        ]
    
    def start(self):
        """チュートリアル開始"""
        self.enabled = True
        self.current_step = 0
        self.completed = False
        # チュートリアル開始時に自動ターン開始フラグを立てる
        self._should_auto_start_turn = True
    
    def get_current_step(self) -> Optional[TutorialStep]:
        """現在のステップを取得"""
        if not self.enabled or self.completed:
            return None
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def advance_step(self):
        """次のステップへ進む"""
        if not self.enabled:
            return
        
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.completed = True
            self.enabled = False
    
    def is_action_allowed(self, action: str) -> bool:
        """指定された操作が現在のステップで許可されているか
        
        Args:
            action: 操作名 ('move_piece', 'play_card', 'end_turn')
        
        Returns:
            bool: 許可されていればTrue
        """
        if not self.enabled:
            return True  # チュートリアル無効時は全て許可
        
        step = self.get_current_step()
        if step is None:
            return True
        
        return action in step.allowed_actions
    
    def get_highlight_info(self) -> dict:
        """現在のハイライト情報を取得
        
        Returns:
            dict: {
                'tiles': [(row, col), ...],
                'pieces': [(row, col), ...],
                'cards': [index, ...]
            }
        """
        step = self.get_current_step()
        if step is None:
            return {'tiles': [], 'pieces': [], 'cards': []}
        
        return {
            'tiles': step.highlight_tiles,
            'pieces': step.highlight_pieces,
            'cards': step.highlight_cards
        }
    
    def get_message(self) -> str:
        """現在のメッセージを取得"""
        step = self.get_current_step()
        if step is None:
            return ""
        return step.message
    
    def get_fixed_deck(self) -> List[str]:
        """現在のステップの固定デッキを取得"""
        step = self.get_current_step()
        if step is None:
            return []
        return step.fixed_deck
    
    def on_piece_moved(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]):
        """駒移動時のコールバック
        
        適切なステップで駒が動かされたら次へ進む
        """
        step = self.get_current_step()
        if step and 'move_piece' in step.allowed_actions:
            # ハイライトされた駒または目標タイルに移動した場合
            if (from_pos in step.highlight_pieces or 
                to_pos in step.highlight_tiles or
                not step.highlight_pieces):  # ハイライト指定なしなら任意の移動でOK
                self.advance_step()
    
    def on_card_played(self, card_index: int):
        """カード使用時のコールバック
        
        適切なステップでカードが使われたら次へ進む
        """
        step = self.get_current_step()
        if step and 'play_card' in step.allowed_actions:
            # ハイライトされたカードまたは任意のカードでOK
            if (card_index in step.highlight_cards or
                not step.highlight_cards):
                self.advance_step()
    
    def on_turn_ended(self):
        """ターン終了時のコールバック
        
        適切なステップでターンが終了したら次へ進む
        """
        step = self.get_current_step()
        if step and 'end_turn' in step.allowed_actions:
            self.advance_step()
    
    def skip(self):
        """チュートリアルをスキップ"""
        self.enabled = False
        self.completed = True
