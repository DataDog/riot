import pytest
from riot.riot import Interpreter, VenvInstance


@pytest.mark.parametrize(
    "v1,v2,equal",
    [
        (3.6, 3.6, True),
        (3.6, "3.6", True),
        ("3.6", "3.6", True),
        ("3.6", 3.6, True),
        (3.6, 3.7, False),
        (3.6, "3.7", False),
        (3.7, 3.7, True),
        (3, 3, True),
        (3, "3", True),
        ("3", 3, True),
    ],
)
def test_interpreter(v1, v2, equal):
    if equal:
        assert Interpreter(v1) == Interpreter(v2)
        assert hash(Interpreter(v1)) == hash(Interpreter(v2))
        assert repr(Interpreter(v1)) == repr(Interpreter(v2))
    else:
        assert Interpreter(v1) != Interpreter(v2)
        assert hash(Interpreter(v1)) != hash(Interpreter(v2))
        assert repr(Interpreter(v1)) != repr(Interpreter(v2))


@pytest.mark.parametrize(
    "v1,v2",
    [
        (
            VenvInstance("name", Interpreter(3.6), "pytest", tuple(), tuple()),
            VenvInstance("name1", Interpreter(3.6), "pytest", tuple(), tuple()),
        ),
        (
            VenvInstance("name", Interpreter(3.6), "pytest", tuple(), tuple()),
            VenvInstance("name", Interpreter(3.7), "pytest", tuple(), tuple()),
        ),
    ],
)
def test_instance_hash_neq(v1, v2):
    assert v1.humanhash() != v2.humanhash()


@pytest.mark.parametrize(
    "v1,v2",
    [
        (
            VenvInstance("name", Interpreter(3.6), "pytest", tuple(), tuple()),
            VenvInstance("name", Interpreter(3.6), "pytest", tuple(), tuple()),
        ),
    ],
)
def test_instance_hash_eq(v1, v2):
    assert v1.humanhash() == v2.humanhash()
