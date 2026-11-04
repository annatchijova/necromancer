from fractions import Fraction

import pytest

from necromancer.canonicalize import check_deterministic, seal


def test_typed_encoding_distinguishes_values():
    assert seal({"v": 1}) != seal({"v": "1"})
    assert seal({"v": 1}) != seal({"v": True})
    assert seal({"v": Fraction(1, 2)}) != seal({"v": "1/2"})


def test_dict_order_does_not_change_seal():
    assert seal({"b": 1, "a": 2}) == seal({"a": 2, "b": 1})


def test_float_is_rejected_from_sealed_path():
    with pytest.raises(TypeError):
        seal({"v": 0.5})


def test_determinism_check_passes_for_pure_factory():
    digest = check_deterministic(lambda: {"x": [1, 2], "r": Fraction(3, 7)}, runs=3)
    assert len(digest) == 64
