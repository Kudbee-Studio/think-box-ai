import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
result = s.connect_ex(('127.0.0.1', 8787))
print(f'Port 8787: {"open" if result == 0 else "closed"}')