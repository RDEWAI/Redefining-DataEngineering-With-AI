#!/usr/bin/env python3
"""Generate synthetic replenish data for library books.

This script generates realistic replenishment data for the 200 books in the library database.
It creates ~500 replenishment records with realistic distributions for:
- Seasonal patterns (higher in Aug-Sep academic prep, Jan new-year budget)
- Category-based cost ranges (Programming $35-75, Fiction $10-25, etc.)
- Supplier distribution (Ingram 35%, Baker & Taylor 25%, etc.)
- Replenish type correlations (New Acquisition, Replacement, Restock, etc.)
- Quantity-based discount tiers

Usage:
    python scripts/generate_replenish_data.py
    python scripts/generate_replenish_data.py --num-records 1000
    python scripts/generate_replenish_data.py --output data/raw/library/replenish_data.csv
"""

import argparse
import csv
import random
from datetime import date
from pathlib import Path

# Ensure reproducible results
random.seed(42)

# Output path
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "raw" / "library" / "replenish_data.csv"

# Replenish data constants
SUPPLIERS = ["Ingram", "Baker & Taylor", "Brodart", "Direct Publisher", "Amazon Business"]
REPLENISH_TYPES = ["New Acquisition", "Replacement", "Restock", "Donation", "Return Processing"]
CONDITIONS = ["New", "Refurbished", "Used - Good", "Used - Fair"]
FUNDING_SOURCES = [
    "Operating Budget",
    "Grant",
    "Donation Fund",
    "Special Collection",
    "Emergency Fund",
]
PRIORITIES = ["Urgent", "High", "Normal", "Low"]

# Category-based unit cost ranges
CATEGORY_COSTS = {
    "Programming": (35.00, 75.00),
    "Science": (30.00, 60.00),
    "History": (20.00, 45.00),
    "Fiction": (10.00, 25.00),
    "Thriller": (12.00, 28.00),
}

# Supplier distribution weights
SUPPLIER_WEIGHTS = {
    "Ingram": 0.35,
    "Baker & Taylor": 0.25,
    "Brodart": 0.15,
    "Direct Publisher": 0.15,
    "Amazon Business": 0.10,
}

# Replenish type weights
REPLENISH_TYPE_WEIGHTS = {
    "Restock": 0.35,
    "New Acquisition": 0.25,
    "Replacement": 0.20,
    "Donation": 0.10,
    "Return Processing": 0.10,
}

# Condition weights by replenish type
CONDITION_WEIGHTS_BY_TYPE = {
    "New Acquisition": {"New": 0.90, "Refurbished": 0.10, "Used - Good": 0.00, "Used - Fair": 0.00},
    "Replacement": {"New": 0.70, "Refurbished": 0.20, "Used - Good": 0.10, "Used - Fair": 0.00},
    "Restock": {"New": 0.80, "Refurbished": 0.15, "Used - Good": 0.05, "Used - Fair": 0.00},
    "Donation": {"New": 0.10, "Refurbished": 0.20, "Used - Good": 0.45, "Used - Fair": 0.25},
    "Return Processing": {
        "New": 0.05,
        "Refurbished": 0.30,
        "Used - Good": 0.40,
        "Used - Fair": 0.25,
    },
}

# Funding source weights
FUNDING_SOURCE_WEIGHTS = {
    "Operating Budget": 0.40,
    "Grant": 0.20,
    "Donation Fund": 0.15,
    "Special Collection": 0.15,
    "Emergency Fund": 0.10,
}

# Priority weights
PRIORITY_WEIGHTS = {
    "Normal": 0.50,
    "High": 0.25,
    "Urgent": 0.10,
    "Low": 0.15,
}

# Monthly replenish distribution (seasonal patterns)
# Higher in Aug-Sep (academic prep), Jan (new-year budget)
MONTHLY_WEIGHTS = {
    1: 0.12,  # January (new-year budget)
    2: 0.07,  # February
    3: 0.08,  # March
    4: 0.07,  # April
    5: 0.06,  # May
    6: 0.05,  # June
    7: 0.05,  # July (summer lull)
    8: 0.13,  # August (academic prep)
    9: 0.12,  # September (academic prep)
    10: 0.08,  # October
    11: 0.09,  # November
    12: 0.08,  # December
}


