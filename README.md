# whichprovides

Package manager agnostic support for "`yum whichprovides`"
which maps a file back to its providing package. This is
useful for generating a package URL (PURL) identifier.

You can install the package like so:

```terminal
$ python -m pip install whichprovides
```

Then use the `whichprovides()` API inside of Python code:

```python
>>> import whichprovides
>>> whichprovides.whichprovides("/usr/lib/x86_64-linux-gnu/libssl3.so")

ProvidedBy(
  package_type='deb',
  distro='ubuntu',
  package_name='libnss3',
  package_version='2:3.98-0ubuntu0.22.04.2'
)
```

The functionality is also accessible from the command line:

```terminal
$ python -m pip install whichprovides
$ python -m whichprovides /usr/lib/x86_64-linux-gnu/libssl3.so 

pkg:deb/ubuntu/libnss3@2:3.98-0ubuntu0.22.04.2
```