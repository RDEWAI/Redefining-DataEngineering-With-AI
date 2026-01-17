"""Sales domain classes for MCP package.

This module defines the core domain objects for sales data:
- CustomerSegment: Customer type enum
- Region: Geographic region enum
- Channel: Sales channel enum
- PaymentMethod: Payment type enum
- Sale: Main sales entity dataclass

All domain objects are immutable and support JSON serialization.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class CustomerSegment(Enum):
    """Customer segment classification.

    Attributes:
        INDIVIDUAL: Individual consumer purchase
        CORPORATE: Business/corporate purchase
        EDUCATIONAL: School/university purchase
        GOVERNMENT: Government institution purchase
    """

    INDIVIDUAL = "Individual"
    CORPORATE = "Corporate"
    EDUCATIONAL = "Educational"
    GOVERNMENT = "Government"


class Region(Enum):
    """Geographic region for sales.

    Attributes:
        NORTHEAST: Northeastern region
        SOUTHEAST: Southeastern region
        MIDWEST: Midwestern region
        WEST: Western region
        INTERNATIONAL: International sales
    """

    NORTHEAST = "Northeast"
    SOUTHEAST = "Southeast"
    MIDWEST = "Midwest"
    WEST = "West"
    INTERNATIONAL = "International"


class Channel(Enum):
    """Sales channel type.

    Attributes:
        IN_STORE: Physical store purchase
        ONLINE: Online/e-commerce purchase
        PHONE_ORDER: Phone order purchase
        PARTNER: Partner/reseller purchase
    """

    IN_STORE = "In-Store"
    ONLINE = "Online"
    PHONE_ORDER = "Phone Order"
    PARTNER = "Partner"


class PaymentMethod(Enum):
    """Payment method type.

    Attributes:
        CREDIT_CARD: Credit card payment
        DEBIT_CARD: Debit card payment
        CASH: Cash payment
        DIGITAL_WALLET: Digital wallet (PayPal, Apple Pay, etc.)
    """

    CREDIT_CARD = "Credit Card"
    DEBIT_CARD = "Debit Card"
    CASH = "Cash"
    DIGITAL_WALLET = "Digital Wallet"


@dataclass(frozen=True)
class Sale:
    """Sales transaction entity.

    Attributes:
        sale_id: Unique identifier (e.g., "S0001")
        book_id: Foreign key to book (e.g., "B001")
        sale_date: Date of sale
        quantity: Number of copies sold
        unit_price: Price per unit
        total_amount: Total sale amount after discount
        discount: Discount percentage applied (0-100)
        payment_method: Payment method used
        customer_id: Customer identifier
        customer_segment: Customer segment type
        region: Geographic region
        channel: Sales channel
    """

    sale_id: str
    book_id: str
    sale_date: date
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    discount: Decimal
    payment_method: PaymentMethod
    customer_id: str
    customer_segment: CustomerSegment
    region: Region
    channel: Channel

    @property
    def is_bulk_purchase(self) -> bool:
        """Check if this is a bulk purchase (quantity > 1)."""
        return self.quantity > 1

    @property
    def is_discounted(self) -> bool:
        """Check if a discount was applied."""
        return self.discount > 0

    @property
    def discount_amount(self) -> Decimal:
        """Calculate the discount amount."""
        subtotal = self.quantity * self.unit_price
        return subtotal - self.total_amount

    def to_dict(self) -> dict[str, Any]:
        """Convert sale to dictionary for JSON serialization."""
        return {
            "sale_id": self.sale_id,
            "book_id": self.book_id,
            "sale_date": self.sale_date.isoformat(),
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_amount": float(self.total_amount),
            "discount": float(self.discount),
            "payment_method": self.payment_method.value,
            "customer_id": self.customer_id,
            "customer_segment": self.customer_segment.value,
            "region": self.region.value,
            "channel": self.channel.value,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "Sale":
        """Create Sale instance from database row tuple."""
        (
            sale_id,
            book_id,
            sale_date_val,
            quantity,
            unit_price,
            total_amount,
            discount,
            payment_method_str,
            customer_id,
            customer_segment_str,
            region_str,
            channel_str,
        ) = row

        # Convert date if needed
        if isinstance(sale_date_val, str):
            sale_date_val = date.fromisoformat(sale_date_val)

        return cls(
            sale_id=sale_id,
            book_id=book_id,
            sale_date=sale_date_val,
            quantity=quantity,
            unit_price=Decimal(str(unit_price)),
            total_amount=Decimal(str(total_amount)),
            discount=Decimal(str(discount)),
            payment_method=PaymentMethod(payment_method_str),
            customer_id=customer_id,
            customer_segment=CustomerSegment(customer_segment_str),
            region=Region(region_str),
            channel=Channel(channel_str),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sale":
        """Create Sale instance from dictionary."""
        # Handle enums
        customer_segment = data["customer_segment"]
        if isinstance(customer_segment, str):
            customer_segment = CustomerSegment(customer_segment)

        region = data["region"]
        if isinstance(region, str):
            region = Region(region)

        channel = data["channel"]
        if isinstance(channel, str):
            channel = Channel(channel)

        payment_method = data["payment_method"]
        if isinstance(payment_method, str):
            payment_method = PaymentMethod(payment_method)

        # Handle date
        sale_date = data["sale_date"]
        if isinstance(sale_date, str):
            sale_date = date.fromisoformat(sale_date)

        return cls(
            sale_id=data["sale_id"],
            book_id=data["book_id"],
            sale_date=sale_date,
            quantity=data["quantity"],
            unit_price=Decimal(str(data["unit_price"])),
            total_amount=Decimal(str(data["total_amount"])),
            discount=Decimal(str(data["discount"])),
            payment_method=payment_method,
            customer_id=data["customer_id"],
            customer_segment=customer_segment,
            region=region,
            channel=channel,
        )
