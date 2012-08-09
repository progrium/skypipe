import os
import json


# OAuth2 client key and secret
CLIENT_KEY = '9b8d4bc07a4a60f7536cafd46ec492'
CLIENT_SECRET = '2fa7e44a09e3c9b7d63de7ffb97112'


class GlobalConfig(object):
    def __init__(self):
        self.dir = os.path.expanduser('~/.dotcloud_cli')
        self.path = self.path_to('config')
        self.key = self.path_to('dotcloud.key')
        self.load()

    def path_to(self, name):
        path = os.path.join(self.dir, name)
        if os.environ.get('SETTINGS_FLAVOR'):
            path = path + '.' + os.environ.get('SETTINGS_FLAVOR')
        return path

    def load(self):
        try:
            self.data = json.load(file(self.path))
            self.loaded = True
        except (IOError, ValueError):
            self.loaded = False

    def save(self):
        if not os.path.exists(self.dir):
            os.mkdir(self.dir, 0700)
        try:
            f = open(self.path, 'w+')
            json.dump(self.data, f, indent=4)
        except:
            raise

    def get(self, *args):
        if not self.loaded:
            return None
        return self.data.get(*args)

    def save_key(self, key):
        f = open(self.key, 'w')
        f.write(key)
        try:
            os.fchmod(f.fileno(), 0600)
        except:
            pass
        f.close()
