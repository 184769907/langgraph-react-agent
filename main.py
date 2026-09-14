from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError

load_dotenv()
#初始化LLM
llm = ChatOpenAI(
    base_url = os.getenv("BASE_URL"),
    api_key = os.getenv("API_KEY"),
    model = os.getenv("MODEL_NAME")
)

#Pydantic参数校验
class ReadFileArags(BaseModel):
    file_path: str = Field(description="../test.txt")

#安全过滤：禁止敏感路径
BLOCK_PATHS_KEYWORDS = ["/etc", "C:/windows", "/root","C:/Users/Administrator"]
#创建读取文件工具
@tool
def read_file(file_path:str) -> str:
    """
    读取本地txt、md文本文件内容。
    当用户要求读取某个文件内容时，**必须调用这个工具**，不要直接回答无法读取。
    Args:
        file_path: 本地文件路径，例如 test.txt
    """
    #Pydantic参数校验
    try:
        args = ReadFileArags(file_path=file_path)
    except ValidationError as e:
        return f"参数校验失败: {str(e)}"

    #安全拦截
    for keyword in BLOCK_PATHS_KEYWORDS:
        if keyword in args.file_path:
            return f"禁止访问敏感路径"

    try:
        with open(args.file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"文件内容:\n{content[:2000]}"
    except FileNotFoundError:
        return f"错误：文本不存在！"
    except Exception as e:
        return f"读取文件失败: {str(e)}"
    
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
tools = [calculator, read_file]
llm_with_tool = llm.bind_tools(tools)

#自定义state：增加调用计数器
from typing_extensions import Annotated, TypedDict
class State(TypedDict):
    messages: Annotated[list, add_messages]
    call_count: int #记录工具调用次数


#定义节点
def agent_node(state: State):
    resp = llm_with_tool.invoke(state['messages'])
    return {
        "messages":[resp],
        "call_count": state["call_count"] + 1
    }

tool_node = ToolNode(tools=tools)

#自定义条件边：判断是否终止（达到最大调用次数）
def custom_cond(state: State):
    max_call = 5
    if state["call_count"] >= max_call:
        return END
    return tools_condition(state)

#构建图
graph_builder = StateGraph(State)
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", tool_node)

#条件边：是否调用工具
graph_builder.add_conditional_edges(
    'agent',
    custom_cond,
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
    #循环测试
    while True:
        user_query = input("请输入问题：")
        for event in graph.stream({"messages": [("user", user_query)], "call_count":0}):
            print(event)