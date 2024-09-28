import argparse
import csv
import json
import logging
import re
import unicodedata
from collections import defaultdict

import requests

logger = logging.getLogger(__name__)
LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# This full list of translations on quran.com
translations_available = [
    {
        "id": 19,
        "name": "M. Pickthall",
        "author_name": "Mohammed Marmaduke William Pickthall",
        "slug": "quran.en.pickthall",
        "language_name": "english",
        "translated_name": {"name": "M. Pickthall", "language_name": "english"},
    },
    {
        "id": 20,
        "name": "Saheeh International",
        "author_name": "Saheeh International",
        "slug": "en-sahih-international",
        "language_name": "english",
        "translated_name": {"name": "Saheeh International", "language_name": "english"},
    },
    {
        "id": 22,
        "name": "A. Yusuf Ali",
        "author_name": "Abdullah Yusuf Ali",
        "slug": "quran.en.yusufali",
        "language_name": "english",
        "translated_name": {"name": "A. Yusuf Ali", "language_name": "english"},
    },
    {
        "id": 57,
        "name": "Transliteration",
        "author_name": "Transliteration",
        "slug": "transliteration",
        "language_name": "english",
        "translated_name": {"name": "Transliteration", "language_name": "english"},
    },
    {
        "id": 84,
        "name": "T. Usmani",
        "author_name": "Mufti Taqi Usmani",
        "slug": "en-taqi-usmani",
        "language_name": "english",
        "translated_name": {"name": "T. Usmani", "language_name": "english"},
    },
    {
        "id": 85,
        "name": "M.A.S. Abdel Haleem",
        "author_name": "Abdul Haleem",
        "slug": "en-haleem",
        "language_name": "english",
        "translated_name": {"name": "M.A.S. Abdel Haleem", "language_name": "english"},
    },
    {
        "id": 95,
        "name": "A. Maududi (Tafhim commentary)",
        "author_name": "Sayyid Abul Ala Maududi",
        "slug": "en-al-maududi",
        "language_name": "english",
        "translated_name": {
            "name": "A. Maududi (Tafhim commentary)",
            "language_name": "english",
        },
    },
    {
        "id": 131,
        "name": "Dr. Mustafa Khattab, The Clear Quran",
        "author_name": "Dr. Mustafa Khattab",
        "slug": "clearquran-with-tafsir",
        "language_name": "english",
        "translated_name": {"name": "Dr. Mustafa Khattab", "language_name": "english"},
    },
    {
        "id": 203,
        "name": "Al-Hilali & Khan",
        "author_name": "Muhammad Taqi-ud-Din al-Hilali & Muhammad Muhsin Khan",
        "slug": "",
        "language_name": "english",
        "translated_name": {"name": "Al-Hilali & Khan", "language_name": "english"},
    },
]
translation_code_map = {
    19: "M. Pickthall",
    20: "Saheeh International",
    22: "A. Yusuf Ali",
    57: "Transliteration",
    84: "T. Usmani",
    85: "M.A.S. Abdel Haleem",
    95: "A. Maududi (Tafhim commentary)",
    131: "Dr. Mustafa Khattab, The Clear Quran",
    203: "Al-Hilali & Khan",
}


class AyahTranslation:
    """How Quran.com returns a translated ayah or verse"""

    id: int
    resource_id: int
    text: str


