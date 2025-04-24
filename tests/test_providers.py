import whichprovides


def test_provider_order():
    package_providers = whichprovides._package_providers()
    assert (
        len(package_providers) == 0
        or package_providers[-1] == whichprovides.AptFilePackageProvider
    )
