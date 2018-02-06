from functools import lru_cache

name = 'services'


def map(images):
    return Services(images)


class Services:
    def __init__(self, services: dict):
        self.services = {name: Service(img) for name, img in services.items()}

        self.__dict__.update(self.services)

    def __getitem__(self, item):
        return self.services[item]

    @lru_cache()
    def using_image(self, image):
        return {name: service for name, service in self.services.items() if service.image == image}


class Service:
    def __init__(self, service):
        self.image = service['image-name']
        self.environments = service['environments']