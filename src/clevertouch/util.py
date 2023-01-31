"""Utility classes for the CleverTouch library"""
from __future__ import annotations
from typing import Union, Any, Dict

from enum import Enum, auto as enum_auto


class ApiError(Exception):
    """General exceptions from the CleverTouch library"""

ApiData = Dict[str, Any]

class StrEnum(str, Enum):
    """Support for StrEnum similar to built-in after version 3.9"""

    def __new__(cls, value: Union[str, enum_auto], *args, **kwargs):
        if not isinstance(value, (str, enum_auto)):
            raise TypeError(
                f"Values of StrEnums must be strings: {value!r} is a {type(value)}"
            )
        return super().__new__(cls, value, *args, **kwargs)

    def __str__(self):
        return str(self.value)

    # pylint: disable=no-self-argument
    def _generate_next_value_(name, *_):
        return name
