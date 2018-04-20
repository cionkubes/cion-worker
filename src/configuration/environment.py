import re
import kube
import base64
import docker
import os.path
import functools
import posixpath as ppath

from logzero import logger
from kubernetes import APISAServer
from abc import ABCMeta, abstractmethod


name = 'swarms'


def map(environments):
    return Environments({name: convert(name, env) for name, env in environments.items()})


def convert(name, environment):
    assert 'mode' in environment, f"Environment {name} missing required option 'mode'."

    mode = environment['mode']
    assert mode in modes, f"Environment {name} using unknown mode '{mode}'."

    params = environment.get('parameters', {})

    convert_fn = modes[mode]
    return convert_fn(name, environment, **params)


def convert_tls(name, environment, **params):
    url = environment['tls']['url']

    cert = environment['tls']['cert']
    key = environment['tls']['key']
    ca = environment['tls']['ca']

    for file in [cert, key, ca]:
        assert os.path.isfile(file), f"File {os.path.abspath(file)} does not exist!"

    tls_config = docker.tls.TLSConfig(
        client_cert=(cert, key),
        ca_cert=ca,
        verify=True
    )

    client = docker.DockerClient(base_url=url, tls=tls_config, **params)
    return DockerSwarm(name, environment, client)


def convert_env(name, environment, **params):
    return DockerSwarm(name, environment, docker.from_env(**params))


def convert_sa(name, environment, **params):
    url = environment['tls']['url']

    ca = environment['tls']['ca']
    token = environment['tls']['token']
    jwt = base64.b64decode(token).decode()

    proxy = APISAServer(url, token=jwt, cafile=ca)
    cluster = kube.Cluster(url=url, proxy=proxy)
    return K8sCluster(name, environment, cluster)


modes = {
    'tls': convert_tls,
    'from_env': convert_env,
    'k8s_serviceaccount': convert_sa
}


class Environments:
    def __init__(self, environments: dict):
        self.environments = environments

    def __getitem__(self, item):
        return self.environments[item]

    def items(self):
        return self.environments.items()


class Environment(metaclass=ABCMeta):
    def __init__(self, name, environment):
        self.name = name
        self.sign = bool(environment.get('sign', False))
        self.has_tag_match = 'tag-match' in environment

        if self.has_tag_match:
            self.tag_match = re.compile(environment['tag-match'])

    def should_push(self, tag):
        if not self.has_tag_match:
            return False

        return self.tag_match.fullmatch(tag)

    @abstractmethod
    def login(self, *args, **kwargs):
        pass

    @abstractmethod
    def services(self):
        pass

    @abstractmethod
    def update(self, svc_name, image):
        pass


class DockerSwarm(Environment):
    def __init__(self, name, environment, client):
        super().__init__(name, environment)
        self.client = client

    def login(self, *args, **kwargs):
        self.client.login(*args, **kwargs)

    def services(self):
        return (service.name for service in self.client.services.list())

    def update(self, svc_name, image):
        repo, tag = image.split(':')

        pull = self.client.images.pull(repo, tag=tag)
        logger.debug(f'Image pulled: {pull.id}')

        svc = self.client.services.get(svc_name)
        svc.update_preserve(image=pull.id)


class K8sCluster(Environment):
    def __init__(self, name, environment, cluster):
        super().__init__(name, environment)
        self.cluster = cluster
        self.namespace = environment.get('namespace', 'default')
        self.deployments = kube.DeploymentView(cluster, namespace=self.namespace)

    def login(self, *args, **kwargs):
        logger.debug(f'Attempting to login to kubernetes environment, image update may fail.')

    def services(self):
        for deployment in self.deployments:
            yield deployment.meta.name

    def update(self, svc_name, image):
        deployment = self.deployments.fetch(svc_name)
        
        self.cluster.proxy.patch(deployment.meta.link, patch={
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "image": image,
                                "name": svc_name
                            }
                        ]
                    }
                }
            }
        })