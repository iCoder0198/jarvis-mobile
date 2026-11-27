"""
JARVIS Mobile Bridge Server (Port 8765)

Serves:
  1. The installable JARVIS Mobile PWA (`/` -> `pwa/index.html`)
  2. Token-protected PC Remote Control API (`/api/op`, `/api/metrics`, `/api/notes`)
  3. Native Uzbek Neural TTS (`/api/tts` using uz-UZ-SardorNeural)
  4. Optional Gemini AI proxy (`/api/ai`) so the phone works even without entering a key
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import socket
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

MOBILE_DIR = Path(__file__).resolve().parent
PWA_DIR = MOBILE_DIR / "pwa"
CFG_FILE = MOBILE_DIR / "bridge_config.json"
JARVIS_DIR = MOBILE_DIR.parent / "JARVIS"

if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))


def _load_or_create_config() -> dict:
    if CFG_FILE.exists():
        try:
            data = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("token"):
                return data
        except Exception:
            pass
    data = {
        "token": secrets.token_urlsafe(18),
        "port": 8765,
    }
    CFG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


BRIDGE_CFG = _load_or_create_config()
TOKEN = str(BRIDGE_CFG["token"])
PORT = int(BRIDGE_CFG.get("port", 8765))


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _verify_token(x_jarvis_token: str | None) -> None:
    if not x_jarvis_token or not hmac.compare_digest(
        str(x_jarvis_token).encode("utf-8"), TOKEN.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid JARVIS Mobile token")


app = FastAPI(title="JARVIS Mobile Bridge", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OpRequest(BaseModel):
    action: str
    arg: str = ""


class AiRequest(BaseModel):
    text: str
    image_b64: str = ""
    image_mime: str = ""


class TtsRequest(BaseModel):
    text: str


@app.get("/api/health")
def api_health(x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    return {"ok": True, "host": socket.gethostname(), "lan_ip": get_lan_ip()}


@app.get("/api/metrics")
def api_metrics(x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    import psutil

    batt = psutil.sensors_battery()
    return {
        "cpu": round(psutil.cpu_percent(interval=0.1)),
        "ram": round(psutil.virtual_memory().percent),
        "battery": round(batt.percent) if batt is not None else None,
        "plugged": bool(batt.power_plugged) if batt is not None else None,
    }


@app.get("/api/notes")
def api_notes(x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    from memory.config_manager import get_plugin_config
    from plugins import _telegram_ops as ops

    cfg = get_plugin_config("telegram_remote")
    notes = ops._load_json(ops._notes_file(cfg), [])
    return {"notes": notes if isinstance(notes, list) else []}


@app.post("/api/op")
def api_op(req: OpRequest, x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    from memory.config_manager import get_plugin_config
    from plugins import _telegram_ops as ops

    cfg = get_plugin_config("telegram_remote")
    try:
        job = ops.produce(req.action, req.arg, cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    out: dict = {"ok": True, "kind": job.get("kind", "text")}
    if job.get("kind") == "multi":
        texts = []
        for sub in job.get("jobs") or []:
            if sub.get("kind") == "text":
                texts.append(sub.get("text", ""))
            elif sub.get("kind") in ("voice", "audio") and sub.get("data"):
                out["audio_b64"] = base64.b64encode(sub["data"]).decode("ascii")
                out["audio_mime"] = sub.get("mime", "audio/ogg")
            elif sub.get("kind") == "photo" and sub.get("data"):
                out["image_b64"] = base64.b64encode(sub["data"]).decode("ascii")
                out["mime"] = sub.get("mime", "image/jpeg")
        out["text"] = "\n\n".join(t for t in texts if t)
    elif job.get("kind") == "photo":
        out["caption"] = job.get("caption", "")
        out["image_b64"] = base64.b64encode(job.get("data") or b"").decode("ascii")
        out["mime"] = job.get("mime", "image/jpeg")
    elif job.get("kind") in ("voice", "audio"):
        out["audio_b64"] = base64.b64encode(job.get("data") or b"").decode("ascii")
        out["audio_mime"] = job.get("mime", "audio/ogg")
        out["text"] = job.get("caption", "🔊 Audio tayyor.")
    else:
        out["text"] = job.get("text") or job.get("caption") or "Bajarildi."
    return out


@app.post("/api/tts")
def api_tts(req: TtsRequest, x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    from memory.config_manager import get_plugin_config
    from plugins import _telegram_ops as ops

    cfg = get_plugin_config("telegram_remote")
    voice = str(cfg.get("voice_name") or "uz-UZ-SardorNeural").strip()
    try:
        mp3 = ops._edge_tts_mp3(req.text.strip()[:700], voice=voice)
        return Response(content=mp3, media_type="audio/mpeg")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None


@app.post("/api/ai")
def api_ai(req: AiRequest, x_jarvis_token: str | None = Header(default=None)):
    _verify_token(x_jarvis_token)
    from google.genai import types as gtypes
    from core import gemini

    parts: list = [
        "Sen J.A.R.V.I.S san — Dilshod akaning shaxsiy mobil AI yordamchisi. "
        "Oʻzbek tilida aniq, qisqa va foydali javob ber.\n\nSavol: "
        + req.text.strip()
    ]
    if req.image_b64:
        try:
            raw = base64.b64decode(req.image_b64)
            parts.append(
                gtypes.Part.from_bytes(
                    data=raw, mime_type=req.image_mime or "image/jpeg"
                )
            )
        except Exception:
            pass
    reply = gemini.text(parts, timeout_ms=40_000, default="").strip()
    return {"reply": reply or "Hozircha javob olinmadi."}


@app.get("/")
@app.get("/index.html")
def serve_index():
    return FileResponse(PWA_DIR / "index.html")


@app.get("/{filename}")
def serve_static(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404)
    target = PWA_DIR / filename
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn

    ip = get_lan_ip()
    if sys.stdout is not None:
        print(f"[JARVIS-Mobile] Local Wi-Fi URL: http://{ip}:{PORT}/?pc=http://{ip}:{PORT}&token={TOKEN}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        log_config=None,
    )
