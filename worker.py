import asyncio
import os

import docker
from logzero import logger, loglevel
loglevel(int(os.environ.get("LOGLEVEL", 10)))

from cion_interface.service import service
from workq.worker import Orchestrator

CERTS = os.path.join(os.path.expanduser('~'), '.docker', 'machine', 'machines', 'manager')
tls_config = docker.tls.TLSConfig(
    client_cert=(os.path.join(CERTS, 'cert.pem'), os.path.join(CERTS, 'key.pem')),
    ca_cert=os.path.join(CERTS, 'ca.pem'),
    verify=True
)

client = docker.DockerClient(base_url='tcp://192.168.99.100:2376', tls=tls_config)
# client = docker.from_env()
client.login(username='haraldfw', password='6Ci!*5Xai!sWRNA')


@service.update.implement
async def update(svc_name, image: str):
    repo, tag = image.split(':')
    pull = client.images.pull(repo, tag=tag)
    logger.info(f'Image pulled: {pull.id}')
    svc = client.services.get(svc_name)
    return svc.update_preserve(image=pull.id)


def main():
    from monkey_patch import setup
    setup()
    address = os.environ['ORCHESTRATOR_ADDRESS']

    logger.info(f"Address: {address}")
    addr, port = address.split(':')

    loop = asyncio.get_event_loop()

    orchestrator = Orchestrator(addr, port)

    loop.run_until_complete(orchestrator.join(service))
    loop.close()


if __name__ == '__main__':
    main()
