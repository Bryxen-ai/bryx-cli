import os

from anthropic import Anthropic
from anthropic import AsyncAnthropic
from anthropic.types import RawContentBlockDeltaEvent, RawMessageDeltaEvent,ThinkingDelta, TextDelta
from anthropic.types.raw_message_delta_event import Delta
from dataclasses import dataclass, field
from typing import Optional, Union, Callable

"""
claude-opus 开头的模型，会映射到 deepseek-v4-pro
claude-haiku、claude-sonnet 开头的模型，会映射到 deepseek-v4-flash

tools:
name	Fully Supported
input_schema	Fully Supported
description	Fully Supported
cache_control	Ignored



"""


@dataclass
class ClientConfig:
    model: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8"))
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", None))
    base_url: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_BASE_URL", None))
    system_prompt:str = "You are a helpful assistant"
    max_token: int = 16384
    max_retrise: int = 3
    timeout: float = 120.00
    stream: bool = True
    """anthropic: thinking={"type": "enabled", "budget_tokens": 10000},"""
    thinking: dict = field(default_factory=lambda: {"type": "adaptive"})
    # """openai: reasoning_effort="high",  extra_body={"thinking": {"type": "enabled"}}"""
    # extra_body: dict = {"thinking": {"type": "enabled"}}
    """{"type": "any"}	强制至少一个; {"type": "none"} 禁用工具;{"type": "tool", "name": "get_weather"} 强制指定工具"""
    tool_choice: dict = field(default_factory=lambda: {"type": "auto"})
    default_headers: dict = field(default_factory=dict)
    
    # """anthropic: Enable strict mode;limit:20;Optional parameters < 24"""
    # strict:bool = True 
    """
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "plan_interest": {"type": "string"},
                    "demo_requested": {"type": "boolean"},
                },
                "required": ["name", "email", "plan_interest", "demo_requested"],
                "additionalProperties": False,
            },
        }
    },
    """
    # output_config: dict = {"type": "json_schema"}
    """
    cited_text: not counted towards output tokens
    {
        "type": "char_location",
        "cited_text": "The exact text being cited",  # not counted towards output tokens
        "document_index": 0,
        "document_title": "Document Title",
        "start_char_index": 0,  # 0-indexed
        "end_char_index": 50,  # exclusive
    }
    """
    """
    Text:
        {
        "type": "document",
        "source": {
            "type": "text",
            "media_type": "text/plain",
            "data": "Plain text content...",
        },
        "title": "Document Title",  # optional
        "context": "Context about the document that will not be cited from",  # optional
        "citations": {"enabled": True},
    }
    
    PDF:
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64_encoded_pdf_data,
            },
            "title": "Document Title",  # optional
            "context": "Context about the document that will not be cited from",  # optional
            "citations": {"enabled": True},
        }
    or
        {
            "type": "document",
            "source": {"type": "url", "url": "https://example.com/document.pdf"},
            "title": "Document Title",  # optional
            "context": "Context about the document that will not be cited from",  # optional
            "citations": {"enabled": True},
        }
    """
    
    """
    Custom content documents:
        ...
        {
            "type": "document",
            "source": {
                "type": "content",
                "content": [
                    {"type": "text", "text": "First chunk"},
                    {"type": "text", "text": "Second chunk"},
                ],
            },
            "title": "Document Title",
            "context": "Context about the document that will not be cited from",
            "citations": {"enabled": True},
            },
        ...
    """
    
    
    
    citations: dict = field(default_factory=lambda: {"enabled": True})
    """ Cache the document content """
    cache_control: dict = field(default_factory=lambda: {"type": "ephemeral"})
    
    
    # def __post_init__(self):
        # extra_headers: dict = field(default=dict)
        #     pass

@dataclass
class Usage:
    """
    deepseek缓存命中规则:
    1. 用户第一轮请求内容为 A + B,第二轮请求内容为 A + B + C,则第二轮请求能完整匹配 A + B 这个缓存前缀单元，可以命中 A + B 的缓存。
    2. 用户第一轮请求的内容为 A + B,第二轮请求的内容为 A + C,则第二轮请求无法命中缓存，因为 A + C 不能完整匹配第一轮的缓存前缀单元（A + B）。但此时系统会识别到两轮请求存在公共前缀 A，并将 A 作为缓存前缀单元落盘。当第三轮请求 A + D 到来时，能完整匹配 A 这个缓存前缀单元，可以命中 A 的缓存
    deepseek usage 中:
        - prompt_cache_hit_tokens:本次请求的输入中，缓存命中的 tokens 数
        - prompt_cache_miss_tokens:本次请求的输入中，缓存未命中的 tokens 数

    """
    
    input_tokens:int = 0
    output_tokens: int = 0
    "deepseek usage: "
    prompt_cache_hit_tokens = 0
    prompt_cache_miss_tokens = 0
    ""
    "anthropic usage"
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0
    
    
    def update(self, usage_obj):
        if usage_obj is None:
            return
        self.input_tokens += getattr(usage_obj, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage_obj, "output_tokens", 0) or 0
    
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
"""
stream和非stream模式 使用同样的client.messages.stream
 if not stream: message = stream.get_final_message()
 else: for text in stream.text_stream:print(text, end="", flush=True)
"""


