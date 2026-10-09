"""Interpret the public GitHub latest-release response without GUI dependencies."""
import json
import re

from . import VERSION

API_URL = "https://api.github.com/repos/dinhduan183/SilenceTrim/releases/latest"
DOWNLOAD_URL = "https://github.com/dinhduan183/SilenceTrim/releases/latest"


def version_parts(version):
    if not isinstance(version, str) or not re.fullmatch(r"v?[0-9]+(?:\.[0-9]+)*", version):
        return None
    try:
        return tuple(int(part) for part in version.removeprefix("v").split("."))
    except ValueError:
        return None


def newer_tag(data, current=VERSION):
    try:
        release = json.loads(data)
        if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
            return None
        latest = version_parts(release.get("tag_name"))
        installed = version_parts(current)
        if latest is None or installed is None:
            return None
        length = max(len(latest), len(installed))
        if latest + (0,) * (length - len(latest)) > installed + (0,) * (length - len(installed)):
            return "v" + ".".join(map(str, latest))
    except (ValueError, TypeError, UnicodeDecodeError):
        pass
    return None