def weighted_choice(weights_dict: dict) -> str:
    """Select a random item based on weights."""
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_replenish_date(year: int = 2024) -> date:
    """Generate a random replenish date with seasonal distribution."""
    month = weighted_choice(MONTHLY_WEIGHTS)

    if month == 2:
        max_day = 28
    elif month in [4, 6, 9, 11]:
        max_day = 30
    else:
        max_day = 31

    day = random.randint(1, max_day)
    return date(year, month, day)


def generate_replenish_data(
    book_ids: list[str],
    book_categories: dict[str, str],
    num_records: int = 500,
) -> list[dict]:
    """Generate synthetic replenishment records.

    Args:
        book_ids: List of book IDs (B001-B200)
        book_categories: Mapping of book_id to category
        num_records: Number of replenishment records to generate

    Returns:
        List of replenishment dictionaries
    """
    records = []

    for i in range(num_records):
        replenish_id = f"R{i + 1:04d}"

        # Select book
        book_id = random.choice(book_ids)
        category = book_categories.get(book_id, "Fiction")

        # Generate replenish attributes
        supplier = weighted_choice(SUPPLIER_WEIGHTS)
        replenish_type = weighted_choice(REPLENISH_TYPE_WEIGHTS)

        # Condition depends on replenish type
        condition_weights = CONDITION_WEIGHTS_BY_TYPE[replenish_type]
        condition_weights = {k: v for k, v in condition_weights.items() if v > 0}
        condition = weighted_choice(condition_weights)

        funding_source = weighted_choice(FUNDING_SOURCE_WEIGHTS)
        priority = weighted_choice(PRIORITY_WEIGHTS)

        # Quantity: 1-3 for standard, 5-20 for bulk restocks
        if replenish_type == "Restock" and random.random() < 0.3:
            quantity = random.choice([5, 8, 10, 12, 15, 20])
        elif replenish_type == "New Acquisition" and random.random() < 0.2:
            quantity = random.choice([3, 5, 8, 10])
        else:
            quantity = random.choices([1, 2, 3], weights=[0.60, 0.25, 0.15], k=1)[0]

        # Unit cost based on category with variance
        cost_range = CATEGORY_COSTS.get(category, (20.00, 40.00))
        # Used/refurbished items cost less
        if condition == "Used - Fair":
            unit_cost = round(random.uniform(cost_range[0] * 0.3, cost_range[0] * 0.5), 2)
        elif condition == "Used - Good":
            unit_cost = round(random.uniform(cost_range[0] * 0.5, cost_range[0] * 0.7), 2)
        elif condition == "Refurbished":
            unit_cost = round(random.uniform(cost_range[0] * 0.6, cost_range[0] * 0.85), 2)
        else:
            unit_cost = round(random.uniform(*cost_range), 2)

        # Discount by quantity: 0% for qty 1, up to 25% for qty 20
        if quantity == 1:
            discount_pct = 0.0
        elif quantity <= 3:
            discount_pct = round(random.uniform(0, 5), 2)
        elif quantity <= 10:
            discount_pct = round(random.uniform(5, 15), 2)
        else:
            discount_pct = round(random.uniform(10, 25), 2)

        # Donations are free
        if replenish_type == "Donation":
            unit_cost = 0.00
            discount_pct = 0.00

        # Calculate total cost
        subtotal = quantity * unit_cost
        discount_amount = subtotal * (discount_pct / 100)
        total_cost = round(subtotal - discount_amount, 2)

        replenish_date = generate_replenish_date(2024)

        records.append(
            {
                "replenish_id": replenish_id,
                "book_id": book_id,
                "replenish_date": replenish_date.isoformat(),
                "quantity": quantity,
                "unit_cost": unit_cost,
                "total_cost": total_cost,
                "discount_pct": discount_pct,
                "supplier": supplier,
                "replenish_type": replenish_type,
                "condition": condition,
                "funding_source": funding_source,
                "priority": priority,
            }
        )

    # Sort by date
    records.sort(key=lambda x: x["replenish_date"])

    return records


