import asyncio
import os

from cion_interface.service import service
from logzero import logger, loglevel

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

    services = cfg.services().using_image(repo)

    ret = []

    logger.debug(f"Image: {repo}, tag: {tag}")
    logger.debug(f"Image services: {services}")

    for sname, swarm in cfg.swarms().swarms.items():
        logger.debug(f"Swarm: {sname}")
        logger.debug(f"Tag match: {swarm.tag_match}")

        if swarm.should_push(tag):
            logger.info(f"Swarm {sname} accepted ")
            ssvc = swarm.client.services.list()
            common = (svc.name for svc in ssvc if svc.name in services)
            ret.extend((sname, service, image) for service in common)

    if not len(ret):
        logger.warn(f"No targets found for image {image}")
    else:
        logger.info(f"Found targets for image {image}: {ret}")

    return ret


@service.update.implement
async def update(swarm, svc_name, image: str):
    client = cfg.swarms()[swarm].client

    logger.info(
        f"Updating image {image} in service.py {svc_name} on swarm {swarm}.")
    repo, tag = image.split(':')
    pull = client.images.pull(repo, tag=tag)
    logger.debug(f'Image pulled: {pull.id}')
    svc = client.services.get(svc_name)
    svc.update_preserve(image=pull.id)


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
    cfg = Config()
    cfg.on_new('swarms', login)
    loop.run_until_complete(cfg.init())

    worker = loop.run_until_complete(orchestrator.join(service))
    hc = setup_healthcheck(worker)

    handler = hc.make_handler()
    create_hc_srv = loop.create_server(handler, '0.0.0.0', 5000)
    srv = loop.run_until_complete(create_hc_srv)
    addr, port = srv.sockets[0].getsockname()

    logger.info(f'Healthcheck endpoint started on http://{addr}:{port}')

    try:
        loop.run_until_complete(worker.run_until_complete())
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()
        loop.run_until_complete(hc.shutdown())
        loop.run_until_complete(handler.shutdown(60.0))
        loop.run_until_complete(handler.finish_connections(1.0))
        loop.run_until_complete(hc.cleanup())
        cfg.teardown()

    loop.close()


def login(swarms):
    logger.info("Logged in to swarms.")
    swarms.login(username='haraldfw', password='6Ci!*5Xai!sWRNA')


def setup_healthcheck(worker):
    from aiohttp import web

    async def endpoint(request):
        ping = await worker.ping()
        return web.json_response({
            "orchestrator_ping": ping,
            "status": 0 if ping else 1
        }, status=200)

    app = web.Application()
    app.router.add_get("/", endpoint)
    return app


if __name__ == '__main__':
    main()
