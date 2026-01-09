"""AI カード戦略モジュール

このモジュールは、AIが戦略的にカードを使用するためのロジックを提供します。
難易度に応じて異なる戦略を適用し、盤面状況を分析してカードを選択します。

改良版v2: 
- チェック優先回避
- 迅雷・暴風警戒時の駒配置戦略
- 鉄壁・氷結の温存
- コンボ対処
"""

import random
from typing import List, Dict, Any, Optional, Tuple


# ゲーム進行フェーズの定義
class GamePhase:
    """ゲームの進行段階"""
    OPENING = 'opening'      # 序盤（ターン1-8）
    MIDGAME = 'midgame'      # 中盤（ターン9-20）
    ENDGAME = 'endgame'      # 終盤（ターン21以降）
    
    @staticmethod
    def get_phase(game) -> str:
        """現在のゲームフェーズを取得"""
        turn = getattr(game, 'turn_count', 1)
        total_pieces = 0
        try:
            for p in game.chess.pieces if hasattr(game, 'chess') else []:
                total_pieces += 1
        except:
            pass
        
        # 駒数が少なければ終盤
        if total_pieces <= 10:
            return GamePhase.ENDGAME
        
        if turn <= 8:
            return GamePhase.OPENING
        elif turn <= 20:
            return GamePhase.MIDGAME
        else:
            return GamePhase.ENDGAME


class OpponentAnalysis:
    """相手（プレイヤー）の状態分析"""
    
    def __init__(self, game):
        self.game = game
        self._analyze()
    
    def _analyze(self):
        """相手の状態を分析"""
        self.hand_count = 0
        self.recent_cards_used = []  # 最近使われたカード
        self.likely_has_lightning = False  # 迅雷を持っている可能性
        self.likely_has_storm = False  # 暴風を持っている可能性
        self.likely_has_freeze = False  # 氷結を持っている可能性
        self.combo_threat = False  # コンボの脅威
        self.aggressive_play = False  # 攻撃的なプレイスタイル
        
        try:
            # プレイヤーの手札数
            if hasattr(self.game, 'player') and hasattr(self.game.player, 'hand'):
                self.hand_count = len(self.game.player.hand.cards)
            
            # ログから最近使われたカードを分析
            if hasattr(self.game, 'log'):
                recent_logs = self.game.log[-20:] if len(self.game.log) > 20 else self.game.log
                for log_entry in recent_logs:
                    if 'プレイヤー' in str(log_entry) or 'Player' in str(log_entry):
                        for card_name in ['迅雷', '暴風', '氷結', '灼熱', '鉄壁', '2ドロー']:
                            if card_name in str(log_entry):
                                self.recent_cards_used.append(card_name)
            
            # 手札が多い場合、危険なカードを持っている可能性が高い
            if self.hand_count >= 3:
                self.likely_has_lightning = True
                self.likely_has_storm = True
            if self.hand_count >= 4:
                self.likely_has_freeze = True
            
            # 最近連続でカードを使用していたらコンボ脅威
            card_count_in_recent = len(self.recent_cards_used)
            if card_count_in_recent >= 2:
                self.combo_threat = True
            if card_count_in_recent >= 3:
                self.aggressive_play = True
                
        except Exception:
            pass
    
    def estimate_threat_level(self) -> int:
        """相手の脅威レベルを推定（0-100）"""
        threat = 0
        
        if self.likely_has_lightning:
            threat += 25
        if self.likely_has_storm:
            threat += 15
        if self.likely_has_freeze:
            threat += 20
        if self.combo_threat:
            threat += 20
        if self.aggressive_play:
            threat += 15
        
        # 手札数に応じた脅威
        threat += min(self.hand_count * 5, 25)
        
        return min(threat, 100)


