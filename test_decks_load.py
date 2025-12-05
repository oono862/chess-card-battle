#!/usr/bin/env python3
import sys, os, json
sys.path.insert(0, 'c.c.b')
from game.deck_manager import load_saved_decks

print("Testing deck loading...")
decks = load_saved_decks()
print(f"Loaded {len(decks) if decks else 0} slots")

if decks:
    for i, d in enumerate(decks):
        if d:
            name = d.get('name', 'no name')
            cards_count = len(d.get('cards', []))
            print(f"  Slot {i}: {name} ({cards_count} cards)")
        else:
            print(f"  Slot {i}: None")
else:
    print("No decks loaded!")

# Also check saved_decks.json directly
print("\nDirect JSON check:")
if os.path.exists("saved_decks.json"):
    with open("saved_decks.json", encoding='utf-8') as f:
        data = json.load(f)
        if 'decks' in data:
            print(f"JSON has 'decks' list with {len(data['decks'])} items")
            for i, d in enumerate(data['decks'][:3]):  # Show first 3
                if d:
                    print(f"  Item {i}: {d.get('name', '?')}")
                else:
                    print(f"  Item {i}: None")
else:
    print("saved_decks.json not found!")