def load_book_data(db_path: str | None = None) -> tuple[list[str], dict[str, str]]:
    """Load book IDs and categories from database or generate defaults."""
    try:
        import duckdb

        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "duckdb" / "chapter2.db")

        if Path(db_path).exists():
            conn = duckdb.connect(db_path, read_only=True)
            result = conn.execute("SELECT book_id, category FROM library.books").fetchall()
            conn.close()

            book_ids = [row[0] for row in result]
            book_categories = {row[0]: row[1] for row in result}
            print(f"Loaded {len(book_ids)} books from database")
            return book_ids, book_categories
    except (ImportError, FileNotFoundError, OSError) as e:
        print(f"Could not load from database: {e}")

    # Fallback: generate default book IDs
    print("Using default book IDs (B001-B200)")
    book_ids = [f"B{i:03d}" for i in range(1, 201)]
    categories = ["Programming", "History", "Science", "Fiction", "Thriller"]
    book_categories = {bid: random.choice(categories) for bid in book_ids}

    return book_ids, book_categories


def write_csv(records: list[dict], output_path: Path) -> None:
    """Write replenish data to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "replenish_id",
        "book_id",
        "replenish_date",
        "quantity",
        "unit_cost",
        "total_cost",
        "discount_pct",
        "supplier",
        "replenish_type",
        "condition",
        "funding_source",
        "priority",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} replenish records to {output_path}")


def print_summary(records: list[dict]) -> None:
    """Print summary statistics of generated data."""
    print("\n" + "=" * 60)
    print("Replenish Data Summary")
    print("=" * 60)

    print(f"\nTotal records: {len(records)}")

    # By supplier
    suppliers: dict[str, int] = {}
    for rec in records:
        sup = rec["supplier"]
        suppliers[sup] = suppliers.get(sup, 0) + 1
    print("\nBy Supplier:")
    for sup, count in sorted(suppliers.items()):
        print(f"  {sup}: {count} ({100*count/len(records):.1f}%)")

    # By type
    types: dict[str, int] = {}
    for rec in records:
        t = rec["replenish_type"]
        types[t] = types.get(t, 0) + 1
    print("\nBy Replenish Type:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count} ({100*count/len(records):.1f}%)")

    # By condition
    conditions: dict[str, int] = {}
    for rec in records:
        c = rec["condition"]
        conditions[c] = conditions.get(c, 0) + 1
    print("\nBy Condition:")
    for c, count in sorted(conditions.items()):
        print(f"  {c}: {count} ({100*count/len(records):.1f}%)")

    # Cost stats
    total_cost = sum(rec["total_cost"] for rec in records)
    total_quantity = sum(rec["quantity"] for rec in records)
    avg_cost = total_cost / len(records) if records else 0

    print("\nCost Statistics:")
    print(f"  Total Cost: ${total_cost:,.2f}")
    print(f"  Total Copies Added: {total_quantity:,}")
    print(f"  Average Record Cost: ${avg_cost:.2f}")

    # Unique books
    unique_books = len(set(rec["book_id"] for rec in records))
    print(f"  Unique Books Replenished: {unique_books}")

    print("=" * 60)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate synthetic replenish data")
    parser.add_argument(
        "--num-records",
        type=int,
        default=500,
        help="Number of replenish records to generate (default: 500)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to DuckDB database to load book IDs from",
    )

    args = parser.parse_args()

    print("Generating replenish data...")

    # Load book data
    book_ids, book_categories = load_book_data(args.db_path)

    # Generate records
    records = generate_replenish_data(book_ids, book_categories, args.num_records)

    # Write to CSV
    write_csv(records, args.output)

    # Print summary
    print_summary(records)


if __name__ == "__main__":
    main()
