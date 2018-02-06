import functools
import docker
import warnings

from docker import auth
from docker.api.service import _check_api_features
import docker.models.services as services
from docker.types import ServiceMode
from docker.utils import utils


def merge(a, b, path=None):
    """merges b into a"""
    if path is None:
        path = []

    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


@functools.wraps(docker.APIClient.update_service)
def update_service_preserve(self, service, version, task_template=None, name=None,
                       labels=None, mode=None, update_config=None,
                       networks=None, endpoint_config=None,
                       endpoint_spec=None, base_spec=None):
    if endpoint_config is not None:
        warnings.warn(
            'endpoint_config has been renamed to endpoint_spec.',
            DeprecationWarning
        )
        endpoint_spec = endpoint_config

    _check_api_features(self._version, task_template, update_config)

    url = self._url('/services/{0}/update', service)
    data = base_spec if base_spec else {}
    headers = {}
    if name is not None:
        data['Name'] = name
    if labels is not None:
        data['Labels'] = labels
    if mode is not None:
        if not isinstance(mode, dict):
            mode = ServiceMode(mode)
        data['Mode'] = mode
    if task_template is not None:
        image = task_template.get('ContainerSpec', {}).get('Image', None)
        if image is not None:
            registry, repo_name = auth.resolve_repository_name(image)
            auth_header = auth.get_config_header(self, registry)
            if auth_header:
                headers['X-Registry-Auth'] = auth_header

        data['TaskTemplate'] = merge(data.setdefault('TaskTemplate', {}), task_template)
    if update_config is not None:
        data['UpdateConfig'] = update_config

    if networks is not None:
        data['Networks'] = utils.convert_service_networks(networks)
    if endpoint_spec is not None:
        data['EndpointSpec'] = endpoint_spec

    resp = self._post_json(
        url, data=data, params={'version': version}, headers=headers
    )
    self._raise_for_status(resp)
    return True


@functools.wraps(services.Service.update)
def update_preserve(self, **kwargs):
    # Image is required, so if it hasn't been set, use current image
    if 'image' not in kwargs:
        spec = self.attrs['Spec']['TaskTemplate']['ContainerSpec']
        kwargs['image'] = spec['Image']

    create_kwargs = services._get_create_service_kwargs('update', kwargs)

    return self.client.api.update_service_preserve(
        self.id,
        self.version,
        base_spec=self.attrs['Spec'],
        **create_kwargs
    )


def setup():
    docker.APIClient.update_service_preserve = update_service_preserve

    services.Service.update_preserve = update_preserve
