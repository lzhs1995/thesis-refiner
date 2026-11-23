"""One parent owns existing transport locks; two children inherit the same FDs.

Closing a child descriptor never calls LOCK_UN, which would unlock the shared
open description for its sibling. A surviving child retains the lock if its
parent exits; absence of a terminal result is never treated as release proof.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat


def identity(value):
    return {'device': value.st_dev, 'inode': value.st_ino}


@contextmanager
def own_existing_locks(paths):
    if not paths or len(paths) != len(set(paths)):
        raise ValueError('UNIQUE_EXISTING_LOCK_PATHS_REQUIRED')
    handles = []
    bindings = []
    try:
        for name in paths:
            path = Path(name)
            if not path.is_absolute():
                raise ValueError('ABSOLUTE_LOCK_PATH_REQUIRED')
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('REGULAR_LOCK_FILE_REQUIRED')
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            handles.append(fd)
            if identity(os.fstat(fd)) != identity(before):
                raise ValueError('LOCK_FILE_REPLACED_DURING_OPEN')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if identity(path.lstat()) != identity(before):
                raise ValueError('LOCK_FILE_REPLACED_DURING_ACQUIRE')
            bindings.append({'path': str(path), 'fd': fd, **identity(before)})
        yield {'parent_pid': os.getpid(), 'pgid': os.getpgrp(), 'locks': bindings}
    finally:
        for fd in reversed(handles):
            os.close(fd)


@contextmanager
def inherited_locks(binding, expected_paths, passed_fds):
    rows = binding.get('locks', [])
    if (binding.get('parent_pid') != os.getppid() or binding.get('pgid') != os.getpgrp()
            or [row['path'] for row in rows] != list(expected_paths)
            or [row['fd'] for row in rows] != list(passed_fds)
            or len(passed_fds) != len(set(passed_fds)) or not passed_fds):
        raise ValueError('ORIGINAL_PARENT_GROUP_LOCK_SET_REQUIRED')
    duplicates = []
    try:
        for row in rows:
            expected = {key: row[key] for key in ('device', 'inode')}
            current = Path(row['path']).lstat()
            opened = os.fstat(row['fd'])
            if (not stat.S_ISREG(current.st_mode) or not stat.S_ISREG(opened.st_mode)
                    or identity(current) != expected or identity(opened) != expected):
                raise ValueError('INHERITED_LOCK_IDENTITY_CHANGED')
            # Succeeds only for the inherited locked open description, or if no
            # holder exists. The independent-open probe below excludes no holder.
            fcntl.flock(row['fd'], fcntl.LOCK_EX | fcntl.LOCK_NB)
            probe = os.open(row['path'], os.O_RDWR | os.O_NOFOLLOW)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise ValueError('INDEPENDENT_OPEN_NOT_EXCLUDED')
            finally:
                os.close(probe)
            duplicates.append(os.dup(row['fd']))
        yield
    finally:
        # No explicit unlock: siblings share the same open descriptions.
        for fd in reversed(duplicates):
            os.close(fd)
