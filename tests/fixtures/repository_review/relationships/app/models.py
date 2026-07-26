"""Classes with local inheritance and bounded type annotations."""


class Entity:
    pass


class Customer(Entity):
    manager: "Customer | None"


class Order(Entity):
    customer: Customer
    external: "ExternalRecord"  # noqa: F821 - fixture-only unresolved evidence


class Combined(Customer, Order):
    pass


class ExternalChild(ExternalBase):  # noqa: F821 - fixture-only syntax evidence
    pass
