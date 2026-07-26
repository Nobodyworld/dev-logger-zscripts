import typing
from typing import Annotated, Callable, Literal, Optional

import typing_extensions


class Customer:
    VALUE = "customer"


class Order:
    pass


class SomeMetadata:
    pass


def inspect(
    literal: Literal["active"],
    qualified_literal: typing.Literal[1, Customer.VALUE],
    extension_literal: typing_extensions.Literal["extension"],
    annotated: Annotated[Customer, "database-key", SomeMetadata()],
    qualified_annotated: typing.Annotated[Customer, SomeMetadata()],
    extension_annotated: typing_extensions.Annotated[Customer, "metadata"],
    sequence: list[Customer],
    mapping: dict[str, Customer],
    optional: Optional[Customer],
    union: Customer | None,
    callback: Callable[[Customer], Order],
) -> Order:
    raise NotImplementedError
