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
                 fixed_deck: List[str] = None,
                 card_name_hints: List[str] = None,
                 restrict_piece_selection: bool = False,
                 restrict_tile_selection: bool = False,
                 lock_ui: bool = False):
        """
        Args:
            step_id: ステップ番号
            message: 表示するメッセージ
            allowed_actions: 許可される操作 {'select_piece', 'move_piece', 'use_card', 'end_turn', 'select_tile'}
            highlight_tiles: ハイライトするマス [(row, col), ...]
            highlight_pieces: ハイライトする駒 [(row, col), ...]
            highlight_cards: ハイライトするカードインデックス [0, 1, ...]
            fixed_deck: 固定デッキ（カード名リスト）
            card_name_hints: ハイライトしたいカード名（部分一致可）
            restrict_piece_selection: ハイライトされた駒のみ選択可にするか
            restrict_tile_selection: ハイライトされたマスのみ選択可にするか
            lock_ui: UIをロックするか（開始前や完了画面）
        """
        self.step_id = step_id
        self.message = message
        normalized_actions = set()
        for a in allowed_actions:
            if a in ('use_card', 'card', 'play_card'):
                normalized_actions.add('play_card')
            elif a in ('select_piece', 'target_piece'):
                normalized_actions.add('select_piece')
            elif a in ('select_tile', 'target_tile'):
                normalized_actions.add('select_tile')
            else:
                normalized_actions.add(a)
        self.allowed_actions = normalized_actions
        self.highlight_tiles = highlight_tiles or []
        self.highlight_pieces = highlight_pieces or []
        self.highlight_cards = highlight_cards or []
        self.fixed_deck = fixed_deck or []
        self.card_name_hints = card_name_hints or []
        self.restrict_piece_selection = restrict_piece_selection
        self.restrict_tile_selection = restrict_tile_selection
        self.lock_ui = lock_ui


