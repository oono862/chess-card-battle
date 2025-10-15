class Gimmick:
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def get_description(self):
        return self.description

    def apply_to_piece(self, piece):
        """ギミックを駒に適用する（デフォルトは何もしない）"""
        pass

class FireGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "炎",
            "盤面の駒のいないマスを1つ選択し選択したマスは相手は次の相手ターンから2ターン通れなくなる"
        )

    def apply_to_piece(self, piece):
        # 例: 指定のマスを変化
        if hasattr(piece, "hp"):
            piece.hp = max(0, piece.hp - 1)

class IceGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "氷",
            "相手の駒1つ選択、その駒は次の相手ターン終了まで操作不能になる"
        )

    def apply_to_piece(self, piece):
        # 例: 指定の駒を行動不能
        piece.frozen = True

class ThunderGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "雷",
            "2回行動できるようになる"
        )

    def apply_to_piece(self, piece):
        # 例: ２回行動
        piece.pending_thunder = 3

class WindGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "風",
            "障害物（駒）を一つ飛び越えられる"
        )

    def apply_to_piece(self, piece):
        # 例: pieceにmoved_by_wind属性を付与
        piece.moved_by_wind = True

class DoubleGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "2",
            "山札からカードを2枚引く"
        )

    def apply_to_piece(self, piece):
        # 例: pieceにdouble属性を付与
        piece.doubled = True

class ExplosionGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "e",
            "カードを山札から1枚引き、手札からカードを1枚選び捨てる"
        )

    def apply_to_piece(self, piece):
        # 例: pieceにexplosion属性を付与
        piece.explosive = True

class CollectGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "収",
            "ランダムに墓地のカードを回収"
        )

    def apply_to_piece(self, piece):
        # 例: pieceにcollect属性を付与
        piece.collector = True

class RecoveryGimmick(Gimmick):
    def __init__(self):
        super().__init__(
            "回",
            "2コスト回復"
        )

    def apply_to_piece(self, piece):
        # 例: pieceにrecovery属性を付与
        piece.healer = True

def get_gimmick_list():
    return [
        DoubleGimmick(),
        ExplosionGimmick(),
        CollectGimmick(),
        RecoveryGimmick(),
        FireGimmick(),
        IceGimmick(),
        ThunderGimmick(),
        WindGimmick()
    ]

__all__ = [
    "Gimmick",
    "FireGimmick",
    "IceGimmick",
    "ThunderGimmick",
    "WindGimmick",
    "DoubleGimmick",
    "ExplosionGimmick",
    "CollectGimmick",
    "RecoveryGimmick",
    "get_gimmick_list"
]
