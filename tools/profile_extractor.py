"""调用 DeepSeek LLM 从简历文本中结构化提取个人信息字段。"""
import json
from config import get_deepseek_client, DEEPSEEK_BASE_URL
from tools.profile_manager import merge_extracted_fields

EXTRACTION_PROMPT = """你是一位简历分析专家。从以下简历文本中提取所有信息，输出 JSON。找不到的信息填 null 或空数组。

## 字段说明

### 基本
- name: 姓名 (字符串)
- phone: 手机号 (字符串)
- email: 邮箱 (字符串)
- location: 城市 (字符串)
- expected_salary: 期望薪资 (字符串，如简历没有则 null)
- photo: 证件照路径，不提取填 ""

### 教育背景 education
数组，每个元素:
- school: 学校，没有就 ""
- school_tag: 标签 211/985/双一流，没有就 ""
- major: 专业，没有就 ""
- degree: 学历，没有就 ""
- period: 时间段 "2020.09 ~ 2024.06"，没有就 ""
- graduation_year: 毕业年份，没有就 null
- gpa: 绩点，简历没写就填 ""（空字符串），不要填"无"

### 主修课程 courses
数组，如 ["数据结构", "操作系统", "计算机网络", "数据库原理"]。
优先从简历中提取。如果简历原文没列出课程，则根据专业(major)合理推断 4-6 门核心课程。
如果连专业都没有，填空数组 []。

### 技能 skills
数组，每个元素: name(技能名), level(精通/熟练/了解)

### 技能标签 skill_tags
数组，每个元素: label(能力类别如"编程语言""框架工具""数据库"), text(具体技能名如"Python、Java")
从 skills 按类别分组生成。如果简历没有明显类别则填空数组。

### 项目经历 projects
数组，每个元素: name, role, start_date, end_date, description, section(固定填"项目经历")

### 实习经历 internships
数组，每个元素: company, position, start_date, end_date, description, section(固定填"实习经历")

### LLM 生成的字段
- career_objective: 岗位列表 ["Python开发", "数据分析师"]，根据技能+项目推导，3-6个
- personal_strengths: 个人优势文本，3-5点，换行分隔
- self_evaluation: 自我评价文本（60-100字），三维度: 我有什么/我擅长什么/为什么适合

### 可选
- certificates: 证书 [{name, issuer, year}]

## 输出 JSON 必须包含的字段
name, phone, email, location, expected_salary, photo,
education, skills, skill_tags, projects, internships,
career_objective, personal_strengths, self_evaluation,
courses, certificates

## 铁律
- career_objective, personal_strengths, self_evaluation 必须生成，不要留空
- skill_tags 从 skills 分组生成，skills 为空则 skill_tags 也空
- courses 根据简历和专业合理推导，实在没有就空数组
- 其余字段找不到就 null 或 []，坚决不编造

## 简历文本
__TEXTS_PLACEHOLDER__

只输出 JSON 对象。"""


def _parse_llm_response(content: str) -> dict:
    """解析 LLM 返回的 JSON 字符串，处理 markdown 代码块包裹。

    Args:
        content: LLM 返回的原始文本

    Returns:
        解析后的 dict
    """
    content = content.strip()
    # 提取 JSON（处理可能的 markdown 代码块包裹）
    if content.startswith("```"):
        lines = content.split("\n")
        # 去掉第一行 ```json 和最后一行 ```
        content = "\n".join(lines[1:-1])

    return json.loads(content)


def extract_profile(texts: dict[str, str]) -> dict:
    """从多份简历文本中提取结构化个人信息。

    Args:
        texts: {"file_path": "text content", ...}

    Returns:
        合并后的完整 profile dict（已写入 profile.json）
    """
    # 整理文本
    combined = ""
    for fp, text in texts.items():
        if text.startswith("[PARSE_ERROR]") or text.startswith("[OCR_"):
            continue
        combined += f"\n=== 文件: {fp} ===\n{text}\n"

    if not combined.strip():
        raise ValueError("No valid text extracted from files")

    client = get_deepseek_client()

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.replace("__TEXTS_PLACEHOLDER__", combined)},
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    content = response.choices[0].message.content.strip()
    extracted = _parse_llm_response(content)

    # 合并到 profile.json
    source_files = list(texts.keys())
    profile = merge_extracted_fields(extracted, source_files)
    return profile
