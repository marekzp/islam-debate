from __future__ import annotations


def opening_history_entry(position: str, response: str) -> str:
    return f"{position.capitalize()} opening argument: {response}"


def response_history_entry(position: str, response: str) -> str:
    return f"{position.capitalize()} response: {response}"


def opponent_history_entry(argument: str) -> str:
    return f"Opponent's argument: {argument}"


def build_opening_prompt(topic: str, position: str) -> str:
    return (
        f"You are participating in a debate on the topic: '{topic}'. "
        f"You are {position} the proposition. Make a convincing opening "
        "argument for your position. Please also provide relevant citations "
        "supporting your position."
    )


def build_response_prompt(topic: str, position: str, history: list[str]) -> str:
    prompt = (
        f"You are participating in a debate on the topic: '{topic}'. "
        f"You are {position} the proposition. Here's the debate history "
        "so far:\n\n"
    )
    prompt += "\n\n".join(history)
    prompt += (
        f"\n\nNow, carefully consider the opponent's latest arguments and, "
        f"maintaining your position {position} the proposition, respond to "
        "those arguments. Please provide relevant citations supporting your "
        "argument."
    )
    return prompt


def build_conclusion_prompt(topic: str, position: str, history: list[str]) -> str:
    prompt = (
        f"You have been participating in a debate on the topic: '{topic}'. "
        f"You are {position} the proposition. Here's the entire debate "
        "history:\n\n"
    )
    prompt += "\n\n".join(history)
    prompt += (
        "\n\nNow, provide a concluding statement for the debate, summarizing your "
        "position and the key points you've made."
    )
    return prompt
