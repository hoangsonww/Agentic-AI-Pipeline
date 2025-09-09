"""Deterministic LLM that replays recorded outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Iterator, Callable
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.outputs import LLMResult, Generation
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from pydantic import Field, PrivateAttr
from ..memory.trace_store import get_trace_store
from ..infra.logging import logger


class ReplayLLM(BaseLanguageModel):
    """LLM that returns recorded outputs for deterministic replay."""
    
    chat_id: str
    fallback_llm: Optional[BaseLanguageModel] = None
    strict_mode: bool = False
    
    # Private attributes
    _trace_store: Any = PrivateAttr()
    _recorded_outputs: List = PrivateAttr()
    _output_index: int = PrivateAttr(default=0)
    
    def __init__(
        self,
        chat_id: str,
        fallback_llm: Optional[BaseLanguageModel] = None,
        strict_mode: bool = False,
        **kwargs
    ):
        """Initialize replay LLM.
        
        Args:
            chat_id: Chat ID to replay from
            fallback_llm: LLM to use when no recorded output is found
            strict_mode: If True, raise error when no recorded output found
        """
        super().__init__(
            chat_id=chat_id,
            fallback_llm=fallback_llm,
            strict_mode=strict_mode,
            **kwargs
        )
    def model_post_init(self, __context) -> None:
        """Initialize after Pydantic model construction."""
        super().model_post_init(__context) if hasattr(super(), 'model_post_init') else None
        self._trace_store = get_trace_store()
        
        # Load recorded outputs
        self._recorded_outputs = list(self._trace_store.get_llm_outputs(self.chat_id))
        self._output_index = 0
        
        logger.info(f"ReplayLLM initialized with {len(self._recorded_outputs)} recorded outputs")
    
    @property
    def _llm_type(self) -> str:
        return "replay"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate response by replaying recorded output."""
        prompt_text = self._messages_to_prompt(messages)
        
        # Try to find matching recorded output
        recorded_output = self._find_matching_output(prompt_text)
        
        if recorded_output is not None:
            logger.info(f"ReplayLLM: Using recorded output (index {self._output_index - 1})")
            generation = Generation(text=recorded_output)
            return LLMResult(generations=[[generation]])
        
        # No recorded output found
        if self.strict_mode:
            raise ValueError(f"No recorded output found for prompt in chat {self.chat_id}")
        
        if self.fallback_llm:
            logger.warning(f"ReplayLLM: No recorded output found, using fallback LLM")
            return self.fallback_llm._generate(messages, stop, run_manager, **kwargs)
        
        # Return a generic fallback message
        logger.warning(f"ReplayLLM: No recorded output found, returning generic response")
        generation = Generation(text="[REPLAY ERROR: No recorded output available]")
        return LLMResult(generations=[[generation]])
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Async version of _generate."""
        return self._generate(messages, stop, run_manager, **kwargs)
    
    def generate_prompt(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs) -> LLMResult:
        """Generate responses for list of prompt strings."""
        messages_list = [[HumanMessage(content=prompt)] for prompt in prompts]
        results = []
        for messages in messages_list:
            result = self._generate(messages, stop, **kwargs)
            results.extend(result.generations)
        return LLMResult(generations=results)
    
    def predict(self, text: str, *, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Predict response for a text input."""
        messages = [HumanMessage(content=text)]
        result = self._generate(messages, stop, **kwargs)
        return result.generations[0][0].text
    
    def predict_messages(self, messages: List[BaseMessage], *, stop: Optional[List[str]] = None, **kwargs) -> BaseMessage:
        """Predict response for message inputs."""
        result = self._generate(messages, stop, **kwargs)
        return AIMessage(content=result.generations[0][0].text)
    
    async def agenerate_prompt(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs) -> LLMResult:
        """Async version of generate_prompt."""
        return self.generate_prompt(prompts, stop, **kwargs)
    
    async def apredict(self, text: str, *, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Async version of predict."""
        return self.predict(text, stop=stop, **kwargs)
    
    async def apredict_messages(self, messages: List[BaseMessage], *, stop: Optional[List[str]] = None, **kwargs) -> BaseMessage:
        """Async version of predict_messages."""
        return self.predict_messages(messages, stop=stop, **kwargs)
    
    def _messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        # Simple conversion - could be made more sophisticated
        parts = []
        for msg in messages:
            role = msg.__class__.__name__.replace('Message', '').lower()
            parts.append(f"{role}: {msg.content}")
        return "\n".join(parts)
    
    def _find_matching_output(self, prompt_text: str) -> Optional[str]:
        """Find recorded output that matches the prompt.
        
        For now, uses sequential ordering. Could be enhanced with 
        fuzzy matching or prompt similarity.
        """
        if self._output_index >= len(self._recorded_outputs):
            return None
        
        # Simple sequential matching
        recorded_prompt, recorded_output = self._recorded_outputs[self._output_index]
        self._output_index += 1
        
        # Log the match attempt for debugging
        logger.debug(f"ReplayLLM matching:\nPrompt: {prompt_text[:100]}...\nRecorded: {recorded_prompt[:100]}...")
        
        return recorded_output
    
    def invoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> AIMessage:
        """Invoke the LLM with input."""
        if isinstance(input, list):
            messages = input
        elif isinstance(input, str):
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=input)]
        else:
            messages = [input]
        
        result = self._generate(messages, **kwargs)
        content = result.generations[0][0].text
        return AIMessage(content=content)
    
    async def ainvoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> AIMessage:
        """Async invoke the LLM with input."""
        if isinstance(input, list):
            messages = input
        elif isinstance(input, str):
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=input)]
        else:
            messages = [input]
        
        result = await self._agenerate(messages, **kwargs)
        content = result.generations[0][0].text
        return AIMessage(content=content)
    
    def stream(self, input: Any, config: Optional[Dict] = None, **kwargs) -> Iterator[str]:
        """Stream response (just return the full response at once)."""
        result = self.invoke(input, config, **kwargs)
        yield result.content
    
    def reset(self):
        """Reset the replay index to start from beginning."""
        self._output_index = 0
        logger.info("ReplayLLM: Reset to beginning")
    
    def get_remaining_outputs(self) -> int:
        """Get number of remaining recorded outputs."""
        return len(self._recorded_outputs) - self._output_index