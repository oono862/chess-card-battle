"""AI カード戦略モジュール

このモジュールは、AIが戦略的にカードを使用するためのロジックを提供します。
難易度に応じて異なる戦略を適用し、盤面状況を分析してカードを選択します。

改良版v3 (ベリーハード強化): 
- チェック優先回避
- 迅雷・暴風警戒時の駒配置戦略
- 鉄壁・氷結の温存
- コンボ対処
- ★NEW: プレイヤーカード使用パターン学習
- ★NEW: クイーン+暴風/迅雷コンボによるチェックメイト狙い
- ★NEW: 2手先読み評価
- ★NEW: 攻撃的/防御的戦略の動的切り替え
- ★NEW: カードコンボの連携使用
"""

import random
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


# =============================================================================
# プレイヤー行動学習システム
# =============================================================================

class PlayerPatternLearner:
    """プレイヤーのカード使用パターンを学習・分析するクラス
    
    学習内容:
    - カードの使用頻度
    - 特定状況でのカード選択傾向
    - コンボパターン
    - 攻撃的/防御的プレイスタイル
    """
    
    # 学習データ保存パス
    SAVE_PATH = os.path.join(os.path.dirname(__file__), 'player_patterns.json')
    
    def __init__(self):
        self.card_usage_count: Dict[str, int] = defaultdict(int)
        self.card_usage_in_check: Dict[str, int] = defaultdict(int)  # チェック時の使用
        self.card_usage_when_ahead: Dict[str, int] = defaultdict(int)  # 優勢時の使用
        self.card_usage_when_behind: Dict[str, int] = defaultdict(int)  # 劣勢時の使用
        self.combo_sequences: List[List[str]] = []  # カードの連続使用パターン
        self.recent_cards: List[str] = []  # 直近の使用カード（コンボ検出用）
        self.total_games: int = 0
        self.total_turns: int = 0
        self.aggressive_score: float = 0.5  # 0=防御的、1=攻撃的
        self._load_patterns()
    
    def _load_patterns(self):
        """保存された学習データを読み込む"""
        try:
            if os.path.exists(self.SAVE_PATH):
                with open(self.SAVE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.card_usage_count = defaultdict(int, data.get('card_usage_count', {}))
                    self.card_usage_in_check = defaultdict(int, data.get('card_usage_in_check', {}))
                    self.card_usage_when_ahead = defaultdict(int, data.get('card_usage_when_ahead', {}))
                    self.card_usage_when_behind = defaultdict(int, data.get('card_usage_when_behind', {}))
                    self.combo_sequences = data.get('combo_sequences', [])[-50:]  # 直近50件
                    self.total_games = data.get('total_games', 0)
                    self.total_turns = data.get('total_turns', 0)
                    self.aggressive_score = data.get('aggressive_score', 0.5)
        except Exception:
            pass
    
    def save_patterns(self):
        """学習データを保存する"""
        try:
            data = {
                'card_usage_count': dict(self.card_usage_count),
                'card_usage_in_check': dict(self.card_usage_in_check),
                'card_usage_when_ahead': dict(self.card_usage_when_ahead),
                'card_usage_when_behind': dict(self.card_usage_when_behind),
                'combo_sequences': self.combo_sequences[-50:],
                'total_games': self.total_games,
                'total_turns': self.total_turns,
                'aggressive_score': self.aggressive_score,
            }
            with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def record_card_usage(self, card_name: str, game_state: Dict[str, Any]):
        """プレイヤーのカード使用を記録"""
        self.card_usage_count[card_name] += 1
        
        # 状況別の使用記録
        if game_state.get('player_in_check', False):
            self.card_usage_in_check[card_name] += 1
        
        material_diff = game_state.get('material_diff', 0)  # 正=プレイヤー優勢
        if material_diff > 2:
            self.card_usage_when_ahead[card_name] += 1
        elif material_diff < -2:
            self.card_usage_when_behind[card_name] += 1
        
        # コンボ検出
        self.recent_cards.append(card_name)
        if len(self.recent_cards) > 3:
            self.recent_cards.pop(0)
        
        # 2枚以上の連続使用はコンボとして記録
        if len(self.recent_cards) >= 2:
            self.combo_sequences.append(list(self.recent_cards[-2:]))
        
        # 攻撃的スコアの更新
        aggressive_cards = {'迅雷', '暴風', '氷結', '灼熱', 'ハンです☆'}
        if card_name in aggressive_cards:
            self.aggressive_score = min(1.0, self.aggressive_score + 0.02)
        else:
            self.aggressive_score = max(0.0, self.aggressive_score - 0.01)
        
        self.total_turns += 1
    
    def record_turn_end(self):
        """ターン終了時に呼び出し（コンボ検出のリセット）"""
        # 同一ターン内でなければコンボリセット
        self.recent_cards = []
    
    def record_game_end(self):
        """ゲーム終了時に呼び出し"""
        self.total_games += 1
        self.recent_cards = []
        self.save_patterns()
    
    def get_most_used_cards(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """最も使用頻度の高いカードを取得"""
        sorted_cards = sorted(self.card_usage_count.items(), key=lambda x: x[1], reverse=True)
        return sorted_cards[:top_n]
    
    def get_likely_next_card(self, last_card: str) -> Optional[str]:
        """直前のカードから次に使われやすいカードを予測"""
        if not self.combo_sequences:
            return None
        
        # 直前カードに続くカードの出現回数をカウント
        follow_up_counts: Dict[str, int] = defaultdict(int)
        for seq in self.combo_sequences:
            if len(seq) >= 2 and seq[0] == last_card:
                follow_up_counts[seq[1]] += 1
        
        if not follow_up_counts:
            return None
        
        # 最頻出のフォローアップカードを返す
        return max(follow_up_counts.items(), key=lambda x: x[1])[0]
    
    def predict_player_strategy(self, game_state: Dict[str, Any]) -> Dict[str, float]:
        """プレイヤーの次の行動を予測"""
        predictions = {}
        
        # 基本予測: 使用頻度に基づく
        total_usage = sum(self.card_usage_count.values()) or 1
        for card, count in self.card_usage_count.items():
            predictions[card] = count / total_usage
        
        # 状況に応じた補正
        if game_state.get('player_in_check', False):
            check_total = sum(self.card_usage_in_check.values()) or 1
            for card, count in self.card_usage_in_check.items():
                predictions[card] = predictions.get(card, 0) * 0.5 + (count / check_total) * 0.5
        
        return predictions
    
    def is_player_aggressive(self) -> bool:
        """プレイヤーが攻撃的なプレイスタイルかどうか"""
        return self.aggressive_score > 0.6
    
    def is_player_defensive(self) -> bool:
        """プレイヤーが防御的なプレイスタイルかどうか"""
        return self.aggressive_score < 0.4


# グローバルインスタンス（ゲーム間で学習を維持）
_player_learner: Optional[PlayerPatternLearner] = None


def get_player_learner() -> PlayerPatternLearner:
    """プレイヤー学習インスタンスを取得"""
    global _player_learner
    if _player_learner is None:
        _player_learner = PlayerPatternLearner()
    return _player_learner


# =============================================================================
# チェックメイトコンボ検出システム
# =============================================================================

class CheckmateComboDetector:
    """チェックメイトに繋がるカードコンボを検出するクラス
    
    検出パターン:
    1. クイーン + 暴風 → 飛び越えてチェック
    2. クイーン + 迅雷 → 2回移動でチェックメイト
    3. 氷結 + 迅雷 → 防御駒を凍結して攻撃
    4. 灼熱 + 迅雷 → 逃げ道を塞いで攻撃
    """
    
    PIECE_VALUES = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 100}
    
    def __init__(self, chess, game, get_valid_moves_func, simulate_move_func=None, is_in_check_func=None):
        self.chess = chess
        self.game = game
        self.get_valid_moves = get_valid_moves_func
        self.simulate_move = simulate_move_func
        self.is_in_check = is_in_check_func
        self._cache = {}
    
    def find_queen_storm_checkmate(self) -> Optional[Dict[str, Any]]:
        """クイーン + 暴風によるチェックメイト機会を検出
        
        暴風で駒を飛び越えてクイーンがキングを攻撃できるかチェック
        """
        # AIのクイーンを探す
        ai_queen = None
        player_king_pos = None
        
        for p in self.chess.pieces:
            color = getattr(p, 'color', None)
            name = getattr(p, 'name', '')
            if color == 'black' and name == 'Q':
                ai_queen = p
            elif color == 'white' and name == 'K':
                player_king_pos = (getattr(p, 'row', 0), getattr(p, 'col', 0))
        
        if not ai_queen or not player_king_pos:
            return None
        
        queen_row = getattr(ai_queen, 'row', 0)
        queen_col = getattr(ai_queen, 'col', 0)
        king_row, king_col = player_king_pos
        
        # 通常の移動ではキングに到達できないが、暴風で飛び越えれば到達できるか
        normal_moves = self.get_valid_moves(ai_queen, ignore_check=True)
        can_reach_normally = player_king_pos in normal_moves
        
        if can_reach_normally:
            # 既にチェックできる状態なら暴風不要
            return None
        
        # クイーンとキングの間に駒があり、飛び越えればチェックできるか
        blocking_pieces = self._get_pieces_between(queen_row, queen_col, king_row, king_col)
        
        if blocking_pieces and len(blocking_pieces) == 1:
            # 1つの駒を飛び越えればチェック可能
            return {
                'combo': 'queen_storm_check',
                'attacker': ai_queen,
                'target': player_king_pos,
                'blocking': blocking_pieces[0],
                'priority': 95,
                'description': f'クイーンが暴風で駒を飛び越えてチェック可能'
            }
        
        return None
    
    def find_queen_lightning_checkmate(self) -> Optional[Dict[str, Any]]:
        """クイーン + 迅雷による2手チェックメイト機会を検出
        
        1手目でチェック、2手目でチェックメイトのパターンを探す
        """
        if not self.simulate_move or not self.is_in_check:
            return None
        
        # AIのクイーンと相手キングを探す
        ai_queen = None
        player_king = None
        player_king_pos = None
        
        for p in self.chess.pieces:
            color = getattr(p, 'color', None)
            name = getattr(p, 'name', '')
            if color == 'black' and name == 'Q':
                ai_queen = p
            elif color == 'white' and name == 'K':
                player_king = p
                player_king_pos = (getattr(p, 'row', 0), getattr(p, 'col', 0))
        
        if not ai_queen or not player_king_pos:
            return None
        
        queen_moves = self.get_valid_moves(ai_queen, ignore_check=True)
        
        # 1手目のチェック手を探す
        for mv1 in queen_moves:
            try:
                # 1手目をシミュレート
                new_pieces = self.simulate_move(ai_queen, mv1[0], mv1[1])
                if not self.is_in_check(new_pieces, 'white'):
                    continue  # チェックにならない
                
                # この位置からの2手目でチェックメイトできるか
                # 簡易評価: キングの逃げ道が少ないほど高評価
                king_escape_count = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = player_king_pos[0] + dr, player_king_pos[1] + dc
                        if 0 <= nr < 8 and 0 <= nc < 8:
                            # 簡易チェック: その位置に逃げられるか
                            blocking = self.chess.get_piece_at(nr, nc)
                            if not blocking or getattr(blocking, 'color', '') == 'black':
                                king_escape_count += 1
                
                if king_escape_count <= 2:
                    return {
                        'combo': 'queen_lightning_checkmate',
                        'attacker': ai_queen,
                        'first_move': mv1,
                        'target': player_king_pos,
                        'priority': 90,
                        'escape_count': king_escape_count,
                        'description': f'クイーンが迅雷で2回動いてチェックメイト狙い（逃げ道{king_escape_count}）'
                    }
            except Exception:
                continue
        
        return None
    
    def find_freeze_attack_combo(self) -> Optional[Dict[str, Any]]:
        """氷結 + 攻撃カードのコンボを検出
        
        防御駒を凍結して、その後で攻撃を仕掛けるパターン
        """
        # 相手キングを守っている駒を探す
        player_king_pos = None
        defender_pieces = []
        
        for p in self.chess.pieces:
            color = getattr(p, 'color', None)
            name = getattr(p, 'name', '')
            row = getattr(p, 'row', 0)
            col = getattr(p, 'col', 0)
            
            if color == 'white' and name == 'K':
                player_king_pos = (row, col)
            elif color == 'white' and name != 'K':
                # キング周辺の駒は防御駒の可能性
                defender_pieces.append((p, row, col))
        
        if not player_king_pos or not defender_pieces:
            return None
        
        # キング周辺の防御駒を探す
        king_row, king_col = player_king_pos
        nearby_defenders = []
        
        for p, row, col in defender_pieces:
            dist = abs(row - king_row) + abs(col - king_col)
            if dist <= 2:
                value = self.PIECE_VALUES.get(getattr(p, 'name', ''), 0)
                nearby_defenders.append((p, value, dist))
        
        if nearby_defenders:
            # 最も価値の高い防御駒
            nearby_defenders.sort(key=lambda x: (x[1], -x[2]), reverse=True)
            best_target = nearby_defenders[0]
            
            return {
                'combo': 'freeze_attack',
                'freeze_target': best_target[0],
                'priority': 70,
                'description': f'{getattr(best_target[0], "name", "")}を凍結してキングへの攻撃ルートを確保'
            }
        
        return None
    
    def find_all_combos(self) -> List[Dict[str, Any]]:
        """全てのコンボ機会を検出"""
        combos = []
        
        # クイーン + 暴風
        queen_storm = self.find_queen_storm_checkmate()
        if queen_storm:
            combos.append(queen_storm)
        
        # クイーン + 迅雷
        queen_lightning = self.find_queen_lightning_checkmate()
        if queen_lightning:
            combos.append(queen_lightning)
        
        # 氷結 + 攻撃
        freeze_attack = self.find_freeze_attack_combo()
        if freeze_attack:
            combos.append(freeze_attack)
        
        # 優先度でソート
        combos.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return combos
    
    def _get_pieces_between(self, r1: int, c1: int, r2: int, c2: int) -> List[Any]:
        """2点間にある駒のリストを取得"""
        pieces = []
        
        dr = 0 if r1 == r2 else (1 if r2 > r1 else -1)
        dc = 0 if c1 == c2 else (1 if c2 > c1 else -1)
        
        # 斜め/直線上にあるかチェック
        if dr != 0 and dc != 0:
            if abs(r2 - r1) != abs(c2 - c1):
                return []  # 斜め直線上にない
        
        r, c = r1 + dr, c1 + dc
        while (r, c) != (r2, c2):
            if not (0 <= r < 8 and 0 <= c < 8):
                break
            piece = self.chess.get_piece_at(r, c)
            if piece:
                pieces.append(piece)
            r += dr
            c += dc
        
        return pieces


# =============================================================================
# 2手先読み評価システム
# =============================================================================

class LookaheadEvaluator:
    """2手先を読んでカード使用の効果を評価するクラス"""
    
    PIECE_VALUES = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 100}
    
    def __init__(self, chess, game, get_valid_moves_func, simulate_move_func=None, is_in_check_func=None):
        self.chess = chess
        self.game = game
        self.get_valid_moves = get_valid_moves_func
        self.simulate_move = simulate_move_func
        self.is_in_check = is_in_check_func
    
    def evaluate_after_storm(self) -> float:
        """暴風使用後の盤面評価"""
        score = 0.0
        
        # 暴風でジャンプ可能になった場合の追加移動先を評価
        for p in self.chess.pieces:
            if getattr(p, 'color', None) != 'black':
                continue
            
            name = getattr(p, 'name', '')
            if name in ['N', 'K']:  # ナイトとキングは元々ジャンプ可能
                continue
            
            # 通常の移動先
            normal_moves = self.get_valid_moves(p, ignore_check=True)
            
            # ジャンプ込みの移動先（簡易シミュレーション）
            row = getattr(p, 'row', 0)
            col = getattr(p, 'col', 0)
            
            # クイーン/ルーク/ビショップの延長線上の位置を評価
            attack_potential = 0
            for mv in normal_moves:
                target = self.chess.get_piece_at(mv[0], mv[1])
                if target and getattr(target, 'color', '') == 'white':
                    attack_potential += self.PIECE_VALUES.get(getattr(target, 'name', ''), 0)
            
            # 高価値駒への攻撃機会が増える場合はボーナス
            if name == 'Q':
                score += attack_potential * 3
            elif name == 'R':
                score += attack_potential * 2
            elif name == 'B':
                score += attack_potential * 1.5
        
        return score
    
    def evaluate_after_lightning(self) -> float:
        """迅雷使用後の盤面評価（2回行動の価値）"""
        score = 0.0
        
        # AI駒の攻撃機会を評価
        attack_opportunities = []
        
        for p in self.chess.pieces:
            if getattr(p, 'color', None) != 'black':
                continue
            
            moves = self.get_valid_moves(p, ignore_check=True)
            for mv in moves:
                target = self.chess.get_piece_at(mv[0], mv[1])
                if target and getattr(target, 'color', '') == 'white':
                    value = self.PIECE_VALUES.get(getattr(target, 'name', ''), 0)
                    attack_opportunities.append((p, mv, value))
        
        # 攻撃機会を価値順にソート
        attack_opportunities.sort(key=lambda x: x[2], reverse=True)
        
        # 上位2つの攻撃機会の価値を合算（2回動けるので）
        if len(attack_opportunities) >= 2:
            score = attack_opportunities[0][2] * 3 + attack_opportunities[1][2] * 2
        elif len(attack_opportunities) == 1:
            score = attack_opportunities[0][2] * 3
        
        # プレイヤーキングへの接近を評価
        player_king_pos = None
        for p in self.chess.pieces:
            if getattr(p, 'color', '') == 'white' and getattr(p, 'name', '') == 'K':
                player_king_pos = (getattr(p, 'row', 0), getattr(p, 'col', 0))
                break
        
        if player_king_pos:
            for p in self.chess.pieces:
                if getattr(p, 'color', None) != 'black':
                    continue
                name = getattr(p, 'name', '')
                if name in ['Q', 'R']:  # 強力な駒
                    row = getattr(p, 'row', 0)
                    col = getattr(p, 'col', 0)
                    dist = abs(row - player_king_pos[0]) + abs(col - player_king_pos[1])
                    if dist <= 3:
                        score += 20  # キングに近い強力な駒にボーナス
        
        return score
    
    def evaluate_after_freeze(self, target_piece) -> float:
        """氷結使用後の盤面評価"""
        if not target_piece:
            return 0.0
        
        score = 0.0
        
        # 凍結駒の価値
        value = self.PIECE_VALUES.get(getattr(target_piece, 'name', ''), 0)
        score += value * 5
        
        # 凍結駒がキング周辺の防御駒だった場合のボーナス
        target_row = getattr(target_piece, 'row', 0)
        target_col = getattr(target_piece, 'col', 0)
        
        player_king_pos = None
        for p in self.chess.pieces:
            if getattr(p, 'color', '') == 'white' and getattr(p, 'name', '') == 'K':
                player_king_pos = (getattr(p, 'row', 0), getattr(p, 'col', 0))
                break
        
        if player_king_pos:
            dist = abs(target_row - player_king_pos[0]) + abs(target_col - player_king_pos[1])
            if dist <= 2:
                score += 15  # キング周辺の駒を凍結
        
        return score


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
    """相手（プレイヤー）の状態分析
    
    改良版v3: クイーン+迅雷コンボの脅威検出を強化
    """
    
    def __init__(self, game, chess=None, get_valid_moves_func=None):
        self.game = game
        self.chess = chess
        self.get_valid_moves = get_valid_moves_func
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
        
        # ★NEW: クイーン+迅雷コンボの脅威分析
        self.queen_lightning_threat = False  # クイーン+迅雷コンボの脅威
        self.queen_lightning_threat_level = 0  # 脅威レベル (0-100)
        self.player_queen_near_king = False  # プレイヤーのクイーンがAIキングに近い
        self.player_queen_can_check = False  # プレイヤーのクイーンがチェックできる
        self.turns_to_checkmate_estimate = 99  # チェックメイトまでの推定ターン数
        
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
            if self.hand_count >= 2:
                self.likely_has_lightning = True  # 2枚以上で迅雷の可能性を警戒
            if self.hand_count >= 3:
                self.likely_has_storm = True
            if self.hand_count >= 4:
                self.likely_has_freeze = True
            
            # 最近連続でカードを使用していたらコンボ脅威
            card_count_in_recent = len(self.recent_cards_used)
            if card_count_in_recent >= 2:
                self.combo_threat = True
            if card_count_in_recent >= 3:
                self.aggressive_play = True
            
            # ★クイーン+迅雷コンボの脅威分析
            self._analyze_queen_lightning_threat()
                
        except Exception:
            pass
    
    def _analyze_queen_lightning_threat(self):
        """プレイヤーのクイーン+迅雷コンボの脅威を分析"""
        if not self.chess or not self.get_valid_moves:
            return
        
        try:
            # AIキングとプレイヤークイーンの位置を取得
            ai_king_pos = None
            player_queen = None
            player_queen_pos = None
            
            for p in self.chess.pieces:
                color = getattr(p, 'color', None)
                name = getattr(p, 'name', '')
                row = getattr(p, 'row', 0)
                col = getattr(p, 'col', 0)
                
                if color == 'black' and name == 'K':
                    ai_king_pos = (row, col)
                elif color == 'white' and name == 'Q':
                    player_queen = p
                    player_queen_pos = (row, col)
            
            if not ai_king_pos or not player_queen:
                return
            
            # クイーンがAIキングに近いか
            queen_to_king_dist = abs(player_queen_pos[0] - ai_king_pos[0]) + abs(player_queen_pos[1] - ai_king_pos[1])
            
            if queen_to_king_dist <= 4:
                self.player_queen_near_king = True
            
            # クイーンがチェックできるか
            try:
                queen_moves = self.get_valid_moves(player_queen, ignore_check=True)
                for mv in queen_moves:
                    if mv == ai_king_pos:
                        self.player_queen_can_check = True
                        break
                
                # チェックできなくても、1手でチェック位置に行けるか
                if not self.player_queen_can_check:
                    for mv in queen_moves:
                        # mvからキングに直線/斜線で攻撃できるか
                        if self._can_attack_from(mv, ai_king_pos):
                            self.player_queen_can_check = True
                            break
            except Exception:
                pass
            
            # 脅威レベルの計算
            threat_level = 0
            
            # クイーンがキングに近い
            if queen_to_king_dist <= 2:
                threat_level += 50
            elif queen_to_king_dist <= 4:
                threat_level += 30
            elif queen_to_king_dist <= 6:
                threat_level += 15
            
            # チェックできる状態
            if self.player_queen_can_check:
                threat_level += 30
            
            # 迅雷を持っている可能性がある
            if self.likely_has_lightning:
                threat_level += 20
            
            # 手札が多い（PPも潤沢と推測）
            if self.hand_count >= 3:
                threat_level += 10
            
            self.queen_lightning_threat_level = min(threat_level, 100)
            
            # 脅威レベルが50以上ならコンボ脅威とみなす
            if self.queen_lightning_threat_level >= 50:
                self.queen_lightning_threat = True
            
            # チェックメイトまでの推定ターン数
            if self.player_queen_can_check and self.likely_has_lightning:
                if queen_to_king_dist <= 2:
                    self.turns_to_checkmate_estimate = 1  # 迅雷で即チェックメイトの危険
                elif queen_to_king_dist <= 4:
                    self.turns_to_checkmate_estimate = 2
                else:
                    self.turns_to_checkmate_estimate = 3
            elif self.player_queen_near_king:
                self.turns_to_checkmate_estimate = 3
            
        except Exception:
            pass
    
    def _can_attack_from(self, from_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> bool:
        """from_posからtarget_posを攻撃できるか（クイーンの動き）"""
        fr, fc = from_pos
        tr, tc = target_pos
        
        # 同じ行
        if fr == tr:
            return True
        # 同じ列
        if fc == tc:
            return True
        # 斜め
        if abs(fr - tr) == abs(fc - tc):
            return True
        
        return False
    
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
        
        # ★クイーン+迅雷コンボの脅威を追加
        if self.queen_lightning_threat:
            threat += 30
        
        # 手札数に応じた脅威
        threat += min(self.hand_count * 5, 25)
        
        return min(threat, 100)
    
    def get_defensive_priority(self) -> str:
        """防御の優先度を決定
        
        Returns:
            'critical': 即座に防御が必要（チェックメイト1-2ターン以内）
            'high': 高優先度で防御（3ターン以内）
            'medium': 中程度の防御
            'low': 通常
        """
        if self.turns_to_checkmate_estimate <= 1:
            return 'critical'
        elif self.turns_to_checkmate_estimate <= 2:
            return 'high'
        elif self.queen_lightning_threat:
            return 'medium'
        else:
            return 'low'


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
    
    def get_player_queen(self) -> Optional[Any]:
        """プレイヤーのクイーンを取得"""
        for p in self.player_pieces:
            if getattr(p, 'name', '') == 'Q':
                return p
        return None
    
    def get_player_queen_threat_info(self) -> Dict[str, Any]:
        """プレイヤーのクイーンによる脅威情報を取得
        
        Returns:
            {
                'queen': プレイヤーのクイーン駒,
                'queen_pos': クイーンの位置,
                'distance_to_ai_king': AIキングまでの距離,
                'can_check_now': 今すぐチェックできるか,
                'can_check_in_one_move': 1手でチェックできるか,
                'is_frozen': クイーンが凍結されているか,
                'threat_level': 脅威レベル (0-100),
            }
        """
        result = {
            'queen': None,
            'queen_pos': None,
            'distance_to_ai_king': 99,
            'can_check_now': False,
            'can_check_in_one_move': False,
            'is_frozen': False,
            'threat_level': 0,
        }
        
        player_queen = self.get_player_queen()
        if not player_queen:
            return result
        
        result['queen'] = player_queen
        queen_row = getattr(player_queen, 'row', 0)
        queen_col = getattr(player_queen, 'col', 0)
        result['queen_pos'] = (queen_row, queen_col)
        result['is_frozen'] = self._is_piece_frozen(player_queen)
        
        if not self.ai_king_pos:
            return result
        
        # AIキングまでの距離
        ai_kr, ai_kc = self.ai_king_pos
        distance = abs(queen_row - ai_kr) + abs(queen_col - ai_kc)
        result['distance_to_ai_king'] = distance
        
        # 凍結されていたら脅威は低い
        if result['is_frozen']:
            result['threat_level'] = 5
            return result
        
        # クイーンの移動先を取得
        try:
            queen_moves = self.get_valid_moves(player_queen, ignore_check=True)
            
            # 今すぐチェックできるか
            if self.ai_king_pos in queen_moves:
                result['can_check_now'] = True
                result['threat_level'] = 90
            else:
                # 1手でチェック位置に行けるか
                for mv in queen_moves:
                    # mvからキングに攻撃できるか
                    mv_r, mv_c = mv
                    # 直線・斜線でキングを攻撃できるか
                    if mv_r == ai_kr or mv_c == ai_kc:  # 同じ行/列
                        result['can_check_in_one_move'] = True
                        break
                    if abs(mv_r - ai_kr) == abs(mv_c - ai_kc):  # 斜め
                        result['can_check_in_one_move'] = True
                        break
        except Exception:
            pass
        
        # 脅威レベルの計算
        if not result['can_check_now']:
            threat = 0
            
            # 距離に基づく脅威
            if distance <= 2:
                threat = 70
            elif distance <= 4:
                threat = 50
            elif distance <= 6:
                threat = 30
            else:
                threat = 10
            
            # 1手でチェックできるならボーナス
            if result['can_check_in_one_move']:
                threat += 20
            
            result['threat_level'] = min(threat, 100)
        
        return result
    
    def should_prioritize_queen_freeze(self) -> bool:
        """クイーンを凍結すべき優先度が高いか"""
        queen_info = self.get_player_queen_threat_info()
        
        # クイーンがいない or 既に凍結
        if not queen_info['queen'] or queen_info['is_frozen']:
            return False
        
        # チェック可能または脅威レベルが高い
        return (queen_info['can_check_now'] or 
                queen_info['can_check_in_one_move'] or
                queen_info['threat_level'] >= 50)
    
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
    
    改良版v3 (ベリーハード強化): 
    - チェック優先回避
    - 迅雷・暴風警戒時の戦略
    - 鉄壁・氷結の温存
    - コンボ対処
    - ★NEW: コンボ検出結果の統合
    - ★NEW: 2手先読み評価
    - ★NEW: プレイヤーパターン学習の活用
    """
    
    def __init__(self, board_analysis: BoardAnalysis, difficulty: int, ai_player, 
                 game_phase: str = None, opponent_analysis: 'OpponentAnalysis' = None,
                 combo_detector: 'CheckmateComboDetector' = None,
                 lookahead: 'LookaheadEvaluator' = None,
                 player_learner: 'PlayerPatternLearner' = None):
        self.analysis = board_analysis
        self.difficulty = difficulty
        self.ai_player = ai_player
        self.game_phase = game_phase or GamePhase.MIDGAME
        self.opponent_analysis = opponent_analysis
        self.combo_detector = combo_detector
        self.lookahead = lookahead
        self.player_learner = player_learner
        self._combo_cache = None
    
    def _get_combos(self) -> List[Dict[str, Any]]:
        """コンボ検出結果をキャッシュ付きで取得"""
        if self._combo_cache is None:
            if self.combo_detector:
                self._combo_cache = self.combo_detector.find_all_combos()
            else:
                self._combo_cache = []
        return self._combo_cache
    
    def _has_combo_for_card(self, card_name: str) -> Optional[Dict[str, Any]]:
        """指定カードに関連するコンボがあるか確認"""
        combos = self._get_combos()
        
        card_combo_mapping = {
            '暴風': ['queen_storm_check'],
            '迅雷': ['queen_lightning_checkmate'],
            '氷結': ['freeze_attack'],
        }
        
        relevant_combos = card_combo_mapping.get(card_name, [])
        
        for combo in combos:
            if combo.get('combo') in relevant_combos:
                return combo
        return None
    
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
        
        # ベリーハード専用: プレイヤーパターン学習に基づく補正
        if self.difficulty >= 4 and self.player_learner:
            base_score = self._apply_player_pattern_bonus(name, base_score)
        
        # 難易度による調整
        if self.difficulty >= 4:
            # ベリーハード: 状況に応じた評価を完全に重視
            return base_score
        elif self.difficulty == 3:
            # 高難易度: 状況に応じた評価を重視
            return base_score
        elif self.difficulty == 2:
            # 中難易度: やや状況を考慮
            return base_score * 0.85 + random.uniform(0, 15)
        else:
            # 低難易度: ランダム性を追加
            return base_score * 0.5 + random.uniform(0, 50)
    
    def _apply_player_pattern_bonus(self, card_name: str, base_score: float) -> float:
        """プレイヤーパターン学習に基づくスコア補正（ベリーハード専用）"""
        if not self.player_learner:
            return base_score
        
        # プレイヤーが攻撃的なら防御カードを優先
        if self.player_learner.is_player_aggressive():
            defensive_cards = {'鉄壁', '氷結'}
            if card_name in defensive_cards:
                base_score += 15
        
        # プレイヤーが防御的なら攻撃カードを優先
        elif self.player_learner.is_player_defensive():
            aggressive_cards = {'迅雷', '暴風', '灼熱'}
            if card_name in aggressive_cards:
                base_score += 10
        
        # プレイヤーがよく使うカードへの対策
        most_used = self.player_learner.get_most_used_cards(3)
        for used_card, _ in most_used:
            # プレイヤーが迅雷をよく使うなら鉄壁の価値UP
            if used_card == '迅雷' and card_name == '鉄壁':
                base_score += 10
            # プレイヤーが氷結をよく使うなら先に氷結を使う
            elif used_card == '氷結' and card_name == '氷結':
                base_score += 8
        
        return base_score
    
    def _should_save_card(self, card_name: str) -> bool:
        """カードを温存すべきかどうか判定
        
        鉄壁・氷結は序盤で軽率に使わない
        """
        if self.difficulty < 2:
            return False  # 低難易度では温存しない
        
        # ベリーハードでは温存判定をより緩く（攻撃的に）
        if self.difficulty >= 4:
            # チャンスがあれば積極的に使う
            combos = self._get_combos()
            if combos:
                return False  # コンボチャンスがあれば温存しない
        
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
        
        改良v4 (ベリーハード防御強化): 
        - 有効なターゲットがない場合は-1を返す
        - チェックメイトを防ぐための緊急使用を優先
        - ★クイーン+迅雷コンボへの対策を最優先
        - 脅威を与えている駒を優先
        - コンボ検出との連携
        - プレイヤー学習に基づく対策
        """
        # 有効なターゲットがなければ使用しない
        if not self.analysis.has_valid_freeze_target():
            return -1
        
        score = 40
        
        # === ★★★ クイーン+迅雷コンボ対策（最優先）★★★ ===
        # ベリーハード専用: プレイヤーの即詰め狙いを先読みして阻止
        if self.difficulty >= 4 and self.opponent_analysis:
            # クイーンが脅威になっている場合、凍結を最優先
            if self.opponent_analysis.queen_lightning_threat:
                threat_level = self.opponent_analysis.queen_lightning_threat_level
                
                # クイーンが凍結可能かチェック
                if self.analysis.should_prioritize_queen_freeze():
                    # 脅威レベルに応じた超高スコア
                    if threat_level >= 80:
                        return 99  # 即座に凍結（チェックメイト阻止）
                    elif threat_level >= 60:
                        return 96  # 非常に高い優先度
                    elif threat_level >= 40:
                        return 90  # 高い優先度
                    else:
                        score = max(score, 75)
                        
            # 推定ターン数が少ない場合も警戒
            if self.opponent_analysis.turns_to_checkmate_estimate <= 2:
                if self.analysis.should_prioritize_queen_freeze():
                    return 97  # 緊急凍結
                    
            # クイーンがキングに近い・チェック可能な場合の早期対応
            queen_info = self.analysis.get_player_queen_threat_info()
            if queen_info.get('queen') and not queen_info.get('is_frozen'):
                if queen_info.get('can_check_now'):
                    return 95  # 今すぐチェック可能なら凍結
                elif queen_info.get('can_check_in_one_move') and queen_info.get('threat_level', 0) >= 50:
                    score = max(score, 85)  # 1手後にチェック可能なら高優先
        
        # === コンボ検出 ===
        combo = self._has_combo_for_card('氷結')
        if combo and self.difficulty >= 4:
            score += combo.get('priority', 0) * 0.5
        
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
        
        # ベリーハード: 2手先読み評価
        if self.difficulty >= 4 and self.lookahead and targets:
            lookahead_score = self.lookahead.evaluate_after_freeze(targets[0][0])
            score += lookahead_score * 0.3
        
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
        
        改良v3 (ベリーハード強化):
        - チェック優先回避
        - 駒が密集している場合の防御（迅雷・暴風警戒）
        - ★コンボ検出: クイーン+暴風でチェック狙い
        - ★2手先読み評価
        """
        score = 30
        
        # 既に暴風効果がある場合は低評価
        if getattr(self.analysis.game, 'ai_next_move_can_jump', False):
            return 5
        
        # === ベリーハード専用: コンボ検出 ===
        if self.difficulty >= 4:
            combo = self._has_combo_for_card('暴風')
            if combo:
                # クイーン+暴風でチェック可能なら最優先
                if combo.get('combo') == 'queen_storm_check':
                    return 96  # 非常に高い優先度
        
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
        
        # ベリーハード: 2手先読み評価
        if self.difficulty >= 4 and self.lookahead:
            lookahead_score = self.lookahead.evaluate_after_storm()
            score += lookahead_score * 0.4
        
        return min(score, 95)
    
    def _eval_lightning(self) -> float:
        """迅雷の評価
        
        改良v3 (ベリーハード強化):
        - チェックメイトを狙える場合は最優先
        - プレイヤーキングを攻撃できる場合は高評価
        - ★コンボ検出: クイーン+迅雷で2手チェックメイト
        - ★2手先読み評価
        - 相手の迅雷への対抗策
        """
        score = 45
        
        # 既に連続ターンがある場合は低評価
        if getattr(self.analysis.game, 'ai_consecutive_turns', 0) >= 1:
            return 5
        
        # === ベリーハード専用: コンボ検出 ===
        if self.difficulty >= 4:
            combo = self._has_combo_for_card('迅雷')
            if combo:
                # クイーン+迅雷でチェックメイト狙い
                if combo.get('combo') == 'queen_lightning_checkmate':
                    escape_count = combo.get('escape_count', 5)
                    if escape_count <= 1:
                        return 99  # ほぼチェックメイト確定
                    elif escape_count <= 2:
                        return 95  # 非常に高い確率
                    else:
                        score += 40
        
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
        
        # ベリーハード: 2手先読み評価
        if self.difficulty >= 4 and self.lookahead:
            lookahead_score = self.lookahead.evaluate_after_lightning()
            score += lookahead_score * 0.5
        
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
        
        改良v4 (ベリーハード防御強化):
        - ★クイーン+迅雷コンボへの先制防御
        - 序盤でも脅威があれば使用
        - 相手のコンボ対処
        - 危機的状況での使用
        - プレイヤー学習に基づく対策
        """
        score = 35
        
        # === ★★★ クイーン+迅雷コンボへの先制防御（最優先）★★★ ===
        if self.difficulty >= 4 and self.opponent_analysis:
            # クイーン+迅雷の脅威が検出されている場合
            if self.opponent_analysis.queen_lightning_threat:
                threat_level = self.opponent_analysis.queen_lightning_threat_level
                
                # 脅威レベルに応じて鉄壁の価値を大幅UP
                if threat_level >= 70:
                    # 高脅威: 迅雷を無効化するために鉄壁を使用
                    # ただし氷結でクイーン凍結の方が効果的な場合もあるため、やや低めに
                    score = max(score, 85)
                elif threat_level >= 50:
                    score = max(score, 75)
                elif threat_level >= 30:
                    score = max(score, 60)
            
            # 推定チェックメイトまでのターン数が少ない場合
            if self.opponent_analysis.turns_to_checkmate_estimate <= 2:
                score = max(score, 80)
            
            # 防御優先度を確認
            defensive_priority = self.opponent_analysis.get_defensive_priority()
            if defensive_priority == 'critical':
                score = max(score, 88)
            elif defensive_priority == 'high':
                score = max(score, 75)
            elif defensive_priority == 'medium':
                score = max(score, 55)
                
            # クイーンがキングに近い場合は早めに鉄壁を張る
            queen_info = self.analysis.get_player_queen_threat_info()
            if queen_info.get('queen') and not queen_info.get('is_frozen'):
                distance = queen_info.get('distance_to_king', 99)
                if distance <= 2:
                    score = max(score, 78)  # 非常に近い
                elif distance <= 3:
                    score = max(score, 65)  # 近い
        
        # === 鉄壁の温存 ===
        # 序盤は温存（ただし、上記の脅威がある場合は使用する）
        if score < 55 and self._should_save_card('鉄壁'):
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
        
        # ベリーハード: プレイヤー学習に基づく補正
        if self.difficulty >= 4 and self.player_learner:
            most_used = self.player_learner.get_most_used_cards(3)
            for card, _ in most_used:
                if card in {'迅雷', '氷結', '暴風'}:
                    score += 10  # プレイヤーがこれらをよく使うなら鉄壁の価値UP
                    break
        
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
        
        return min(score, 92)
    
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
    
    改良版v3 (ベリーハード強化):
    - チェック優先回避
    - 迅雷・暴風警戒
    - 鉄壁・氷結の温存
    - コンボ対処
    - ★NEW: プレイヤーパターン学習の活用
    - ★NEW: コンボ検出との統合
    - ★NEW: 2手先読み評価
    - ★NEW: 攻撃的/防御的戦略の動的切り替え
    - ★NEW: カードの連携使用（コンボプレイ）
    """
    
    def __init__(self, difficulty: int, simulate_move_func=None, is_in_check_func=None):
        self.difficulty = difficulty
        self.simulate_move = simulate_move_func
        self.is_in_check = is_in_check_func
        
        # 難易度別のカード使用確率
        self.play_probabilities = {
            1: 0.35,  # Easy: 35%の確率でカードを使用
            2: 0.55,  # Normal: 55% (少し控えめに - 決着を遅らせる)
            3: 0.75,  # Hard: 75%
            4: 0.95,  # Expert: 95% (ベリーハード強化)
        }
        # 難易度別の試行回数
        self.max_attempts = {
            1: 1,
            2: 2,
            3: 2,  # Hard: 2回に制限（温存戦略）
            4: 4,  # Expert: 4回に増加（コンボ使用のため）
        }
        
        # ベリーハード専用: コンボ使用の追跡
        self._combo_cards_to_play: List[str] = []
        self._last_played_card: Optional[str] = None
    
    def should_play_card(self) -> bool:
        """カードを使用すべきかどうかの確率判定"""
        # コンボ中は必ず使用
        if self._combo_cards_to_play:
            return True
        
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
    
    def _detect_combo_opportunity(self, ai_player, game, chess, get_valid_moves_func) -> List[str]:
        """コンボ使用の機会を検出（ベリーハード専用）
        
        Returns:
            使用すべきカードの名前リスト（順序付き）
        """
        if self.difficulty < 4:
            return []
        
        combo_detector = CheckmateComboDetector(
            chess, game, get_valid_moves_func,
            self.simulate_move, self.is_in_check
        )
        combos = combo_detector.find_all_combos()
        
        if not combos:
            return []
        
        # 最も優先度の高いコンボを選択
        best_combo = combos[0]
        combo_type = best_combo.get('combo', '')
        
        # コンボタイプに応じたカード順序を決定
        hand_cards = {c.name for c in ai_player.hand.cards if c.can_play(ai_player)}
        
        if combo_type == 'queen_storm_check':
            if '暴風' in hand_cards:
                return ['暴風']
        
        elif combo_type == 'queen_lightning_checkmate':
            if '迅雷' in hand_cards:
                return ['迅雷']
        
        elif combo_type == 'freeze_attack':
            if '氷結' in hand_cards and '迅雷' in hand_cards:
                return ['氷結', '迅雷']
            elif '氷結' in hand_cards:
                return ['氷結']
        
        return []
    
    def _get_strategic_mode(self, analysis: BoardAnalysis, opponent_analysis: OpponentAnalysis) -> str:
        """現在の戦略モードを決定（ベリーハード専用）
        
        Returns:
            'aggressive': 攻撃的戦略
            'defensive': 防御的戦略
            'balanced': バランス戦略
        """
        if self.difficulty < 4:
            return 'balanced'
        
        # チェックメイトできそうなら攻撃的
        if analysis.ai_can_checkmate or analysis.player_in_check:
            return 'aggressive'
        
        # 危機的状況なら防御的
        if analysis.ai_in_check or analysis.ai_checkmate_threat:
            return 'defensive'
        
        # マテリアル差で判断
        material_diff = analysis.ai_material - analysis.player_material
        
        if material_diff > 5:
            return 'aggressive'  # 大幅に優勢なら攻めて決める
        elif material_diff < -3:
            return 'defensive'  # 劣勢なら守りながら挽回を狙う
        
        # プレイヤーの傾向に応じた対応
        learner = get_player_learner()
        if learner.is_player_aggressive():
            return 'defensive'  # 攻撃的プレイヤーには守りで対応
        elif learner.is_player_defensive():
            return 'aggressive'  # 防御的プレイヤーには攻めで対応
        
        return 'balanced'
    
    def _adjust_scores_by_strategy(self, card_scores: List[Tuple[int, float, str]], 
                                    strategy_mode: str) -> List[Tuple[int, float, str]]:
        """戦略モードに応じてスコアを調整（ベリーハード専用）"""
        if self.difficulty < 4:
            return card_scores
        
        adjusted = []
        
        aggressive_cards = {'迅雷', '暴風', '灼熱', '氷結', 'ハンです☆'}
        defensive_cards = {'鉄壁', '摂取', '2ドロー'}
        
        for idx, score, name in card_scores:
            if strategy_mode == 'aggressive':
                if name in aggressive_cards:
                    score *= 1.3
                elif name in defensive_cards:
                    score *= 0.8
            elif strategy_mode == 'defensive':
                if name in defensive_cards:
                    score *= 1.3
                elif name in aggressive_cards:
                    score *= 0.9
            
            adjusted.append((idx, score, name))
        
        return adjusted
    
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
        
        # === ベリーハード専用: コンボ検出 ===
        if self.difficulty >= 4:
            # コンボ使用中かチェック
            if self._combo_cards_to_play:
                next_card = self._combo_cards_to_play[0]
                for idx in playable_indices:
                    if ai_player.hand.cards[idx].name == next_card:
                        self._combo_cards_to_play.pop(0)
                        self._last_played_card = next_card
                        return idx
                # コンボカードが使えなくなった
                self._combo_cards_to_play = []
            
            # 新しいコンボ機会を検出
            combo_cards = self._detect_combo_opportunity(ai_player, game, chess, get_valid_moves_func)
            if combo_cards:
                # コンボの最初のカードを使用
                first_card = combo_cards[0]
                for idx in playable_indices:
                    if ai_player.hand.cards[idx].name == first_card:
                        if len(combo_cards) > 1:
                            self._combo_cards_to_play = combo_cards[1:]
                        self._last_played_card = first_card
                        return idx
        
        # === コンボ検出器と先読み評価器の作成 ===
        combo_detector = None
        lookahead = None
        player_learner = None
        
        if self.difficulty >= 4:
            combo_detector = CheckmateComboDetector(
                chess, game, get_valid_moves_func,
                self.simulate_move, self.is_in_check
            )
            lookahead = LookaheadEvaluator(
                chess, game, get_valid_moves_func,
                self.simulate_move, self.is_in_check
            )
            player_learner = get_player_learner()
        
        # カード評価（新しい分析を使用）
        evaluator = CardEvaluator(
            analysis, self.difficulty, ai_player,
            game_phase=game_phase,
            opponent_analysis=opponent_analysis,
            combo_detector=combo_detector,
            lookahead=lookahead,
            player_learner=player_learner
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
        
        # === ベリーハード専用: 戦略モードに応じたスコア調整 ===
        if self.difficulty >= 4:
            strategy_mode = self._get_strategic_mode(analysis, opponent_analysis)
            valid_card_scores = self._adjust_scores_by_strategy(valid_card_scores, strategy_mode)
        
        # スコアでソート
        valid_card_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 難易度に応じた選択
        if self.difficulty >= 4:
            # Expert (ベリーハード): 常に最高スコアのカードを選択
            chosen_idx = valid_card_scores[0][0]
            self._last_played_card = ai_player.hand.cards[chosen_idx].name
            return chosen_idx
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
    
    def notify_player_card_used(self, card_name: str, game_state: Dict[str, Any]):
        """プレイヤーがカードを使用したことを記録（学習用）"""
        if self.difficulty >= 4:
            learner = get_player_learner()
            learner.record_card_usage(card_name, game_state)
    
    def notify_turn_end(self):
        """ターン終了を記録（学習用）"""
        if self.difficulty >= 4:
            learner = get_player_learner()
            learner.record_turn_end()
    
    def notify_game_end(self):
        """ゲーム終了を記録（学習データ保存）"""
        if self.difficulty >= 4:
            learner = get_player_learner()
            learner.record_game_end()


def create_ai_card_strategy(difficulty: int, simulate_move_func=None, is_in_check_func=None) -> AICardStrategy:
    """AI カード戦略インスタンスを作成"""
    return AICardStrategy(difficulty, simulate_move_func, is_in_check_func)


# テスト用
if __name__ == "__main__":
    print("AI Card Strategy Module loaded successfully")
