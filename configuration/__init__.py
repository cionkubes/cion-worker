import os
import re
from collections import defaultdict

from async_rethink import Connection
import configuration.swarm
import configuration.image
from logzero import logger


class Glob:
    name = 'glob'

    @staticmethod
    def map(x):
        return re.compile(x)


async def config():
    cfg = Config()
    await cfg.init()
    return cfg


class Config:
    def __init__(self):
        self.addr = os.environ.get('DATABASE_HOST')
        self.port = os.environ.get('DATABASE_PORT')

        self.connection = Connection(self.addr, self.port)
        self.subscriptions = []
        self.documents = None
        self.latest_config = {}
        self.callbacks = defaultdict(lambda: [])

        self.configs = [
            swarm,
            image,
            Glob
        ]

    async def init(self):
        await self.connection.connect()

        self.documents = self.connection.observe('documents')

        async def get_current(name):
            q = self.connection.db().table('documents').get(name)
            return await self.connection.run(q)

        def map_cfg(cfg, x):
            try:
                return cfg.map(x)
            except:
                logger.exception("Got exception while updating config.")
                return None

        async def subscribe(cfg):
            subscription = self.documents\
                .map(lambda c: c['new_val'])\
                .filter(lambda new: new['name'] == cfg.name)\
                .start_with(await get_current(cfg.name))\
                .map(lambda new: map_cfg(cfg, new['document']))\
                .filter(lambda x: x is not None)\
                .subscribe(
                    self._update_config(cfg.name),
                    logger.warn,
                    lambda: self.subscriptions.remove(subscription)
                )

            return subscription

        for cfg in self.configs:
            self.subscriptions.append(await subscribe(cfg))

    def on_new(self, name, callback):
        self.callbacks[name].append(callback)

    def teardown(self):
        for sub in self.subscriptions:
            sub.dispose()

    def _update_config(self, name):
        def update(new):
            try:
                self.latest_config[name] = new

                for cb in self.callbacks[name]:
                    cb(new)
            except:
                logger.exception("Exception in config update.")
                raise

        return update

    def swarms(self) -> configuration.swarm.Swarms:
        return self.latest_config[swarm.name]

    def images(self) -> configuration.image.Images:
        return self.latest_config[image.name]

    def glob(self):
        return self.latest_config[Glob.name]