import logging
from typing import List

logger = logging.getLogger(__name__)


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
        logger.info(f"{position} debater initialized")

    def start(self) -> str:
        logger.info(f"Starting debate as {self.position} position")
        initial_prompt: str = (
            f"You are participating in a debate on the topic: '{self.topic}'. "
            f"You are {self.position} the proposition. Make a convincing opening "
            "argument for your position. Please also provide relevant citations "
            "supporting your position."
        )
        response: str = self.llm_client.get_response(initial_prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(
            f"{self.position.capitalize()} opening argument: {response}"
        )
        logger.info(f"Opening argument generated for {self.position} position")
        return response

    def respond_to(self, opponent_argument: str) -> str:
        logger.info(f"Generating response for {self.position} position")
        self.debate_history.append(f"Opponent's argument: {opponent_argument}")

        prompt: str = (
            f"You are participating in a debate on the topic: '{self.topic}'. "
            f"You are {self.position} the proposition. Here's the debate history "
            "so far:\n\n"
        )
        prompt += "\n\n".join(self.debate_history)
        prompt += (
            f"\n\nNow, carefully consider the opponent's latest arguments and, "
            f"maintaining your position {self.position} the proposition, respond to "
            "those arguments. Please provide relevant citations supporting your "
            "argument."
        )

        response: str = self.llm_client.get_response(prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(f"{self.position.capitalize()} response: {response}")
        logger.info(f"Response generated for {self.position} position")

        return response

    def conclude(self) -> str:
        logger.info(f"Generating conclusion for {self.position} position")
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
        logger.info(f"Conclusion generated for {self.position} position")

        return response
