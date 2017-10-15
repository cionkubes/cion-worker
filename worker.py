import asyncio
import os

from logzero import logger, loglevel
from cion_interface.service import service

from swarms import swarms_from_config

loglevel(int(os.environ.get("LOGLEVEL", 10)))

swarms_file = os.environ.get("SWARM_CONFIG", "swarms.yml")
swarms = swarms_from_config(swarms_file)

swarms.login(username='haraldfw', password='6Ci!*5Xai!sWRNA')


@service.update.implement
async def update(svc_name, image: str):
    repo, tag = image.split(':')
    pull = swarms.test.images.pull(repo, tag=tag)
    logger.info(f'Image pulled: {pull.id}')
    svc = swarms.test.services.get(svc_name)
    return svc.update_preserve(image=pull.id)


def main():
    from workq.worker import Orchestrator
    from monkey_patch import setup
    setup()

    address = os.environ['ORCHESTRATOR_ADDRESS']

    logger.info(f"Address: {address}")
    addr, port = address.split(':')
    orchestrator = Orchestrator(addr, port)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(orchestrator.join(service))
    loop.close()


if __name__ == '__main__':
    main()
