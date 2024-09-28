import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_filename(topic: str) -> str:
    """Generate a filename based on the debate topic and current datetime."""
    snake_case_topic = topic.lower().replace(" ", "_")
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{snake_case_topic}_{current_time}"


def save_json(data: Dict[str, Any], filename: str) -> str:
    """Save the debate results as a JSON file."""
    file_path = f"{filename}.json"
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    return file_path


def save_html(data: Dict[str, Any], filename: str) -> str:
    """Save the debate results as an HTML file."""
    html_content = generate_html(data)
    file_path = f"{filename}.html"
    with open(file_path, "w") as f:
        f.write(html_content)
    return file_path


def generate_html(data: Dict[str, Any]) -> str:
    """Generate HTML content for the debate results."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, "template.html")

    try:
        with open(template_path) as file:
            html_template = file.read()
    except FileNotFoundError:
        logger.exception("HTML template file not found")
        return "HTML template file not found"

    debate_content = ""
    for round_name, round_data in data["debate"].items():
        round_title = round_name.replace("_", " ").title()
        debate_content += f'<div class="round"><h2>{round_title}</h2>'
        for side, argument in round_data.items():
            debate_content += f"""
    <div class="argument {side}">
        <h3>{side.capitalize()}</h3>
        <p>{argument}</p>
    </div>"""
        debate_content += "</div>"

    html_content = html_template.replace("{topic}", data["metadata"]["topic"])
    html_content = html_content.replace("{llm_type}", data["metadata"]["llm_type"])
    html_content = html_content.replace("{model}", data["metadata"]["model"])
    html_content = html_content.replace("{date}", data["metadata"]["date"])
    html_content = html_content.replace(
        "{time_taken}", f"{data['metadata']['time_taken']:.2f}"
    )
    html_content = html_content.replace("{debate_content}", debate_content)

    return html_content
