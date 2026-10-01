# SPDX-License-Identifier: GPL-3.0-or-later
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
from .netcheck import LOOPBACK, find_cert_pair, lan_ip, pick_advertised_host, port_state, san_info
from .privacy import apply_offline_defaults, private_umask, sync_warning


def die(message: str) -> None:
    """A startup problem, in plain words: no usage dump, no traceback."""
    print(f"\nCan't start: {message}\n", file=sys.stderr)
    sys.exit(2)


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
    # Created with mode 0600 in the same step, so there is never a moment when another account could read it.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    return token


def main(argv: Optional[list] = None) -> int:
    with private_umask():   # everything this run creates is readable by you alone
        return _run(argv)


def _run(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="freeform_studio", description="Capture, transcribe, and review free-speech recordings for Piper training.")
    p.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder (default: %(default)s)")
    p.add_argument("--code", default="en-US", help="language code folder to export into (default: %(default)s)")
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from your phone")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--certs-dir", help="folder holding your mkcert certificate + key; the newest pair is used "
                                       "(easier than --certfile/--keyfile, nothing to mistype)")
    p.add_argument("--certfile", help="TLS certificate (needed for the phone microphone)")
    p.add_argument("--keyfile", help="TLS private key")
    p.add_argument("--token", default="auto", help="'auto' (remembered), 'none', or a value")
    p.add_argument("--asr-engine", choices=["faster-whisper", "fake"], default="faster-whisper")
    p.add_argument("--asr-model", default="small.en", help="e.g. small.en, medium.en, distil-large-v3, or the path of a model folder")
    p.add_argument("--allow-model-download", action="store_true",
                   help="let the server fetch a missing speech model itself. Off by default: the server never uses the internet; "
                        "fetch a model once, on purpose, with: python -m freeform_studio.models fetch small.en")
    p.add_argument("--asr-device", choices=["cpu", "cuda", "auto"], default="cpu",
                   help="use cpu while training is running; cuda when the GPU is free")
    p.add_argument("--asr-compute-type", default="auto")
    p.add_argument("--asr-idle-unload", type=int, default=300, help="seconds idle before freeing the model (0 = never)")
    p.add_argument("--no-auto-transcribe", action="store_true")
    p.add_argument("--backup-dir", default="~/backups/freeform-studio", help="where backups are kept (default: %(default)s)")
    p.add_argument("--backup-every", type=float, default=6.0, metavar="HOURS",
                   help="back up automatically this often, but only when something has changed (default: %(default)s)")
    p.add_argument("--no-auto-backup", action="store_true", help="don't back up on a timer (the Back up now button still works)")
    p.add_argument("--min-free-mb", type=int, default=500, help="refuse new audio when the disk has less than this free (default: %(default)s)")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    apply_offline_defaults(args.allow_model_download)   # before anything imports the Hugging Face libraries
    if bool(args.certfile) != bool(args.keyfile):
        p.error("--certfile and --keyfile go together")
    if args.certs_dir:
        if args.certfile:
            p.error("use either --certs-dir or --certfile/--keyfile, not both")
        pair = find_cert_pair(Path(args.certs_dir))
        if pair is None:
            die(f"no certificate pair found in {args.certs_dir}\n  It should contain files like 192.168.1.2+2.pem and "
                f"192.168.1.2+2-key.pem (made by mkcert). List the folder with:  ls {args.certs_dir}")
        args.certfile, args.keyfile = str(pair[0]), str(pair[1])
        print(f"using certificate {pair[0].name}")

    output = Path(args.output).expanduser()
    if not output.is_dir():
        die(f"output folder not found: {output}")
    cert_ips = []
    if args.certfile:
        for what, path in (("certificate", args.certfile), ("key", args.keyfile)):
            if not Path(path).expanduser().is_file():
                die(f"the {what} file was not found: {path}\n  Check the path (a placeholder like <your-ip> left in the "
                        f"command will do this). List your certificates with:  ls ~/piper-recording-studio/certs")
        args.certfile, args.keyfile = str(Path(args.certfile).expanduser()), str(Path(args.keyfile).expanduser())
        info = san_info(Path(args.certfile))
        if info["error"]:
            die(f"the certificate could not be read: {info['error']}")
        cert_ips = info["ips"]
    if port_state(args.host, args.port) == "in_use":
        die(f"port {args.port} is already in use (is Freeform Studio already running in another terminal?). "
                f"Stop it, or choose another port with --port.")
    token = resolve_token(args.token, output, args.code)
    cfg = Config(output_dir=output, code=args.code, token=token, asr_engine=args.asr_engine, asr_model=args.asr_model,
                 asr_device=args.asr_device, asr_compute_type=args.asr_compute_type,
                 asr_allow_download=args.allow_model_download,
                 asr_idle_unload_s=args.asr_idle_unload, auto_transcribe=not args.no_auto_transcribe,
                 backup_dir=Path(args.backup_dir).expanduser(), backup_every_hours=0.0 if args.no_auto_backup else args.backup_every,
                 min_free_mb=args.min_free_mb)

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
    warn = None
    if args.host in ("0.0.0.0", "::"):
        host, warn = pick_advertised_host(lan_ip(), cert_ips)
    else:
        host = args.host
    q = f"?token={token}" if token else ""
    url = f"{scheme}://{host}:{args.port}/{q}"
    print(f"\nFreeform Studio {__version__}  (ASR: {cfg.asr_engine}/{cfg.asr_model} on {cfg.asr_device})")
    print(f"  recordings and edits: {cfg.root}")
    print(f"  backups:              {cfg.backup_dir}" + (f" (every {cfg.backup_every_hours:g} h when something has changed)" if cfg.backup_every_hours > 0 else " (automatic backups off)"))
    print(f"  open on your phone:   {url}")
    print(f"  open on this PC:      {scheme}://localhost:{args.port}/{q}")
    if warn:
        print(f"  NOTE: {warn}")
    print("  can't connect? run this in a second terminal:  python -m freeform_studio.doctor --port "
          f"{args.port}" + (f" --certs-dir {args.certs_dir}" if args.certs_dir else " --certfile <same cert> --keyfile <same key>" if args.certfile else ""))
    if not token and args.host not in LOOPBACK:
        print("\n  WARNING: no access token and reachable from your network. Anyone on it can read and change your recordings.")
    if not args.certfile:
        print("  note: the phone microphone needs https; add --certfile/--keyfile (see docs/VOICE_TRAINING_GUIDE.md).")
    if cfg.asr_engine == "faster-whisper":
        print("  speech model:         " + ("may be downloaded by the server on first use (--allow-model-download)" if args.allow_model_download
                                            else "loaded from this computer only; the server never uses the internet"))
    for folder, what in ((cfg.root, "Your recordings folder"), (cfg.backup_dir, "Your backup folder")):
        warning = sync_warning(folder, what) if folder else None
        if warning:
            print(f"\n  WARNING: {warning}")
    print()
    try:
        asyncio.run(serve(app, hyper))
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
