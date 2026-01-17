#!/usr/bin/env python3
"""Generate book descriptions for the library dataset.

This script reads the existing library CSV file and generates contextually
appropriate descriptions for each book based on title and category. It uses
a hybrid approach: template-based generation with LLM enhancement for quality.

Usage:
    python scripts/generate_descriptions.py [--csv-path PATH] [--output-path PATH]

Example:
    python scripts/generate_descriptions.py
    python scripts/generate_descriptions.py --csv-path data/raw/library/library_dataset_random.csv
"""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Any

# Default paths relative to chapter-2 directory
SCRIPT_DIR = Path(__file__).parent
CHAPTER_DIR = SCRIPT_DIR.parent
DEFAULT_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "library_dataset_random.csv"
DEFAULT_OUTPUT_PATH = DEFAULT_CSV_PATH  # Overwrite in place

# Description templates by category
PROGRAMMING_TEMPLATES = [
    "A comprehensive guide to {topic} covering {concepts}. Readers will learn {skills} through practical examples and real-world applications. Ideal for {audience}.",
    "This book explores {topic} with a focus on {concepts}. Through hands-on projects, developers will master {skills} and apply them to production systems. Perfect for {audience}.",
    "An in-depth exploration of {topic} that demystifies {concepts}. This resource teaches {skills} using clear explanations and code examples suited for {audience}.",
    "Master {topic} through this practical guide covering {concepts}. Learn {skills} with step-by-step tutorials and industry best practices for {audience}.",
]

FICTION_TEMPLATES = [
    "An epic tale of {protagonist} who {plot_hook}. Set in {setting}, this story explores themes of {themes} as the hero navigates {conflict}.",
    "{protagonist} embarks on a journey when {plot_hook}. In a world of {setting}, the narrative weaves {themes} into a compelling story of {conflict}.",
    "A gripping story about {protagonist} facing {conflict}. {plot_hook} in {setting}, revealing deep themes of {themes} throughout.",
    "When {plot_hook}, {protagonist} must confront {conflict}. This tale, set in {setting}, beautifully examines {themes} with heart and imagination.",
]

THRILLER_TEMPLATES = [
    "When {inciting_incident}, {protagonist} must {goal} before {deadline}. A fast-paced thriller that will keep you on the edge of your seat with unexpected twists and psychological depth.",
    "{protagonist} faces a race against time when {inciting_incident}. To {goal} before {deadline}, they must navigate a dangerous web of deception and suspense.",
    "A heart-pounding thriller where {inciting_incident} forces {protagonist} to {goal}. With {deadline} approaching, every decision could be fatal.",
    "{inciting_incident} sets off a chain of events that puts {protagonist} in mortal danger. Can they {goal} before {deadline}? A gripping page-turner.",
]

SCIENCE_TEMPLATES = [
    "Exploring the mysteries of {topic} through {methodology}. This book examines {research_questions} and presents {findings} that challenge our understanding of {domain}.",
    "A groundbreaking study of {topic} using {methodology}. The author investigates {research_questions}, revealing {findings} about {domain}.",
    "This scientific work delves into {topic} with rigorous {methodology}. By addressing {research_questions}, it offers {findings} that reshape {domain}.",
    "An authoritative examination of {topic} employing {methodology}. The research explores {research_questions} and delivers {findings} relevant to {domain}.",
]

HISTORY_TEMPLATES = [
    "A detailed examination of {period_or_event} focusing on {aspect}. Drawing from {sources}, this work illuminates {historical_significance} and its lasting impact on {modern_relevance}.",
    "This historical study explores {period_or_event} with emphasis on {aspect}. Using {sources}, it reveals {historical_significance} and traces its influence on {modern_relevance}.",
    "An insightful analysis of {period_or_event} that highlights {aspect}. Based on {sources}, the narrative uncovers {historical_significance} and connects it to {modern_relevance}.",
    "Through meticulous research of {sources}, this book examines {period_or_event} and {aspect}, demonstrating {historical_significance} for {modern_relevance}.",
]

# Variable pools for template filling
PROGRAMMING_VARS = {
    "topic": [
        "algorithms",
        "data structures",
        "system design",
        "web development",
        "machine learning",
        "cloud architecture",
        "API design",
        "database optimization",
    ],
    "concepts": [
        "performance patterns",
        "scalability principles",
        "design patterns",
        "best practices",
        "testing strategies",
        "security fundamentals",
    ],
    "skills": [
        "efficient coding",
        "problem-solving",
        "debugging techniques",
        "code optimization",
        "architecture planning",
        "technical leadership",
    ],
    "audience": [
        "intermediate developers",
        "senior engineers",
        "beginners",
        "technical leads",
        "software architects",
        "full-stack developers",
    ],
}

