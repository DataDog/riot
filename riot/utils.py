import itertools
import typing as t

from .constants import _K, _V


def rm_singletons(d: t.Dict[_K, t.Union[_V, t.List[_V]]]) -> t.Dict[_K, t.List[_V]]:
    """Convert single values in a dictionary to a list with that value.

    >>> rm_singletons({ "k": "v" })
    {'k': ['v']}
    >>> rm_singletons({ "k": ["v"] })
    {'k': ['v']}
    >>> rm_singletons({ "k": ["v", "x", "y"] })
    {'k': ['v', 'x', 'y']}
    >>> rm_singletons({ "k": [1, 2, 3] })
    {'k': [1, 2, 3]}
    """
    return {k: to_list(v) for k, v in d.items()}


def to_list(x: t.Union[_K, t.List[_K]]) -> t.List[_K]:
    """Convert a single value to a list containing that value.

    >>> to_list(["x", "y", "z"])
    ['x', 'y', 'z']
    >>> to_list(["x"])
    ['x']
    >>> to_list("x")
    ['x']
    >>> to_list(1)
    [1]
    """
    return [x] if not isinstance(x, list) else x


def rmchars(chars: str, s: str) -> str:
    """Remove chars from s.

    >>> rmchars("123", "123456")
    '456'
    >>> rmchars(">=<.", ">=2.0")
    '20'
    >>> rmchars(">=<.", "")
    ''
    """
    for c in chars:
        s = s.replace(c, "")
    return s


def get_pep_dep(libname: str, version: str) -> str:
    """Return a valid PEP 508 dependency string.

    ref: https://www.python.org/dev/peps/pep-0508/

    >>> get_pep_dep("riot", "==0.2.0")
    'riot==0.2.0'
    """
    return f"{libname}{version}"


def env_to_str(envs: t.Dict[str, str]) -> str:
    """Return a human-friendly representation of environment variables.

    >>> env_to_str({"FOO": "BAR"})
    'FOO=BAR'
    >>> env_to_str({"K": "V", "K2": "V2"})
    'K=V K2=V2'
    """
    return " ".join(f"{k}={v}" for k, v in envs.items())


def expand_specs(specs: t.Dict[_K, t.List[_V]]) -> t.Iterator[t.Tuple[t.Tuple[_K, _V]]]:
    """Return the product of all items from the passed dictionary.

    In summary:

    {X: [X0, X1, ...], Y: [Y0, Y1, ...]} ->
      [(X, X0), (Y, Y0)), ((X, X0), (Y, Y1)), ((X, X1), (Y, Y0)), ((X, X1), (Y, Y1)]

    >>> list(expand_specs({"x": ["x0", "x1"]}))
    [(('x', 'x0'),), (('x', 'x1'),)]
    >>> list(expand_specs({"x": ["x0", "x1"], "y": ["y0", "y1"]}))
    [(('x', 'x0'), ('y', 'y0')), (('x', 'x0'), ('y', 'y1')), (('x', 'x1'), ('y', 'y0')), (('x', 'x1'), ('y', 'y1'))]
    """
    all_vals = [[(name, val) for val in vals] for name, vals in specs.items()]

    # Need to cast because the * star typeshed of itertools.product returns Any
    return t.cast(t.Iterator[t.Tuple[t.Tuple[_K, _V]]], itertools.product(*all_vals))


def pip_deps(pkgs: t.Dict[str, str]) -> str:
    return " ".join(
        [
            f"'{get_pep_dep(lib, version)}'"
            for lib, version in pkgs.items()
            if version is not None
        ]
    )
