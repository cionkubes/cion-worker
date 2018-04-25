from collections import defaultdict
import json
import re

from configuration.abc import ConfigABC

class Repo:
    defaults = {
        "login": None,
        "glob": "(.*)/(.*):(.*)"
    }

    def __init__(self, repo):
        repo = {**Repo.defaults, **repo}

        self.login_file = repo['login']
        self.glob = re.compile(repo['glob'])

    def require_login(self):
        return self.login_file is not None

    def login_to(self, client):
        with open(self.login_file) as file:
            credentials = json.load(file)
            client.login(
                username=credentials['username'], password=credentials['password'])


class Repos(ConfigABC):
    default_repo = Repo({})

    def __init__(self):
        super().__init__()
        self.repos = defaultdict(
            lambda: defaultdict(lambda: Repos.default_repo))
    
    def set(self, user):
        defaults = {}
        if "default_login" in user:
            defaults["login"] = user["default_login"]

        if "default_glob" in user:
            defaults["glob"] = user["default_glob"]

        for repo in user["repos"]:
            self.repos[user["user"]][repo["repo"]] = Repo({**defaults, **repo})

    def delete(self, user):
        self.repos.pop(user['user'], None)

    def repo(self, image):
        image = image.split("/")

        if len(image) == 2:
            user, repo = image
            repo = repo.split(":")[0]

            return self.repos[user][repo]
        else:
            return Repos.default_repo


name = "repos"
init = Repos
