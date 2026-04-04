"""
WebSocket Client — async bridge between Tkinter (sync) and Zee Server (async).
Runs its own event loop in a background thread.
Auto-reconnects with exponential back-off.
"""
import asyncio
import json
import threading
from typing import Callable, Optional

import websockets


class ZeeWSClient:
    def __init__(
        self,
        url: str = "ws://localhost:8765/ws",
        on_token:   Optional[Callable[[str], None]] = None,
        on_action:  Optional[Callable[[dict], None]] = None,
        on_done:    Optional[Callable[[str], None]]  = None,
        on_error:   Optional[Callable[[str], None]]  = None,
        on_connect: Optional[Callable[[], None]]     = None,
    ):
        self.url        = url
        self.on_token   = on_token
        self.on_action  = on_action
        self.on_done    = on_done
        self.on_error   = on_error
        self.on_connect = on_connect

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue]            = None
        self._connected = False
        self._thread: Optional[threading.Thread]        = None

    # ── Public (thread-safe) ──────────────────────────────────────────────────

    def start(self):
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ws-client"
        )
        self._thread.start()

    def send(self, payload: dict):
        """Thread-safe: enqueue a message to be sent over the WebSocket."""
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_loop(self):
        self._loop  = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue()
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=None,
                    ping_timeout=None,
                    close_timeout=5,
                ) as ws:
                    self._connected = True
                    backoff = 1.0
                    if self.on_connect:
                        self.on_connect()
                    
                    await asyncio.gather(
                        self._recv_loop(ws),
                        self._send_loop(ws)
                    )
            except Exception as e:
                self._connected = False
                if not isinstance(e, websockets.exceptions.ConnectionClosedOK):
                    if self.on_error:
                        self.on_error(f"Connection lost — retrying in {backoff:.0f}s ({e})")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)

    async def _recv_loop(self, ws):
        async for raw in ws:
            try:
                msg = json.loads(raw)
                t   = msg.get("type", "")
                if t == "token"  and self.on_token:
                    self.on_token(msg.get("content", ""))
                elif t in ("action", "result") and self.on_action:
                    self.on_action(msg)
                elif t == "done" and self.on_done:
                    self.on_done(msg.get("full_response", ""))
                elif t == "error" and self.on_error:
                    self.on_error(msg.get("message", "Unknown error"))
            except Exception as e:
                print(f"[WSClient] Parse error: {e}")

    async def _send_loop(self, ws):
        while True:
            payload = await self._queue.get()
            try:
                await ws.send(json.dumps(payload))
            except Exception as e:
                print(f"[WSClient] Send error: {e}")
                break  # exit cleanly so _connect_loop triggers reconnect