class LLMClient:
    def __init__(self, config: ClientConfig):
        self.cfg = config
        self.usage = Usage()
        kwargs: dict = {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "max_retries": config.max_retrise,
            "timeout": config.timeout,
            "default_headers": config.default_headers,
        }
        
        self._client = AsyncAnthropic(**kwargs)
        
    def _extra_params(self) -> dict:
        params: dict = {}
        if self.cfg.thinking:
            params["thinking"] = {"type": "adaptive"}
        return params
    
    async def _stream(
        self,
        kwargs,
        on_text:Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ):
        on_text = on_text or (lambda t: print(t, end=""))
        on_thinking = on_thinking or (lambda t: print(t, end=""))
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    current_block_type = event.content_block.type
                    if current_block_type == "thinking" and on_thinking:
                        on_thinking("<think>\n")
                elif etype == "content_block_delta":
                    delta = event.delta
                    if isinstance(delta, TextDelta):
                        on_text(delta.text)
                    elif isinstance(delta, ThinkingDelta):
                        on_thinking(delta.thinking)
                elif etype == "content_block_stop":
                    if current_block_type == "thinking" and on_thinking:
                        on_thinking("</think>\n")
                    current_block_type = None
                
            msg = await stream.get_final_message()
        
        self.usage.update(msg.usage)
        return msg
    
    def _build_tools_param(self, tools: list[dict]) -> list[dict] | None:
        return tools if tools else None

    async def create(
        self, 
        messages: list[dict],
        tools: list[dict] | None = None,
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None
    ):
        tools_param = self._build_tools_param(tools or [])
        # extra = self._extra_params()
        
        kwargs = {
            "model": self.cfg.model,
            "messages": messages,
            "max_tokens": self.cfg.max_token,
            "system": self.cfg.system_prompt,
            **self._extra_params()
        }
        if tools_param:
            kwargs["tools"] = tools_param
        
        if self.cfg.stream:
            return await self._stream(kwargs, on_text=on_text, on_thinking=on_thinking)
        else:
            async with self._client.messages.stream(**kwargs) as stream:
                msg = await stream.get_final_message()
            self.usage.update(msg.usage)
            return msg
        
    


# "养成在响应处理逻辑中检查 stop_reason 的习惯："
# def handle_response(response):
#     if response.stop_reason == "tool_use":
#         return handle_tool_use(response)
#     elif response.stop_reason == "max_tokens":
#         return handle_truncation(response)
#     elif response.stop_reason == "model_context_window_exceeded":
#         return handle_context_limit(response)
#     elif response.stop_reason == "pause_turn":
#         return handle_pause(response)
#     elif response.stop_reason == "refusal":
#         return handle_refusal(response)
#     else:
#         # 处理 end_turn 及其他情况
#         return response.content[0].text

# "优雅地处理被截断的响应"
# def handle_truncated_response(response):
#     if response.stop_reason in ["max_tokens", "model_context_window_exceeded"]:
#         if response.stop_reason == "max_tokens":
#             note = "[Response truncated due to max_tokens limit]"
#         else:
#             note = "[Response truncated due to context window limit]"
#         return f"{response.content[0].text}\n\n{note}"
#     return response.content[0].text

    
if __name__ == "__main__":
    import argparse
    import asyncio
    parser = argparse.ArgumentParser()
    
    config = ClientConfig(
        model="deepseek-v4-pro",
        api_key="sgw_hpwo4w5f6fyxmj25u5kqxq8i",
        base_url="http://127.0.0.1:3000/anthropic"
    )
    
    client = LLMClient(config)
    kwargs = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": "hello"}
        ],
        "max_tokens": config.max_token,
        **client._extra_params()
    }
    
    # response = asyncio.run(client._stream(kwargs))
    response = asyncio.run(client.create(messages=kwargs["messages"]))
    breakpoint()
    