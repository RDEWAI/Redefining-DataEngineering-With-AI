"""Unit tests for replenish domain classes.

Tests enums, dataclass creation, properties, and serialization methods.
"""

from datetime import date
from decimal import Decimal

from src.mcp.replenish_domain import (
    BookCondition,
    FundingSource,
    Priority,
    Replenishment,
    ReplenishType,
    Supplier,
)


class TestSupplierEnum:
    """Test Supplier enum values."""

    def test_all_values(self) -> None:
        assert Supplier.INGRAM.value == "Ingram"
        assert Supplier.BAKER_TAYLOR.value == "Baker & Taylor"
        assert Supplier.BRODART.value == "Brodart"
        assert Supplier.DIRECT_PUBLISHER.value == "Direct Publisher"
        assert Supplier.AMAZON_BUSINESS.value == "Amazon Business"

    def test_from_string(self) -> None:
        assert Supplier("Ingram") == Supplier.INGRAM
        assert Supplier("Baker & Taylor") == Supplier.BAKER_TAYLOR


class TestReplenishTypeEnum:
    """Test ReplenishType enum values."""

    def test_all_values(self) -> None:
        assert ReplenishType.NEW_ACQUISITION.value == "New Acquisition"
        assert ReplenishType.REPLACEMENT.value == "Replacement"
        assert ReplenishType.RESTOCK.value == "Restock"
        assert ReplenishType.DONATION.value == "Donation"
        assert ReplenishType.RETURN_PROCESSING.value == "Return Processing"


class TestBookConditionEnum:
    """Test BookCondition enum values."""

    def test_all_values(self) -> None:
        assert BookCondition.NEW.value == "New"
        assert BookCondition.REFURBISHED.value == "Refurbished"
        assert BookCondition.USED_GOOD.value == "Used - Good"
        assert BookCondition.USED_FAIR.value == "Used - Fair"


class TestFundingSourceEnum:
    """Test FundingSource enum values."""

    def test_all_values(self) -> None:
        assert FundingSource.OPERATING_BUDGET.value == "Operating Budget"
        assert FundingSource.GRANT.value == "Grant"
        assert FundingSource.DONATION_FUND.value == "Donation Fund"
        assert FundingSource.SPECIAL_COLLECTION.value == "Special Collection"
        assert FundingSource.EMERGENCY_FUND.value == "Emergency Fund"


class TestPriorityEnum:
    """Test Priority enum values."""

    def test_all_values(self) -> None:
        assert Priority.URGENT.value == "Urgent"
        assert Priority.HIGH.value == "High"
        assert Priority.NORMAL.value == "Normal"
        assert Priority.LOW.value == "Low"


class TestReplenishment:
    """Test Replenishment dataclass."""

    def _make_replenishment(self, **kwargs) -> Replenishment:
        defaults = {
            "replenish_id": "R0001",
            "book_id": "B001",
            "replenish_date": date(2024, 3, 15),
            "quantity": 5,
            "unit_cost": Decimal("45.00"),
            "total_cost": Decimal("213.75"),
            "discount_pct": Decimal("5.00"),
            "supplier": Supplier.INGRAM,
            "replenish_type": ReplenishType.RESTOCK,
            "condition": BookCondition.NEW,
            "funding_source": FundingSource.OPERATING_BUDGET,
            "priority": Priority.NORMAL,
        }
        defaults.update(kwargs)
        return Replenishment(**defaults)

    def test_creation(self) -> None:
        rec = self._make_replenishment()
        assert rec.replenish_id == "R0001"
        assert rec.book_id == "B001"
        assert rec.quantity == 5
        assert rec.supplier == Supplier.INGRAM

    def test_is_bulk_true(self) -> None:
        rec = self._make_replenishment(quantity=5)
        assert rec.is_bulk is True

    def test_is_bulk_false(self) -> None:
        rec = self._make_replenishment(quantity=1)
        assert rec.is_bulk is False

    def test_has_discount_true(self) -> None:
        rec = self._make_replenishment(discount_pct=Decimal("5.00"))
        assert rec.has_discount is True

    def test_has_discount_false(self) -> None:
        rec = self._make_replenishment(discount_pct=Decimal("0.00"))
        assert rec.has_discount is False

    def test_discount_amount(self) -> None:
        rec = self._make_replenishment(
            quantity=5, unit_cost=Decimal("45.00"), total_cost=Decimal("213.75")
        )
        # subtotal = 5 * 45 = 225, discount = 225 - 213.75 = 11.25
        assert rec.discount_amount == Decimal("11.25")

    def test_to_dict(self) -> None:
        rec = self._make_replenishment()
        d = rec.to_dict()
        assert d["replenish_id"] == "R0001"
        assert d["book_id"] == "B001"
        assert d["replenish_date"] == "2024-03-15"
        assert d["quantity"] == 5
        assert d["unit_cost"] == 45.0
        assert d["total_cost"] == 213.75
        assert d["discount_pct"] == 5.0
        assert d["supplier"] == "Ingram"
        assert d["replenish_type"] == "Restock"
        assert d["condition"] == "New"
        assert d["funding_source"] == "Operating Budget"
        assert d["priority"] == "Normal"

    def test_from_row(self) -> None:
        row = (
            "R0002",
            "B010",
            date(2024, 6, 1),
            3,
            Decimal("30.00"),
            Decimal("85.50"),
            Decimal("5.00"),
            "Baker & Taylor",
            "New Acquisition",
            "Refurbished",
            "Grant",
            "High",
        )
        rec = Replenishment.from_row(row)
        assert rec.replenish_id == "R0002"
        assert rec.book_id == "B010"
        assert rec.supplier == Supplier.BAKER_TAYLOR
        assert rec.replenish_type == ReplenishType.NEW_ACQUISITION
        assert rec.condition == BookCondition.REFURBISHED
        assert rec.funding_source == FundingSource.GRANT
        assert rec.priority == Priority.HIGH

    def test_from_dict(self) -> None:
        data = {
            "replenish_id": "R0003",
            "book_id": "B020",
            "replenish_date": "2024-08-10",
            "quantity": 10,
            "unit_cost": 50.0,
            "total_cost": 425.0,
            "discount_pct": 15.0,
            "supplier": "Brodart",
            "replenish_type": "Restock",
            "condition": "New",
            "funding_source": "Special Collection",
            "priority": "Urgent",
        }
        rec = Replenishment.from_dict(data)
        assert rec.replenish_id == "R0003"
        assert rec.quantity == 10
        assert rec.supplier == Supplier.BRODART
        assert rec.priority == Priority.URGENT
        assert rec.replenish_date == date(2024, 8, 10)

    def test_frozen(self) -> None:
        """Test that Replenishment is immutable."""
        rec = self._make_replenishment()
        try:
            rec.quantity = 10  # type: ignore[misc]
            assert False, "Should not be able to modify frozen dataclass"
        except AttributeError:
            pass

    def test_roundtrip_dict(self) -> None:
        """Test to_dict -> from_dict roundtrip."""
        original = self._make_replenishment()
        d = original.to_dict()
        restored = Replenishment.from_dict(d)
        assert original.replenish_id == restored.replenish_id
        assert original.book_id == restored.book_id
        assert original.quantity == restored.quantity
        assert original.supplier == restored.supplier
