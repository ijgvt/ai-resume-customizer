"""调用 DeepSeek LLM 从简历文本中结构化提取个人信息字段。"""
import json
from config import get_deepseek_client, DEEPSEEK_BASE_URL
from tools.profile_manager import merge_extracted_fields

EXTRACTION_PROMPT = """你是一位简历分析专家。请从以下简历文本中提取信息，输出 JSON。

## 提取规则

### 固定字段（必须提取，找不到填 null）
1. name: 姓名
2. expected_salary: 期望薪资（如 "15K-20K"、"面议"），简历未写明填 null
3. location: 所在城市（如 "深圳"）
4. phone: 手机号码
5. email: 邮箱地址
6. education: 教育背景列表 [{school, major, degree, graduation_year}]
7. skills: 技能列表 [{name, level}] level 可选：精通/熟练/了解
8. projects: 项目经历列表 [{name, role, start_date, end_date, description}]

### LLM 生成字段（你必须基于全部分析结果来填写）
9. career_objective: 一句话求职意向，概括目标岗位和方向
10. personal_strengths: 个人优势，3-5 点，用换行分隔

### 可选字段（有则提取，无则填 null 或空数组）
11. internships: 实习经历列表 [{company, position, start_date, end_date, description}]
12. certificates: 技能证书与获奖荣誉列表 [{name, issuer, year}]

## 重要规则
- 除 career_objective 和 personal_strengths 外，其他字段提取不到必须填 null（字符串）或 []（数组），禁止编造
- career_objective 和 personal_strengths 由你根据全部分析来合理生成，不要留空
- skills 的 level 从文本中推断，没有明确说明则填 "熟练"

## 简历文本

{texts}

## 输出格式
只输出一个 JSON 对象，不要有任何其他文字。"""


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
            {"role": "user", "content": EXTRACTION_PROMPT.format(texts=combined)},
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
