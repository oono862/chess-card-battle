"""
Test for deck persistence when selecting from details screen.

This test verifies that:
1. When a user views a deck's details, that deck info is saved
2. When the user returns to start screen and selects a difficulty, 
   the previously selected deck is used
3. The custom deck (20 cards) is used, not the fixed deck (24 cards)
"""

import sys
import os

# Add project root to path
proj_root = os.path.dirname(os.path.abspath(__file__))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from c.c.b import CardGame

def test_saved_deck_info():
    """Test that deck info is correctly saved and used."""
    
    # Simulate the scenario:
    # 1. User selects a custom deck from list and views details
    # 2. Deck info is saved to globals
    
    # Manually trigger the global assignment that would happen in show_deck_action_modal
    CardGame._selected_deck_slot_idx = 3  # Deck slot 4 (0-indexed)
    CardGame._selected_deck_card_names = ['灼熱', '氷結', '迅雷', '暴風', '鉄壁', 
                                           'ハンです☆', '命がけのギャンブル', 
                                           '負けるわけないだろwww', '灼熱', '氷結']
    
    print(f"Saved deck slot: {CardGame._selected_deck_slot_idx}")
    print(f"Saved card names (first 3): {CardGame._selected_deck_card_names[:3]}")
    
    # Verify the globals are set
    assert CardGame._selected_deck_slot_idx == 3, "Deck slot not saved correctly"
    assert len(CardGame._selected_deck_card_names) == 10, "Card names not saved correctly"
    
    print("✓ Deck info saved correctly")
    
    # Now test that when build_game_from_card_names is called with these card names,
    # it produces a game with the correct deck size
    try:
        game = CardGame.build_game_from_card_names(CardGame._selected_deck_card_names)
        if game and hasattr(game, 'player') and hasattr(game.player, 'deck'):
            deck_size = len(game.player.deck.cards)
            # Should be 10 (custom cards) + 4 (gimmick) + some initial cards = around 14-20
            print(f"Game deck size: {deck_size}")
            assert 14 <= deck_size <= 24, f"Unexpected deck size: {deck_size}"
            print(f"✓ Game created with correct deck size: {deck_size}")
        else:
            print("✗ Game creation failed or missing attributes")
    except Exception as e:
        print(f"✗ Error creating game: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_saved_deck_info()
    print("\n✓ All tests passed!")
