from ai.providers.llm import ChatMessage, ChatProvider, ProviderError, get_provider


class OtaAgent:
    """
    Base Observe -> Think -> Act agent.

    Subclasses can customize the role prompts and add domain-specific
    tools or behavior without changing the OTA interface.
    """

    _BASE_PROMPT = """
        You are part of an Observe-Think-Act system.
        Follow your assigned role, use only the provided information, and do not invent facts.
    """.strip()

    _OBSERVER_PROMPT = """
        Observe the current input or state.
        Extract relevant facts, changes, constraints, and uncertainties.
        Do not make decisions or take actions.
    """.strip()

    _THINKER_PROMPT = """
        Analyze the observation and determine the next best action.
        Use the available context and tools.
        Return a concise decision and the information needed to act.
    """.strip()

    _ACTOR_PROMPT = """
        Execute the selected action using the available tools or capabilities.
        Do not claim an action succeeded unless it actually did.
        Return the result or clearly report why the action could not be completed.
    """.strip()

    def __init__(self, provider: str):
        self.llm = get_provider(provider)

    def _build_prompt(
        self,
        role_prompt: str,
        system_prompt: str = "",
    ) -> str:
        parts = [
            self._BASE_PROMPT,
            role_prompt,
            system_prompt.strip(),
        ]

        return "\n\n".join(
            part for part in parts if part
        )

    async def _chat(
        self,
        message: str,
        system_prompt: str,
    ) -> str:
        try:
            response = await self.llm.chat(
                messages=[ChatMessage("user", message)],
                system=system_prompt,
            )
            return response.content

        except ProviderError:
            raise

    async def observe(
        self,
        message: str,
        system_prompt: str = "",
    ) -> str:
        return await self._chat(
            message,
            self._build_prompt(
                self._OBSERVER_PROMPT,
                system_prompt,
            ),
        )

    async def think(
        self,
        observation: str,
        system_prompt: str = "",
    ) -> str:
        return await self._chat(
            observation,
            self._build_prompt(
                self._THINKER_PROMPT,
                system_prompt,
            ),
        )

    async def act(
        self,
        action: str,
        system_prompt: str = "",
    ) -> str:
        return await self._chat(
            action,
            self._build_prompt(
                self._ACTOR_PROMPT,
                system_prompt,
            ),
        )