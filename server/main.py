"""
Zee Server — FastAPI WebSocket backend.
Endpoints:
  GET  /health  — status & model info
  WS   /ws      — streaming chat
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ZEE_MODEL   = os.getenv("ZEE_MODEL",   "qwen2-vl")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888")
WS_PORT     = int(os.getenv("ZEE_WS_PORT", "8765"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Update search service URL from env at startup
    from server.search import search_service
    search_service.searxng_url = SEARXNG_URL
    print(f"[Zee Server] Ready  model={ZEE_MODEL}  host={OLLAMA_HOST}")
    yield
    print("[Zee Server] Shutdown.")


app = FastAPI(title="Zee AI Server", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status":      "online",
        "model":       ZEE_MODEL,
        "ollama_host": OLLAMA_HOST,
        "searxng":     SEARXNG_URL,
    }


@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    await ws.accept()

    from server.brain import ZeeBrain
    from server.tools import dispatch

    brain = ZeeBrain(model=ZEE_MODEL, host=OLLAMA_HOST)
    print("[WS] Client connected.")

    try:
        while True:
            raw     = await ws.receive_text()
            payload = json.loads(raw)

            if payload.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue

            user_text   = payload.get("text", "").strip()
            image_b64   = payload.get("image")          # optional pre-captured b64
            screen_mode = payload.get("screen_mode", False)

            if not user_text:
                continue

            # Auto-capture screen if screen_mode and no image provided
            if screen_mode and not image_b64:
                try:
                    from server.system_control import capture_screenshot_b64
                    image_b64 = capture_screenshot_b64()
                    await ws.send_json({"type": "action", "tag": "LOOK",
                                        "status": "screen captured"})
                except Exception as e:
                    await ws.send_json({"type": "action", "tag": "LOOK",
                                        "status": f"capture failed: {e}"})

            # Streaming token callback (async)
            async def on_token(token: str):
                await ws.send_json({"type": "token", "content": token})

            # Tool dispatcher with live WS notifications
            async def dispatch_with_notify(tag: str, args: dict):
                await ws.send_json({
                    "type": "action", "tag": tag,
                    "args": str(args)[:120],
                })
                result = await dispatch(tag, args)
                # Avoid sending raw image data in status channel
                status = (
                    "[image attached]"
                    if isinstance(result, dict) and "image" in result
                    else str(result)[:300]
                )
                await ws.send_json({
                    "type": "result", "tag": tag, "content": status,
                })
                return result

            final = await brain.stream_chat(
                user_text=user_text,
                image_b64=image_b64,
                on_token=on_token,
                tool_dispatcher=dispatch_with_notify,
            )

            await ws.send_json({"type": "done", "full_response": final})

    except WebSocketDisconnect:
        print("[WS] Client disconnected.")
    except Exception as e:
        print(f"[WS Error] {e}")
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


def run():
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=WS_PORT,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    run()
