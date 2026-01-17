import socket
import json


def send_ipc_command(socket_path: str, command: str) -> dict:
    """
    Sends a command to the BGP Agent via Unix Domain Socket.
    """
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client_socket.connect(socket_path)
        request = json.dumps({"command": command})
        client_socket.sendall(request.encode())

        # Read response
        response_data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk

        return json.loads(response_data.decode())
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        client_socket.close()
