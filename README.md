# LLM Debate Project

This project facilitates structured debates between two Language Model (LLM) instances on a given topic. It organises the debate into distinct phases: opening arguments, multiple rounds of rebuttals, and concluding statements. Each LLM takes turns presenting arguments for and against the proposition, creating a comprehensive exploration of the topic. The project supports OpenAI and Anthropic models and generates both JSON and HTML outputs of the debate.

## Debate Structure

1. **Opening Arguments**: Both LLMs present their initial stance on the topic.
2. **Rebuttal Rounds**: A series of back-and-forth exchanges (default is 3 rounds, but customisable).
3. **Concluding Statements**: Both LLMs summarise their positions and key points.

This structure ensures a balanced and thorough examination of the debate topic, with each LLM having equal opportunity to present and defend their viewpoints.

## Prerequisites

- Python 3.11
- Poetry (for dependency management)
- OpenAI API key and/or Anthropic API key

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/llm-debate.git
   cd llm-debate
   ```

2. Ensure you have Python 3.11 installed. You can check your Python version with:
   ```
   python --version
   ```
   If you don't have Python 3.11, you can download it from [python.org](https://www.python.org/downloads/) or use your preferred method of Python version management.

3. Install Poetry if you haven't already:
   ```
   curl -sSL https://install.python-poetry.org | python3 -
   ```

4. (Optional) Configure Poetry to create the virtual environment in the project directory:
   ```
   poetry config virtualenvs.in-project true
   ```
   This step is optional but recommended for better visibility of the virtual environment.

5. Install project dependencies:
   ```
   poetry install
   ```
   By default, Poetry will create a virtual environment in a centralized location (usually ~/.cache/pypoetry/virtualenvs/ on Unix systems). If you configured Poetry in step 4, it will create a .venv directory in your project folder instead.

6. Create a `.env` file in the project root and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

7. Activate the virtual environment:
   ```
   poetry shell
   ```
   This command will spawn a new shell with the virtual environment activated. You can also use `poetry run python your_script.py` to run commands in the virtual environment without activating it.

## Usage

Ensure you're in the project directory and the virtual environment is activated (you should see `(.venv)` in your terminal prompt if you configured Poetry to create the virtual environment in the project directory).

Run a debate using the following command structure:
```
python llm-debate/main.py <llm_type> <model> "<topic>" [--rounds <number_of_rounds>] [--output <custom_filename>] [--log-level <log_level>]
```

### Parameters:

- `<llm_type>`: Either "openai" or "anthropic"
- `<model>`: The specific model to use (e.g., "gpt-3.5-turbo" for OpenAI or "claude-2" for Anthropic)
- `"<topic>"`: The debate topic (enclose in quotes if it contains spaces)
- `--rounds`: (Optional) Number of rebuttal rounds (default is 3)
- `--output`: (Optional) Custom output filename (without extension)
- `--log-level`: (Optional) Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Examples:

1. Basic debate using OpenAI:
   ```
   python llm-debate/main.py openai gpt-3.5-turbo "Is artificial intelligence beneficial for society?"
   ```

2. Debate using Anthropic with 5 rebuttal rounds:
   ```
   python llm-debate/main.py anthropic claude-2 "Should space exploration be a priority?" --rounds 5
   ```

3. Debate with custom output filename and DEBUG log level:
   ```
   python llm-debate/main.py openai gpt-4 "The future of renewable energy" --output energy_debate --log-level DEBUG
   ```

## Output

The script generates two files for each debate:
1. A JSON file containing the full debate data, including metadata and all arguments.
2. An HTML file for a formatted, human-readable version of the debate, displaying the structured flow of arguments.

Both files will be saved in the project directory with names based on the debate topic and timestamp, unless a custom filename is specified.

## Troubleshooting

- If you encounter any "API key not found" errors, ensure that your `.env` file is properly set up with the correct API keys.
- For any "template not found" errors, verify that `template.html` and `error_template.html` are present in the `llm-debate` directory.
- If you have issues with Python versions, make sure you have Python 3.11 installed and selected in your environment.
- If you're using a different Python version manager or virtual environment tool, ensure it's correctly set to use Python 3.11 for this project.

## Contributing

Contributions to this project are welcome. Please ensure you follow the existing code style and add unit tests for any new features.

## Licence

This project is licensed under the MIT Licence - see the [LICENCE](LICENCE) file for details.