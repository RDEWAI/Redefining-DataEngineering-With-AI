#!/usr/bin/env python3
"""Generate synthetic sales data for library books.

This script generates realistic sales data for the 200 books in the library database.
It creates ~750 sales records with realistic distributions for:
- Seasonal patterns (higher in Nov-Dec holidays, Aug-Sep back-to-school)
- Category-based pricing (Programming $35-65, Fiction $15-25, etc.)
- Customer segment correlations (Corporate = higher bulk purchases)
- Channel distribution (Online 60%, In-Store 30%, Others 10%)

Usage:
    python scripts/generate_sales_data.py
    python scripts/generate_sales_data.py --num-sales 1000
    python scripts/generate_sales_data.py --output data/raw/library/sales_data.csv
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

# Ensure reproducible results
random.seed(42)

# Output path
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "raw" / "library" / "sales_data.csv"

# Sales data constants
CUSTOMER_SEGMENTS = ["Individual", "Corporate", "Educational", "Government"]
REGIONS = ["Northeast", "Southeast", "Midwest", "West", "International"]
CHANNELS = ["In-Store", "Online", "Phone Order", "Partner"]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "Cash", "Digital Wallet"]

# Category-based pricing ranges
CATEGORY_PRICES = {
    "Programming": (35.00, 65.00),
    "Science": (30.00, 55.00),
    "History": (20.00, 40.00),
    "Fiction": (15.00, 28.00),
    "Thriller": (12.00, 25.00),
}

# Segment distribution weights (Individual most common)
SEGMENT_WEIGHTS = {
    "Individual": 0.55,
    "Corporate": 0.20,
    "Educational": 0.15,
    "Government": 0.10,
}

# Channel distribution weights
CHANNEL_WEIGHTS = {
    "Online": 0.55,
    "In-Store": 0.30,
    "Phone Order": 0.08,
    "Partner": 0.07,
}

# Region distribution weights
REGION_WEIGHTS = {
    "Northeast": 0.25,
    "Southeast": 0.22,
    "Midwest": 0.18,
    "West": 0.28,
    "International": 0.07,
}

# Payment method weights by channel
PAYMENT_WEIGHTS_BY_CHANNEL = {
    "Online": {"Credit Card": 0.50, "Debit Card": 0.30, "Digital Wallet": 0.20, "Cash": 0.00},
    "In-Store": {"Credit Card": 0.35, "Debit Card": 0.25, "Cash": 0.35, "Digital Wallet": 0.05},
    "Phone Order": {"Credit Card": 0.60, "Debit Card": 0.30, "Digital Wallet": 0.10, "Cash": 0.00},
    "Partner": {"Credit Card": 0.45, "Debit Card": 0.35, "Digital Wallet": 0.15, "Cash": 0.05},
}

# Monthly sales distribution (seasonal patterns)
# Higher in Nov-Dec (holidays), Aug-Sep (back-to-school)
MONTHLY_WEIGHTS = {
    1: 0.07,   # January
    2: 0.06,   # February
    3: 0.07,   # March
    4: 0.08,   # April
    5: 0.07,   # May
    6: 0.06,   # June
    7: 0.05,   # July (summer lull)
    8: 0.10,   # August (back-to-school)
    9: 0.11,   # September (back-to-school)
    10: 0.08,  # October
    11: 0.12,  # November (holidays)
    12: 0.13,  # December (holidays)
}

# Quantity distributions by segment
QUANTITY_WEIGHTS_BY_SEGMENT = {
    "Individual": {1: 0.85, 2: 0.10, 3: 0.03, 4: 0.01, 5: 0.01},
    "Corporate": {1: 0.20, 2: 0.25, 3: 0.20, 5: 0.15, 10: 0.12, 15: 0.05, 20: 0.03},
    "Educational": {1: 0.15, 2: 0.20, 3: 0.20, 5: 0.20, 10: 0.15, 15: 0.07, 20: 0.03},
    "Government": {1: 0.30, 2: 0.25, 3: 0.20, 5: 0.15, 10: 0.07, 15: 0.03},
}

# Discount distributions by segment (discount percentages)
DISCOUNT_WEIGHTS_BY_SEGMENT = {
    "Individual": {0: 0.70, 5: 0.15, 10: 0.10, 15: 0.04, 20: 0.01},
    "Corporate": {0: 0.30, 5: 0.25, 10: 0.25, 15: 0.12, 20: 0.08},
    "Educational": {0: 0.20, 5: 0.20, 10: 0.25, 15: 0.20, 20: 0.15},
    "Government": {0: 0.25, 5: 0.25, 10: 0.25, 15: 0.15, 20: 0.10},
}


def weighted_choice(weights_dict: dict) -> str:
    """Select a random item based on weights."""
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_sale_date(year: int = 2024) -> date:
    """Generate a random sale date with seasonal distribution."""
    # First pick a month based on weights
    month = weighted_choice(MONTHLY_WEIGHTS)

    # Then pick a random day in that month
    if month == 12:
        max_day = 25  # Stop before Christmas
    elif month == 2:
        max_day = 28  # February
    elif month in [4, 6, 9, 11]:
        max_day = 30  # 30-day months
    else:
        max_day = 31

    day = random.randint(1, max_day)
    return date(year, month, day)


def generate_customer_id(segment: str, existing_customers: dict) -> str:
    """Generate or reuse a customer ID based on segment."""
    # Corporate and Educational tend to be repeat customers
    if segment in ["Corporate", "Educational", "Government"]:
        # 70% chance of reusing existing customer
        if segment in existing_customers and random.random() < 0.70:
            return random.choice(existing_customers[segment])

    # Generate new customer ID
    if segment not in existing_customers:
        existing_customers[segment] = []

    customer_num = len(existing_customers[segment]) + 1
    prefix = {"Individual": "IND", "Corporate": "CORP", "Educational": "EDU", "Government": "GOV"}
    customer_id = f"{prefix[segment]}{customer_num:04d}"
    existing_customers[segment].append(customer_id)

    return customer_id


def generate_sales_data(
    book_ids: list[str],
    book_categories: dict[str, str],
    num_sales: int = 750,
) -> list[dict]:
    """Generate synthetic sales records.

    Args:
        book_ids: List of book IDs (B001-B200)
        book_categories: Mapping of book_id to category
        num_sales: Number of sales records to generate

    Returns:
        List of sale dictionaries
    """
    sales = []
    existing_customers: dict[str, list[str]] = {}

    for i in range(num_sales):
        sale_id = f"S{i + 1:04d}"

        # Select book (weight popular categories slightly higher)
        book_id = random.choice(book_ids)
        category = book_categories.get(book_id, "Fiction")

        # Generate sale attributes
        segment = weighted_choice(SEGMENT_WEIGHTS)
        region = weighted_choice(REGION_WEIGHTS)
        channel = weighted_choice(CHANNEL_WEIGHTS)

        # Payment method depends on channel
        payment_weights = PAYMENT_WEIGHTS_BY_CHANNEL[channel]
        # Filter out zero-weight options
        payment_weights = {k: v for k, v in payment_weights.items() if v > 0}
        payment_method = weighted_choice(payment_weights)

        # Quantity depends on segment
        quantity = weighted_choice(QUANTITY_WEIGHTS_BY_SEGMENT[segment])

        # Price based on category with some variance
        price_range = CATEGORY_PRICES.get(category, (20.00, 40.00))
        unit_price = round(random.uniform(*price_range), 2)

        # Discount depends on segment
        discount = weighted_choice(DISCOUNT_WEIGHTS_BY_SEGMENT[segment])

        # Calculate total
        subtotal = quantity * unit_price
        discount_amount = subtotal * (discount / 100)
        total_amount = round(subtotal - discount_amount, 2)

        # Generate date and customer
        sale_date = generate_sale_date(2024)
        customer_id = generate_customer_id(segment, existing_customers)

        sales.append({
            "sale_id": sale_id,
            "book_id": book_id,
            "sale_date": sale_date.isoformat(),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "discount": discount,
            "payment_method": payment_method,
            "customer_id": customer_id,
            "customer_segment": segment,
            "region": region,
            "channel": channel,
        })

    # Sort by date for realistic data appearance
    sales.sort(key=lambda x: x["sale_date"])

    return sales


def load_book_data(db_path: str | None = None) -> tuple[list[str], dict[str, str]]:
    """Load book IDs and categories from database or generate defaults."""
    try:
        import duckdb

        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "duckdb" / "chapter3.db")

        if Path(db_path).exists():
            conn = duckdb.connect(db_path, read_only=True)
            result = conn.execute("SELECT book_id, category FROM library.books").fetchall()
            conn.close()

            book_ids = [row[0] for row in result]
            book_categories = {row[0]: row[1] for row in result}
            print(f"Loaded {len(book_ids)} books from database")
            return book_ids, book_categories
    except Exception as e:
        print(f"Could not load from database: {e}")

    # Fallback: generate default book IDs
    print("Using default book IDs (B001-B200)")
    book_ids = [f"B{i:03d}" for i in range(1, 201)]
    categories = ["Programming", "History", "Science", "Fiction", "Thriller"]
    book_categories = {bid: random.choice(categories) for bid in book_ids}

    return book_ids, book_categories


def write_csv(sales: list[dict], output_path: Path) -> None:
    """Write sales data to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "sale_id", "book_id", "sale_date", "quantity", "unit_price",
        "total_amount", "discount", "payment_method", "customer_id",
        "customer_segment", "region", "channel"
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sales)

    print(f"Wrote {len(sales)} sales records to {output_path}")