class BoardAnalysis:
    """盤面分析クラス - 現在のゲーム状態を評価"""
    
    PIECE_VALUES = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 100}
    
    def __init__(self, chess, game, get_valid_moves_func):
        self.chess = chess
        self.game = game
        self.get_valid_moves = get_valid_moves_func
        self._analyze()
    
    def _analyze(self):
        """盤面状態を分析"""
        self.ai_pieces = []
        self.player_pieces = []
        self.ai_mobility = 0
        self.player_mobility = 0
        self.ai_material = 0
        self.player_material = 0
        self.ai_king_pos = None
        self.player_king_pos = None
        self.ai_king = None
        self.player_king = None
        self.ai_frozen_count = 0
        self.player_frozen_count = 0
        self.player_frozen_pieces = []  # 既に凍結されているプレイヤー駒
        self.ai_frozen_pieces = []  # 既に凍結されているAI駒
        self.threats_to_ai = []  # プレイヤーがAI駒を取れる移動
        self.threats_to_ai_king = []  # プレイヤーがAIキングを脅かす移動
        self.ai_attack_opportunities = []  # AIがプレイヤー駒を取れる移動
        self.ai_attacks_on_player_king = []  # AIがプレイヤーキングを脅かす移動
        self.ai_in_check = False
        self.player_in_check = False
        self.ai_checkmate_threat = False  # AIがチェックメイトされる危険
        self.ai_can_checkmate = False  # AIがチェックメイトできる状態
        
        try:
            for p in self.chess.pieces:
                color = getattr(p, 'color', None)
                name = getattr(p, 'name', '')
                row = getattr(p, 'row', 0)
                col = getattr(p, 'col', 0)
                
                # 凍結判定（複数の方法で確認）
                frozen = self._is_piece_frozen(p)
                
                if color == 'black':
                    self.ai_pieces.append(p)
                    self.ai_material += self.PIECE_VALUES.get(name, 0)
                    if name == 'K':
                        self.ai_king_pos = (row, col)
                        self.ai_king = p
                    if frozen:
                        self.ai_frozen_count += 1
                        self.ai_frozen_pieces.append(p)
                    # モビリティ計算（凍結駒は移動不可）
                    if not frozen:
                        try:
                            moves = self.get_valid_moves(p, ignore_check=True)
                            self.ai_mobility += len(moves)
                            # 攻撃機会の分析
                            for mv in moves:
                                target = self.chess.get_piece_at(mv[0], mv[1])
                                if target and getattr(target, 'color', None) == 'white':
                                    self.ai_attack_opportunities.append((p, mv, target))
                                    if getattr(target, 'name', '') == 'K':
                                        self.ai_attacks_on_player_king.append((p, mv, target))
                        except Exception:
                            pass
                elif color == 'white':
                    self.player_pieces.append(p)
                    self.player_material += self.PIECE_VALUES.get(name, 0)
                    if name == 'K':
                        self.player_king_pos = (row, col)
                        self.player_king = p
                    if frozen:
                        self.player_frozen_count += 1
                        self.player_frozen_pieces.append(p)
                    # 脅威の分析（凍結駒は移動不可なので脅威にならない）
                    if not frozen:
                        try:
                            moves = self.get_valid_moves(p, ignore_check=True)
                            self.player_mobility += len(moves)
                            for mv in moves:
                                target = self.chess.get_piece_at(mv[0], mv[1])
                                if target and getattr(target, 'color', None) == 'black':
                                    self.threats_to_ai.append((p, mv, target))
                                    if getattr(target, 'name', '') == 'K':
                                        self.threats_to_ai_king.append((p, mv, target))
                        except Exception:
                            pass
            
            # チェック状態の分析
            self._analyze_check_status()
            
        except Exception:
            pass
    
    def _is_piece_frozen(self, piece) -> bool:
        """駒が凍結しているかを複数の方法で確認"""
        # 方法1: frozen_turns属性
        if getattr(piece, 'frozen_turns', 0) > 0:
            return True
        
        # 方法2: gameのfrozen_pieces辞書
        try:
            if self.game and hasattr(self.game, 'frozen_pieces'):
                piece_id = id(piece)
                if piece_id in self.game.frozen_pieces:
                    if self.game.frozen_pieces[piece_id] > 0:
                        return True
        except Exception:
            pass
        
        return False
    
    def _analyze_check_status(self):
        """チェック・チェックメイト状態を分析"""
        try:
            # AIキングがチェックされているか
            if self.ai_king_pos and self.threats_to_ai_king:
                self.ai_in_check = True
                
                # チェックメイトの危険性を評価
                # AIキングの逃げ場があるか確認
                if self.ai_king:
                    try:
                        king_moves = self.get_valid_moves(self.ai_king, ignore_check=False)
                        if not king_moves:
                            # キングが動けない場合、他の駒でブロックできるか
                            can_block = self._can_block_check()
                            if not can_block:
                                self.ai_checkmate_threat = True
                    except Exception:
                        pass
            
            # プレイヤーキングがチェックされているか
            if self.player_king_pos and self.ai_attacks_on_player_king:
                self.player_in_check = True
                
                # AIがチェックメイトできるか評価
                if self.player_king:
                    try:
                        player_king_moves = self.get_valid_moves(self.player_king, ignore_check=False)
                        if not player_king_moves:
                            # プレイヤーキングが動けない場合
                            self.ai_can_checkmate = True
                    except Exception:
                        pass
        except Exception:
            pass
    
    def _can_block_check(self) -> bool:
        """AI駒がチェックをブロックできるか"""
        # 簡略化: 他のAI駒に移動可能な手があれば、ブロックの可能性あり
        for p in self.ai_pieces:
            if p is self.ai_king:
                continue
            if self._is_piece_frozen(p):
                continue
            try:
                moves = self.get_valid_moves(p, ignore_check=False)
                if moves:
                    return True
            except Exception:
                pass
        return False
    
    def get_unfrozen_high_value_player_pieces(self) -> List:
        """凍結されていない高価値のプレイヤー駒を取得（キング以外）"""
        result = []
        for p in self.player_pieces:
            name = getattr(p, 'name', '')
            if name == 'K':
                continue
            # 凍結チェック
            if self._is_piece_frozen(p):
                continue
            
            value = self.PIECE_VALUES.get(name, 0)
            result.append((p, value, False))  # False = not frozen
        result.sort(key=lambda x: x[1], reverse=True)
        return result
    
    def get_high_value_player_pieces(self) -> List:
        """高価値のプレイヤー駒を取得（キング以外）- 凍結状態も含む"""
        result = []
        for p in self.player_pieces:
            name = getattr(p, 'name', '')
            if name != 'K':
                value = self.PIECE_VALUES.get(name, 0)
                frozen = self._is_piece_frozen(p)
                result.append((p, value, frozen))
        result.sort(key=lambda x: x[1], reverse=True)
        return result
    
    def get_threatening_pieces(self) -> List:
        """AIを脅かしているプレイヤー駒を取得（凍結可能なもののみ）"""
        threatening = []
        seen_pieces = set()
        
        for attacker, mv, target in self.threats_to_ai:
            piece_id = id(attacker)
            if piece_id in seen_pieces:
                continue
            seen_pieces.add(piece_id)
            
            # 凍結済みは除外
            if self._is_piece_frozen(attacker):
                continue
            
            # キングは凍結対象外
            if getattr(attacker, 'name', '') == 'K':
                continue
            
            target_value = self.PIECE_VALUES.get(getattr(target, 'name', ''), 0)
            attacker_value = self.PIECE_VALUES.get(getattr(attacker, 'name', ''), 0)
            
            # 高価値ターゲットを狙っている駒ほど優先
            score = target_value * 10 + attacker_value * 5
            
            # AIキングを狙っている場合は最優先
            if getattr(target, 'name', '') == 'K':
                score += 100
            
            threatening.append((attacker, score))
        
        threatening.sort(key=lambda x: x[1], reverse=True)
        return threatening
    
    def is_ai_under_pressure(self) -> bool:
        """AIが圧迫されているか"""
        # チェックメイトの危険
        if self.ai_checkmate_threat:
            return True
        
        # チェック状態
        if self.ai_in_check:
            return True
        
        # 脅威の数が多い、またはマテリアル差で負けている
        high_value_threats = sum(1 for _, _, target in self.threats_to_ai 
                                 if self.PIECE_VALUES.get(getattr(target, 'name', ''), 0) >= 3)
        return (high_value_threats >= 2 or 
                self.player_material > self.ai_material + 3 or
                self.player_mobility > self.ai_mobility + 10)
    
    def is_ai_dominant(self) -> bool:
        """AIが優勢か"""
        # プレイヤーをチェックメイトできる状態
        if self.ai_can_checkmate:
            return True
        
        # プレイヤーがチェック状態
        if self.player_in_check:
            return True
        
        return (self.ai_material > self.player_material + 3 or
                len(self.ai_attack_opportunities) >= 3)
    
    def has_valid_freeze_target(self) -> bool:
        """有効な凍結ターゲットが存在するか"""
        for p in self.player_pieces:
            name = getattr(p, 'name', '')
            if name == 'K':
                continue
            if not self._is_piece_frozen(p):
                return True
        return False
    
    def get_best_freeze_target(self) -> Optional[Any]:
        """凍結に最適なターゲットを取得（凍結済みは除外）"""
        candidates = []
        
        # まず脅威を与えている駒を優先
        threatening = self.get_threatening_pieces()
        for attacker, threat_score in threatening:
            value = self.PIECE_VALUES.get(getattr(attacker, 'name', ''), 0)
            row = getattr(attacker, 'row', 0)
            col = getattr(attacker, 'col', 0)
            
            score = threat_score + value * 10
            
            # AIキングを狙っている駒は最優先
            for _, _, target in self.threats_to_ai_king:
                if _ is attacker:
                    score += 50
                    break
            
            candidates.append((attacker, score))
        
        # 脅威を与えていない高価値駒も候補に
        for p in self.player_pieces:
            name = getattr(p, 'name', '')
            if name == 'K':
                continue
            if self._is_piece_frozen(p):
                continue
            
            # 既に候補に含まれているか確認
            if any(c[0] is p for c in candidates):
                continue
            
            value = self.PIECE_VALUES.get(name, 0)
            row = getattr(p, 'row', 0)
            col = getattr(p, 'col', 0)
            
            score = value * 10
            
            # 中央の駒は高評価
            center_dist = abs(row - 3.5) + abs(col - 3.5)
            score += (7 - center_dist) * 2
            
            # AIキング周辺の駒は高評価（防御的）
            if self.ai_king_pos:
                king_dist = abs(row - self.ai_king_pos[0]) + abs(col - self.ai_king_pos[1])
                if king_dist <= 2:
                    score += 15
            
            candidates.append((p, score))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def get_best_block_positions(self, max_tiles: int = 3) -> List[Tuple[int, int]]:
        """封鎖に最適な位置を取得"""
        candidates = []
        
        # 高価値駒の周囲を封鎖
        for p, value, frozen in self.get_high_value_player_pieces():
            if value < 3:
                continue
            row = getattr(p, 'row', 0)
            col = getattr(p, 'col', 0)
            
            # 周囲のマスを候補に
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = row + dr, col + dc
                    if not (0 <= nr < 8 and 0 <= nc < 8):
                        continue
                    
                    # 空きマスのみ
                    if self.chess.get_piece_at(nr, nc) is not None:
                        continue
                    
                    # 既に封鎖されていないか
                    if (nr, nc) in getattr(self.game, 'blocked_tiles', {}):
                        continue
                    
                    score = value * 5
                    # 中央寄りはボーナス
                    center_dist = abs(nr - 3.5) + abs(nc - 3.5)
                    score += (7 - center_dist)
                    
                    candidates.append(((nr, nc), score))
        
        # スコア順にソートして上位を返す
        candidates.sort(key=lambda x: x[1], reverse=True)
        seen = set()
        result = []
        for pos, _ in candidates:
            if pos not in seen:
                seen.add(pos)
                result.append(pos)
                if len(result) >= max_tiles:
                    break
        
        return result
    
    def are_pieces_clustered(self) -> bool:
        """AI駒が密集しているか（迅雷・暴風への脆弱性）"""
        if not self.ai_pieces:
            return False
        
        positions = []
        for p in self.ai_pieces:
            if self._is_piece_frozen(p):
                continue
            row = getattr(p, 'row', None)
            col = getattr(p, 'col', None)
            if row is not None and col is not None:
                positions.append((row, col))
        
        if len(positions) < 3:
            return False
        
        # 密集度を計算（駒間の平均距離）
        total_dist = 0
        count = 0
        for i, (r1, c1) in enumerate(positions):
            for j, (r2, c2) in enumerate(positions):
                if i < j:
                    total_dist += abs(r1 - r2) + abs(c1 - c2)
                    count += 1
        
        if count == 0:
            return False
        
        avg_dist = total_dist / count
        return avg_dist < 2.5  # 平均距離が2.5未満なら密集
    
    def get_safe_king_escape_moves(self) -> List:
        """キングの安全な逃げ場所を取得"""
        if not self.ai_king:
            return []
        
        safe_moves = []
        try:
            king_moves = self.get_valid_moves(self.ai_king, ignore_check=False)
            for mv in king_moves:
                # この位置に移動した場合、攻撃されないか確認
                is_safe = True
                for attacker, _, _ in self.threats_to_ai:
                    attacker_row = getattr(attacker, 'row', 0)
                    attacker_col = getattr(attacker, 'col', 0)
                    # 簡易チェック：攻撃者との距離
                    dist = abs(mv[0] - attacker_row) + abs(mv[1] - attacker_col)
                    if dist <= 1:
                        is_safe = False
                        break
                if is_safe:
                    safe_moves.append(mv)
        except Exception:
            pass
        return safe_moves
    
    def count_defenders_around_king(self) -> int:
        """キング周辺の防御駒数"""
        if not self.ai_king_pos:
            return 0
        
        kr, kc = self.ai_king_pos
        count = 0
        for p in self.ai_pieces:
            if p is self.ai_king:
                continue
            if self._is_piece_frozen(p):
                continue
            row = getattr(p, 'row', 0)
            col = getattr(p, 'col', 0)
            if abs(row - kr) <= 2 and abs(col - kc) <= 2:
                count += 1
        return count


