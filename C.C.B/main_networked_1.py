
import pygame
import socket
import threading
import json
import queue

pygame.init()
WIDTH, HEIGHT = 640, 640
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ネットワークチェス")
font = pygame.font.SysFont("NotoSans", 24)
clock = pygame.time.Clock()

PORT = 50007
BUFFER_SIZE = 4096
ENCODING = 'utf-8'

role = None
sock = None
recv_queue = queue.Queue()
current_turn = 'white'
selected_piece = None
pieces = []

# --- ユーティリティ（仮） ---
def get_clicked_pos(pos):
    x, y = pos
    return y // 80, x // 80

def get_piece_at(row, col, pieces):
    for p in pieces:
        if p.row == row and p.col == col:
            return p
    return None

def move_piece(piece, to_row, to_col):
    piece.row = to_row
    piece.col = to_col

def send_message(sock, data):
    try:
        json_data = json.dumps(data)
        sock.sendall(json_data.encode(ENCODING))
    except Exception as e:
        print("送信エラー:", e)

def recv_thread(sock):
    while True:
        try:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                break
            message = json.loads(data.decode(ENCODING))
            recv_queue.put(message)
        except:
            break

# --- UI 選択 ---
def draw_role_selection():
    screen.fill((240, 240, 240))
    title = font.render("役割を選んでください", True, (0, 0, 0))
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 100))

    host_rect = pygame.Rect(WIDTH//2 - 150, 200, 300, 60)
    client_rect = pygame.Rect(WIDTH//2 - 150, 300, 300, 60)
    pygame.draw.rect(screen, (100, 200, 100), host_rect)
    pygame.draw.rect(screen, (100, 100, 200), client_rect)

    screen.blit(font.render("ホスト（白）", True, (255,255,255)), (host_rect.x + 70, host_rect.y + 15))
    screen.blit(font.render("クライアント（黒）", True, (255,255,255)), (client_rect.x + 50, client_rect.y + 15))
    pygame.display.flip()
    return host_rect, client_rect

def select_role():
    global role
    while True:
        host_btn, client_btn = draw_role_selection()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if host_btn.collidepoint(event.pos):
                    role = 'host'; return
                elif client_btn.collidepoint(event.pos):
                    role = 'client'; return
        clock.tick(30)

# --- 通信初期化 ---
def init_network(role):
    global sock
    if role == 'host':
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", PORT))
        s.listen(1)
        print("接続待機中...")
        conn, addr = s.accept()
        sock = conn
        print("接続:", addr)
    else:
        ip = input("ホストのIPアドレスを入力: ")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, PORT))
        sock = s
        print("接続成功")

    threading.Thread(target=recv_thread, args=(sock,), daemon=True).start()

# --- メイン ---
select_role()
init_network(role)

# 仮の駒
class Piece:
    def __init__(self, row, col, color):
        self.row = row
        self.col = col
        self.color = color

    def get_valid_moves(self, pieces):
        return [(self.row+1, self.col)] if self.color == 'white' else [(self.row-1, self.col)]

white = Piece(6, 0, 'white')
black = Piece(1, 0, 'black')
pieces = [white, black]

running = True
while running:
    screen.fill((255, 255, 255))
    for p in pieces:
        color = (0, 0, 0) if p.color == 'black' else (255, 255, 255)
        pygame.draw.circle(screen, color, (p.col*80+40, p.row*80+40), 30)

    is_player_turn = (role == 'host' and current_turn == 'white') or (role == 'client' and current_turn == 'black')

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and is_player_turn:
            row, col = get_clicked_pos(event.pos)
            clicked = get_piece_at(row, col, pieces)
            if selected_piece:
                if (row, col) in selected_piece.get_valid_moves(pieces):
                    move_piece(selected_piece, row, col)
                    send_message(sock, {"from": [selected_piece.row, selected_piece.col], "to": [row, col]})
                    current_turn = 'black' if current_turn == 'white' else 'white'
                    selected_piece = None
            else:
                if clicked and clicked.color == current_turn:
                    selected_piece = clicked

    # 相手の手を処理
    while not recv_queue.empty():
        move = recv_queue.get()
        from_row, from_col = move["from"]
        to_row, to_col = move["to"]
        piece = get_piece_at(from_row, from_col, pieces)
        if piece:
            move_piece(piece, to_row, to_col)
            current_turn = 'black' if current_turn == 'white' else 'white'

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
