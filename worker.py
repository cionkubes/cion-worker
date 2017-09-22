import asyncio
import os
import time

import docker
from logzero import logger

from cion_interface.service import service
from workq.worker import Orchestrator

# CERTS = os.path.join(os.path.expanduser('~'), '.docker', 'machine', 'machines', 'manager')
# tls_config = docker.tls.TLSConfig(
#     client_cert=(os.path.join(CERTS, 'cert.pem'), os.path.join(CERTS, 'key.pem')),
#     ca_cert=os.path.join(CERTS, 'ca.pem'),
#     verify=True
# )

# client = docker.DockerClient(base_url='tcp://192.168.99.100:2376', tls=tls_config)
client = docker.from_env()


@service.update.implement
async def update(svc_name, image):
    start = time.perf_counter()
    svc = client.services.get(svc_name)
    ret = svc.update(image=image, name=svc_name)
    end = time.perf_counter()
    logger.info(f"Update took {end - start} seconds.")
    await asyncio.sleep(10)
    return ret


def main():
    address = os.environ['ORCHESTRATOR_ADDRESS']

    logger.info(f"Address: {address}")
    addr, port = address.split(':')

    loop = asyncio.get_event_loop()

    orchestrator = Orchestrator(addr, port)

    loop.run_until_complete(orchestrator.join(service))
    loop.close()


if __name__ == '__main__':
    main()
