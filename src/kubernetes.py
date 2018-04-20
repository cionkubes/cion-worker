import kube


class APISAServer(kube.APIServerProxy):
    def __init__(self, url, token=None, cafile=None):
        super().__init__(url)
        self._session.verify = cafile
        self._session.headers.update({"Authorization": f"Bearer {token}"})