def print_summary(sales: list[dict]) -> None:
    """Print summary statistics of generated data."""
    print("\n" + "=" * 60)
    print("Sales Data Summary")
    print("=" * 60)

    print(f"\nTotal records: {len(sales)}")

    # By segment
    segments = {}
    for sale in sales:
        seg = sale["customer_segment"]
        segments[seg] = segments.get(seg, 0) + 1
    print("\nBy Customer Segment:")
    for seg, count in sorted(segments.items()):
        print(f"  {seg}: {count} ({100*count/len(sales):.1f}%)")

    # By region
    regions = {}
    for sale in sales:
        reg = sale["region"]
        regions[reg] = regions.get(reg, 0) + 1
    print("\nBy Region:")
    for reg, count in sorted(regions.items()):
        print(f"  {reg}: {count} ({100*count/len(sales):.1f}%)")

    # By channel
    channels = {}
    for sale in sales:
        ch = sale["channel"]
        channels[ch] = channels.get(ch, 0) + 1
    print("\nBy Channel:")
    for ch, count in sorted(channels.items()):
        print(f"  {ch}: {count} ({100*count/len(sales):.1f}%)")

    # Revenue stats
    total_revenue = sum(sale["total_amount"] for sale in sales)
    total_quantity = sum(sale["quantity"] for sale in sales)
    avg_order = total_revenue / len(sales)

    print(f"\nRevenue Statistics:")
    print(f"  Total Revenue: ${total_revenue:,.2f}")
    print(f"  Total Units Sold: {total_quantity:,}")
    print(f"  Average Order Value: ${avg_order:.2f}")

    # Unique customers
    unique_customers = len(set(sale["customer_id"] for sale in sales))
    print(f"  Unique Customers: {unique_customers}")

    print("=" * 60)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate synthetic sales data")
    parser.add_argument(
        "--num-sales",
        type=int,
        default=750,
        help="Number of sales records to generate (default: 750)",
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

    print("Generating sales data...")

    # Load book data
    book_ids, book_categories = load_book_data(args.db_path)

    # Generate sales
    sales = generate_sales_data(book_ids, book_categories, args.num_sales)

    # Write to CSV
    write_csv(sales, args.output)

    # Print summary
    print_summary(sales)


if __name__ == "__main__":
    main()
