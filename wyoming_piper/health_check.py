"""Health check for the Wyoming server.

Used by the Dockerfile's HEALTHCHECK. Asking for info rather than just opening a
socket is deliberate: the port is bound by the OS, so a connect-only check stays
green even if the event loop is wedged. A Describe/Info round trip proves the
accept loop and the event handler are both still running.

Only imports wyoming, so it stays fast and does not depend on the optional
extras or on the backend being importable.
"""

import argparse
import asyncio
import sys

from wyoming.client import AsyncClient
from wyoming.info import Describe, Info


async def check(uri: str) -> None:
    """Ask the server for its info, or raise."""
    async with AsyncClient.from_uri(uri) as client:
        await client.write_event(Describe().event())

        while True:
            event = await client.read_event()
            if event is None:
                raise RuntimeError("Connection closed without info")

            if Info.is_type(event.type):
                info = Info.from_event(event)
                if not info.tts:
                    raise RuntimeError("No TTS programs in info")

                return

            # The server sends nothing else in response to Describe, but skip
            # anything unexpected instead of failing on it.


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uri", default="tcp://127.0.0.1:10200", help="unix:// or tcp://"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for info (default: 15)",
    )
    args = parser.parse_args()

    try:
        await asyncio.wait_for(check(args.uri), timeout=args.timeout)
    except Exception as err:  # pylint: disable=broad-except
        # Docker only reports the exit status, so the reason has to be printed.
        # It shows up in "docker inspect" as the health check's output.
        # TimeoutError, among others, has an empty message, so fall back to the
        # class name.
        print(f"unhealthy: {str(err) or type(err).__name__}", file=sys.stderr)
        sys.exit(1)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
