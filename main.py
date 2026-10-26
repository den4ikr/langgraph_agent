from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools import WikipediaQueryRun
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain.tools import tool

from typing import Annotated
from typing_extensions import TypedDict

import wikipedia

wikipedia.set_user_agent(
    "SearchAgent/1.0 (personal learning project)"
)

load_dotenv()

# memory saver
memory = MemorySaver()

# init wikipedia tool
wikipedia_api_wrapper = WikipediaAPIWrapper(top_k_results=1)
wikipedia_tool = WikipediaQueryRun(api_wrapper=wikipedia_api_wrapper)

llm = ChatOpenAI(model='gpt-4o-mini')

@tool
def historical_events(date: str) -> str:
    """Provide a list of historical event for given date in any format"""
    try:
        answer = llm.invoke(f"List of important historical event that happened on {date}")

        return answer
    except Exception as e:
        return f"Something wen wrong: {str(e)}"

@tool
def palindrome_checker(text: str) -> str:
    """Check if the word or phrase is a palindrome"""
    cleaned = ''.join(char.lower() for char in text if char.isalnum())

    if cleaned == cleaned[::-1]:
        return f"The phrase or word {text} is a palindrome"
    else:
        return f"The phrase or word {text} is not a palindrome"

tools = [wikipedia_tool, historical_events, palindrome_checker]


llm_with_tools = llm.bind_tools(tools=tools)


class State(TypedDict):
    messages: Annotated[list, add_messages]

def chatbot(state: State):
    return {'messages': llm_with_tools.invoke(state['messages'])}

builder = StateGraph(State)
tool_node = ToolNode(tools=tools)

builder.add_node('chatbot', chatbot)
builder.add_node('tools', tool_node)
builder.add_conditional_edges('chatbot', tools_condition)

builder.add_edge('tools', 'chatbot')
builder.add_edge(START, 'chatbot')
builder.add_edge('chatbot', END)

gr = builder.compile(checkpointer=memory)

config = {'configurable': {'thread_id': 'single_session_memory'}}


def stream(user_input):
    for step in gr.stream(
        {'messages': [('user', user_input)]},
        stream_mode='updates',
        config=config
    ):
        for node, update in step.items():

            if node == 'chatbot':
                message = update['messages']

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        print(f"🔧 Using tool: {tool_call['name']}")
                        print(f"🔎 Query: {tool_call['args']}")
                else:
                    print(f"\n🤖 Assistant: {message.content}")

            elif node == 'tools':
                for message in update['messages']:
                    print(f"📄 Tool result: {message.content[:300]}...")



while True:
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    stream(user_input)