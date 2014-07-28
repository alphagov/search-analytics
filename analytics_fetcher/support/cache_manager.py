"""Simple file-based caching support.

"""

import hashlib
import json
import logging
import os
import tempfile
import time


up = os.path.dirname
logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = os.path.join(
    up(up(up(os.path.abspath(__file__)))),
    "cache",
)


class AtomicFileCreate(object):
    """A context manager for writing a file atomically.

    Uses a temporary file to write to
    If the context block is exited with an exception,
    deletes

    """
    def __init__(self, dirname, filename):
        self.dirname = dirname
        self.filename = filename

    def __enter__(self):
        fd, self.tmppath = tempfile.mkstemp(
            prefix=self.filename + '.tmp_',
            dir=self.dirname,
        )
        self.fobj = os.fdopen(fd, "w")
        return self.fobj

    def __exit__(self, exc, value, tb):
        self.fobj.close()
        if exc is None:
            os.rename(self.tmppath, os.path.join(dirname, filename))
        else:
            os.unlink(self.tmppath)
        return False


class CacheManager(object):
    """A simple manager for cached files.

    Very simple policy: maintains a directory of files.  Any files in the
    directory which are more than max_age_days old are deleted when `cleanup`
    is called.

    """
    def __init__(self, max_age_days):
        self.max_age_days = max_age_days
        self.cache_path = os.environ.get("CACHE_DIR", DEFAULT_CACHE_DIR)
        if not os.path.isdir(self.cache_path):
            logger.info("Making cache dir %s", self.cache_path)
            os.makedirs(self.cache_path)

    def _path(self, filename):
        return os.path.join(self.cache_path, filename)

    def exists(self, filename):
        return os.path.exists(self._path(filename))

    def open_for_read(self, filename):
        return open(self._path(filename))

    def atomic_write(self, filename):
        return AtomicFileCreate(self.cache_path, filename)

    def cleanup(self, now=None):
        if now is None:
            now = time.time()
        mtime_limit = now - self.max_age_days * 24 * 60 * 60
        for filename in os.listdir(self.cache_path):
            path = os.path.join(self.cache_path, filename)
            mtime = os.stat(path).st_mtime
            logger.debug("Checking %s; mtime=%s mtime_limit=%s" % (
                path, mtime, mtime_limit))
            if mtime < mtime_limit:
                logger.info("Removing old entry from cache: %s" % (path,))
                os.unlink(path)


def cached_iterator(fn):
    """Wrap an iterator, serving its results from cache if cached.

    Requires that the iterator is a method on an object that has a
    cache_manager property containing a CacheManager.

    """
    def wrapped(self, *args, **kwargs):
        h = hashlib.sha1(repr([args, kwargs])).hexdigest()
        if self.cache_manager.exists(h):
            logger.info("Serving GA request from cache")
            with self.cache_manager.open_for_read(h) as fobj:
                for row in fobj:
                    yield json.loads(row)
            return

        logger.info("Performing GA request %s", h)
        with self.cache_manager.atomic_write(h) as fobj:
            for result in fn(self, *args, **kwargs):
                fobj.write(json.dumps(result, separators=(',', ':')) + '\n')
                yield result

    return wrapped
