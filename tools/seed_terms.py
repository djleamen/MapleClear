#!/usr/bin/env python3
"""
Seed terminology database with common Canadian government acronyms and terms.

This script creates a SQLite database with acronyms and terminology commonly
found on government websites. The data comes from public sources and helps
improve the accuracy of simplification and translation.
"""

import argparse
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
import json

# Common Canadian government acronyms
GOVERNMENT_ACRONYMS = [
    {
        "acronym": "CRA",
        "expansion": "Canada Revenue Agency",
        "definition": "Federal agency responsible for tax collection and benefits administration",
        "source_url": "https://www.canada.ca/en/revenue-agency.html",
        "language": "en"
    },
    {
        "acronym": "ARC",
        "expansion": "Agence du revenu du Canada",
        "definition": "Agence fédérale responsable de la perception des impôts et de l'administration des prestations",
        "source_url": "https://www.canada.ca/fr/agence-revenu.html",
        "language": "fr"
    },
    {
        "acronym": "EI",
        "expansion": "Employment Insurance",
        "definition": "Government program providing temporary income support for unemployed workers",
        "source_url": "https://www.canada.ca/en/services/benefits/ei.html",
        "language": "en"
    },
    {
        "acronym": "AE",
        "expansion": "Assurance-emploi",
        "definition": "Programme gouvernemental offrant un soutien temporaire du revenu aux travailleurs sans emploi",
        "source_url": "https://www.canada.ca/fr/services/prestations/ae.html",
        "language": "fr"
    },
    {
        "acronym": "CPP",
        "expansion": "Canada Pension Plan",
        "definition": "Government pension program for Canadian workers",
        "source_url": "https://www.canada.ca/en/services/benefits/publicpensions/cpp.html",
        "language": "en"
    },
    {
        "acronym": "RPC",
        "expansion": "Régime de pensions du Canada",
        "definition": "Programme de pension gouvernemental pour les travailleurs canadiens",
        "source_url": "https://www.canada.ca/fr/services/prestations/pensionspubliques/rpc.html",
        "language": "fr"
    },
    {
        "acronym": "GST",
        "expansion": "Goods and Services Tax",
        "definition": "Federal value-added tax on most goods and services",
        "source_url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html",
        "language": "en"
    },
    {
        "acronym": "TPS",
        "expansion": "Taxe sur les produits et services",
        "definition": "Taxe fédérale sur la valeur ajoutée sur la plupart des biens et services",
        "source_url": "https://www.canada.ca/fr/agence-revenu/services/impot/entreprises/sujets/tps-tvh-entreprises.html",
        "language": "fr"
    },
    {
        "acronym": "HST",
        "expansion": "Harmonized Sales Tax",
        "definition": "Combined federal and provincial sales tax in participating provinces",
        "source_url": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html",
        "language": "en"
    },
    {
        "acronym": "SIN",
        "expansion": "Social Insurance Number",
        "definition": "Nine-digit number needed to work in Canada or access government programs",
        "source_url": "https://www.canada.ca/en/employment-social-development/services/sin.html",
        "language": "en"
    },
    {
        "acronym": "NAS",
        "expansion": "Numéro d'assurance sociale",
        "definition": "Numéro à neuf chiffres nécessaire pour travailler au Canada ou accéder aux programmes gouvernementaux",
        "source_url": "https://www.canada.ca/fr/emploi-developpement-social/services/nas.html",
        "language": "fr"
    },
    {
        "acronym": "IRCC",
        "expansion": "Immigration, Refugees and Citizenship Canada",
        "definition": "Federal department responsible for immigration and citizenship services",
        "source_url": "https://www.canada.ca/en/immigration-refugees-citizenship.html",
        "language": "en"
    },
    {
        "acronym": "ESDC",
        "expansion": "Employment and Social Development Canada",
        "definition": "Federal department responsible for employment and social programs",
        "source_url": "https://www.canada.ca/en/employment-social-development.html",
        "language": "en"
    },
    {
        "acronym": "PHAC",
        "expansion": "Public Health Agency of Canada",
        "definition": "Federal agency responsible for public health protection and promotion",
        "source_url": "https://www.canada.ca/en/public-health.html",
        "language": "en"
    },
    {
        "acronym": "ASPC",
        "expansion": "Agence de la santé publique du Canada",
        "definition": "Agence fédérale responsable de la protection et de la promotion de la santé publique",
        "source_url": "https://www.canada.ca/fr/sante-publique.html",
        "language": "fr"
    }
]