def clean_text(text):
    """Removes symbols and numbers from translation to make comparison easier"""
    # Remove text inside angle brackets
    text = re.sub("<[^>]+>", "", text)
    # Remove standalone numbers (assumes numbers are not part of words)
    text = re.sub(r"\d+", "", text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # remove any square brackets that start with i.e.
    text = re.sub(r"\[i\.e\..*?\]", "", text)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ASCII", "ignore").decode("ASCII")
    replacements = {"ā": "a", "ī": "i", "ū": "u", "Ā": "A", "Ī": "I", "Ū": "U"}
    for original, replacement in replacements.items():
        ascii_text = ascii_text.replace(original, replacement)
    return ascii_text


def get_translations(surah: int, ayah: int) -> list[dict]:
    url = f"https://api.quran.com/api/v4/verses/by_key/{surah}:{ayah}"
    translation_codes = ",".join(
        [str(translation["id"]) for translation in translations_available]
    )
    params = {"language": "en", "translations": translation_codes}
    headers = {"Accept": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()["verse"]["translations"]


def cleaned_translations(translations: list[dict]) -> list[dict]:
    return [
        {**translation, "text": clean_text(translation["text"])}
        for translation in translations
    ]


def merge_translations(translations: list[dict]) -> dict:
    merged_translations = defaultdict(str)
    for translation in translations:
        merged_translations[translation["resource_id"]] += " " + translation["text"]
    return dict(merged_translations)


def verify_citation(citation: dict) -> tuple[bool, str]:
    match = re.search(r"Quran (\d+):(\d+)(?:-(\d+))?", citation["source"])
    if not match:
        return None, None  # Not a Quranic citation or invalid format

    citation_text = clean_text(citation["quote"])

    surah = int(match.group(1))
    start_ayah = int(match.group(2))
    end_ayah = int(match.group(3)) if match.group(3) else start_ayah

    all_translations = []
    for ayah in range(start_ayah, end_ayah + 1):
        translations = get_translations(surah, ayah)
        clean_translations = cleaned_translations(translations)
        all_translations.extend(clean_translations)

    merged_translations = merge_translations(all_translations)

    for translation_code, cleaned_text in merged_translations.items():
        if citation_text in cleaned_text:
            return True, translation_code_map[translation_code]

    return False, merged_translations[20]  # use Sahih International as default


def is_direct_citation(text: str) -> bool:
    if any(
        phrase in text.lower()
        for phrase in [
            "analysis",
            "emphasi",
            "interpret",
            "quran",
            "reference",
            "verse",
        ]
    ):
        return False
    return True


def is_quranic_citation(source: str) -> bool:
    return bool(re.search(r"Quran (\d+):(\d+)(?:-(\d+))?", source))


def validate_citation(citation: dict):
    if type(citation) is not dict:
        raise TypeError
    elif "source" not in citation or "quote" not in citation:
        raise KeyError


def process_combined_section(section: dict, model: str, topic: str) -> list[dict]:
    results = []
    for citation in section["citations_llm"]:
        try:
            validate_citation(citation)
        except Exception:
            logger.exception(
                "model %s, topic %s, contains invalid citation", model, topic
            )
            continue

        is_quran = is_quranic_citation(citation["source"])
        is_direct = is_direct_citation(citation["quote"])
        if is_quran and is_direct:
            is_valid, translation = verify_citation(citation)
        else:
            is_direct = False
            is_valid, translation = None, None

        results.append(
            {
                "model": model,
                "topic": topic,
                "source": citation["source"],
                "is_quran": is_quran,
                "direct_quranic_citation": is_direct,
                "quote": citation["quote"],
                "is_valid": is_valid,
                "translation": translation,
            }
        )
    return results


def main():
    with open(
        "/home/marekzp/llm-debate/llm-debate/data/citation_analysis_results.json"
    ) as f:
        data = json.load(f)

    csv_filename = "combined_results.csv"
    csv_headers = [
        "model",
        "topic",
        "source",
        "is_quran",
        "direct_quranic_citation",
        "quote",
        "is_valid",
        "translation",
        "argument_type",
    ]

    with open(csv_filename, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()

        for item in data:
            topic = item["topic"]
            model = item["model"]
            for_results = process_combined_section(item["combined_for"], model, topic)
            against_results = process_combined_section(
                item["combined_against"], model, topic
            )

            for result in for_results:
                result["argument_type"] = "For"
                writer.writerow(result)

            for result in against_results:
                result["argument_type"] = "Against"
                writer.writerow(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check whether Quranic citations are correctly translated."
    )

    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS.keys(),
        default="INFO",
        help="Set the logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=LOG_LEVELS[args.log_level],
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    main()
