"""Lending domain classes for MCP package.

This module defines the core domain objects for lending data:
- PatronSegment: Patron type enum
- Region: Geographic region enum
- Channel: Lending channel enum
- PaymentMethod: Payment type enum
- Loan: Main lending entity dataclass

All domain objects are immutable and support JSON serialization.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class PatronSegment(Enum):
    """Patron segment classification.

    Attributes:
        INDIVIDUAL: Individual patron loan
        CORPORATE: Business/corporate loan
        EDUCATIONAL: School/university loan
        GOVERNMENT: Government institution loan
    """

    INDIVIDUAL = "Individual"
    CORPORATE = "Corporate"
    EDUCATIONAL = "Educational"
    GOVERNMENT = "Government"


class Region(Enum):
    """Geographic region for lending.

    Attributes:
        NORTHEAST: Northeastern region
        SOUTHEAST: Southeastern region
        MIDWEST: Midwestern region
        WEST: Western region
        INTERNATIONAL: International lending
    """

    NORTHEAST = "Northeast"
    SOUTHEAST = "Southeast"
    MIDWEST = "Midwest"
    WEST = "West"
    INTERNATIONAL = "International"


class Channel(Enum):
    """Lending channel type.

    Attributes:
        IN_STORE: Physical store loan
        ONLINE: Online/e-commerce loan
        PHONE_ORDER: Phone order loan
        PARTNER: Partner/reseller loan
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
class Loan:
    """Lending transaction entity.

    Attributes:
        loan_id: Unique identifier (e.g., "L0001")
        book_id: Foreign key to book (e.g., "B001")
        loan_date: Date of loan
        quantity: Number of copies lent
        lending_fee: Fee per unit
        total_fees: Total loan fees after fee waiver
        fee_waiver: Fee waiver percentage applied (0-100)
        payment_method: Payment method used
        patron_id: Patron identifier
        patron_segment: Patron segment type
        region: Geographic region
        channel: Lending channel
    """

    loan_id: str
    book_id: str
    loan_date: date
    quantity: int
    lending_fee: Decimal
    total_fees: Decimal
    fee_waiver: Decimal
    payment_method: PaymentMethod
    patron_id: str
    patron_segment: PatronSegment
    region: Region
    channel: Channel

    @property
    def is_bulk_loan(self) -> bool:
        """Check if this is a bulk loan (quantity > 1)."""
        return self.quantity > 1

    @property
    def has_fee_waiver(self) -> bool:
        """Check if a fee waiver was applied."""
        return self.fee_waiver > 0

    @property
    def waiver_amount(self) -> Decimal:
        """Calculate the waiver amount."""
        subtotal = self.quantity * self.lending_fee
        return subtotal - self.total_fees

    def to_dict(self) -> dict[str, Any]:
        """Convert loan to dictionary for JSON serialization."""
        return {
            "loan_id": self.loan_id,
            "book_id": self.book_id,
            "loan_date": self.loan_date.isoformat(),
            "quantity": self.quantity,
            "lending_fee": float(self.lending_fee),
            "total_fees": float(self.total_fees),
            "fee_waiver": float(self.fee_waiver),
            "payment_method": self.payment_method.value,
            "patron_id": self.patron_id,
            "patron_segment": self.patron_segment.value,
            "region": self.region.value,
            "channel": self.channel.value,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "Loan":
        """Create Loan instance from database row tuple."""
        (
            loan_id,
            book_id,
            loan_date_val,
            quantity,
            lending_fee,
            total_fees,
            fee_waiver,
            payment_method_str,
            patron_id,
            patron_segment_str,
            region_str,
            channel_str,
        ) = row

        # Convert date if needed
        if isinstance(loan_date_val, str):
            loan_date_val = date.fromisoformat(loan_date_val)

        return cls(
            loan_id=loan_id,
            book_id=book_id,
            loan_date=loan_date_val,
            quantity=quantity,
            lending_fee=Decimal(str(lending_fee)),
            total_fees=Decimal(str(total_fees)),
            fee_waiver=Decimal(str(fee_waiver)),
            payment_method=PaymentMethod(payment_method_str),
            patron_id=patron_id,
            patron_segment=PatronSegment(patron_segment_str),
            region=Region(region_str),
            channel=Channel(channel_str),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Loan":
        """Create Loan instance from dictionary."""
        # Handle enums
        patron_segment = data["patron_segment"]
        if isinstance(patron_segment, str):
            patron_segment = PatronSegment(patron_segment)

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
        loan_date = data["loan_date"]
        if isinstance(loan_date, str):
            loan_date = date.fromisoformat(loan_date)

        return cls(
            loan_id=data["loan_id"],
            book_id=data["book_id"],
            loan_date=loan_date,
            quantity=data["quantity"],
            lending_fee=Decimal(str(data["lending_fee"])),
            total_fees=Decimal(str(data["total_fees"])),
            fee_waiver=Decimal(str(data["fee_waiver"])),
            payment_method=payment_method,
            patron_id=data["patron_id"],
            patron_segment=patron_segment,
            region=region,
            channel=channel,
        )
