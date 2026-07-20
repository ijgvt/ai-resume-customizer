"""Agent ReAct 循环：接收用户消息，调用 DeepSeek + MCP 工具，流式返回结果。"""
import json
from typing import Generator
from openai import OpenAI

from config import get_deepseek_client, PROFILE_PATH

# 加载系统提示词
SYSTEM_PROMPT_PATH = PROFILE_PATH.parent.parent / "prompts" / "system.md"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

MAX_LOOP = 15  # 最大 tool-calling 循环次数

# MCP 工具定义（与 mcp_server/server.py 中注册的工具一致）
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "profile_get",
            "description": "获取用户完整个人信息档案",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_check",
            "description": "检查个人信息是否完整",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_update",
            "description": "手动更新个人信息中的指定字段",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string", "description": "字段名"},
                    "value": {"type": "string", "description": "新值（JSON字符串）"},
                },
                "required": ["field_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_search",
            "description": "在向量数据库中检索最相关的简历片段",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "JD描述或关键词"},
                    "top_k": {"type": "integer", "description": "返回数量，默认5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "boss_search_list",
            "description": "在Boss直聘搜索岗位列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "city": {"type": "string", "description": "城市中文名"},
                    "max_pages": {"type": "integer", "description": "最大翻页数，默认3"},
                },
                "required": ["keyword", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "boss_job_detail",
            "description": "爬取Boss直聘岗位详情JD",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "岗位详情页URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_generate",
            "description": "生成定制化PDF简历",
            "parameters": {
                "type": "object",
                "properties": {
                    "jd_json": {"type": "string", "description": "岗位JD的JSON字符串"},
                },
                "required": ["jd_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "greeting_generate",
            "description": "生成Boss直聘风格打招呼语",
            "parameters": {
                "type": "object",
                "properties": {
                    "jd_json": {"type": "string", "description": "岗位JD的JSON字符串"},
                },
                "required": ["jd_json"],
            },
        },
    },
]


class AgentLoop:
    """管理单次对话的 Agent ReAct 循环。"""

    def __init__(self, mcp_invoke_fn):
        """
        Args:
            mcp_invoke_fn: async function(tool_name: str, args: dict) -> str
                           负责将工具调用转发到 MCP Server
        """
        self.client = get_deepseek_client()
        self.mcp_invoke = mcp_invoke_fn
        self.messages: list[dict] = []

    def run(self, user_message: str, profile: dict) -> Generator[dict, None, None]:
        """执行一次 Agent 循环。

        Args:
            user_message: 用户输入的消息
            profile: 当前用户个人信息

        Yields:
            事件 dict：
            - {"type": "status", "text": "正在..."}  状态提示
            - {"type": "tool_call", "name": "xxx", "args": {...}} 工具调用
            - {"type": "tool_result", "name": "xxx", "result": "..."} 工具结果
            - {"type": "text", "text": "..."} 最终回复文本
        """
        # 构建系统消息
        profile_summary = self._build_profile_summary(profile)
        system_content = SYSTEM_PROMPT + f"\n\n## 当前用户信息\n{profile_summary}"

        self.messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        for _ in range(MAX_LOOP):
            yield {"type": "status", "text": "思考中..."}

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                tools=MCP_TOOLS,
                tool_choice="auto",
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                # 处理工具调用
                self.messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                    try:
                        result = self.mcp_invoke(tool_name, tool_args)
                    except Exception as e:
                        result = json.dumps({"error": str(e)}, ensure_ascii=False)

                    yield {"type": "tool_result", "name": tool_name, "result": result}

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # 无工具调用，最终回复
                final_text = msg.content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                yield {"type": "text", "text": final_text}
                return

        # 超限
        yield {"type": "text", "text": "（操作步骤过多，请简化需求后重试）"}

    def _build_profile_summary(self, profile: dict) -> str:
        """构建个人信息摘要，注入系统提示词。"""
        fields = profile.get("fields", {})
        lines = []
        for name, f in fields.items():
            status = f.get("status", "missing")
            value = f.get("value")
            if status == "missing":
                lines.append(f"- {name}: [缺失]")
            else:
                if isinstance(value, list):
                    summary = "、".join([
                        v.get("name", str(v)) if isinstance(v, dict) else str(v)
                        for v in value[:5]
                    ])
                    lines.append(f"- {name}: {summary}")
                else:
                    lines.append(f"- {name}: {value}")
        return "\n".join(lines)
