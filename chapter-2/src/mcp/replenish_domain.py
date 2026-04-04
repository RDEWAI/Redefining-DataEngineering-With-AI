"""Replenish domain classes for MCP package.

This module defines the core domain objects for replenishment data:
- Supplier: Supplier source enum
- ReplenishType: Type of replenishment enum
- BookCondition: Condition of replenished books enum
- FundingSource: Funding source enum
- Priority: Priority level enum
- Replenishment: Main replenish entity dataclass

All domain objects are immutable and support JSON serialization.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class Supplier(Enum):
    """Supplier source for book replenishment.

    Attributes:
        INGRAM: Ingram Content Group
        BAKER_TAYLOR: Baker & Taylor
        BRODART: Brodart Company
        DIRECT_PUBLISHER: Direct from publisher
        AMAZON_BUSINESS: Amazon Business
    """

    INGRAM = "Ingram"
    BAKER_TAYLOR = "Baker & Taylor"
    BRODART = "Brodart"
    DIRECT_PUBLISHER = "Direct Publisher"
    AMAZON_BUSINESS = "Amazon Business"


class ReplenishType(Enum):
    """Type of book replenishment.

    Attributes:
        NEW_ACQUISITION: Brand new title added to collection
        REPLACEMENT: Replacing damaged/lost copy
        RESTOCK: Restocking existing title
        DONATION: Received as donation
        RETURN_PROCESSING: Returned item processing
    """

    NEW_ACQUISITION = "New Acquisition"
    REPLACEMENT = "Replacement"
    RESTOCK = "Restock"
    DONATION = "Donation"
    RETURN_PROCESSING = "Return Processing"


class BookCondition(Enum):
    """Condition of replenished book.

    Attributes:
        NEW: Brand new condition
        REFURBISHED: Refurbished/restored
        USED_GOOD: Used in good condition
        USED_FAIR: Used in fair condition
    """

    NEW = "New"
    REFURBISHED = "Refurbished"
    USED_GOOD = "Used - Good"
    USED_FAIR = "Used - Fair"


class FundingSource(Enum):
    """Funding source for replenishment.

    Attributes:
        OPERATING_BUDGET: Regular operating budget
        GRANT: Grant funding
        DONATION_FUND: Donation fund
        SPECIAL_COLLECTION: Special collection budget
        EMERGENCY_FUND: Emergency fund
    """

    OPERATING_BUDGET = "Operating Budget"
    GRANT = "Grant"
    DONATION_FUND = "Donation Fund"
    SPECIAL_COLLECTION = "Special Collection"
    EMERGENCY_FUND = "Emergency Fund"


class Priority(Enum):
    """Priority level for replenishment.

    Attributes:
        URGENT: Urgent priority
        HIGH: High priority
        NORMAL: Normal priority
        LOW: Low priority
    """

    URGENT = "Urgent"
    HIGH = "High"
    NORMAL = "Normal"
    LOW = "Low"


@dataclass(frozen=True)
class Replenishment:
    """Replenishment transaction entity.

    Attributes:
        replenish_id: Unique identifier (e.g., "R0001")
        book_id: Foreign key to book (e.g., "B001")
        replenish_date: Date of replenishment
        quantity: Number of copies added
        unit_cost: Cost per copy
        total_cost: Total cost after discount
        discount_pct: Bulk discount percentage (0-100)
        supplier: Supplier source
        replenish_type: Type of replenishment
        condition: Book condition
        funding_source: Funding source
        priority: Priority level
    """

    replenish_id: str
    book_id: str
    replenish_date: date
    quantity: int
    unit_cost: Decimal
    total_cost: Decimal
    discount_pct: Decimal
    supplier: Supplier
    replenish_type: ReplenishType
    condition: BookCondition
    funding_source: FundingSource
    priority: Priority

    @property
    def is_bulk(self) -> bool:
        """Check if this is a bulk replenishment (quantity > 1)."""
        return self.quantity > 1

    @property
    def has_discount(self) -> bool:
        """Check if a discount was applied."""
        return self.discount_pct > 0

    @property
    def discount_amount(self) -> Decimal:
        """Calculate the discount amount."""
        subtotal = self.quantity * self.unit_cost
        return subtotal - self.total_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert replenishment to dictionary for JSON serialization."""
        return {
            "replenish_id": self.replenish_id,
            "book_id": self.book_id,
            "replenish_date": self.replenish_date.isoformat(),
            "quantity": self.quantity,
            "unit_cost": float(self.unit_cost),
            "total_cost": float(self.total_cost),
            "discount_pct": float(self.discount_pct),
            "supplier": self.supplier.value,
            "replenish_type": self.replenish_type.value,
            "condition": self.condition.value,
            "funding_source": self.funding_source.value,
            "priority": self.priority.value,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "Replenishment":
        """Create Replenishment instance from database row tuple."""
        (
            replenish_id,
            book_id,
            replenish_date_val,
            quantity,
            unit_cost,
            total_cost,
            discount_pct,
            supplier_str,
            replenish_type_str,
            condition_str,
            funding_source_str,
            priority_str,
        ) = row

        # Convert date if needed
        if isinstance(replenish_date_val, datetime):
            replenish_date_val = replenish_date_val.date()
        elif isinstance(replenish_date_val, str):
            replenish_date_val = date.fromisoformat(replenish_date_val)

        return cls(
            replenish_id=replenish_id,
            book_id=book_id,
            replenish_date=replenish_date_val,
            quantity=quantity,
            unit_cost=Decimal(str(unit_cost)),
            total_cost=Decimal(str(total_cost)),
            discount_pct=Decimal(str(discount_pct)),
            supplier=Supplier(supplier_str),
            replenish_type=ReplenishType(replenish_type_str),
            condition=BookCondition(condition_str),
            funding_source=FundingSource(funding_source_str),
            priority=Priority(priority_str),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Replenishment":
        """Create Replenishment instance from dictionary."""
        # Handle enums
        supplier = data["supplier"]
        if isinstance(supplier, str):
            supplier = Supplier(supplier)

        replenish_type = data["replenish_type"]
        if isinstance(replenish_type, str):
            replenish_type = ReplenishType(replenish_type)

        condition = data["condition"]
        if isinstance(condition, str):
            condition = BookCondition(condition)

        funding_source = data["funding_source"]
        if isinstance(funding_source, str):
            funding_source = FundingSource(funding_source)

        priority = data["priority"]
        if isinstance(priority, str):
            priority = Priority(priority)

        # Handle date
        replenish_date = data["replenish_date"]
        if isinstance(replenish_date, datetime):
            replenish_date = replenish_date.date()
        elif isinstance(replenish_date, str):
            replenish_date = date.fromisoformat(replenish_date)

        return cls(
            replenish_id=data["replenish_id"],
            book_id=data["book_id"],
            replenish_date=replenish_date,
            quantity=data["quantity"],
            unit_cost=Decimal(str(data["unit_cost"])),
            total_cost=Decimal(str(data["total_cost"])),
            discount_pct=Decimal(str(data["discount_pct"])),
            supplier=supplier,
            replenish_type=replenish_type,
            condition=condition,
            funding_source=funding_source,
            priority=priority,
        )
