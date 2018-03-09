from collections import defaultdict
import json
import re

name = "repos"


def map(repos):
    return Repos(repos)


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


class Repos:
    default_repo = Repo({})

    def __init__(self, repos):
        self.repos = defaultdict(
            lambda: defaultdict(lambda: Repos.default_repo))

        for user in repos:
            defaults = {}
            if "default_login" in user:
                defaults["login"] = user["default_login"]

            if "default_glob" in user:
                defaults["glob"] = user["default_glob"]

            for repo in user["repos"]:
                self.repos[user["user"]][repo["repo"]] = Repo(repo)

    def repo(self, image):
        user, repo = image.split("/")
        repo = repo.split(":")[0]

        return self.repos[user][repo]