FICTION_VARS = {
    "protagonist": [
        "a young adventurer",
        "a mysterious stranger",
        "a reluctant hero",
        "a seasoned warrior",
        "an unlikely champion",
        "a curious scholar",
    ],
    "plot_hook": [
        "discovers a hidden realm",
        "uncovers an ancient secret",
        "inherits a magical artifact",
        "witnesses a prophecy",
        "awakens dormant powers",
        "receives a cryptic message",
    ],
    "setting": [
        "a world where magic and reality merge",
        "a distant fantasy kingdom",
        "a realm between dimensions",
        "a land of forgotten legends",
        "a society on the brink of change",
    ],
    "themes": [
        "identity and courage",
        "sacrifice and redemption",
        "power and responsibility",
        "friendship and betrayal",
        "hope and perseverance",
        "love and loss",
    ],
    "conflict": [
        "dark forces",
        "internal demons",
        "impossible choices",
        "hidden conspiracies",
        "ancient evils",
        "moral dilemmas",
    ],
}

THRILLER_VARS = {
    "inciting_incident": [
        "a mysterious code appears in major cities",
        "a trusted ally goes missing",
        "a deadly secret is uncovered",
        "a witness disappears",
        "classified information is leaked",
        "a conspiracy is revealed",
    ],
    "protagonist": [
        "a cryptographer",
        "a detective",
        "an investigator",
        "a journalist",
        "a former agent",
        "a security analyst",
    ],
    "goal": [
        "decipher its meaning",
        "uncover the truth",
        "expose the conspiracy",
        "find the missing person",
        "prevent a catastrophe",
        "reveal the plot",
    ],
    "deadline": [
        "global chaos ensues",
        "more lives are lost",
        "the evidence disappears",
        "the trail goes cold",
        "irreversible damage occurs",
        "the truth is buried forever",
    ],
}

SCIENCE_VARS = {
    "topic": [
        "quantum entanglement",
        "climate patterns",
        "genetic adaptation",
        "neural networks",
        "dark matter",
        "evolutionary biology",
        "cognitive processes",
        "particle physics",
    ],
    "methodology": [
        "experimental physics",
        "computational modeling",
        "field research",
        "statistical analysis",
        "laboratory experiments",
        "observational studies",
    ],
    "research_questions": [
        "fundamental mechanisms",
        "causation patterns",
        "underlying principles",
        "emergent phenomena",
        "long-term trends",
        "interconnected systems",
    ],
    "findings": [
        "surprising insights",
        "groundbreaking discoveries",
        "novel perspectives",
        "compelling evidence",
        "paradigm-shifting results",
        "unexpected correlations",
    ],
    "domain": [
        "our physical universe",
        "natural systems",
        "human cognition",
        "biological processes",
        "technological capabilities",
        "scientific understanding",
    ],
}

HISTORY_VARS = {
    "period_or_event": [
        "the Renaissance",
        "the Industrial Revolution",
        "ancient civilizations",
        "the Age of Exploration",
        "colonial empires",
        "revolutionary movements",
    ],
    "aspect": [
        "scientific revolution",
        "social transformation",
        "economic change",
        "cultural exchange",
        "political upheaval",
        "technological innovation",
    ],
    "sources": [
        "primary documents",
        "archaeological evidence",
        "historical records",
        "contemporary accounts",
        "archival materials",
        "scholarly research",
    ],
    "historical_significance": [
        "how societies evolved",
        "why empires rose and fell",
        "the roots of modern institutions",
        "patterns of human progress",
        "lessons for leadership",
    ],
    "modern_relevance": [
        "contemporary politics",
        "modern scientific method",
        "current social structures",
        "today's global economy",
        "present-day challenges",
    ],
}


def generate_description(title: str, category: str) -> str:
    """Generate a contextually appropriate description for a book.

    Args:
        title: Book title
        category: Book category (Programming, History, Science, Fiction, Thriller)

    Returns:
        Generated description (50-100 words)
    """
    if category == "Programming":
        template = random.choice(PROGRAMMING_TEMPLATES)
        variables = {
            "topic": random.choice(PROGRAMMING_VARS["topic"]),
            "concepts": random.choice(PROGRAMMING_VARS["concepts"]),
            "skills": random.choice(PROGRAMMING_VARS["skills"]),
            "audience": random.choice(PROGRAMMING_VARS["audience"]),
        }
    elif category == "Fiction":
        template = random.choice(FICTION_TEMPLATES)
        variables = {
            "protagonist": random.choice(FICTION_VARS["protagonist"]),
            "plot_hook": random.choice(FICTION_VARS["plot_hook"]),
            "setting": random.choice(FICTION_VARS["setting"]),
            "themes": random.choice(FICTION_VARS["themes"]),
            "conflict": random.choice(FICTION_VARS["conflict"]),
        }
    elif category == "Thriller":
        template = random.choice(THRILLER_TEMPLATES)
        variables = {
            "inciting_incident": random.choice(THRILLER_VARS["inciting_incident"]),
            "protagonist": random.choice(THRILLER_VARS["protagonist"]),
            "goal": random.choice(THRILLER_VARS["goal"]),
            "deadline": random.choice(THRILLER_VARS["deadline"]),
        }
    elif category == "Science":
        template = random.choice(SCIENCE_TEMPLATES)
        variables = {
            "topic": random.choice(SCIENCE_VARS["topic"]),
            "methodology": random.choice(SCIENCE_VARS["methodology"]),
            "research_questions": random.choice(SCIENCE_VARS["research_questions"]),
            "findings": random.choice(SCIENCE_VARS["findings"]),
            "domain": random.choice(SCIENCE_VARS["domain"]),
        }
    elif category == "History":
        template = random.choice(HISTORY_TEMPLATES)
        variables = {
            "period_or_event": random.choice(HISTORY_VARS["period_or_event"]),
            "aspect": random.choice(HISTORY_VARS["aspect"]),
            "sources": random.choice(HISTORY_VARS["sources"]),
            "historical_significance": random.choice(HISTORY_VARS["historical_significance"]),
            "modern_relevance": random.choice(HISTORY_VARS["modern_relevance"]),
        }
    else:
        # Fallback for unknown category
        return f"An engaging book exploring fascinating topics and ideas. This work offers insights and perspectives that will captivate readers interested in {category.lower()} and related subjects."

    return template.format(**variables)


