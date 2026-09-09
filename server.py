"""Entry point: uvicorn server."""

import uvicorn

from app.config import load_config


def main() -> None:
    cfg = load_config()
    server_cfg = cfg.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = int(server_cfg.get("port", 8080))
    log_level = server_cfg.get("log_level", "info")

    print(f"\n  Sable Search Engine")
    print(f"  http://{host}:{port}")
    print(f"  API docs: http://{host}:{port}/docs\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
    )


if __name__ == "__main__":
    main()
