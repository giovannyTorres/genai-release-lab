"""Worker entrypoint; all domain logic is shared with the API package."""

import asyncio
from release_lab.worker import run

asyncio.run(run())
