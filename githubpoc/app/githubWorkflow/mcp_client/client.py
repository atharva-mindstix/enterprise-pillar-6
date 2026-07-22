"""AgentCore Gateway MCP client (IAM / SigV4) for LangChain.

Bootcamp gateway is AWS_IAM inbound — use mcp-proxy-for-aws, not Bearer JWT.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_GATEWAY_MCP_URL = (
    "https://bootcamp-gateway-jwodqi3x4j.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
)
BOOTCAMP_GATEWAY_CONNECTION_TOKEN = "BOOTCAMP_GATEWAY"


def resolve_gateway_mcp_url() -> str | None:
    for env_name in (
        f"GATEWAY_{BOOTCAMP_GATEWAY_CONNECTION_TOKEN}_URL",
        f"GATEWAY_{BOOTCAMP_GATEWAY_CONNECTION_TOKEN}_MCP_URL",
        "AGENTCORE_GATEWAY_MCP_URL",
        "GATEWAY_BOOTCAMP_GATEWAY_URL",
    ):
        url = os.getenv(env_name, "").strip()
        if url:
            logger.info("Resolved gateway MCP URL from %s", env_name)
            return url.rstrip("/")
    return DEFAULT_GATEWAY_MCP_URL


def aws_region() -> str:
    return os.getenv("AWS_REGION", "us-west-2")


async def load_gateway_mcp_tools() -> tuple[list[Any], Any]:
    """
    Open IAM MCP session and load LangChain tools.

    Returns (tools, session_cm) where session_cm is an async context manager
    that must stay entered for the duration of tool use. Caller should use:

        tools, stack = await load_gateway_mcp_tools()
        # ... invoke agent with tools while gateway session is held by caller
    """
    from contextlib import AsyncExitStack

    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp import ClientSession

    endpoint = resolve_gateway_mcp_url()
    if not endpoint:
        logger.warning("Gateway MCP URL not configured; gateway tools disabled")
        return [], None

    try:
        from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
    except ImportError:
        logger.warning("mcp-proxy-for-aws not installed; gateway MCP tools disabled")
        return [], None

    stack = AsyncExitStack()
    try:
        read, write, _get_sid = await stack.enter_async_context(
            aws_iam_streamablehttp_client(
                endpoint=endpoint,
                aws_region=aws_region(),
                aws_service="bedrock-agentcore",
            )
        )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools = await load_mcp_tools(session)
        logger.info(
            "Loaded %d gateway MCP tools from %s",
            len(tools),
            endpoint,
        )
        return tools, stack
    except Exception as exc:
        await stack.aclose()
        logger.warning("Failed to load gateway MCP tools: %s", exc)
        return [], None
