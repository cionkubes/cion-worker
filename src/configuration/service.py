from functools import lru_cache

from configuration.abc import ConfigABC

class Services(ConfigABC):
    def __init__(self):
        super().__init__()
        self.services = {}

    def set(self, service):
        self.services[service["name"]] = Service(service)

    def delete(self, service):
        self.services.pop(service['name'], None)

    def using_image(self, image):
        return {name: service for name, service in self.services.items() if service.image == image}

    def __getitem__(self, item):
        return self.services[item]

    def __repr__(self):
        return repr(self.services)


name = 'services'
init = Services

class Service:
    def __init__(self, service):
        self.image = service['image-name']
        self.environments = service['environments']

    def __repr__(self):
        return repr({
            "image": self.image,
            "envs": self.environments
        })