class CardEvaluator:
    """カード評価クラス - 各カードの使用価値を評価
    
    改良版v2: 
    - チェック優先回避
    - 迅雷・暴風警戒時の戦略
    - 鉄壁・氷結の温存
    - コンボ対処
    """
    
    def __init__(self, board_analysis: BoardAnalysis, difficulty: int, ai_player, 
                 game_phase: str = None, opponent_analysis: 'OpponentAnalysis' = None):
        self.analysis = board_analysis
        self.difficulty = difficulty
        self.ai_player = ai_player
        self.game_phase = game_phase or GamePhase.MIDGAME
        self.opponent_analysis = opponent_analysis
    
    def evaluate_card(self, card) -> float:
        """カードの使用価値を評価（0-100のスコア）
        
        -1を返す場合は「使用すべきでない」（有効なターゲットがない等）
        """
        name = card.name
        
        evaluators = {
            '氷結': self._eval_freeze,
            '灼熱': self._eval_heat,
            '暴風': self._eval_storm,
            '迅雷': self._eval_lightning,
            '2ドロー': self._eval_draw2,
            '錬成': self._eval_alchemy,
            '墓地ルーレット': self._eval_graveyard,
            '摂取': self._eval_leech,
            '鉄壁': self._eval_ironwall,
            'ハンです☆': self._eval_hand_discard,
        }
        
        eval_func = evaluators.get(name)
        if eval_func:
            base_score = eval_func()
        else:
            base_score = 30  # 未知のカードはデフォルトスコア
        
        # スコアが負の場合は使用すべきでない
        if base_score < 0:
            return -1
        
        # 難易度による調整
        if self.difficulty >= 3:
            # 高難易度: 状況に応じた評価を重視
            return base_score
        elif self.difficulty == 2:
            # 中難易度: やや状況を考慮
            return base_score * 0.85 + random.uniform(0, 15)
        else:
            # 低難易度: ランダム性を追加
            return base_score * 0.5 + random.uniform(0, 50)
    
    def _should_save_card(self, card_name: str) -> bool:
        """カードを温存すべきかどうか判定
        
        鉄壁・氷結は序盤で軽率に使わない
        """
        if self.difficulty < 2:
            return False  # 低難易度では温存しない
        
        # 序盤は温存すべきカード
        save_in_opening = {'鉄壁', '氷結'}
        
        if self.game_phase == GamePhase.OPENING and card_name in save_in_opening:
            # 序盤では危機的状況でのみ使用
            if not self.analysis.ai_in_check and not self.analysis.ai_checkmate_threat:
                if not self.analysis.is_ai_under_pressure():
                    return True
        
        return False
    
    def _eval_freeze(self) -> float:
        """氷結の評価
        
        改良v2: 
        - 有効なターゲットがない場合は-1を返す
        - チェックメイトを防ぐための緊急使用を優先
        - 脅威を与えている駒を優先
        - 序盤は温存
        """
        # 有効なターゲットがなければ使用しない
        if not self.analysis.has_valid_freeze_target():
            return -1
        
        score = 40
        
        # === チェック優先回避 ===
        # チェックメイトの危機がある場合、AIキングを脅かす駒を凍結する価値が高い
        if self.analysis.ai_checkmate_threat or self.analysis.ai_in_check:
            threatening = self.analysis.get_threatening_pieces()
            # AIキングを直接狙っている駒がいれば最優先
            for attacker, _ in threatening:
                for piece, mv, target in self.analysis.threats_to_ai_king:
                    if piece is attacker:
                        return 98  # 最優先で使用
            # チェック状態なら高評価
            if self.analysis.ai_in_check:
                score = 85
        
        # AIがチェックメイトできる状態なら、相手の駒を凍結する価値は低い
        # （チェックメイトを優先すべき）
        if self.analysis.ai_can_checkmate:
            return 15  # 低評価（チェックメイトを優先）
        
        # === 氷結の温存 ===
        # 序盤では危機的状況でない限り温存
        if self._should_save_card('氷結'):
            return 20  # 温存のため低評価
        
        # === コンボ対処 ===
        # 相手がコンボを狙っている可能性がある場合、攻撃的な駒を凍結
        if self.opponent_analysis and self.opponent_analysis.combo_threat:
            threatening = self.analysis.get_threatening_pieces()
            if threatening:
                score += 25
        
        # 脅威を与えている未凍結駒がいれば高評価
        threatening = self.analysis.get_threatening_pieces()
        if threatening:
            score += 30
        
        # 高価値の未凍結駒がいれば評価
        targets = self.analysis.get_unfrozen_high_value_player_pieces()
        if targets:
            best_target, value, _ = targets[0]
            if value >= 9:  # クイーン
                score += 35
            elif value >= 5:  # ルーク
                score += 25
            elif value >= 3:  # ナイト/ビショップ
                score += 15
        
        # AIが圧迫されている場合は防御的に使用
        if self.analysis.is_ai_under_pressure():
            score += 15
        
        return min(score, 95)
    
    def _eval_heat(self) -> float:
        """灼熱の評価
        
        改良:
        - AI側に凍結駒がいる場合は解凍を優先
        - チェックメイトの危機がある場合の防御使用
        """
        score = 35
        
        # AI側に凍結駒がいる場合は解凍オプションの価値が高い
        if self.analysis.ai_frozen_count > 0:
            # 高価値駒が凍結されているほど解凍の価値が高い
            frozen_value = 0
            for p in self.analysis.ai_frozen_pieces:
                val = BoardAnalysis.PIECE_VALUES.get(getattr(p, 'name', ''), 0)
                frozen_value += val
            score += frozen_value * 8
            
            # チェック状態で凍結駒がいるなら解凍が重要
            if self.analysis.ai_in_check:
                score += 30
        
        # 相手のモビリティが高い場合は封鎖が効果的
        mobility_diff = self.analysis.player_mobility - self.analysis.ai_mobility
        if mobility_diff > 5:
            score += mobility_diff * 2
        
        # 高価値駒の動きを制限できるなら評価
        targets = self.analysis.get_unfrozen_high_value_player_pieces()
        if targets and targets[0][1] >= 5:
            score += 10
        
        return min(score, 90)
    
    def _eval_storm(self) -> float:
        """暴風の評価
        
        改良v2:
        - チェック優先回避
        - 駒が密集している場合の防御（迅雷・暴風警戒）
        - 攻撃的使用も考慮
        """
        score = 30
        
        # 既に暴風効果がある場合は低評価
        if getattr(self.analysis.game, 'ai_next_move_can_jump', False):
            return 5
        
        # === チェック優先回避 ===
        # チェックメイトの危機がある場合、逃げ道を作るために使用
        if self.analysis.ai_checkmate_threat:
            # キングの逃げ場がない場合、暴風で駒を飛び越えて守りを作る
            safe_moves = self.analysis.get_safe_king_escape_moves()
            if not safe_moves:
                score += 50
        elif self.analysis.ai_in_check:
            score += 30
        
        # === 迅雷・暴風警戒時の対応 ===
        # 相手が迅雷・暴風を持っていそうで、AI駒が密集している場合
        if self.opponent_analysis:
            if self.opponent_analysis.likely_has_lightning or self.opponent_analysis.likely_has_storm:
                if self.analysis.are_pieces_clustered():
                    # 密集を解消するために暴風を使う（駒を移動させやすくする）
                    score += 25
        
        # AIのモビリティが低い場合は高評価
        if self.analysis.ai_mobility < self.analysis.player_mobility:
            score += 20
        
        # 駒が密集している場合（ジャンプが有効）
        non_knight_count = sum(1 for p in self.analysis.ai_pieces 
                               if getattr(p, 'name', '') not in ['N', 'K']
                               and not self.analysis._is_piece_frozen(p))
        if non_knight_count >= 3:
            score += 15
        
        # 攻撃機会が少ない場合
        if len(self.analysis.ai_attack_opportunities) < 2:
            score += 15
        
        return min(score, 85)
    
    def _eval_lightning(self) -> float:
        """迅雷の評価
        
        改良v2:
        - チェックメイトを狙える場合は最優先
        - プレイヤーキングを攻撃できる場合は高評価
        - 相手の迅雷への対抗策
        """
        score = 45
        
        # 既に連続ターンがある場合は低評価
        if getattr(self.analysis.game, 'ai_consecutive_turns', 0) >= 1:
            return 5
        
        # === チェックメイト狙い ===
        # AIがチェックメイトできる状態なら最優先
        if self.analysis.ai_can_checkmate:
            return 98
        
        # プレイヤーがチェック状態なら追い込みチャンス
        if self.analysis.player_in_check:
            score += 30
        
        # プレイヤーキングを攻撃できる機会がある
        if self.analysis.ai_attacks_on_player_king:
            score += 25
        
        # === コンボ対処 ===
        # 相手がコンボを使ってきた場合、迅雷で対抗（2回動いて取り返す）
        if self.opponent_analysis and self.opponent_analysis.combo_threat:
            if len(self.analysis.ai_attack_opportunities) >= 1:
                score += 20
        
        # 攻撃機会が多い場合は高評価（2回動けることで取れる駒が増える）
        attack_count = len(self.analysis.ai_attack_opportunities)
        if attack_count >= 2:
            score += attack_count * 8
        
        # AIが優勢な場合は押し込みに使える
        if self.analysis.is_ai_dominant():
            score += 15
        
        # 相手キングへの脅威がある場合
        if self.analysis.player_king_pos:
            for p, mv, _ in self.analysis.ai_attack_opportunities:
                king_dist = abs(mv[0] - self.analysis.player_king_pos[0]) + \
                           abs(mv[1] - self.analysis.player_king_pos[1])
                if king_dist <= 2:
                    score += 10
                    break
        
        return min(score, 95)
    
    def _eval_draw2(self) -> float:
        """2ドローの評価"""
        hand_size = len(self.ai_player.hand.cards)
        
        # 手札が少ない場合は高評価
        if hand_size <= 2:
            return 75
        elif hand_size <= 4:
            return 50
        else:
            return 25  # 手札が多いと手札上限に達するリスク
    
    def _eval_alchemy(self) -> float:
        """錬成の評価"""
        score = 35
        hand_size = len(self.ai_player.hand.cards)
        
        # 手札が多い場合は不要カードを捨てる機会になる
        if hand_size >= 5:
            score += 15
        
        # コスト0なので気軽に使える
        if self.ai_player.pp_current <= 1:
            score += 20
        
        return score
    
    def _eval_graveyard(self) -> float:
        """墓地ルーレットの評価"""
        graveyard = getattr(self.ai_player, 'graveyard', [])
        
        if not graveyard:
            return 0
        
        # 墓地に良いカードがあれば高評価
        good_cards = {'氷結', '迅雷', '暴風', '鉄壁'}
        good_count = sum(1 for c in graveyard if c.name in good_cards)
        
        score = 30 + good_count * 15
        return min(score, 70)
    
    def _eval_leech(self) -> float:
        """摂取の評価"""
        pp = self.ai_player.pp_current
        pp_max = self.ai_player.pp_max
        
        # PPが少ない場合は高評価
        if pp <= 1:
            return 70
        elif pp < pp_max:
            return 45
        else:
            return 10  # 既にPP最大
    
    def _eval_ironwall(self) -> float:
        """鉄壁の評価
        
        改良v2:
        - 序盤は温存
        - 相手のコンボ対処
        - 危機的状況での使用
        """
        score = 35
        
        # === 鉄壁の温存 ===
        # 序盤は温存（終盤や危機的状況でのみ使用）
        if self._should_save_card('鉄壁'):
            return 15  # 温存のため低評価
        
        # === コンボ対処 ===
        # 相手がコンボを狙っている場合、鉄壁で防御
        if self.opponent_analysis and self.opponent_analysis.combo_threat:
            score += 35
        
        # 相手が攻撃的なプレイスタイルの場合
        if self.opponent_analysis and self.opponent_analysis.aggressive_play:
            score += 25
        
        # 相手が迅雷・氷結を持っている可能性が高い場合
        if self.opponent_analysis:
            if self.opponent_analysis.likely_has_lightning:
                score += 15
            if self.opponent_analysis.likely_has_freeze:
                score += 15
        
        # 相手が脅威的なカードを持っている可能性を考慮
        # （相手の手札数から推測）
        try:
            opponent_hand_count = len(self.analysis.game.player.hand.cards)
            if opponent_hand_count >= 4:
                score += 15
        except Exception:
            pass
        
        # AIが不利な場合は防御的に
        if self.analysis.is_ai_under_pressure():
            score += 25
        
        # チェック状態なら鉄壁も選択肢に
        if self.analysis.ai_in_check:
            score += 20
        
        return min(score, 85)
    
    def _eval_hand_discard(self) -> float:
        """ハンです☆の評価"""
        score = 40
        
        # 相手の手札が多い場合は効果的
        try:
            opponent_hand_count = len(self.analysis.game.player.hand.cards)
            if opponent_hand_count >= 5:
                score += 25
            elif opponent_hand_count >= 3:
                score += 10
            elif opponent_hand_count <= 1:
                return 10  # 相手の手札が少ないと効果薄い
        except Exception:
            pass
        
        return min(score, 75)


