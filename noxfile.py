import nox


@nox.session(python=["3.9", "3.10", "3.11", "3.12", "3.13"])
def tests(session):
    session.install("-e.", "pytest")
    session.run("pytest", *session.posargs)
