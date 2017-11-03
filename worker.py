import asyncio
import os

from logzero import logger, loglevel
from cion_interface.service import service

from configuration import config, Config

loglevel(int(os.environ.get("LOGLEVEL", 10)))

cfg: Config = None


@service.distribute_to.implement
async def distribute_to(image):
    match = cfg.glob().fullmatch(image)

    if not match:
        logger.info(f"New image '{image}' did not match pattern {cfg.glob()}.")
        return []

    repo, tag = match.group(1), match.group(2)
    try:
        img = cfg.images().images[repo]
    except KeyError:
        logger.info(f"Image {repo} not configured.")
        return []

    ret = []

    logger.debug(f"Image: {repo}, tag: {tag}")
    logger.debug(f"Image services: {img.services}")

    for sname, swarm in cfg.swarms().swarms.items():
        logger.debug(f"Swarm: {sname}")
        logger.debug(f"Tag match: {swarm.tag_match}")

        if swarm.should_push(tag):
            ssvc = swarm.client.services.list()
            common = (svc.name for svc in ssvc if svc.name in img.services)
            ret.extend((sname, service) for service in common)

    if not len(ret):
        logger.warn(f"No targets found for image {image}")

    return ret


@service.update.implement
async def update(swarm, svc_name, image: str):
    client = cfg.swarms()[swarm].client

    logger.info(f"Updating image {image} in service {svc_name} on swarm {swarm}.")
    repo, tag = image.split(':')
    pull = client.images.pull(repo, tag=tag)
    logger.debug(f'Image pulled: {pull.id}')
    svc = client.services.get(svc_name)
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

    global cfg
    cfg = loop.run_until_complete(config())
    cfg.on_new('swarms', login)

    loop.run_until_complete(orchestrator.join(service))
    cfg.teardown()
    loop.close()

    
def login(swarms):
    logger.info("Logged in to swarms.")
    swarms.login(username='haraldfw', password='6Ci!*5Xai!sWRNA')


if __name__ == '__main__':
    main()
