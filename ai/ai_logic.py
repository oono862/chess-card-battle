"""AI思考・行動ロジックモジュール

このモジュールは、AIの駒選択とカードプレイの判断を担当します。
"""

import random


def ai_make_move(game, chess, ai_player, CPU_DIFFICULTY, 
                 ai_continuation, get_valid_moves, simulate_move, 
                 is_in_check, apply_move, get_opponent_hand_count=None):
    """AIの手を選択して実行する
    
    Args:
        game: ゲームオブジェクト
        chess: チェスエンジンモジュール
        ai_player: AIプレイヤーオブジェクト
        CPU_DIFFICULTY: CPU難易度 (1-4)
        ai_continuation: 迅雷による連続ターンフラグ
        get_valid_moves: 有効な移動先を取得する関数
        simulate_move: 移動をシミュレートする関数
        is_in_check: チェック判定関数
        apply_move: 移動を適用する関数
        get_opponent_hand_count: 相手の手札数を取得する関数（オプション）
    
    Returns:
        dict: 更新されたAI状態
            {
                'ai_next_move_can_jump': bool,
                'ai_extra_moves_this_turn': int,
                'ai_consecutive_turns': int,
                'ai_continuation': bool
            }
    """
    # 戻り値用の状態辞書
    ai_state = {
        'ai_next_move_can_jump': False,
        'ai_extra_moves_this_turn': 0,
        'ai_consecutive_turns': 0,
        'ai_continuation': False
    }
    
    # Begin AI turn: restore PP and draw 1 card (simple turn-start behavior for AI).
    # If this ai_make_move() call is a continuation of a '迅雷' extra-turn
    # (ai_continuation True), skip start-of-turn effects (PP reset / draw).
    try:
        if ai_continuation:
            # This is an extra consecutive AI move; do not reset PP or draw.
            ai_state['ai_continuation'] = False
        else:
            ai_player.reset_pp()
            # draw 1 card if available and hand limit not exceeded
            if len(ai_player.hand.cards) < getattr(ai_player, 'hand_limit', 7):
                c = ai_player.deck.draw()
                if c:
                    ai_player.hand.add(c)
                    game.log.append("AI: ターン開始で1枚ドローしました。")
    except Exception:
        # defensive: ignore if ai_player not properly initialized
        pass

    # --- AI: consider playing a card before moving ---
    def ai_consider_play_card():
        """AIがカードをプレイするか判断する内部関数"""
        # aggressiveness / per-attempt probability by difficulty
        # increased base play probability so AI uses cards more often on Easy/Normal
        probs = {1: 0.35, 2: 0.60, 3: 0.80, 4: 0.98}
        p_play = probs.get(CPU_DIFFICULTY, 0.45)
        if not ai_player.hand.cards:
            return False

        # Gather simple board metrics to influence card choice (mobility, high-value targets)
        try:
            my_move_count = 0
            opp_move_count = 0
            for p in chess.pieces:
                try:
                    moves = get_valid_moves(p, ignore_check=True)
                except Exception:
                    moves = []
                if getattr(p, 'color', None) == 'black':
                    my_move_count += len(moves)
                else:
                    opp_move_count += len(moves)
        except Exception:
            my_move_count = opp_move_count = 0

        # highest opponent piece value (for targeting priorities)
        vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        highest_opp_val = 0
        try:
            for p in chess.pieces:
                if getattr(p, 'color', None) == 'white':
                    highest_opp_val = max(highest_opp_val, vals.get(getattr(p, 'name', ''), 0))
        except Exception:
            highest_opp_val = 0

        # decide how many attempts to try this turn (higher difficulty => more plays)
        max_attempts = {1: 1, 2: 2, 3: 3, 4: 4}.get(CPU_DIFFICULTY, 2)
        attempts = 0
        made_any = False
        played_names = set()  # avoid repeating the same card multiple times in one AI think session
        
        while attempts < max_attempts:
            # if random roll fails, stop trying further plays
            if random.random() > p_play:
                break

            # recompute playable indices according to current PP
            playable = [i for i, c in enumerate(ai_player.hand.cards) if c.can_play(ai_player) and c.name not in played_names]
            if not playable:
                break

            # prefer list (disruptive first), but adjust order by simple board heuristics
            names = [ai_player.hand.cards[i].name for i in playable]
            prefer = ['氷結', '灼熱', '暴風', '迅雷', '2ドロー', '錬成']
            
            # If opponent has much higher mobility, prefer blocking (灼熱)
            if opp_move_count > my_move_count + 4:
                if '灼熱' in prefer:
                    prefer.remove('灼熱')
                    prefer.insert(0, '灼熱')
            
            # If AI has low mobility, prefer buffs that grant movement (暴風/迅雷)
            if '暴風' in prefer:
                # Estimate whether 暴風 (jump) would actually increase AI mobility.
                try:
                    before_moves = my_move_count
                    added = 0
                    try:
                        # set a temporary flag so get_valid_moves considers jump
                        prev_flag_game = getattr(game, 'ai_next_move_can_jump', None)
                        try:
                            setattr(game, 'ai_next_move_can_jump', True)
                        except Exception:
                            pass
                        # recompute AI move count with jump
                        with_jump = 0
                        for p in chess.pieces:
                            try:
                                if getattr(p, 'color', None) == 'black':
                                    with_jump += len(get_valid_moves(p, ignore_check=True))
                            except Exception:
                                pass
                        added = with_jump - before_moves
                    finally:
                        # restore flags
                        try:
                            if prev_flag_game is None:
                                try:
                                    delattr(game, 'ai_next_move_can_jump')
                                except Exception:
                                    pass
                            else:
                                setattr(game, 'ai_next_move_can_jump', prev_flag_game)
                        except Exception:
                            pass
                    # prefer 暴風 only if it yields at least one extra legal move
                    if my_move_count < opp_move_count and added > 0:
                        prefer.remove('暴風')
                        prefer.insert(0, '暴風')
                    elif my_move_count < opp_move_count and added <= 0:
                        # don't aggressively pick 暴風 if it doesn't increase mobility
                        if '暴風' in prefer:
                            prefer.remove('暴風')
                            # reinsert lower in preference
                            pref_tail = ['迅雷', '2ドロー', '錬成']
                            for t in pref_tail:
                                if t in prefer:
                                    prefer.insert(prefer.index(t), '暴風')
                                    break
                except Exception:
                    # fallback to original behavior if any error
                    if my_move_count < opp_move_count and '暴風' in prefer:
                        prefer.remove('暴風')
                        prefer.insert(0, '暴風')
            
            # If there are no good non-king targets, deprioritize 氷結
            try:
                opp_non_king_exists = any(getattr(p, 'color', None) == 'white' and getattr(p, 'name', None) != 'K' for p in chess.pieces)
            except Exception:
                opp_non_king_exists = False
            if not opp_non_king_exists and '氷結' in prefer:
                # move 氷結 to the end so AI won't pick it unless nothing better
                prefer = [x for x in prefer if x != '氷結'] + ['氷結']
            
            # If opponent has a high-value piece, prioritize 氷結
            if highest_opp_val >= 5:
                if '氷結' in prefer:
                    prefer.remove('氷結')
                    prefer.insert(0, '氷結')
            
            chosen_idx = None
            # Difficulty-aware selection: for Normal+ use a scoring function to pick the best card
            if CPU_DIFFICULTY >= 2:
                scores = {}
                
                # helper: estimate added mobility from 暴風 for current board
                def estimate_jump_added():
                    try:
                        before = 0
                        for p in chess.pieces:
                            try:
                                if getattr(p, 'color', None) == 'black':
                                    before += len(get_valid_moves(p, ignore_check=True))
                            except Exception:
                                pass
                        # toggle jump flag
                        prev_game_flag = getattr(game, 'ai_next_move_can_jump', None)
                        try:
                            try:
                                setattr(game, 'ai_next_move_can_jump', True)
                            except Exception:
                                pass
                            with_jump = 0
                            for p in chess.pieces:
                                try:
                                    if getattr(p, 'color', None) == 'black':
                                        with_jump += len(get_valid_moves(p, ignore_check=True))
                                except Exception:
                                    pass
                        finally:
                            # restore
                            try:
                                if prev_game_flag is None:
                                    try:
                                        delattr(game, 'ai_next_move_can_jump')
                                    except Exception:
                                        pass
                                else:
                                    setattr(game, 'ai_next_move_can_jump', prev_game_flag)
                            except Exception:
                                pass
                        return with_jump - before
                    except Exception:
                        return 0

                # precompute some context used in heuristics
                try:
                    candidates = []
                    for p in chess.pieces:
                        if p.color != 'black':
                            continue
                        v = get_valid_moves(p, ignore_check=True)
                        for mv in v:
                            candidates.append((p, mv))
                    
                    capture_ops = 0
                    for p, mv in candidates:
                        tgt = chess.get_piece_at(mv[0], mv[1])
                        if tgt is not None and getattr(tgt, 'color', None) == 'white':
                            capture_ops += 1
                except Exception:
                    capture_ops = 0

                for idx in playable:
                    try:
                        card = ai_player.hand.cards[idx]
                        name = card.name
                        # base score from preference order (higher better)
                        base = 0
                        if name in prefer:
                            base = (len(prefer) - prefer.index(name)) * 10
                        else:
                            base = 5
                        score = base
                        # heuristics per card
                        if name == '暴風':
                            added = estimate_jump_added()
                            # reward if jump actually increases mobility
                            score += max(0, added) * 8
                        elif name == '氷結':
                            # prefer freezing non-king high-value pieces
                            try:
                                best_v = 0
                                for p in chess.pieces:
                                    if getattr(p, 'color', None) == 'white' and getattr(p, 'name', '') != 'K':
                                        v = {'P':1,'N':3,'B':3,'R':5,'Q':9}.get(getattr(p, 'name', ''), 0)
                                        best_v = max(best_v, v)
                                score += best_v * 6
                            except Exception:
                                pass
                        elif name == '灼熱':
                            # useful when opponent mobility >> ours
                            score += max(0, opp_move_count - my_move_count) * 6
                        elif name == '迅雷':
                            # prefer if capture opportunities exist or we have mobility to exploit
                            score += capture_ops * 8
                            # also prefer when AI mobility is lower than opponent
                            if my_move_count < opp_move_count:
                                score += 6
                        elif name == '2ドロー':
                            if len(ai_player.hand.cards) <= 2:
                                score += 20
                        elif name == '錬成':
                            # small preference to generate immediate value
                            score += 5
                        scores[idx] = score
                    except Exception:
                        scores[idx] = 0

                # pick best according to difficulty randomness
                if scores:
                    best_idx = max(scores, key=scores.get)
                    if CPU_DIFFICULTY == 2:
                        # Normal: 80% pick best, 20% choose random among playable
                        if random.random() < 0.8:
                            chosen_idx = best_idx
                        else:
                            chosen_idx = random.choice(playable)
                    elif CPU_DIFFICULTY == 3:
                        # Hard: 95% pick best
                        if random.random() < 0.95:
                            chosen_idx = best_idx
                        else:
                            chosen_idx = random.choice(playable)
                    else:
                        # Very-hard: always pick best
                        chosen_idx = best_idx
                else:
                    chosen_idx = random.choice(playable)
            else:
                # Easy: keep original simple preference/random behavior
                for pref in prefer:
                    if pref in names:
                        chosen_idx = playable[names.index(pref)]
                        break
                if chosen_idx is None:
                    chosen_idx = random.choice(playable)

            # attempt play via unified resolver so AI follows same rules as player
            try:
                ok, msg = game.play_card_for(ai_player, chosen_idx)
                card_name = ai_player.hand.cards[chosen_idx].name if 0 <= chosen_idx < len(ai_player.hand.cards) else None
                if ok:
                    made_any = True
                    # record that we've just used this card to avoid repeating it
                    if card_name:
                        played_names.add(card_name)
                else:
                    try:
                        game.log.append(f"AI: カードの使用に失敗しました: {msg}")
                    except Exception:
                        pass
                    # if failed due to unusable context, avoid retrying same card
                    if card_name:
                        played_names.add(card_name)
            except Exception as e:
                try:
                    game.log.append(f"AI: カード使用中に例外が発生しました: {e}")
                except Exception:
                    pass

            attempts += 1

        return made_any

    # attempt to play a card (may mutate ai state)
    try:
        prev_turn_active = getattr(game, 'turn_active', False)
        # allow AI to play via game.play_card_for which requires turn_active
        game.turn_active = True
        ai_consider_play_card()
        game.turn_active = prev_turn_active
    except Exception:
        try:
            game.turn_active = prev_turn_active
        except Exception:
            pass

    # (animation rendering moved to draw_panel where board metrics are available)
    candidates = []  # list of (piece, move)
    for p in chess.pieces:
        if p.color != 'black':
            continue
        # Use wrapper to respect freeze/blocked tiles; ignore self-check here and handle per difficulty
        v = get_valid_moves(p, ignore_check=True)
        for mv in v:
            candidates.append((p, mv))

    if not candidates:
        game.log.append('AI: 動ける手がありません')
        return ai_state

    # Difficulty 1: fully random
    if CPU_DIFFICULTY == 1:
        sel = random.choice(candidates)

    # Difficulty 2: avoid moves that leave black in check; otherwise random
    elif CPU_DIFFICULTY == 2:
        safe = []
        for p, mv in candidates:
            newp = simulate_move(p, mv[0], mv[1])
            if not is_in_check(newp, 'black'):
                safe.append((p, mv))
        sel = random.choice(safe) if safe else random.choice(candidates)

    # Difficulty 3: prefer captures (highest piece value captured)
    elif CPU_DIFFICULTY == 3:
        best = []
        best_score = -999
        values = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        for p, mv in candidates:
            tgt = chess.get_piece_at(mv[0], mv[1])
            score = values.get(tgt.name,0) if tgt else 0
            if score > best_score:
                best_score = score
                best = [(p,mv)]
            elif score == best_score:
                best.append((p,mv))
        sel = random.choice(best)

    # Difficulty 4: prefer captures, avoid self-check, and favor higher-value captures
    else:
        best = []
        best_score = -999
        values = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        for p, mv in candidates:
            newp = simulate_move(p, mv[0], mv[1])
            if is_in_check(newp, 'black'):
                continue
            tgt = chess.get_piece_at(mv[0], mv[1])
            score = values.get(tgt.name,0) if tgt else 0
            if score > best_score:
                best_score = score
                best = [(p,mv)]
            elif score == best_score:
                best.append((p,mv))
        sel = random.choice(best) if best else random.choice(candidates)

    p, mv = sel
    apply_move(p, mv[0], mv[1])
    game.log.append(f"AI({CPU_DIFFICULTY}): {p.name} を {mv} に移動")
    
    # consume AI jump flag or extra moves
    try:
        # Prefer game-level flag if present (set by card_core), fallback to module-level
        if getattr(game, 'ai_next_move_can_jump', False):
            # consumed for one move
            try:
                game.ai_next_move_can_jump = False
                ai_state['ai_next_move_can_jump'] = False
            except Exception:
                pass
    except Exception:
        pass
    
    return ai_state
