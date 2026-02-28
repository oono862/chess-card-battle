"""AIモジュール初期化

このパッケージは、AI関連の機能を提供します。
- ai_logic: AIの駒移動とカード使用の判断
- card_strategy: 戦略的なカード選択と盤面分析

改良版v3 (侵攻ルート予測):
- チェック優先回避
- 迅雷・暴風警戒時の駒配置
- 鉄壁・氷結の温存
- コンボ対処
- ★NEW: プレイヤーカード使用時の侵攻ルート予測
- ★NEW: 防御カード自動選択（短期決着防止）
"""

from .ai_logic import ai_make_move
from .card_strategy import (
    AICardStrategy,
    BoardAnalysis,
    CardEvaluator,
    create_ai_card_strategy,
    GamePhase,
    OpponentAnalysis,
    ThreatPredictor,
    DefensiveStrategy,
)

__all__ = [
    'ai_make_move',
    'AICardStrategy',
    'BoardAnalysis',
    'CardEvaluator',
    'create_ai_card_strategy',
    'GamePhase',
    'OpponentAnalysis',
    'ThreatPredictor',
    'DefensiveStrategy',
]
