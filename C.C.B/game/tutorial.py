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
        self._should_auto_start_turn = False  # 自動ターン開始フラグ
        self._should_auto_end_turn = False    # 自動ターン終了フラグ
        
    def _create_tutorial_steps(self) -> List[TutorialStep]:
        """チュートリアルステップを定義
        
        5ターンで基本操作とカード連携を学ぶ進行
        進行表に従い、Turn 1〜5を実装
        """
        return [
            # ステップ0: 開始説明（開始ボタンのみ有効）
            TutorialStep(
                step_id=0,
                message=(
                    "ようこそ Chess-Card-Battle へ\n\n"
                    "このチュートリアルでは\n"
                    "・駒の動かし方\n"
                    "・カードの使い方\n"
                    "を実際に体験します\n\n"
                    "[開始] を押して進めましょう"
                ),
                allowed_actions=set(),
                lock_ui=True,
                fixed_deck=[
                    '2ドロー', '氷結', '灼熱', '錬成',
                    '暴風', '迅雷', '墓地ルーレット',
                    '摂取', '2ドロー'
                ]
            ),
            
            # ステップ1 (Turn 1): 駒を動かす
            # 駒はポーン1体のみ操作可能、カード使用不可
            TutorialStep(
                step_id=1,
                message="【Turn 1】まずは駒を動かしてみましょう。\n\n光っているポーンをクリックして、\n前のマス（黄色い枠）へ移動させてください。",
                allowed_actions={'select_piece', 'move_piece'},
                highlight_pieces=[(6, 4)],  # e2のポーン
                highlight_tiles=[(5, 4), (4, 4)],  # e3またはe4
                restrict_piece_selection=True
            ),
            
            # ステップ2 (Turn 2): カードを使う（2ドロー）
            # 手札：2ドロー、PP：3、駒は移動不可（カードのみ）
            TutorialStep(
                step_id=2,
                message="【Turn 2】次はカードを使います。\n\n『2ドロー』カード（青い枠）を\nクリックまたは [1] キーで使用してください。\n\n（PPを1消費して、カードを2枚引きます）",
                allowed_actions={'use_card', 'play_card'},
                card_name_hints=['2ドロー']
            ),
            
            # ステップ3 (Turn 3): 氷結で状態異常
            # 手札：氷結、敵駒1体が強調表示
            TutorialStep(
                step_id=3,
                message="【Turn 3】『氷結』で相手の駒を凍らせましょう。\n\n1. まず『氷結』カード（青い枠）を使用\n2. 次に光っている敵のナイトをクリック\n（2ターン行動不能になります）",
                allowed_actions={'play_card', 'select_piece'},
                highlight_pieces=[(0, 6)],  # g8のナイト
                card_name_hints=['氷結'],
                restrict_piece_selection=False
            ),
            
            # ステップ4 (Turn 4): 灼熱で封鎖
            # 手札：灼熱、敵キングの逃げ道がハイライト
            TutorialStep(
                step_id=4,
                message="【Turn 4】マスを封鎖して相手の逃げ道を塞ぎましょう。\n\n1. まず『灼熱』カード（青い枠）を使用\n2. 光っている3マス（黄色い枠）をクリック\n（相手のみ通行不可になります）",
                allowed_actions={'play_card', 'select_tile'},
                highlight_tiles=[(3, 3), (3, 4), (3, 5)],  # d5, e5, f5
                card_name_hints=['灼熱'],
                restrict_tile_selection=False
            ),

            # ステップ5 (Turn 5): チェックと詰みの確認
            # チェックメイト演出
            TutorialStep(
                step_id=5,
                message=(
                    "【Turn 5】チェックメイト！\n\n"
                    "逃げる・守る・取る\n"
                    "すべて不可能な状態です。\n\n"
                    "カードを駆使して相手を追い詰める\n"
                    "これが Chess-Card-Battle の醍醐味です！\n\n"
                    "チュートリアル完了！\n"
                    "次は実戦で遊んでみましょう"
                ),
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
        self._should_auto_end_turn = False

    def begin_after_intro(self):
        """開始ボタン押下時に進行を開始"""
        if not self.enabled:
            return
        self.waiting_for_start = False
        self.start_button_rect = None
        # ステップ0→1へ進行
        if self.current_step == 0:
            import logging
            logging.debug("チュートリアル: ステップ0から1へ進行（開始ボタン押下）")
            # ステップ0→1は特別: ターンは既に開始されているものとして扱う
            # （バトル開始時に4枚ドロー済み、これがTurn 1）
            self.current_step = 1
            self.tutorial_step = 1
            self._awaiting_event = None
            print(f"[DEBUG] チュートリアル begin_after_intro: 0 → 1 へ進行（自動ターン開始なし）")
        # 最初のターンは既に開始済みとして扱うため、自動開始フラグは立てない
        # ターン1のドローは行わない（バトル開始時の4枚だけ）
        self._should_auto_start_turn = False
    
    def get_current_step(self) -> Optional[TutorialStep]:
        """現在のステップを取得"""
        # 完了時のみNoneを返す（完了画面表示のため）
        if self.completed:
            return None
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def advance_step(self):
        """次のステップへ進む"""
        import logging
        old_step = self.current_step
        self.current_step += 1
        self.tutorial_step = self.current_step
        # 待機イベントをクリア
        self._awaiting_event = None
        logging.debug(f"チュートリアル: ステップ {old_step} → {self.current_step} へ進行")
        print(f"[DEBUG] チュートリアル advance_step: {old_step} → {self.current_step}")
        
        if self.current_step >= len(self.steps):
            self.completed = True
            # enabledはTrueのままにして完了画面を表示
            logging.debug("チュートリアル: 全ステップ完了")
            print("[DEBUG] チュートリアル: 全ステップ完了")
        else:
            # 現在のターンを終了して、次のターンを開始するフラグを設定
            self._should_auto_end_turn = True
            # 次のステップでターンを自動開始する必要があるかチェック
            next_step = self.steps[self.current_step]
            # lock_ui でなければ自動ターン開始（ステップ1以降すべて）
            if not next_step.lock_ui:
                self._should_auto_start_turn = True
                logging.debug(f"チュートリアル: ステップ {self.current_step} で自動ターン開始フラグを設定")
                print(f"[DEBUG] チュートリアル: ステップ {self.current_step} で自動ターン開始フラグを設定, message={next_step.message[:30]}...")
    
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
        import logging
        logging.debug(f"チュートリアル on_piece_moved: from={from_pos}, to={to_pos}, enabled={self.enabled}, current_step={self.current_step}")
        print(f"[DEBUG] チュートリアル on_piece_moved: from={from_pos}, to={to_pos}, enabled={self.enabled}, current_step={self.current_step}")
        
        if not self.enabled:
            return
            
        step = self.get_current_step()
        if not step:
            logging.debug("チュートリアル on_piece_moved: step is None")
            print("[DEBUG] チュートリアル on_piece_moved: step is None")
            return
            
        if 'move_piece' not in step.allowed_actions:
            logging.debug(f"チュートリアル on_piece_moved: move_piece not in allowed_actions={step.allowed_actions}")
            print(f"[DEBUG] チュートリアル on_piece_moved: move_piece not in allowed_actions={step.allowed_actions}")
            return
            
        logging.debug(f"チュートリアル: 駒移動検知 from={from_pos} to={to_pos}, step_id={step.step_id}")
        print(f"[DEBUG] チュートリアル: 駒移動検知 from={from_pos} to={to_pos}, step_id={step.step_id}")
        
        # ステップ1: ハイライトされた駒(6,4)が目標タイル(5,4)または(4,4)に移動したか
        if step.step_id == 1:
            print(f"[DEBUG] highlight_pieces={step.highlight_pieces}, highlight_tiles={step.highlight_tiles}")
            if from_pos in step.highlight_pieces and to_pos in step.highlight_tiles:
                logging.debug("チュートリアル: 正しい駒移動、ステップ1→2へ進行")
                print("[DEBUG] チュートリアル: 正しい駒移動、ステップ1→2へ進行")
                self.advance_step()
            else:
                logging.debug(f"チュートリアル: 条件不一致")
                print(f"[DEBUG] チュートリアル: 条件不一致")
        else:
            # その他のステップ: ハイライト指定なしなら任意の移動でOK
            if not step.highlight_pieces or from_pos in step.highlight_pieces:
                self.advance_step()
    
    def on_card_played(self, card_index: int):
        """カード使用時のコールバック
        
        適切なステップでカードが使われたら次へ進む
        """
        if not self.enabled:
            return
        step = self.get_current_step()
        if step is None:
            return
        
        normalized_allowed = {self._normalize_action(a) for a in step.allowed_actions}
        if 'play_card' not in normalized_allowed:
            return
            
        import logging
        logging.debug(f"チュートリアル: カード使用検知 (step_id={step.step_id}, card_index={card_index})")
        
        # ステップごとに完了条件を分ける
        if step.step_id == 2:
            # 2ドローは即座に効果が発動するので即進行
            logging.debug("チュートリアル: 2ドロー使用、ステップ2→3へ進行")
            self.advance_step()
        elif step.step_id == 3:
            # 氷結は駒選択後に効果が発動するので待機
            logging.debug("チュートリアル: 氷結使用、効果解決待機")
            self._awaiting_event = 'freeze'
        elif step.step_id == 4:
            # 灼熱はタイル選択後に効果が発動するので待機
            logging.debug("チュートリアル: 灼熱使用、効果解決待機")
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
            import logging
            logging.debug(f"チュートリアル: イベント '{event}' 解決、ステップ {step.step_id} から進行")
            self._awaiting_event = None
            self.advance_step()
        else:
            import logging
            logging.debug(f"チュートリアル: イベント '{event}' 受信（待機中: {self._awaiting_event}）")

    def set_start_button_rect(self, rect):
        self.start_button_rect = rect
