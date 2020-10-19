from setuptools import setup, find_packages


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
    ],
    entry_points={"console_scripts": ["riot = riot.__main__:main"]},
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache 2",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.6",
    install_requires=[
        "attrs>=19.1.0",
        "click>=7,<8",
        "virtualenv",
    ],
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
)
