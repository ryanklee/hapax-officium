"""Entry point for logos: web dashboard API server."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="System logos — web dashboard API server for the agent stack",
        prog="logos",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for API server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Bind port for API server (default: 8050)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on file changes (dev mode)",
    )
    args = parser.parse_args()

    # Launch API server (web dashboard backend)
    import uvicorn

    uvicorn.run(
        "logos.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
