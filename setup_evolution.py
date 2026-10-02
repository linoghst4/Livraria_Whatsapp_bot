"""Regista o webhook na Evolution API.

Uso:  python setup_evolution.py http://host.docker.internal:8000/webhook
(a Evolution em Docker, o bot no Windows)  ou  http://localhost:8000/webhook (ambos fora do Docker)
"""
import sys

import evolution

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    r = evolution.set_webhook(sys.argv[1])
    print(r.status_code, r.text)
