import logging

from islam_debate.prompts import (
    build_conclusion_prompt,
    build_opening_prompt,
    build_response_prompt,
    opening_history_entry,
    opponent_history_entry,
    response_history_entry,
)

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
        self.responses: list[str] = []
        self.debate_history: list[str] = []
        logger.info(f"{position} debater initialized")

    def start(self) -> str:
        logger.info(f"Starting debate as {self.position} position")
        initial_prompt = build_opening_prompt(self.topic, self.position)
        response: str = self.llm_client.get_response(initial_prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(opening_history_entry(self.position, response))
        logger.info(f"Opening argument generated for {self.position} position")
        return response

    def respond_to(self, opponent_argument: str) -> str:
        logger.info(f"Generating response for {self.position} position")
        self.debate_history.append(opponent_history_entry(opponent_argument))

        prompt = build_response_prompt(self.topic, self.position, self.debate_history)

        response: str = self.llm_client.get_response(prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(response_history_entry(self.position, response))
        logger.info(f"Response generated for {self.position} position")

        return response

    def conclude(self) -> str:
        logger.info(f"Generating conclusion for {self.position} position")
        prompt = build_conclusion_prompt(self.topic, self.position, self.debate_history)
        response: str = self.llm_client.get_response(prompt, self.model)
        self.responses.append(response)
        self.debate_history.append(
            f"{self.position.capitalize()} conclusion: {response}"
        )
        logger.info(f"Conclusion generated for {self.position} position")

        return response
