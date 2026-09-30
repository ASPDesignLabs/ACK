"""python -m freeform_studio --output ~/piper-recording-studio/output"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import secrets
import socket
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .config import Config

LOOPBACK = ("127.0.0.1", "localhost", "::1")


def lan_ip() -> str:
    """Best-effort address other devices can reach. Opens no connection; UDP connect only picks a route."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostname()
    finally:
        s.close()


def resolve_token(arg: str, output: Path, code: str) -> Optional[str]:
    if arg == "none":
        return None
    if arg != "auto":
        return arg
    path = output / "_freeform" / "token"
    if path.exists():
        return path.read_text().strip() or None
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(16)
    path.write_text(token + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="freeform_studio", description="Capture, transcribe, and review free-speech recordings for Piper training.")
    p.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder (default: %(default)s)")
    p.add_argument("--code", default="en-US", help="language code folder to export into (default: %(default)s)")
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from your phone")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--certfile", help="TLS certificate (needed for the phone microphone)")
    p.add_argument("--keyfile", help="TLS private key")
    p.add_argument("--token", default="auto", help="'auto' (remembered), 'none', or a value")
    p.add_argument("--asr-engine", choices=["faster-whisper", "fake"], default="faster-whisper")
    p.add_argument("--asr-model", default="small.en", help="e.g. small.en, medium.en, distil-large-v3")
    p.add_argument("--asr-device", choices=["cpu", "cuda", "auto"], default="cpu",
                   help="use cpu while training is running; cuda when the GPU is free")
    p.add_argument("--asr-compute-type", default="auto")
    p.add_argument("--asr-idle-unload", type=int, default=300, help="seconds idle before freeing the model (0 = never)")
    p.add_argument("--no-auto-transcribe", action="store_true")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if bool(args.certfile) != bool(args.keyfile):
        p.error("--certfile and --keyfile go together")

    output = Path(args.output).expanduser()
    if not output.is_dir():
        p.error(f"output folder not found: {output}")
    token = resolve_token(args.token, output, args.code)
    cfg = Config(output_dir=output, code=args.code, token=token, asr_engine=args.asr_engine, asr_model=args.asr_model,
                 asr_device=args.asr_device, asr_compute_type=args.asr_compute_type,
                 asr_idle_unload_s=args.asr_idle_unload, auto_transcribe=not args.no_auto_transcribe)

    from hypercorn.asyncio import serve
    from hypercorn.config import Config as HyperConfig
    from .app import create_app

    app = create_app(cfg)
    hyper = HyperConfig()
    hyper.bind = [f"{args.host}:{args.port}"]
    if args.certfile:
        hyper.certfile, hyper.keyfile = args.certfile, args.keyfile
        # hypercorn 0.14 + current h2/priority libraries drop the connection on Chrome's second HTTP/2 request.
        # Nothing here benefits from HTTP/2, so speak HTTP/1.1 only.
        hyper.alpn_protocols = ["http/1.1"]

    scheme = "https" if args.certfile else "http"
    host = lan_ip() if args.host in ("0.0.0.0", "::") else args.host
    url = f"{scheme}://{host}:{args.port}/" + (f"?token={token}" if token else "")
    print(f"\nFreeform Studio {__version__}  (ASR: {cfg.asr_engine}/{cfg.asr_model} on {cfg.asr_device})")
    print(f"  recordings and edits: {cfg.root}")
    print(f"  open on your phone:   {url}")
    if not token and args.host not in LOOPBACK:
        print("\n  WARNING: no access token and reachable from your network. Anyone on it can read and change your recordings.")
    if not args.certfile:
        print("  note: the phone microphone needs https; add --certfile/--keyfile (see docs/VOICE_TRAINING_GUIDE.md).")
    print()
    try:
        asyncio.run(serve(app, hyper))
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
