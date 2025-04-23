import pathlib
import re
import shutil
import subprocess
import typing

import pytest


class SubprocessProtocol(typing.Protocol):
    def __call__(self, *args, **kwargs) -> subprocess.Popen:
        pass


@pytest.fixture(scope="session")
def docker() -> SubprocessProtocol:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker isn't available, skipping test")

    def run_docker(argv, **kwargs) -> subprocess.Popen:
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.STDOUT)
        return subprocess.Popen([docker_bin, *argv], **kwargs)

    yield run_docker


def run_commands_in_docker(docker, *, image: str, commands: list[str]):
    src_dir = pathlib.Path(__file__).absolute().parent.parent
    argv = [
        "run",
        "--rm",
        "-t",
        "-v",
        f"{src_dir}:/src:ro",
        image,
        "sh",
        "-c",
        ";".join(commands),
    ]
    return docker(argv)


def test_apk(docker):
    proc = run_commands_in_docker(
        docker=docker,
        image="alpine:3.21",
        commands=[
            "apk add python3",
            "python3 -m venv venv",
            "venv/bin/python -m pip install /src",
            "venv/bin/python -m whichprovides /usr/bin/python",
        ],
    )
    proc.wait(timeout=30)
    assert proc.returncode == 0
    purl = proc.stdout.read().decode().strip().split("\n")[-1]
    assert re.search(
        r"pkg:apk\/alpine\/python3@3\.[0-9a-zA-Z.-]+$", purl
    )  # pkg:apk/alpine/python3@3.11.11-r0


def test_apt(docker):
    proc = run_commands_in_docker(
        docker=docker,
        image="debian:bookworm",
        commands=[
            "apt-get update",
            "apt-get install --yes --no-install-recommends python3 python3-venv python3-pip",
            "python3 -m venv venv",
            "venv/bin/python -m pip install /src",
            "venv/bin/python -m whichprovides /usr/bin/python3",
        ],
    )
    proc.wait(timeout=30)
    assert proc.returncode == 0, proc.stdout.read().decode()
    purl = proc.stdout.read().decode().strip().split("\n")[-1]
    assert re.search(
        r"pkg:deb\/debian\/python3[.0-9]+-minimal@3\.[0-9a-zA-Z.%-]+$", purl
    ), purl  # pkg:deb/debian/python3-minimal@3.11.2-1%2Bb1


def test_apt_ubuntu(docker):
    proc = run_commands_in_docker(
        docker=docker,
        image="ubuntu:24.04",
        commands=[
            "apt-get update",
            "DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends python3 python3-venv python3-pip",
            "python3 -m venv venv",
            "venv/bin/python -m pip install /src",
            "venv/bin/python -m whichprovides /usr/bin/python3",
        ],
    )
    proc.wait(timeout=60)
    assert proc.returncode == 0, proc.stdout.read().decode()
    purl = proc.stdout.read().decode().strip().split("\n")[-1]
    assert re.search(
        r"pkg:deb/ubuntu/python3[.0-9]+-minimal@3\.[0-9a-zA-Z.%-]+$", purl
    ), purl  # pkg:deb/ubuntu/python3-minimal@3.12.3-0ubuntu2


@pytest.mark.parametrize(
    ["package", "path"],
    [
        ("libopenblas0-pthread", "/usr/lib/x86_64-linux-gnu/libblas.so.3"),
        ("libwebpdemux2", "/lib/x86_64-linux-gnu/libwebpdemux.so.2"),
    ],
)
def test_apt_symlink(docker, package, path):
    proc = run_commands_in_docker(
        docker=docker,
        image="ubuntu:24.04",
        commands=[
            "apt-get update",
            f"DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends python3 python3-venv python3-pip {package}",
            "python3 -m venv venv",
            "venv/bin/python -m pip install /src",
            # This package uses the Ubuntu 'alternatives' system
            # and thus is a symlink to the actual binary.
            f"venv/bin/python -m whichprovides {path}",
        ],
    )
    proc.wait(timeout=60)
    assert proc.returncode == 0, proc.stdout.read().decode()
    purl = proc.stdout.read().decode().strip().split("\n")[-1]
    assert re.search(
        rf"pkg:deb/ubuntu/{package}@[0-9a-zA-Z.%-]+$", purl
    ), purl  # pkg:deb/ubuntu/libopenblas0-pthread@0.3.26%2Bds-1


def test_rpm(docker):
    proc = run_commands_in_docker(
        docker=docker,
        image="almalinux:9",
        commands=[
            "yum install --assumeyes python3.12",
            "python3.12 -m venv venv",
            "venv/bin/python -m pip install /src",
            "venv/bin/python -m whichprovides /usr/bin/python3.12",
        ],
    )
    proc.wait(timeout=60)
    assert proc.returncode == 0, proc.stdout.read().decode()
    purl = proc.stdout.read().decode().strip().split("\n")[-1]
    assert re.search(
        r"pkg:rpm/almalinux/python3.[0-9]+@3.[0-9]+.[0-9]+-[0-9a-z_\.\-]+$", purl
    ), purl  # pkg:rpm/almalinux/python3.12@3.12.5-2.el9_5.2
