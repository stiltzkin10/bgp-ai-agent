import asyncio
import argparse
from src.server import BGPServer
from src.config import load_config


async def main():
    parser = argparse.ArgumentParser(description="Asyncio BGP Speaker")
    parser.add_argument("config", help="Path to config.yaml")

    args = parser.parse_args()

    config = load_config(args.config)

    server = BGPServer(config)

    try:
        await server.start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
