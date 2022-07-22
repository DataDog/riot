"""
Setup file for testing purpose.

Session.generate_base_venvs executes `pip ... install -e .` and
looking for a setup.py or pyproject.toml
"""
from setuptools import setup

setup(name="riot_tests")
