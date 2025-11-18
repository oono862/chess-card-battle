"""Deck management system for loading, saving, and building decks."""

import os
import sys
import json
import logging

logger = logging.getLogger(__name__)


def get_main_module():
    """Get the main B.B.C module."""
    main_mod_name = "B.B.C"
    if main_mod_name in sys.modules:
        return sys.modules[main_mod_name]
    if "__main__" in sys.modules:
        return sys.modules["__main__"]
    return None


# Deck save file location
try:
    DECK_SAVE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saved_decks.json')
except Exception:
    DECK_SAVE_FILE = 'saved_decks.json'


def _custom_decks_dir():
    """Return path to custom decks directory (may not exist)."""
    try:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'decks')
    except Exception:
        return 'decks'


def list_custom_decks():
    """Return a list of custom deck basenames (without .json)."""
    d = _custom_decks_dir()
    out = []
    try:
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith('.json'):
                    out.append(os.path.splitext(fn)[0])
    except Exception:
        logger.exception("Error while listing custom decks")
    return out


def load_custom_deck_by_name(name: str):
    """Load a custom deck (list of card names) from decks/<name>.json.

    Returns list of card names or None on error.
    """
    d = _custom_decks_dir()
    path = os.path.join(d, f"{name}.json")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
    except Exception:
        logger.exception("Failed to load custom deck: %s", path)
    return None


def load_saved_decks():
    """保存されたデッキをJSONファイルから読み込む。最大9個。"""
    if not os.path.exists(DECK_SAVE_FILE):
        return [None] * 9  # 空の9スロット
    try:
        with open(DECK_SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 9スロット確保
            decks = data.get('decks', [])
            while len(decks) < 9:
                decks.append(None)
            return decks[:9]  # 最大9個まで
    except Exception:
        return [None] * 9


def save_decks_to_file(decks):
    """デッキリストをJSONファイルに保存"""
    try:
        with open(DECK_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'decks': decks}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"デッキ保存エラー: {e}")


def build_deck_for_mode(mode: str):
    """Return a Deck object appropriate for the chosen deck mode.

    - 'fixed' -> full rule deck (24 cards)
    - 'custom' -> trimmed deck (20 cards)
    """
    try:
        # Import card_core to access make_rule_cards_deck
        try:
            from card_core import make_rule_cards_deck
        except Exception:
            try:
                main = get_main_module()
                make_rule_cards_deck = getattr(main, 'make_rule_cards_deck', None)
                if make_rule_cards_deck is None:
                    raise ImportError("make_rule_cards_deck not found")
            except Exception:
                return None
        
        deck = make_rule_cards_deck()
        # make_rule_cards_deck already shuffles its pool; for custom decks
        # we trim to 20 and reshuffle so randomness is preserved.
        if mode == 'custom':
            try:
                deck.cards = deck.cards[:20]
                deck.shuffle()
            except Exception:
                pass
        return deck
    except Exception:
        # fallback: return whatever rule deck returns or raise
        try:
            from card_core import make_rule_cards_deck
            return make_rule_cards_deck()
        except Exception:
            return None


def build_ai_player(mode: str):
    """Create and return a PlayerState for the AI matching the deck mode."""
    try:
        # Import dependencies
        try:
            from card_core import PlayerState
        except Exception:
            main = get_main_module()
            PlayerState = getattr(main, 'PlayerState', None)
            if PlayerState is None:
                raise ImportError("PlayerState not found")
        
        deck = build_deck_for_mode(mode)
        if deck is None:
            return None
        deck.shuffle()
        return PlayerState(deck=deck)
    except Exception:
        return None