# Common government terms for translation consistency
GOVERNMENT_TERMS = [
    {
        "term_en": "Canada Revenue Agency",
        "term_fr": "Agence du revenu du Canada",
        "definition_en": "Federal agency responsible for tax collection",
        "definition_fr": "Agence fédérale responsable de la perception des impôts",
        "category": "organization",
        "official": True
    },
    {
        "term_en": "Employment Insurance",
        "term_fr": "Assurance-emploi",
        "definition_en": "Temporary income support for unemployed workers",
        "definition_fr": "Soutien temporaire du revenu pour les travailleurs sans emploi",
        "category": "program",
        "official": True
    },
    {
        "term_en": "Canada Pension Plan",
        "term_fr": "Régime de pensions du Canada",
        "definition_en": "Government pension program",
        "definition_fr": "Programme de pension gouvernemental",
        "category": "program",
        "official": True
    },
    {
        "term_en": "Social Insurance Number",
        "term_fr": "Numéro d'assurance sociale",
        "definition_en": "Nine-digit identification number",
        "definition_fr": "Numéro d'identification à neuf chiffres",
        "category": "document",
        "official": True
    },
    {
        "term_en": "Goods and Services Tax",
        "term_fr": "Taxe sur les produits et services",
        "definition_en": "Federal value-added tax",
        "definition_fr": "Taxe fédérale sur la valeur ajoutée",
        "category": "tax",
        "official": True
    }
]


def create_database(db_path: Path) -> None:
    """Create the terminology database with initial schema."""
    print(f"Creating database at {db_path}")

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Create acronyms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acronyms (
                id INTEGER PRIMARY KEY,
                acronym TEXT UNIQUE,
                expansion TEXT,
                definition TEXT,
                source_url TEXT,
                language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create terms table for translation consistency
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY,
                term_en TEXT,
                term_fr TEXT,
                definition_en TEXT,
                definition_fr TEXT,
                category TEXT,
                official BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster lookups
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_acronym ON acronyms(acronym)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_term_en ON terms(term_en)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_term_fr ON terms(term_fr)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_language ON acronyms(language)")

        conn.commit()
        print("✅ Database schema created")


def seed_acronyms(db_path: Path, acronyms: List[Dict[str, Any]]) -> None:
    """Seed the database with acronym data."""
    print(f"Seeding {len(acronyms)} acronyms...")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for acronym_data in acronyms:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO acronyms 
                    (acronym, expansion, definition, source_url, language)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    acronym_data["acronym"],
                    acronym_data["expansion"],
                    acronym_data["definition"],
                    acronym_data["source_url"],
                    acronym_data["language"]
                ))
            except sqlite3.Error as e:
                print(
                    f"❌ Failed to insert acronym {acronym_data['acronym']}: {e}")

        conn.commit()
        print("✅ Acronyms seeded")


def seed_terms(db_path: Path, terms: List[Dict[str, Any]]) -> None:
    """Seed the database with translation term data."""
    print(f"Seeding {len(terms)} terms...")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for term_data in terms:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO terms 
                    (term_en, term_fr, definition_en, definition_fr, category, official)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    term_data["term_en"],
                    term_data["term_fr"],
                    term_data["definition_en"],
                    term_data["definition_fr"],
                    term_data["category"],
                    term_data["official"]
                ))
            except sqlite3.Error as e:
                print(f"❌ Failed to insert term {term_data['term_en']}: {e}")

        conn.commit()
        print("✅ Terms seeded")


def load_custom_data(file_path: Path) -> List[Dict[str, Any]]:
    """Load custom acronym/term data from JSON file."""
    if not file_path.exists():
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"📄 Loaded {len(data)} items from {file_path}")
            return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Failed to load {file_path}: {e}")
        return []


def print_stats(db_path: Path) -> None:
    """Print database statistics."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM acronyms")
        acronym_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM terms")
        term_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM acronyms WHERE language = 'en'")
        en_acronym_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM acronyms WHERE language = 'fr'")
        fr_acronym_count = cursor.fetchone()[0]

        print("\n📊 Database Statistics:")
        print(f"   Total acronyms: {acronym_count}")
        print(f"   English acronyms: {en_acronym_count}")
        print(f"   French acronyms: {fr_acronym_count}")
        print(f"   Translation terms: {term_count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed MapleClear terminology database")
    parser.add_argument(
        "--out",
        type=Path,
        default="data/terms.sqlite",
        help="Output database path (default: data/terms.sqlite)"
    )
    parser.add_argument(
        "--custom-acronyms",
        type=Path,
        help="Path to custom acronyms JSON file"
    )
    parser.add_argument(
        "--custom-terms",
        type=Path,
        help="Path to custom terms JSON file"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only print database statistics"
    )

    args = parser.parse_args()

    if args.stats_only:
        if args.out.exists():
            print_stats(args.out)
        else:
            print(f"❌ Database not found: {args.out}")
        return

    print("🍁 MapleClear Terminology Database Seeder")
    print("=" * 50)

    # Create database
    create_database(args.out)

    # Load default data
    all_acronyms = GOVERNMENT_ACRONYMS.copy()
    all_terms = GOVERNMENT_TERMS.copy()

    # Load custom data if provided
    if args.custom_acronyms:
        custom_acronyms = load_custom_data(args.custom_acronyms)
        all_acronyms.extend(custom_acronyms)

    if args.custom_terms:
        custom_terms = load_custom_data(args.custom_terms)
        all_terms.extend(custom_terms)

    # Seed database
    seed_acronyms(args.out, all_acronyms)
    seed_terms(args.out, all_terms)

    # Print final statistics
    print_stats(args.out)

    print(f"\n✅ Database seeded successfully: {args.out}")
    print("💡 Use --stats-only to view statistics anytime")


if __name__ == "__main__":
    main()
