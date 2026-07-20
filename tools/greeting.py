"""生成 Boss 直聘风格招呼语，100-200 字，突出匹配点。"""
from config import get_deepseek_client

GREETING_PROMPT = """你是一位求职顾问，需要为以下候选人写一段 Boss 直聘风格的打招呼语。

## 候选人背景
{profile_summary}

## 目标岗位
{jd_summary}

## 要求
- 风格：简洁干练，突出亮点，有针对性
- 字数：100-200 字
- 结构：称呼（"您好"）+ 核心匹配点（"我有X年XX经验，做过XX项目"）+ 表达兴趣 + 期待回复
- 包含至少一个与 JD 直接相关的技能或项目亮点
- 不要过度推销，语气真诚
- 直接输出招呼语文本，不要加任何说明或前缀"""


def generate_greeting(profile: dict, jd: dict) -> str:
    """生成 Boss 直聘风格招呼语。

    Args:
        profile: 用户个人信息
        jd: 岗位 JD 信息

    Returns:
        招呼语文案（纯文本）
    """
    client = get_deepseek_client()

    # 构建候选人摘要
    fields = profile.get("fields", {})
    name = _f(fields, "name")
    skills = _v(fields, "skills")
    projects = _v(fields, "projects")
    strengths = _f(fields, "personal_strengths")
    objective = _f(fields, "career_objective")

    profile_summary = f"""姓名：{name}
求职意向：{objective}
技能：{_fmt_list(skills, "name")}
项目经历：{_fmt_list(projects, "name")}
个人优势：{strengths}"""

    jd_summary = f"""岗位：{jd.get("title", "")}
公司：{jd.get("company", "")}
薪资：{jd.get("salary", "")}
JD：{jd.get("jd_text", "")}"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": GREETING_PROMPT.format(
                profile_summary=profile_summary,
                jd_summary=jd_summary,
            )},
        ],
        temperature=0.7,
        max_tokens=500,
    )

    return response.choices[0].message.content.strip()


def _f(fields: dict, name: str) -> str:
    val = fields.get(name, {}).get("value", "") if isinstance(fields.get(name), dict) else ""
    return str(val) if val else ""


def _v(fields: dict, name: str):
    return fields.get(name, {}).get("value") if isinstance(fields.get(name), dict) else None


def _fmt_list(items, key) -> str:
    """格式化列表为逗号分隔字符串。"""
    if not isinstance(items, list):
        return ""
    names = []
    for item in items:
        if isinstance(item, dict):
            names.append(item.get(key, ""))
        elif isinstance(item, str):
            names.append(item)
    return "、".join(names[:10])