class TutorialManager:
    """チュートリアル進行を管理"""
    
    def __init__(self):
        self.enabled = False
        self.current_step = 0
        self.tutorial_step = 0  # 公開用の進行カウンタ
        self.steps = self._create_tutorial_steps()
        self.completed = False
        self.waiting_for_start = True
        self.start_button_rect = None
        self._awaiting_event: Optional[str] = None
        
    def _create_tutorial_steps(self) -> List[TutorialStep]:
        """チュートリアルステップを定義
        
        5ターンで基本操作とカード連携を学ぶ進行
        """
        return [
            # ステップ0: 開始説明（開始ボタンのみ有効）
            TutorialStep(
                step_id=0,
                message=(
                    "ようこそ Chess-Card-Battle へ\n"
                    "このチュートリアルでは\n"
                    "・駒の動かし方\n"
                    "・カードの使い方\n"
                    "を体験します\n"
                    "[開始] を押して進めましょう"
                ),
                allowed_actions=set(),
                lock_ui=True,
                fixed_deck=[
                    '2ドロー', '氷結', '灼熱', 'Quick Draw',
                    'Quick Draw', 'Meditate', 'Tactical Surge',
                    'Meditate', 'Quick Draw'
                ]
            ),
            
            # ステップ1: 駒を動かす
            TutorialStep(
                step_id=1,
                message="まずは駒を動かしてみましょう。光っているポーンを1マス前進。",
                allowed_actions={'select_piece', 'move_piece'},
                highlight_pieces=[(6, 4)],  # e2のポーン
                highlight_tiles=[(5, 4)],  # e3
                restrict_piece_selection=True
            ),
            
            # ステップ2: カードを使う（2ドロー）
            TutorialStep(
                step_id=2,
                message="次はカードを使います。『2ドロー』を使ってみましょう。",
                allowed_actions={'use_card'},
                card_name_hints=['2ドロー']
            ),
            
            # ステップ3: 氷結で状態異常
            TutorialStep(
                step_id=3,
                message="このカードは相手の駒を止めます。氷結したい駒を選んでください。",
                allowed_actions={'use_card', 'select_piece'},
                highlight_pieces=[(0, 6)],  # g8のナイトを例に
                card_name_hints=['氷結'],
                restrict_piece_selection=True
            ),
            
            # ステップ4: 灼熱で封鎖
            TutorialStep(
                step_id=4,
                message="マスを封鎖して相手の逃げ道を塞ぎましょう。指定の3マスを封鎖。",
                allowed_actions={'use_card', 'select_tile', 'end_turn'},
                highlight_tiles=[(3, 3), (3, 4), (3, 5)],
                card_name_hints=['灼熱'],
                restrict_tile_selection=True
            ),

            # ステップ5: チェックと詰みの確認
            TutorialStep(
                step_id=5,
                message="逃げる・守る・取る、すべて不可能です。チェックメイト！",
                allowed_actions=set(),
                lock_ui=True
            ),
        ]
    
    def start(self):
        """チュートリアル開始"""
        self.enabled = True
        self.current_step = 0
        self.tutorial_step = 0
        self.completed = False
        self.waiting_for_start = True
        self.start_button_rect = None
        self._awaiting_event = None
        # 開始ボタン押下後に立てるフラグ（最初は無効のまま）
        self._should_auto_start_turn = False

    def begin_after_intro(self):
        """開始ボタン押下時に進行を開始"""
        if not self.enabled:
            return
        self.waiting_for_start = False
        self.start_button_rect = None
        # ステップ0→1へ進行
        if self.current_step == 0:
            self.advance_step()
        # ターン自動開始を有効化
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
        self.tutorial_step = self.current_step
        if self.current_step >= len(self.steps):
            self.completed = True
            self.enabled = False
    
    def _normalize_action(self, action: str) -> str:
        if action in ('use_card', 'card', 'play_card'):
            return 'play_card'
        if action in ('select_piece', 'target_piece'):
            return 'select_piece'
        if action in ('select_tile', 'target_tile'):
            return 'select_tile'
        return action

    def is_action_allowed(self, action: str) -> bool:
        """指定された操作が現在のステップで許可されているか
        
        Args:
            action: 操作名 ('move_piece', 'play_card', 'end_turn')
        
        Returns:
            bool: 許可されていればTrue
        """
        if not self.enabled:
            return True  # チュートリアル無効時は全て許可

        # 開始前は開始ボタンのみ有効
        if self.waiting_for_start:
            return self._normalize_action(action) == 'start_tutorial'
        
        step = self.get_current_step()
        if step is None:
            return True
        
        return self._normalize_action(action) in step.allowed_actions

    def is_piece_selection_allowed(self, pos: Tuple[int, int]) -> bool:
        step = self.get_current_step()
        if step is None:
            return True
        if not step.restrict_piece_selection:
            return True
        return pos in step.highlight_pieces

    def is_tile_selection_allowed(self, pos: Tuple[int, int]) -> bool:
        step = self.get_current_step()
        if step is None:
            return True
        if not step.restrict_tile_selection:
            return True
        return pos in step.highlight_tiles
    
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

    def get_card_name_hints(self) -> List[str]:
        step = self.get_current_step()
        if step is None:
            return []
        return step.card_name_hints
    
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
        if step and 'play_card' in {self._normalize_action(a) for a in step.allowed_actions}:
            # ステップごとに完了条件を分ける
            if step.step_id == 2:
                self.advance_step()
            elif step.step_id == 3:
                self._awaiting_event = 'freeze'
            elif step.step_id == 4:
                self._awaiting_event = 'heat'
    
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
        self.tutorial_step = len(self.steps)
        self.waiting_for_start = False
        self._awaiting_event = None

    def on_effect_resolved(self, event: str):
        """カード効果の解決完了を通知"""
        if not self.enabled:
            return
        step = self.get_current_step()
        if step is None:
            return
        if self._awaiting_event and event == self._awaiting_event:
            self._awaiting_event = None
            self.advance_step()

    def set_start_button_rect(self, rect):
        self.start_button_rect = rect
