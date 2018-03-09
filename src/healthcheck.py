import asyncio
import aiohttp
import sys


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.get(sys.argv[1]) as resp:
            if resp.status != 200:
                return 1, f"Error: Expected 200 got {resp.status}"
            else:
                json = await resp.json()
                return json['status'], json

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    status, msg = loop.run_until_complete(main())
    print(msg)
    exit(int(status))
