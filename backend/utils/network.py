import socket


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            s.connect(("10.0.0.1", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())
