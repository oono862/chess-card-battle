import os
import card_core

IMG='images'

def main():
    try:
        deck=card_core.make_rule_cards_deck()
    except Exception:
        deck=card_core.make_rule_cards_deck()
    names = []
    for c in deck.cards:
        names.append(c.name)
    uniq = list(dict.fromkeys(names))
    files = [f for f in os.listdir(IMG) if os.path.isfile(os.path.join(IMG,f))]
    print('Found images:', len(files))
    for n in uniq[:40]:
        matched = False
        for f in files:
            fn, ext = os.path.splitext(f)
            if fn == n:
                matched = True
                break
            if fn.replace(' ','').replace('\u3000','') == n.replace(' ','').replace('\u3000',''):
                matched = True
                break
        print(n, '->', 'OK' if matched else 'MISSING')

if __name__ == '__main__':
    main()
