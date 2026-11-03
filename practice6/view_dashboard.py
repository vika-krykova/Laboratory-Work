import http.server
import socketserver
import webbrowser
import os
import socket
from pathlib import Path

def get_free_port(start_port=8000):
    port = start_port
    while port < 9000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    return 9000

PORT = get_free_port()

os.chdir(Path(__file__).parent.resolve())

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.getcwd(), **kwargs)

url = f"http://localhost:{PORT}/out/dashboard.html"

print("\n" + "="*50)
print("Локальный сервер запущен!")
print(f"Переход по ссылке: {url}")
print("="*50 + "\n")
print("Нажмите Ctrl+C, чтобы остановить сервер.\n")

webbrowser.open(url)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен. До встречи!")