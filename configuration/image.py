name = 'images'


def map(images):
    return Images(images)


class Images:
    def __init__(self, images: dict):
        self.images = {name: Image(img) for name, img in images.items()}

        self.__dict__.update(self.images)

    def __getitem__(self, item):
        return self.images[item]


class Image:
    def __init__(self, image):
        self.services = image['services']