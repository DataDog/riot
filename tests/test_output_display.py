import warnings


def warning():
    warnings.warn(UserWarning("WARNING"))


def error():
    raise Exception("ERROR")


def success():
    print("SUCCESS")
