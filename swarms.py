import docker


def convert(name, swarm):
    assert 'mode' in swarm, f"Swarm {name} missing required option 'mode'."

    mode = swarm['mode']
    assert mode in modes, f"Swarm {name} using unknown mode '{mode}'."

    params = swarm.get('parameters', {})

    convert_fn = modes[mode]
    return convert_fn(name, swarm, **params)


def convert_tls(name, swarm, **params):
    url = swarm['url']

    cert = swarm['cert']
    key = swarm['key']
    ca = swarm['ca']

    tls_config = docker.tls.TLSConfig(
        client_cert=(cert, key),
        ca_cert=ca,
        verify=True
    )

    return docker.DockerClient(base_url=url, tls=tls_config, **params)


def convert_env(name, swarm, **params):
    return docker.from_env(**params)

modes = {
    'tls': convert_tls,
    'from_env': convert_env
}


def swarms_from_config(config_file):
    import yaml
    with open(config_file) as fd:
        swarms = yaml.load(fd)

        return Swarms({name: convert(name, swarm) for name, swarm in swarms.items()})


class Swarms:
    def __init__(self, swarms: dict):
        self.swarms = swarms

        self.__dict__.update(swarms)

    @property
    def list_swarms(self):
        return self.swarms.keys()

    def login(self, *args, **kwargs):
        for client in self.swarms.values():
            client.login(*args, **kwargs)

    def __getitem__(self, item):
        return self.swarms[item]