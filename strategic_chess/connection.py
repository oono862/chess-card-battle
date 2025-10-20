
import socket
import threading
import queue
import json
import time

class NetworkManager:
    """
    安全・安定化したネットワーク管理クラス
    - ホスト/クライアント両対応（is_hostで切替）
    - JSON + 改行区切り (NDJSON) でシリアライズ
    - 受信は専用スレッドで行い、queue に積む
    - タイムアウト/例外処理/切断検知を実装
    既存コードと互換性のある public API:
      - __init__(host='localhost', port=50007, is_host=True)
      - start()
      - send(message: dict|list|str|int|float|bool|None)
      - close()
      - recv_queue (queue.Queue): 受信メッセージを取り出す
    """
    def __init__(self, host='localhost', port=50007, is_host=True, connect_timeout=5.0, retry=10):
        self.host = host
        self.port = port
        self.is_host = is_host
        self.sock = None        # listening socket (host only)
        self.conn = None        # connected socket
        self.recv_queue = queue.Queue()
        self.running = False
        self._recv_thread = None
        self._accept_thread = None
        self._connect_timeout = connect_timeout
        self._retry = retry
        self._send_lock = threading.Lock()
        self.last_error = None

    def start(self):
        if self.is_host:
            self._start_host()
        else:
            self._start_client()

    # --- Host side ---
    def _start_host(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(1)
        except Exception as e:
            self.last_error = f'ホスト初期化エラー: {e}'
            print(self.last_error)
            return

        self.running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self):
        try:
            self.sock.settimeout(1.0)
            while self.running and self.conn is None:
                try:
                    conn, addr = self.sock.accept()
                    self.conn = conn
                    self.conn.settimeout(1.0)
                    # 受信開始
                    self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                    self._recv_thread.start()
                    # 相手に握手メッセージ
                    self.send({"type": "hello", "role": "host"})
                    break
                except socket.timeout:
                    continue
        except Exception as e:
            self.last_error = f'acceptエラー: {e}'
            print(self.last_error)

    # --- Client side ---
    def _start_client(self):
        self.running = True
        t = threading.Thread(target=self._connect_loop, daemon=True)
        t.start()

    def _connect_loop(self):
        attempts = 0
        while self.running and self.conn is None and (self._retry <= 0 or attempts < self._retry):
            attempts += 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self._connect_timeout)
                s.connect((self.host, self.port))
                s.settimeout(1.0)
                self.conn = s
                # 受信開始
                self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                self._recv_thread.start()
                # 握手
                self.send({"type": "hello", "role": "client"})
                return
            except Exception as e:
                self.last_error = f'接続リトライ{attempts}: {e}'
                print(self.last_error)
                time.sleep(1.0)

    # --- Common recv loop ---
    def _recv_loop(self):
        buffer = b""
        try:
            while self.running and self.conn:
                try:
                    data = self.conn.recv(4096)
                    if not data:
                        # 相手が切断
                        self.recv_queue.put({"type": "disconnect"})
                        break
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line:
                            continue
                        try:
                            msg = json.loads(line.decode('utf-8'))
                        except Exception:
                            # 互換性のため、旧形式(str(dict))も許容してbest-effortでevalを使わずにパース
                            txt = line.decode('utf-8', errors='ignore').strip()
                            # かなり安全側に: 先頭/末尾が{}や[]でないものは文字列として扱う
                            if (txt.startswith('{') and txt.endswith('}')) or (txt.startswith('[') and txt.endswith(']')):
                                try:
                                    msg = json.loads(txt.replace("'", '"'))
                                except Exception:
                                    msg = {"type": "raw", "data": txt}
                            else:
                                msg = {"type": "raw", "data": txt}
                        self.recv_queue.put(msg)
                except socket.timeout:
                    continue
        except Exception as e:
            self.last_error = f'recvエラー: {e}'
            print(self.last_error)
        finally:
            # クリーンアップ
            if self.conn:
                try:
                    self.conn.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.conn.close()
                except Exception:
                    pass
            self.conn = None
            self.running = False
            # テスト用

    # --- Send ---
    def send(self, message):
        conn = self.conn
        if not conn:
            return False
        try:
            with self._send_lock:
                payload = json.dumps(message, ensure_ascii=False).encode('utf-8') + b"\n"
                conn.sendall(payload)
            return True
        except Exception as e:
            self.last_error = f'送信エラー: {e}'
            print(self.last_error)
            return False

    def close(self):
        self.running = False
        # close order: conn then sock
        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
