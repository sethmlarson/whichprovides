# SPDX-License-Identifier: MIT

"""
Module which provides (heh) 'yum provides'
functionality across many package managers.
"""

import dataclasses
import pathlib
import re
import shutil
import subprocess
import sys
import typing
from urllib.parse import quote

__all__ = ["whichprovides", "ProvidedBy"]
__version__ = "0.3.0"

_PACKAGE_MANAGER_BINS: dict[str, str | typing.Literal[False]] = {}
_OS_RELEASE_LINES_RE = re.compile(r"^([A-Z_]+)=(?:\"([^\"]*)\"|(.*))$", re.MULTILINE)
_APK_WHO_OWNS_RE = re.compile(r" is owned by ([^\s\-]+)-([^\s]+)$", re.MULTILINE)
_DPKG_SEARCH_RE = re.compile(r"^([^:]+):")
_DPKG_VERSION_RE = re.compile(r"^Version: ([^\s]+)", re.MULTILINE)
_APT_FILE_SEARCH_RE = re.compile(r"^([^:]+): ")


@dataclasses.dataclass
class ProvidedBy:
    package_type: str
    package_name: str
    package_version: str
    distro: str | None = None

    @property
    def purl(self) -> str:
        """The Package URL (PURL) of the providing package"""
        # PURL disallows many characters in the package type field.
        if not re.match(r"^[a-zA-Z0-9\+\-\.]+$", self.package_type):
            raise ValueError("Package type must be ASCII letters, numbers, +, -, and .")

        parts = ["pkg:", self.package_type.lower(), "/"]
        if self.distro:
            parts.extend((_quote_purl(self.distro), "/"))
        parts.extend(
            (_quote_purl(self.package_name), "@", _quote_purl(self.package_version))
        )
        return "".join(parts)


def _os_release() -> dict[str, str]:
    """Dumb method of finding os-release information."""
    try:
        with open("/etc/os-release") as f:
            os_release = {}
            for name, value_quoted, value_unquoted in _OS_RELEASE_LINES_RE.findall(
                f.read()
            ):
                value = value_quoted if value_quoted else value_unquoted
                os_release[name] = value
            return os_release
    except OSError:
        return {}


def _package_manager_bin(
    binaryname: str, *, allowed_returncodes: None | set[int] = None
) -> str | None:
    has_bin = _PACKAGE_MANAGER_BINS.get(binaryname)
    assert has_bin is not True
    if has_bin is False:
        return None
    elif has_bin is not None:
        return has_bin
    bin_which = shutil.which(binaryname)
    if bin_which is None:  # Cache the 'not-found' result.
        _PACKAGE_MANAGER_BINS[binaryname] = False
        return None
    try:
        subprocess.check_call(
            [bin_which, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _PACKAGE_MANAGER_BINS[binaryname] = bin_which
        return bin_which
    except subprocess.CalledProcessError as e:
        # If running --version returns an non-zero exit we
        # explicitly allow that here.
        if allowed_returncodes and e.returncode in allowed_returncodes:
            _PACKAGE_MANAGER_BINS[binaryname] = bin_which
            return bin_which
        _PACKAGE_MANAGER_BINS[binaryname] = False
    return None


def whichprovides(filepath: str) -> ProvidedBy | None:
    """Return a package URL (PURL) for the package that provides a file"""
    distro = _os_release().get("ID", None)
    filepath = pathlib.Path(filepath).absolute()

    # Resolve links to an actual filepath.
    # .resolve() also makes a path absolute.
    if filepath.is_symlink():
        filepath = filepath.resolve()

    # apk (Alpine)
    if distro and (apk_bin := _package_manager_bin("apk")):
        try:
            # $ apk info --who-owns /bin/bash
            # /bin/bash is owned by bash-5.2.26-r0
            stdout = subprocess.check_output(
                [apk_bin, "info", "--who-owns", str(filepath)],
                stderr=subprocess.DEVNULL,
            ).decode()
            if match := _APK_WHO_OWNS_RE.search(stdout):
                package_name = match.group(1)
                package_version = match.group(2)
                return ProvidedBy(
                    package_type="apk",
                    distro=distro,
                    package_name=package_name,
                    package_version=package_version,
                )
        except subprocess.CalledProcessError:
            pass

    # rpm (CentOS, Red Hat, AlmaLinux, Rocky Linux)
    if distro and (rpm_bin := _package_manager_bin("rpm")):
        try:
            # $ rpm -qf --queryformat "%{NAME} %{VERSION} %{RELEASE} ${ARCH}" /bin/bash
            # bash 4.4.20 4.el8_6
            stdout = subprocess.check_output(
                [
                    rpm_bin,
                    "-qf",
                    "--queryformat",
                    "%{NAME} %{VERSION} %{RELEASE} %{ARCH}",
                    str(filepath),
                ],
                stderr=subprocess.DEVNULL,
            ).decode()
            package_name, package_version, package_release, *_ = stdout.strip().split(
                " ", 4
            )
            return ProvidedBy(
                package_type="rpm",
                distro=distro,
                package_name=package_name,
                package_version=f"{package_version}-{package_release}",
            )
        except subprocess.CalledProcessError:
            pass

    # dpkg (Debian, Ubuntu)
    if distro and (dpkg_bin := _package_manager_bin("dpkg")):
        try:
            # $ dpkg -S /bin/bash
            # bash: /bin/bash
            stdout = subprocess.check_output(
                [dpkg_bin, "-S", str(filepath)],
                stderr=subprocess.DEVNULL,
            ).decode()
            if match := _DPKG_SEARCH_RE.search(stdout):
                package_name = match.group(1)
                # $ dpkg -s bash
                # ...
                # Version: 5.1-6ubuntu1.1
                stdout = subprocess.check_output(
                    [dpkg_bin, "-s", package_name],
                    stderr=subprocess.DEVNULL,
                ).decode()
                if match := _DPKG_VERSION_RE.search(stdout):
                    package_version = match.group(1)
                    return ProvidedBy(
                        package_type="deb",
                        distro=distro,
                        package_name=package_name,
                        package_version=package_version,
                    )
        except subprocess.CalledProcessError:
            pass

    return None


def _quote_purl(value: str) -> str:
    """
    Quotes according to PURL rules which are different from
    typical URL percent encoding.
    """
    return quote(value, safe="")


def _main():
    if len(sys.argv) != 2:
        print(
            "Must provide single path argument " "('$ python -m whichprovides <path>')",
            file=sys.stderr,
        )
        sys.exit(1)

    filepath = sys.argv[1]
    provided_by = whichprovides(filepath)
    if provided_by:
        print(provided_by.purl)
    else:
        print(f"No known package providing {filepath}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
