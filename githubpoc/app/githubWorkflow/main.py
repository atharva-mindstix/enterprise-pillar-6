from collections import OrderedDict

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import load_gateway_mcp_tools
from github_token import resolve_github_token_async
from prompt import build_system_prompt

LangchainInstrumentor().instrument()

app = BedrockAgentCoreApp()
log = app.logger

_llm = None


def get_or_create_model():
    global _llm
    if _llm is None:
        _llm = load_model()
    return _llm


@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a + b


tools = [add_numbers]

# Module-level checkpointer preserves conversation history across invocations.
# InMemorySaver keeps every thread_id (= session_id) checkpoint in memory
# forever, so we bound it to 128 active threads with LRU eviction (the
# least-recently-used thread is deleted and its history reset) to keep a
# long-running process from growing without limit. For durable history, swap in
# a persistent checkpointer (e.g. SqliteSaver/AsyncSqliteSaver with a file path).
_CHECKPOINT_LIMIT = 128
_checkpointer = InMemorySaver()
_thread_ids = OrderedDict()


def touch_thread(thread_id):
    if thread_id in _thread_ids:
        _thread_ids.move_to_end(thread_id)
        return
    while len(_thread_ids) >= _CHECKPOINT_LIMIT:
        evicted, _ = _thread_ids.popitem(last=False)
        _checkpointer.delete_thread(evicted)
    _thread_ids[thread_id] = True


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    # Prefer UI-forwarded GitHub OAuth (custom header); Identity fetch is fallback only
    github_token = await resolve_github_token_async(payload, context)

    # IAM MCP session; Option A interceptor injects Authorization for Lambda
    mcp_tools, gateway_stack = await load_gateway_mcp_tools(github_token)
    try:
        session_context = payload.get("session")
        system_prompt = build_system_prompt(session_context)

        graph = create_react_agent(
            get_or_create_model(),
            tools=mcp_tools + tools,
            prompt=system_prompt,
            checkpointer=_checkpointer,
        )

        prompt = payload.get("prompt", "What can you help me with?")
        session_id = getattr(context, "session_id", "default-session")
        touch_thread(session_id)
        log.info(f"Agent input: {prompt}")

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": session_id}},
        )

        output = result["messages"][-1].content
        log.info(f"Agent output: {output}")
        return {"result": output}
    finally:
        if gateway_stack is not None:
            await gateway_stack.aclose()


if __name__ == "__main__":
    app.run()
