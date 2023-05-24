import os

from pip._internal.build_env import BuildEnvironment as BE

original_be_enter = BE.__enter__


def be_enter(self):
    pythonpath = os.getenv("PYTHONPATH")
    try:
        return original_be_enter(self)
    finally:
        # We fix the PYTHONPATH override done by pip before returning
        if pythonpath is not None:
            os.environ["PYTHONPATH"] = os.pathsep.join(
                (os.getenv("PYTHONPATH"), pythonpath)
            )


# pip does not support edit install with prefix in Python 2
# https://github.com/pypa/pip/issues/7627
BE.__enter__ = be_enter
