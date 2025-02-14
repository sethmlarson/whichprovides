import pytest

import whichprovides


def test_purl() -> None:
    provided_by = whichprovides.ProvidedBy(
        package_type="pypi", package_name="whichprovides", package_version="0.1.0"
    )
    assert provided_by.purl == "pkg:pypi/whichprovides@0.1.0"

    provided_by = whichprovides.ProvidedBy(
        package_type="deb",
        distro="ubuntu",
        package_name="libnss3",
        package_version="2:3.98-0ubuntu0.22.04.2",
    )
    assert provided_by.purl == "pkg:deb/ubuntu/libnss3@2%3A3.98-0ubuntu0.22.04.2"


def test_purl_quoting():
    provided_by = whichprovides.ProvidedBy(
        package_type="type",
        distro="cá",
        package_name="@org/name",
        package_version="2.1.3#fragment+plus",
    )
    assert provided_by.purl == "pkg:type/c%C3%A1/%40org%2Fname@2.1.3%23fragment%2Bplus"


def test_purl_bad_type():
    provided_by = whichprovides.ProvidedBy(
        package_type="@", package_name="name", package_version="1.0.0"
    )
    with pytest.raises(ValueError):
        _ = provided_by.purl
