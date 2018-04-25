import asyncio
import logging
import socket
import os

from async_rethink import connection

from cion_interface.service import service
from logzero import logger, loglevel

from configuration import config, Config

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
    translated_img = f"{user}/{repo}"
    logger.debug(f"Image: {image} -> {translated_img}")

    logger.debug(f"Services: {cfg.services().services}")
    services = cfg.services().using_image(f"{user}/{repo}")
    logger.debug(f"Services using image {translated_img}: {services}")

    ret = []

    for svc_name, service in services.items():
        for env_name in service.environments:
            environment = cfg.environments()[env_name]

            if environment.should_push(tag):
                logger.debug(f"Environment {env_name} accepted image {image} with tag {tag}")
                ret.append((env_name, svc_name, image))

    if not len(ret):
        logger.warn(f"No targets found for image {image}")
    else:
        logger.info(f"Found targets for image {image}: {ret}")

    return ret


@service.update.implement
async def update(env, svc_name, image: str):
    repo_cfg = cfg.repos().repo(image)
    environment = cfg.environments()[env]

    if repo_cfg.require_login():
        repo_cfg.login_to(environment)
    
    logger.info(
        f"Updating image {image} for service {svc_name} in environment {env}.")

    environment.update(svc_name, image)


async def main(loop):
    from workq.worker import Orchestrator
    from monkey_patch import setup
    setup()

    address = os.environ['ORCHESTRATOR_ADDRESS']

    db_host = os.environ.get('DATABASE_HOST')
    db_port = os.environ.get('DATABASE_PORT')

    logger.info(f"Address: {address}")
    addr, port = address.split(':')
    orchestrator = Orchestrator(addr, port)

    global cfg
    cfg = await config()

    worker = await orchestrator.join(service)

    hc = setup_healthcheck(worker)
    handler = hc.make_handler()

    srv = await loop.create_server(handler, '0.0.0.0', 5000)
    addr, port = srv.sockets[0].getsockname()

    logger.debug(f'Healthcheck endpoint started on http://{addr}:{port}')

    db = await connection(db_host, db_port)
    log_handler = db.get_log_handler(f"worker-{worker.own_ip()}")
    log_handler.setLevel(logging.INFO)
    logger.addHandler(log_handler)

    try:
        await worker.run_until_complete()
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()
        await hc.shutdown()
        await handler.shutdown(60.0)
        await handler.finish_connections(1.0)
        await hc.cleanup()
        cfg.teardown()


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
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
