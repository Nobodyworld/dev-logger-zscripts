"""Imported inheritance and aliased type references."""

from .models import Customer as Client
from .models import Order


class BaseService:
    pass


class ImportedCustomer(Client):
    pass


class CustomerService(BaseService):
    current: Client

    def build(self, customer: Client) -> Order:
        self.last_customer: Client
        return Order()
