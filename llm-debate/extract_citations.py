import argparse
import json
import logging
import os
import re
from collections import defaultdict

import spacy
from openai import OpenAI

logger = logging.getLogger(__name__)
LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

nlp = spacy.load("en_core_web_sm")
logger.info("Loaded spaCy English language model")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_entities(text: str) -> dict[str, list[str]]:
    """Extract people, organizations, and works of art from the text."""
    doc = nlp(text)
    entities = defaultdict(set)

    for ent in doc.ents:
        category = ent.label_.lower()
        if category in ["person", "org", "norp", "work_of_art"]:
            category = "organizations" if category in ["org", "norp"] else category
            entities[category].add(ent.text)

    logger.debug(f"Extracted {sum(len(v) for v in entities.values())} entities")
    return {k: list(v) for k, v in entities.items()}


def extract_citations(text: str) -> list[str]:
    """Extract citations using regex patterns and clean them."""
    patterns = [
        r"\([\w\s]+,\s*\d{4}\)",  # (Author, YYYY)
        r"[\w\s]+\s*\(\d{4}\)",  # Author (YYYY)
        r"[\w\s]+\s*et\s*al\.",  # Author et al.
        r"\"[^\"]+\"",  # "Title of Work"
        r"Quran \d+:\d+",  # Quran X:Y
        r"Surah [A-Z][a-z-]+ \(\d+:\d+\)",  # Surah Name (X:Y)
        r"Hadith - [^,]+",  # Hadith - Source
    ]

    citations = []
    for pattern in patterns:
        found_citations = re.findall(pattern, text)
        cleaned_citations = [
            citation.strip().strip("'\"") for citation in found_citations
        ]
        citations.extend(cleaned_citations)

    logger.debug(f"Extracted {len(citations)} citations using regex patterns")
    return citations


def extract_citations_gpt4(
    text: str,
) -> list[dict]:
    """Extract citations using GPT-4"""
    standard_no_citations_reply = "No citations or quotations found."
    response_text = ""

    try:
        logger.info("Attempting GPT-4 citation extraction")

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that identifies citations "
                        "and quotations in text, including indirect references."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Please identify all citations and quotations in the "
                        "following text, including indirect references. For each, "
                        "provide the source and the quote or paraphrased content. "
                        "Quran citations should follow the format: "
                        "Quran Chapter:Verse."
                        "Return the result as a list of JSON objects, each with "
                        "'source' and 'quote' keys. If there are no citations or "
                        "quotations, please reply with the phrase: "
                        f"'{standard_no_citations_reply}'.\n\nText: {text}"
                    ),
                },
            ],
        )

        response_text = response.choices[0].message.content.strip()
        logger.debug("Raw GPT-4 response: %s", response_text)

        if standard_no_citations_reply in response_text:
            logger.info("No citations or quotations found in the text.")
            return []

        result = json.loads(response_text)

        assert isinstance(
            result, list
        ), f"GPT-4 response is not a list. Actual type: {type(result)}"
        for item in result:
            assert isinstance(item, dict), (
                f"GPT-4 response item is not a dictionary. "
                f"Actual type: {type(item)}"
            )
            assert "source" in item, (
                f"GPT-4 response item missing 'source' key. "
                f"Keys present: {item.keys()}"
            )
            assert "quote" in item, (
                f"GPT-4 response item missing 'quote' key. "
                f"Keys present: {item.keys()}"
            )

        logger.info("Successfully extracted %d citations using GPT-4", len(result))
        return result

    except json.JSONDecodeError:
        logger.exception(
            "JSON Decode Error on attempt %d. Problematic content: %s",
            response_text,
        )
    except AssertionError:
        logger.exception(
            "Assertion Error on attempt %d. Parsed result: %s",
            response_text,
        )
    except Exception:
        logger.exception(
            "Unexpected error in GPT-4 citation extraction on attempt %d",
        )

    logger.error("All attempts failed for GPT-4 citation extraction")
    return [response_text]


def analyze_debate_section(section: dict[str, str]) -> dict:
    """Analyze a debate section and extract entities, citations, and GPT-4 citations."""
    result = {}
    for key, text in section.items():
        logger.info(f"Analyzing debate section: {key}")
        result[key] = {
            "entities": extract_entities(text),
            "citations": extract_citations(text),
            "citations_llm": extract_citations_gpt4(text),
        }
    return result


def combine_for_against(debate_data: dict) -> dict:
    """Combine all 'for' and 'against' entities, citations, and GPT-4 citations."""
    logger.info("Combining 'for' and 'against' data")
    combined = {
        "for": {"entities": defaultdict(set), "citations": set(), "citations_llm": []},
        "against": {
            "entities": defaultdict(set),
            "citations": set(),
            "citations_llm": [],
        },
    }

    for section in debate_data.values():
        for side in ["for", "against"]:
            if side in section:
                for entity_type, entities in section[side]["entities"].items():
                    combined[side]["entities"][entity_type].update(entities)
                combined[side]["citations"].update(section[side]["citations"])
                combined[side]["citations_llm"].extend(section[side]["citations_llm"])

    # Convert sets back to lists for JSON serialization
    for side in ["for", "against"]:
        combined[side]["entities"] = {
            k: list(v) for k, v in combined[side]["entities"].items()
        }
        combined[side]["citations"] = list(combined[side]["citations"])

    logger.info("Finished combining 'for' and 'against' data")
    return combined


def analyze_file(file_path: str) -> dict:
    """Analyze a single JSON file and return the extracted information."""
    logger.info("Analyzing file: %s", file_path)
    try:
        with open(file_path) as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        debate = data.get("debate", {})

        debate_analysis = {
            "opening_arguments": analyze_debate_section(
                debate.get("opening_arguments", {})
            ),
            "round_1": analyze_debate_section(debate.get("round_1", {})),
            "conclusions": analyze_debate_section(debate.get("conclusions", {})),
        }

        combined_analysis = combine_for_against(debate_analysis)

        result = {
            "filename": os.path.basename(file_path),
            "model": metadata.get("model", ""),
            "topic": metadata.get("topic", ""),
            "debate_analysis": debate_analysis,
            "combined_for": combined_analysis["for"],
            "combined_against": combined_analysis["against"],
        }
        logger.info("Successfully analyzed file: %s", file_path)
        return result
    except Exception:
        logger.exception("Error analyzing file %s", file_path)
        return {}


def analyze_files(directory: str) -> list[dict]:
    """Analyze all JSON files in the given directory."""
    logger.info(f"Analyzing files in directory: {directory}")
    results = []
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            file_path = os.path.join(directory, filename)
            result = analyze_file(file_path)
            if result:
                results.append(result)
    len_results = len(results)
    logger.info("Finished analyzing %d files in directory: %s", len_results, directory)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Analyze debate JSON files for citations and entities."
    )
    parser.add_argument(
        "directory", help="Directory containing the JSON files to analyze"
    )
    parser.add_argument(
        "--output",
        default="citation_analysis_results.json",
        help="Output file name (default: citation_analysis_results.json)",
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

    logger.info(f"Starting analysis with input directory: {args.directory}")

    if not os.path.isdir(args.directory):
        logger.error(f"Error: The directory '{args.directory}' does not exist.")
        return

    results = analyze_files(args.directory)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("Analysis complete. Results saved to %s", args.output)


if __name__ == "__main__":
    main()
