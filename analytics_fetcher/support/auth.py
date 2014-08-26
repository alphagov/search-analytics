"""Handle authentication with google.

gapy and google's oauth2client are awkward to use without writing secrets files
to disk.  We want to be able to pass the secrets files in as environment
variables.  This code manages this by using a temporary directory to place the
secrets in, and serialising / unserialising the contents of this directory to a
base-64 encoded string.

This code is used in two situations; firstly for setting up the auth, and
secondly for creating an authenticated client for making requests to google.

For auth setup, simply call the `calc_env_var` function.  This performs the
oauth flow, and then returns the encoded value of the returned secrets.
The script in `scripts/setup_auth.py` performs this flow.

For creating a client, first make an AuthFileManager and enter its context.
Then call `AuthFileManager.from_env_var()` to populate it with the secrets.
Finally, call the `open_client` function, passing it the AuthFileManager, to
get an authenticated client.  The client will be valid until the
AuthFileManager context is exited.  ie, if the secrets had been passed in the
"GAAUTH" environment variable:

    with AuthFileManager() as afm:
        afm.from_env_var(os.environ["GAAUTH"])
        client = open_client(afm)
        # Use the client in this context

"""

import gapy.client
import json
import logging
import oauth2client.tools
import os
import stat
import tempfile
import zlib


logger = logging.getLogger(__name__)


def base64(s):
    return s.encode('base64').replace("\n", "")


def to_json(obj):
    return json.dumps(obj, separators=(',', ':'))


class AuthFileManager(object):
    """Manage a set of authentication files.

    Returns paths to the files, and more importantly, ensures that they're
    deleted after use.  Works as a context manager.

    Can also serialise all the stored data to and from a base64 representation
    suitable for passing in as an environment variable.  This makes it easy to
    avoid storing the secrets files on disk, where they may get accidentally
    leaked (eg, by being comitted).

    """
    def __init__(self):
        self.entered = False
        self.base_path = tempfile.mkdtemp(prefix='ga_analytics')
        # Make sure only the current user can access the tmpdir
        os.chmod(self.base_path, stat.S_IRWXU)

    def __enter__(self):
        self.paths = {}
        self.entered = True
        return self

    def __exit__(self, exc, value, tb):
        self.entered = False
        while self.paths:
            key, path = self.paths.popitem()
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError as e:
                    logger.error("Couldn't clean up %r: %s" % (path, e))
        os.rmdir(self.base_path)
        return False

    def _check_entered(self):
        if not self.entered:
            raise RuntimeError("Not in AuthFileManager context")

    def path(self, key):
        self._check_entered()
        if key in self.paths:
            return self.paths[key]
        path = os.path.join(self.base_path, key)
        self.paths[key] = path
        return path

    def data(self, key):
        self._check_entered()
        with open(self.path(key), 'rb') as fobj:
            return json.loads(fobj.read())

    def set_data(self, key, value):
        with open(self.path(key), 'wb') as fobj:
            fobj.write(to_json(value))

    def to_env_var(self):
        self._check_entered()
        value = [
            [key, self.data(key)]
            for key in self.paths.keys()
        ]
        return base64(zlib.compress(to_json(value), 9))

    def from_env_var(self, value):
        self._check_entered()
        for key, value in json.loads(zlib.decompress(value.decode('base64'))):
            self.set_data(key, value)


def calc_env_var(client_secrets_path):
    """Calculate an environment variable value holding auth information.

    Performs the initial auth flow and then encodes the resulting secrets
    appropriately.

    """
    with open(client_secrets_path, "rb") as fobj:
        client_secrets = json.load(fobj)
    with AuthFileManager() as afm:
        afm.set_data("client_secrets.json", client_secrets)
        open_client(afm)
        return afm.to_env_var()


def open_client(afm):
    """Open an oauth2client.

    :param afm: an AuthFileManager which will be used to lookup the filenames
    needed.

    """
    # Prevent oauth2client from trying to open a browser
    # This is run from inside the VM so there is no browser
    oauth2client.tools.FLAGS.auth_local_webserver = False

    return gapy.client.from_secrets_file(
        afm.path("client_secrets.json"),
        storage_path=afm.path("storage.json"),
        readonly=True,
    )
