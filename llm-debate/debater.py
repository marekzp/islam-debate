from typing import List


class Debater:
    def __init__(
        self,
        llm_client,
        model: str,
        topic: str,
        position: str,
    ) -> None:
        self.llm_client = llm_client
        self.model: str = model
        self.topic: str = topic
        self.position: str = position
        self.responses: List[str] = []
        self.debate_history: List[str] = []

    def start(self) -> str:
        initial_prompt: str = (
            f"You are participating in a debate on the topic: '{self.topic}'. "
            f"You are {self.position} the proposition. Make a convincing opening "
            "argument for your position."
        )
        response: str = self.llm_client.get_response(initial_prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(
            f"{self.position.capitalize()} opening argument: {response}"
        )
        return response

    def respond_to(self, opponent_argument: str) -> str:
        self.debate_history.append(f"Opponent's argument: {opponent_argument}")

        prompt: str = (
            f"You are participating in a debate on the topic: '{self.topic}'. "
            f"You are {self.position} the proposition. Here's the debate history "
            "so far:\n\n"
        )
        prompt += "\n\n".join(self.debate_history)
        prompt += (
            f"\n\nNow, respond to the opponent's latest argument, maintaining your "
            f"position {self.position} the proposition."
        )

        response: str = self.llm_client.get_response(prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(
            f"{self.position.capitalize()} response: {response}"
        )
        return response

    def conclude(self) -> str:
        prompt: str = (
            f"You have been participating in a debate on the topic: '{self.topic}'. "
            f"You are {self.position} the proposition. Here's the entire debate "
            "history:\n\n"
        )
        prompt += "\n\n".join(self.debate_history)
        prompt += (
            "\n\nNow, provide a concluding statement for the debate, summarizing your "
            "position and the key points you've made."
        )
        response: str = self.llm_client.get_response(prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(
            f"{self.position.capitalize()} conclusion: {response}"
        )
        return response