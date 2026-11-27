"""
Starts the JARVIS Mobile Bridge (port 8765) + a 4G/5G Public HTTPS Tunnel
using Windows built-in OpenSSH (`localhost.run`, fallback `serveo.net`).

Works over 4G/5G mobile data from anywhere in the world — zero Mixed Content,
zero port forwarding, zero VPN — and immediately sends the auto-configured
link to @jarvistdiubot!
"""
from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

MOBILE_DIR = Path(__file__).resolve().parent
JARVIS_DIR = MOBILE_DIR.parent / "JARVIS"


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def ensure_bridge_running() -> tuple[str, int]:
    sys.path.insert(0, str(MOBILE_DIR))
    import bridge_server

    token = bridge_server.TOKEN
    port = bridge_server.PORT
    if not port_open(port):
        py = JARVIS_DIR / ".venv" / "Scripts" / "python.exe"
        exe = str(py if py.exists() else sys.executable)
        subprocess.Popen(
            [exe, str(MOBILE_DIR / "bridge_server.py")],
            cwd=str(MOBILE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _ in range(30):
            if port_open(port):
                break
            time.sleep(0.3)
    return token, port


def send_telegram_link(https_url: str, token: str) -> None:
    try:
        sys.path.insert(0, str(JARVIS_DIR))
        import requests
        from memory.config_manager import get_plugin_config
        from plugins import telegram_remote as tr

        cfg = get_plugin_config("telegram_remote")
        bot_tok = tr._clean_token(cfg.get("bot_token"))
        ids = tr._parse_ids(cfg.get("allowed_chat_ids", ""))
        if not bot_tok or not ids:
            return
        cid = ids[0]
        pages = "https://icoder0198.github.io/jarvis-mobile/"
        auto_pages = (
            f"{pages}?pc={urllib.parse.quote(https_url, safe='')}"
            f"&token={urllib.parse.quote(token, safe='')}"
        )
        direct_pair = (
            f"{https_url}/?pc={urllib.parse.quote(https_url, safe='')}"
            f"&token={urllib.parse.quote(token, safe='')}"
        )
        msg = (
            "🌐 4G / 5G KOMPYUTER KOʻPRIGI (BRIDGE) FAOL!\n\n"
            "Endi telefoningiz 4G mobil internetda boʻlsa ham 💻 Kompyuter menyusi va ovozli buyruqlar 100% ishlaydi!\n\n"
            "1️⃣ APK ichida ulash uchun shu havolani nusxalab ⚙ Sozlama → '📋 Telegram havolasidan avtomatik toʻldirish' ga qoʻying:\n"
            f"{direct_pair}\n\n"
            "2️⃣ Yoki 1 bosishda HTTPS Web-Ilovani oching:"
        )
        requests.post(
            f"https://api.telegram.org/bot{bot_tok}/sendMessage",
            json={
                "chat_id": cid,
                "text": msg,
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🚀 4G Kompyuter + AI Ilovani Ochish", "url": auto_pages}]
                    ]
                },
            },
            timeout=15,
        )
        print("[Tunnel] Sent 4G/5G HTTPS pair link to Telegram!", flush=True)
    except Exception as exc:
        print(f"[Tunnel] Telegram notice failed: {exc}", flush=True)


def run_ssh_tunnel(port: int, token: str) -> None:
    # Auto-reconnect loop: prefers localhost.run, falls back to serveo.net
    providers = [
        ("nokey@localhost.run", re.compile(r"https://[a-z0-9-]+\.lhr\.life", re.I)),
        ("serveo.net", re.compile(r"https://[a-z0-9-]+\.serveo(?:usercontent)?\.net", re.I)),
    ]
    idx = 0
    while True:
        target, url_re = providers[idx % len(providers)]
        idx += 1
        print(f"[Tunnel] Connecting SSH HTTPS tunnel via {target}...", flush=True)
        proc = subprocess.Popen(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=NUL",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-R", f"80:127.0.0.1:{port}",
                target,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        sent = False
        assert proc.stdout is not None
        for line in proc.stdout:
            clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).strip()
            if not sent:
                m = url_re.search(clean)
                if m:
                    https_url = m.group(0)
                    print(f"[Tunnel] LIVE 4G/5G HTTPS URL: {https_url}", flush=True)
                    (MOBILE_DIR / "last_tunnel_url.txt").write_text(https_url, encoding="utf-8")
                    send_telegram_link(https_url, token)
                    sent = True
        proc.wait()
        print("[Tunnel] Disconnected, reconnecting in 4s...", flush=True)
        time.sleep(4)


def main() -> None:
    token, port = ensure_bridge_running()
    print(f"[Tunnel] Local Bridge ready on 127.0.0.1:{port}", flush=True)
    run_ssh_tunnel(port, token)


if __name__ == "__main__":
    main()
