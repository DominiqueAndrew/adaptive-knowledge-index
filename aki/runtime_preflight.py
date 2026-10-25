"""Read-only mount checks; these do not validate a complete execution sandbox."""
from pathlib import PurePosixPath
import re


class RuntimePreflightError(RuntimeError):
    pass


def assert_interpreter_mount_allows_exec(path: str, mount_lines: list[str]) -> str:
    """Reject noexec before trying a copied interpreter, using /proc/mounts data.

    This checks mount flags only, not permissions, binary integrity or architecture.
    A nested mount overrides its parent's flags. Missing coverage fails closed.
    """
    candidate = PurePosixPath(path)
    if not candidate.is_absolute() or '..' in candidate.parts:
        raise RuntimePreflightError('interpreter path must be absolute and normalized')
    matches = []
    for line in mount_lines:
        fields = line.split()
        if len(fields) < 4:
            raise RuntimePreflightError('malformed mount record')
        mount = PurePosixPath(re.sub(r'\\([0-7]{3})',
                                    lambda m: chr(int(m[1], 8)), fields[1]))
        if candidate == mount or mount in candidate.parents:
            matches.append((len(mount.parts), str(mount), set(fields[3].split(','))))
    if not matches:
        raise RuntimePreflightError('interpreter mount is unobserved')
    _, mount, flags = max(matches, key=lambda item: item[0])
    if 'noexec' in flags:
        raise RuntimePreflightError('interpreter is on a noexec mount: '+mount)
    return mount
