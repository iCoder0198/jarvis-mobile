"""
Starts the JARVIS Mobile Bridge (port 8765) + a Cloudflare HTTPS Quick Tunnel
so the JARVIS Mobile PWA works with full Microphone, Camera, PWA Install,
and 4G/5G remote PC control from anywhere in the world.

Also sends the auto-configured clickable link straight to @jarvistdiubot!
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

MOBILE_DIR = Path(__file__).resolve().parent
JARVIS_DIR = MOBILE_DIR.parent / "JARVIS"
BIN_DIR = MOBILE_DIR / "bin"
CLOUDFLARED = BIN_DIR / "cloudflared.exe"
CFG_FILE = MOBILE_DIR / "bridge_config.json"

CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)


def ensure_cloudflared() -> Path:
    if CLOUDFLARED.is_file():
        try:
            res = subprocess.run(
                [str(CLOUDFLARED), "--version"],
                capture_output=True,
                timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if res.returncode == 0:
                return CLOUDFLARED
        except Exception:
            pass
        try:
            CLOUDFLARED.unlink(missing_ok=True)
        except Exception:
            pass
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CLOUDFLARED.with_suffix(".exe.tmp")
    print("[Tunnel] Downloading official cloudflared.exe...")
    urllib.request.urlretrieve(CLOUDFLARED_URL, tmp)
    tmp.replace(CLOUDFLARED)
    print("[Tunnel] Downloaded:", CLOUDFLARED)
    return CLOUDFLARED


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
        pythonw = JARVIS_DIR / ".venv" / "Scripts" / "pythonw.exe"
        exe = str(pythonw if pythonw.exists() else sys.executable)
        subprocess.Popen(
            [exe, str(MOBILE_DIR / "bridge_server.py")],
            cwd=str(MOBILE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if port_open(port):
                break
            time.sleep(0.3)
    return token, port


def send_telegram_link(https_url: str, lan_url: str, token: str) -> None:
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
        full_https = (
            f"{https_url}/?pc={urllib.parse.quote(https_url, safe='')}"
            f"&token={urllib.parse.quote(token, safe='')}"
        )
        full_lan = (
            f"{lan_url}/?pc={urllib.parse.quote(lan_url, safe='')}"
            f"&token={urllib.parse.quote(token, safe='')}"
        )
        msg = (
            "📱 J.A.R.V.I.S MOBILE ILOVASI TAYYOR!\n\n"
            "1️⃣ Pastdagi HTTPS tugmani Android Chrome'da oching (4G/5G va Wi-Fi dan ishlaydi, mikrofon + kamera + ilova oʻrnatish yoqiq):\n"
            f"{full_https}\n\n"
            "2️⃣ Chrome'da ⋮ → 'Bosh ekranga qoʻshish' (Install app) ni bosing — JARVIS alohida ilova boʻlib oʻrnatiladi!\n\n"
            f"🏠 Uy Wi-Fi manzili:\n{full_lan}"
        )
        requests.post(
            f"https://api.telegram.org/bot{bot_tok}/sendMessage",
            json={
                "chat_id": cid,
                "text": msg,
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "📱 J.A.R.V.I.S Mobil Ilovani Ochish", "url": full_https}]
                    ]
                },
            },
            timeout=15,
        )
        print("[Tunnel] Sent clickable mobile app link to Telegram!")
    except Exception as exc:
        print(f"[Tunnel] Telegram notice skipped: {exc}")


def main() -> None:
    token, port = ensure_bridge_running()
    cf = ensure_cloudflared()
    sys.path.insert(0, str(MOBILE_DIR))
    import bridge_server

    lan_url = f"http://{bridge_server.get_lan_ip()}:{port}"
    print(f"[Tunnel] Local Bridge: {lan_url}")
    print("[Tunnel] Opening Cloudflare HTTPS tunnel...")

    proc = subprocess.Popen(
        [
            str(cf),
            "tunnel",
            "--protocol",
            "http2",
            "--url",
            f"http://127.0.0.1:{port}",
            "--no-autoupdate",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    url_re = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)
    sent = False
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not sent:
            m = url_re.search(line)
            if m and not m.group(0).lower().startswith("https://api."):
                https_url = m.group(0)
                print(f"[Tunnel] LIVE HTTPS URL: {https_url}", flush=True)
                (MOBILE_DIR / "last_tunnel_url.txt").write_text(https_url, encoding="utf-8")
                send_telegram_link(https_url, lan_url, token)
                sent = True
    proc.wait()


if __name__ == "__main__":
    main()
