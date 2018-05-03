import os
from collections import defaultdict
from operator import itemgetter

from async_rethink import Connection
from aioreactive.operators import from_iterable, merge
from aioreactive.core import AsyncAnonymousObserver, subscribe, Operators

import configuration.environment as environment
import configuration.service as service
import configuration.repo as repo

from logzero import logger


async def config():
    cfg = Config()
    await cfg.init()
    return cfg


class Config:
    def __init__(self):
        self.addr = os.environ.get('DATABASE_HOST')
        self.port = os.environ.get('DATABASE_PORT')

        self.connection = Connection(self.addr, self.port)
        self.latest_config = keydefaultdict(lambda name: self.configs[name].init())
        
        self.configs = {cfg.name: cfg for cfg in [
            environment,
            service,
            repo
        ]}

    async def init(self):
        await self.connection.connect()
        unpack = itemgetter("config", "old_val", "new_val")

        async def update(x):
            cfg, old, new = unpack(x)

            try:
                if new is None:
                    self.latest_config[cfg].delete(old)
                else:
                    self.latest_config[cfg].set(new)
            except:
                logger.exception(f"Unhandled error while updating config {cfg}.")
            else:
                logger.info(f"Updated config {cfg} with {x}")

        return await subscribe(
            from_iterable(self.configs.values())
                | Operators.flat_map(self.config_observable),
            AsyncAnonymousObserver(update))

    async def config_observable(self, cfg):
        return self.connection.start_with_and_changes(self.connection.db().table(cfg.name))\
            | Operators.map(lambda elem: {**elem, "config": cfg.name})\

    def environments(self) -> environment.Environments:
        return self.latest_config[environment.name]

    def services(self) -> service.Services:
        return self.latest_config[service.name]

    def repos(self) -> repo.Repos:
        return self.latest_config[repo.name]


class keydefaultdict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            ret = self[key] = self.default_factory(key)
            return ret
