import asyncio
import os

from cion_interface.service import service
from logzero import logger, loglevel

from configuration import config

loglevel(int(os.environ.get("LOGLEVEL", 10)))

cfg: Config = None


@service.distribute_to.implement
async def distribute_to(image):
    re = cfg.repos().repo(image).glob
    match = re.fullmatch(image)

    if not match:
        logger.info(f"New image '{image}' did not match pattern {re}.")
        return []

    user, repo, tag = match.group(1), match.group(2), match.group(3)

    services = cfg.services().using_image(f"{user}/{repo}")

    ret = []

    logger.debug(f"Image: {image}")
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
    repo_cfg = cfg.repos().repo(image)
    client = cfg.swarms()[swarm].client

    if repo_cfg.require_login():
        repo_cfg.login_to(client)

    logger.info(
        f"Updating image {image} in service {svc_name} on swarm {swarm}.")
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
    cfg = loop.run_until_complete(config())

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