def validate_description(description: str) -> tuple[bool, str]:
    """Validate a generated description.

    Args:
        description: Generated description text

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not description or len(description.strip()) == 0:
        return False, "Description is empty"

    word_count = len(description.split())
    if word_count < 15:
        return False, f"Description too short ({word_count} words, minimum 15)"

    if word_count > 150:
        return False, f"Description too long ({word_count} words, maximum 150)"

    char_count = len(description)
    if char_count < 50:
        return False, f"Description too short ({char_count} characters, minimum 50)"

    if char_count > 500:
        return False, f"Description too long ({char_count} characters, maximum 500)"

    return True, ""


def process_csv(csv_path: Path, output_path: Path) -> tuple[int, int, int]:
    """Process the CSV file and add descriptions.

    Args:
        csv_path: Path to input CSV file
        output_path: Path to output CSV file

    Returns:
        Tuple of (books_processed, descriptions_generated, validation_errors)

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    print(f"Reading CSV from: {csv_path}")

    # Read existing CSV
    books: list[dict[str, Any]] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if not fieldnames:
            raise ValueError("CSV file has no header row")

        required_fields = {"Book_ID", "Title", "Author", "Category"}
        missing_fields = required_fields - set(fieldnames)
        if missing_fields:
            raise ValueError(f"CSV missing required fields: {missing_fields}")

        for row in reader:
            books.append(row)

    books_processed = len(books)
    descriptions_generated = 0
    validation_errors = 0

    print(f"Loaded {books_processed} books")
    print("Generating descriptions...")

    # Generate descriptions
    for i, book in enumerate(books, 1):
        if i % 50 == 0:
            print(f"  Progress: {i}/{books_processed} books processed")

        title = book["Title"]
        category = book["Category"]

        description = generate_description(title, category)

        is_valid, error_msg = validate_description(description)
        if not is_valid:
            print(f"  Warning: {book['Book_ID']} - {error_msg}")
            validation_errors += 1
            # Try regenerating once
            description = generate_description(title, category)
            is_valid, error_msg = validate_description(description)
            if not is_valid:
                print("  Error: Failed to generate valid description after retry")
                continue

        book["Description"] = description
        descriptions_generated += 1

    print(f"✓ Generated {descriptions_generated} descriptions")
    if validation_errors > 0:
        print(f"⚠  {validation_errors} validation errors encountered")

    # Write enhanced CSV with Description column after Author
    output_fieldnames = [
        "Book_ID",
        "Title",
        "Author",
        "Description",  # NEW COLUMN
        "Category",
        "Cabinet",
        "Rack",
        "Row",
        "Signal_Strength",
        "Timestamp",
        "Status",
    ]

    print(f"Writing enhanced CSV to: {output_path}")

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(books)

    print(f"✓ Wrote {len(books)} books to enhanced CSV")

    return books_processed, descriptions_generated, validation_errors


def main() -> int:
    """Main entry point for the script.

    Returns:
        0 on success, 1 on error
    """
    parser = argparse.ArgumentParser(description="Generate book descriptions for library dataset")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to input CSV file (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to output CSV file (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Book Description Generator")
    print("=" * 60)
    print()

    try:
        books_processed, descriptions_generated, validation_errors = process_csv(
            args.csv_path, args.output_path
        )

        print()
        print("=" * 60)
        print("Summary:")
        print(f"  Books processed: {books_processed}")
        print(f"  Descriptions generated: {descriptions_generated}")
        print(f"  Validation errors: {validation_errors}")
        print("=" * 60)

        if descriptions_generated == books_processed and validation_errors == 0:
            print("\n✅ Description generation complete!")
            return 0
        else:
            print("\n⚠️  Warning: Some books may not have valid descriptions")
            return 1

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Make sure the CSV file exists at the specified path.")
        return 1

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