class AICardStrategy:
    """AI カード戦略メインクラス
    
    改良版v2:
    - チェック優先回避
    - 迅雷・暴風警戒
    - 鉄壁・氷結の温存
    - コンボ対処
    """
    
    def __init__(self, difficulty: int):
        self.difficulty = difficulty
        # 難易度別のカード使用確率
        self.play_probabilities = {
            1: 0.35,  # Easy: 35%の確率でカードを使用
            2: 0.55,  # Normal: 55% (少し控えめに - 決着を遅らせる)
            3: 0.75,  # Hard: 75%
            4: 0.90,  # Expert: 90%
        }
        # 難易度別の試行回数
        self.max_attempts = {
            1: 1,
            2: 2,
            3: 2,  # Hard: 2回に制限（温存戦略）
            4: 3,  # Expert: 3回に制限
        }
    
    def should_play_card(self) -> bool:
        """カードを使用すべきかどうかの確率判定"""
        prob = self.play_probabilities.get(self.difficulty, 0.5)
        return random.random() < prob
    
    def should_prioritize_check_escape(self, analysis: BoardAnalysis) -> bool:
        """チェック回避を優先すべきか判定
        
        Normal以上の難易度では、チェック状態の時は駒移動を優先
        """
        if self.difficulty < 2:
            return False
        
        # チェック状態またはチェックメイトの危機
        if analysis.ai_in_check or analysis.ai_checkmate_threat:
            # 氷結でチェック回避できる場合は除く
            if analysis.threats_to_ai_king:
                # 脅威を与えている駒を凍結できるか
                for attacker, _, _ in analysis.threats_to_ai_king:
                    if not analysis._is_piece_frozen(attacker):
                        if getattr(attacker, 'name', '') != 'K':
                            # 凍結可能な駒が脅威を与えている → カードで対処可能
                            return False
            # 駒移動でチェック回避を優先
            return True
        
        return False
    
    def select_card(self, ai_player, game, chess, get_valid_moves_func) -> Optional[int]:
        """使用するカードを選択
        
        Returns:
            使用するカードの手札インデックス、または None
        """
        playable_indices = [
            i for i, c in enumerate(ai_player.hand.cards)
            if c.can_play(ai_player)
        ]
        
        if not playable_indices:
            return None
        
        # 盤面分析
        analysis = BoardAnalysis(chess, game, get_valid_moves_func)
        
        # ゲームフェーズ分析
        game_phase = GamePhase.get_phase(game)
        
        # 相手（プレイヤー）の分析
        opponent_analysis = OpponentAnalysis(game)
        
        # チェック回避を優先すべき場合
        if self.should_prioritize_check_escape(analysis):
            # チェック回避できるカードがあるか確認
            has_escape_card = False
            for idx in playable_indices:
                card = ai_player.hand.cards[idx]
                if card.name == '氷結' and analysis.has_valid_freeze_target():
                    # 脅威を与えている駒を凍結できる
                    for attacker, _, _ in analysis.threats_to_ai_king:
                        if not analysis._is_piece_frozen(attacker):
                            has_escape_card = True
                            break
                elif card.name == '暴風':
                    # 暴風で逃げられる可能性
                    has_escape_card = True
            
            if not has_escape_card:
                # カードでチェック回避できない → 駒移動を優先
                return None
        
        # カード評価（新しい分析を使用）
        evaluator = CardEvaluator(
            analysis, self.difficulty, ai_player,
            game_phase=game_phase,
            opponent_analysis=opponent_analysis
        )
        
        # 各カードをスコアリング
        card_scores = []
        for idx in playable_indices:
            card = ai_player.hand.cards[idx]
            score = evaluator.evaluate_card(card)
            card_scores.append((idx, score, card.name))
        
        
        # スコアが -1 のカード（使用すべきでない）を除外
        valid_card_scores = [(idx, score, name) for idx, score, name in card_scores if score >= 0]
        
        # 使用可能なカードがない場合
        if not valid_card_scores:
            return None
        
        # スコアでソート
        valid_card_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 難易度に応じた選択
        if self.difficulty >= 4:
            # Expert: 最高スコアのカードを選択
            return valid_card_scores[0][0]
        elif self.difficulty == 3:
            # Hard: 95%で最高スコア、5%で2番目
            if random.random() < 0.95 or len(valid_card_scores) == 1:
                return valid_card_scores[0][0]
            else:
                return valid_card_scores[min(1, len(valid_card_scores) - 1)][0]
        elif self.difficulty == 2:
            # Normal: 80%で上位2枚から、20%でランダム
            if random.random() < 0.80:
                top_2 = valid_card_scores[:min(2, len(valid_card_scores))]
                return random.choice(top_2)[0]
            else:
                return random.choice(valid_card_scores)[0]
        else:
            # Easy: 完全ランダム
            return random.choice(valid_card_scores)[0]
    
    def get_freeze_target(self, game, chess, player_color='white') -> Optional[Any]:
        """氷結のターゲットを選択"""
        analysis = BoardAnalysis(chess, game, lambda p, **kw: [])
        return analysis.get_best_freeze_target()
    
    def get_block_positions(self, game, chess, max_tiles: int = 3) -> List[Tuple[int, int]]:
        """封鎖位置を選択"""
        analysis = BoardAnalysis(chess, game, lambda p, **kw: [])
        return analysis.get_best_block_positions(max_tiles)


def create_ai_card_strategy(difficulty: int) -> AICardStrategy:
    """AI カード戦略インスタンスを作成"""
    return AICardStrategy(difficulty)


# テスト用
if __name__ == "__main__":
    print("AI Card Strategy Module loaded successfully")
