from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()


setup(
    name="riot",
    description="A simple Python test runner runner.",
    url="https://github.com/DataDog/riot",
    author="Datadog, Inc.",
    author_email="dev@datadoghq.com",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    entry_points={"console_scripts": ["riot = riot.__main__:main"]},
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache 2",
    packages=find_packages(exclude=["tests*"]),
    package_data={"riot": ["py.typed"]},
    python_requires=">=3.6",
    install_requires=[
        "dataclasses; python_version<'3.7'",
        "click>=7,<8",
        "virtualenv",
        "rich",
    ],
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    # Required for mypy compatibility, see
    # https://mypy.readthedocs.io/en/stable/installed_packages.html#making-pep-561-compatible-packages
    zip_safe=False,
)
