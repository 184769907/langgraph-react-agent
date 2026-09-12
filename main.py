from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool

load_dotenv()
#初始化LLM
llm = ChatOpenAI(
    base_url = os.getenv("BASE_URL"),
    api_key = os.getenv("API_KEY"),
    model = os.getenv("MODEL_NAME")
)

#创建计算工具
@tool
def calculator(a:float, b:float, op:str) -> str:
    """
    计算器工具，支持 + - * /
    Args:
        a: 数字1
        b: 数字2
        op: 运算符，可选 add sub mul div
    """
    if op == "add":
        res = a + b
    elif op == "sub":
        res = a - b
    elif op == "mul":
        res = a * b
    elif op == "div":
        res = a / b
    else:
        return "运算符错误"
    return f"计算结果：{a} {op} {b} = {res}"

#初始化工具
tools = [calculator]
llm_with_tool = llm.bind_tools(tools)

#定义节点
def agent_node(state: MessagesState):
    return {'messages':[llm_with_tool.invoke(state["messages"])]}

tool_node = ToolNode(tools=tools)
#构建图
graph_builder = StateGraph(MessagesState)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", tool_node)

#条件边：是否调用工具
graph_builder.add_conditional_edges(
    'agent',
    tools_condition,
    {
        'tools': 'tools',
        END: END
    }
)
graph_builder.add_edge("tools", "agent")
graph_builder.set_entry_point("agent")
graph = graph_builder.compile()

#测试运行
if __name__ == "__main__":
    user_query = "介绍一下你自己"
    for event in graph.stream({'messages': [('user', user_query)]}):
        print(event)