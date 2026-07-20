"""MCP Server SSE 入口：注册所有工具，通过 SSE 暴露。"""
import asyncio
import json
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from tools.profile_manager import load_profile, save_profile, check_completeness, update_field
from tools.resume_parser import parse_file, parse_files, parse_directory
from tools.resume_store import init_chroma, store_chunks
from tools.profile_extractor import extract_profile
from tools.resume_search import search as resume_search_fn
from tools.boss_search import search_boss
from tools.boss_detail import get_job_detail
from tools.pdf_generator import generate_pdf
from tools.greeting import generate_greeting
from config import RESUME_FILES_DIR


app = Server("resume-agent")


# === 个人信息管理 ===

@app.tool()
async def profile_get() -> list[TextContent]:
    """获取用户完整个人信息档案，包括每个字段的值和状态。"""
    profile = load_profile()
    return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]


@app.tool()
async def profile_update(field_name: str, value: str) -> list[TextContent]:
    """手动更新个人信息中的指定字段。

    Args:
        field_name: 字段名（name/phone/email/location/expected_salary 等）
        value: 新值（JSON 字符串，复杂类型用 JSON 格式传入）
    """
    try:
        # 尝试解析 JSON
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value
    update_field(field_name, parsed)
    return [TextContent(type="text", text=f"已更新 {field_name}")]


@app.tool()
async def profile_check() -> list[TextContent]:
    """检查个人信息是否完整，返回缺失的固定模块字段列表。"""
    missing = check_completeness()
    if missing:
        return [TextContent(
            type="text",
            text=f"个人信息不完整，以下字段缺失：{', '.join(missing)}。请提醒用户补充这些信息。"
        )]
    return [TextContent(type="text", text="个人信息完整，可以使用。")]


# === 简历文件解析 ===

@app.tool()
async def resume_parse(file_path: str) -> list[TextContent]:
    """解析单个简历文件，返回提取的纯文本。

    支持 .txt / .docx / .pdf（PDF 统一走智谱 OCR）。
    """
    text = parse_file(file_path)
    return [TextContent(type="text", text=text)]


@app.tool()
async def resume_parse_directory(dir_path: str | None = None) -> list[TextContent]:
    """解析目录下所有简历文件，返回文本集合。

    Args:
        dir_path: 目录路径，默认使用 data/resume_files/
    """
    path = dir_path or str(RESUME_FILES_DIR)
    results = parse_directory(path)
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


@app.tool()
async def resume_store(text: str, source_file: str = "") -> list[TextContent]:
    """将简历文本分块后向量化存入 ChromaDB。

    Args:
        text: 简历完整文本
        source_file: 来源文件名（可选）
    """
    init_chroma()
    n = store_chunks(text, {"source": source_file} if source_file else None)
    return [TextContent(type="text", text=f"已存储 {n} 个文本块到向量数据库")]


@app.tool()
async def resume_extract(texts_json: str) -> list[TextContent]:
    """调用 LLM 从简历文本中提取结构化个人信息，写入 profile.json。

    Args:
        texts_json: JSON 字符串，格式 {"file_path": "文本内容", ...}
    """
    texts = json.loads(texts_json)
    profile = extract_profile(texts)
    return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]


@app.tool()
async def resume_search(query: str, top_k: int = 5) -> list[TextContent]:
    """基于 JD 描述或关键词，在 ChromaDB 中检索最相关的简历片段。

    Args:
        query: JD 描述或搜索关键词
        top_k: 返回 top-k 个最相似片段（默认 5）
    """
    results = resume_search_fn(query, top_k)
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


# === Boss 直聘 ===

@app.tool()
async def boss_search_list(keyword: str, city: str, max_pages: int = 3) -> list[TextContent]:
    """在 Boss 直聘搜索岗位列表。

    Args:
        keyword: 搜索关键词，如 "Python开发"
        city: 城市名（中文），如 "深圳"、"北京"
        max_pages: 最大翻页数（默认 3）
    """
    # 城市名 → Boss 直聘城市编码（部分映射）
    city_map = {
        "深圳": "101280600", "广州": "101280100", "东莞": "101281600",
        "珠海": "101280700", "惠州": "101280300", "佛山": "101280800",
        "北京": "100010000", "天津": "100030000", "石家庄": "100450000",
        "上海": "100020000", "杭州": "101210100", "苏州": "101190400",
        "南京": "101190100", "宁波": "101210400",
        "成都": "101270100", "重庆": "100060000", "绵阳": "101270500",
        "武汉": "101200100", "长沙": "101250100", "郑州": "101180100",
        "西安": "101110100", "咸阳": "101110200", "宝鸡": "101110900",
    }
    city_code = city_map.get(city, "100010000")
    jobs = search_boss(keyword, city_code, max_pages)
    return [TextContent(type="text", text=json.dumps(jobs, ensure_ascii=False, indent=2))]


@app.tool()
async def boss_job_detail(url: str) -> list[TextContent]:
    """爬取单个 Boss 直聘岗位的详细 JD。

    Args:
        url: 岗位详情页完整 URL
    """
    detail = get_job_detail(url)
    return [TextContent(type="text", text=json.dumps(detail, ensure_ascii=False, indent=2))]


# === 生成 ===

@app.tool()
async def pdf_generate(jd_json: str) -> list[TextContent]:
    """根据当前个人信息和指定 JD，生成定制化 PDF 简历。

    Args:
        jd_json: 岗位 JD 的 JSON 字符串
    """
    profile = load_profile()
    jd = json.loads(jd_json)

    # 先检索相关片段来确定哪些技能/项目应加重
    jd_text = jd.get("jd_text", "") + " " + jd.get("title", "")
    relevant = resume_search_fn(jd_text, top_k=5)

    relevant_skills = []
    relevant_projects = []
    for item in relevant:
        text = item.get("text", "")
        # 从 chunk 中提取项目名和技能名（简单匹配）
        skills = _v(profile["fields"], "skills") or []
        if isinstance(skills, list):
            for s in skills:
                name = s.get("name", "") if isinstance(s, dict) else s
                if name and name in text:
                    relevant_skills.append(name)

        projects = _v(profile["fields"], "projects") or []
        if isinstance(projects, list):
            for p in projects:
                name = p.get("name", "") if isinstance(p, dict) else p
                if name and name in text:
                    relevant_projects.append(name)

    output_path = generate_pdf(
        profile=profile,
        jd=jd,
        relevant_skills=list(set(relevant_skills)),
        relevant_projects=list(set(relevant_projects)),
    )
    return [TextContent(type="text", text=f"PDF 已生成：{output_path}")]


@app.tool()
async def greeting_generate(jd_json: str) -> list[TextContent]:
    """生成一段 Boss 直聘风格的打招呼语。

    Args:
        jd_json: 岗位 JD 的 JSON 字符串
    """
    profile = load_profile()
    jd = json.loads(jd_json)
    greeting_text = generate_greeting(profile, jd)
    return [TextContent(type="text", text=greeting_text)]


def _v(value, field_name: str):
    """安全获取字段值。"""
    if not isinstance(value, dict):
        return None
    f = value.get(field_name, {})
    return f.get("value") if isinstance(f, dict) else None


async def main():
    """启动 MCP SSE Server。"""
    init_chroma()
    async with SseServerTransport("/messages") as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