def build_game_from_card_names(names):
    """Build a Game whose player's deck contains cards named in `names`.

    This maps names to prototypes from make_rule_cards_deck(); unknown
    names are skipped. On failure, fall back to new_game_with_mode('custom').
    """
    try:
        # Import dependencies
        try:
            from card_core import Card, Deck, PlayerState, Game, make_rule_cards_deck
        except Exception:
            main = get_main_module()
            Card = getattr(main, 'Card', None)
            Deck = getattr(main, 'Deck', None)
            PlayerState = getattr(main, 'PlayerState', None)
            Game = getattr(main, 'Game', None)
            make_rule_cards_deck = getattr(main, 'make_rule_cards_deck', None)
            if any(x is None for x in [Card, Deck, PlayerState, Game, make_rule_cards_deck]):
                raise ImportError("Required card_core imports not found")
        
        proto_deck = make_rule_cards_deck()
        proto_map = {c.name: c for c in proto_deck.cards}
        
        # build a normalization map for prototypes to improve matching robustness
        def _norm_key(s: str) -> str:
            try:
                ss = str(s)
            except Exception:
                ss = s
            ss = ss.replace('\u3000', ' ')
            ss = ' '.join(ss.split())
            return ss
        
        proto_map_norm = {}
        for c in proto_deck.cards:
            k = _norm_key(c.name)
            proto_map_norm[k] = c
            proto_map_norm[k.replace(' ', '')] = c

        pool = []
        # allow some cards that are build-only (not included in make_rule_cards_deck)
        extra_map = {}
        try:
            import card_core as cc
            extra_map = {
                '命がけのギャンブル': getattr(cc, 'eff_risky_gamble', None),
                '負けるわけないだろwww': getattr(cc, 'eff_no_lose', None),
                '鉄壁': getattr(cc, 'eff_iron_wall', None),
                'ハンです☆': getattr(cc, 'eff_hand_discard', None),
            }
        except Exception:
            extra_map = {}

        def _norm(n: str) -> str:
            # normalize whitespace and common fullwidth space variants
            try:
                s = str(n)
            except Exception:
                s = n
            s = s.replace('\u3000', ' ')  # fullwidth space -> normal
            # collapse multiple whitespace and strip ends
            s = ' '.join(s.split())
            return s

        unmatched = []
        for nm in names:
            norm_nm = _norm(nm)
            # prefer normalized prototype lookup to avoid mismatch
            p = (proto_map.get(nm) or proto_map.get(norm_nm) or 
                 proto_map.get(norm_nm.replace(' ', '')) or 
                 proto_map_norm.get(norm_nm) or 
                 proto_map_norm.get(norm_nm.replace(' ', '')))
            
            if p is None:
                # try extra_map fallback with normalized keys
                eff = (extra_map.get(nm) or extra_map.get(norm_nm) or 
                       extra_map.get(norm_nm.replace(' ', '')))
                if eff:
                    try:
                        cost = 3 if norm_nm == '命がけのギャンブル' else (4 if norm_nm == '負けるわけないだろwww' else 2)
                        pool.append(Card(norm_nm, cost, eff))
                        continue
                    except Exception:
                        pass
                unmatched.append(nm)
                continue
            
            try:
                # clone prototype (best-effort)
                pool.append(Card(p.name, p.cost, p.effect, getattr(p, 'precheck', None)))
            except Exception:
                try:
                    pool.append(Card(p.name, p.cost, p.effect))
                except Exception:
                    continue

        # debug: report unmatched names and how many matched
        try:
            print(f"DEBUG: build_game_from_card_names - unmatched={unmatched}, matched_count={len(pool)}")
            print(f"DEBUG: pool sample names={[getattr(c,'name',None) for c in pool[:20]]}")
        except Exception:
            pass

        if not pool:
            print(f"DEBUG: build_game_from_card_names - no pool built from names")
            deck = build_deck_for_mode('custom')
        else:
            try:
                types_info = [type(c).__name__ for c in pool[:8]]
                print(f"DEBUG: pool types sample={types_info}")
            except Exception:
                pass
            
            deck = Deck(pool)
            
            try:
                deck_names_before = [(getattr(c,'name',None), id(c)) for c in deck.cards[:20]]
                print(f"DEBUG: deck names before shuffle={deck_names_before}")
                sys.stdout.flush()
            except Exception:
                pass
            
            try:
                deck.shuffle()
                deck_names_after = [(getattr(c,'name',None), id(c)) for c in deck.cards[:20]]
                print(f"DEBUG: deck names after shuffle={deck_names_after}")
                sys.stdout.flush()
            except Exception:
                # if shuffle fails, continue with unshuffled deck
                pass

        deck.shuffle()
        player = PlayerState(deck=deck)
        g = Game(player=player)
        
        try:
            g.setup_battle()
        except Exception:
            pass
        
        # debug: print initial hand and deck top after setup_battle
        try:
            hand_names = [c.name for c in g.player.hand.cards]
            deck_cards = getattr(g.player.deck, 'cards', [])
            deck_count = len(deck_cards)
            top_names = [c.name for c in deck_cards[:8]]
            print(f"DEBUG: after setup_battle hand={hand_names} deck_remaining={deck_count} top={top_names}")
        except Exception:
            pass
        
        return g
        
    except Exception as e:
        # Try to use the module logger if present
        try:
            logger.exception("Failed to build game from card names, falling back to custom deck")
        except Exception:
            try:
                import traceback
                print(f"DEBUG: build_game_from_card_names unexpected exception: {e}")
                traceback.print_exc()
            except Exception:
                print(f"DEBUG: build_game_from_card_names unexpected exception (no traceback available): {e}")
        
        # Fallback to new_game_with_mode
        try:
            main = get_main_module()
            new_game_with_mode = getattr(main, 'new_game_with_mode', None)
            if new_game_with_mode:
                return new_game_with_mode('custom')
        except Exception:
            pass
        
        return None
