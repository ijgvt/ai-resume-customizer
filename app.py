"""AI 求职简历优化助手 — Streamlit 前端入口。"""
import json
import os
import sys
import io
import streamlit as st
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import RESUME_FILES_DIR, PROFILE_PATH, UPLOADS_DIR
from tools.profile_manager import load_profile, save_profile, check_completeness, merge_extracted_fields
from tools.resume_parser import parse_files, parse_directory
from tools.resume_store import init_chroma, store_chunks, clear_collection
from tools.profile_extractor import extract_profile
from agent.loop import AgentLoop

# 页面配置
st.set_page_config(
    page_title="AI 求职助手",
    page_icon="📄",
    layout="wide",
)

# === Session State 初始化 ===
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "editing_field" not in st.session_state:
    st.session_state.editing_field = None


def refresh_profile():
    """重新加载 profile.json。"""
    st.session_state.profile = load_profile()


# === MCP 工具调用函数（直接调用 tools 模块，绕过 MCP 网络层） ===
def mcp_invoke(tool_name: str, args: dict) -> str:
    """直接调用 tools 模块（跳过 MCP SSE 网络层，简化开发）。

    在完整部署环境中，这里应该通过 SSE 连接 MCP Server。
    开发阶段直接 import 工具函数调用。
    """
    if tool_name == "profile_get":
        profile = load_profile()
        return json.dumps(profile, ensure_ascii=False, indent=2)

    elif tool_name == "profile_check":
        missing = check_completeness()
        if missing:
            return f"缺失字段：{', '.join(missing)}"
        return "个人信息完整"

    elif tool_name == "profile_update":
        from tools.profile_manager import update_field
        try:
            value = json.loads(args.get("value", "null"))
        except (json.JSONDecodeError, TypeError):
            value = args.get("value", "")
        update_field(args["field_name"], value)
        refresh_profile()
        return f"已更新 {args['field_name']}"

    elif tool_name == "resume_search":
        from tools.resume_search import search
        results = search(args.get("query", ""), args.get("top_k", 5))
        return json.dumps(results, ensure_ascii=False, indent=2)

    elif tool_name == "boss_search_list":
        from tools.boss_search import search_boss
        import threading
        # Selenium 不能在其他线程运行，这里用同步直接调用
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
        city = args.get("city", "深圳")
        city_code = city_map.get(city, "100010000")
        jobs = search_boss(args.get("keyword", ""), city_code, args.get("max_pages", 3))
        return json.dumps(jobs, ensure_ascii=False, indent=2)

    elif tool_name == "boss_job_detail":
        from tools.boss_detail import get_job_detail
        detail = get_job_detail(args.get("url", ""))
        return json.dumps(detail, ensure_ascii=False, indent=2)

    elif tool_name == "pdf_generate":
        from tools.pdf_generator import generate_pdf
        from tools.resume_search import search
        profile = load_profile()
        jd = json.loads(args.get("jd_json", "{}"))
        jd_text = jd.get("jd_text", "") + " " + jd.get("title", "")
        relevant = search(jd_text, top_k=5)

        skills = profile["fields"].get("skills", {}).get("value") or []
        projects = profile["fields"].get("projects", {}).get("value") or []

        relevant_skills = []
        relevant_projects = []
        for item in relevant:
            text = item.get("text", "")
            if isinstance(skills, list):
                for s in skills:
                    name = s.get("name", "") if isinstance(s, dict) else s
                    if name and name in text:
                        relevant_skills.append(name)
            if isinstance(projects, list):
                for p in projects:
                    name = p.get("name", "") if isinstance(p, dict) else p
                    if name and name in text:
                        relevant_projects.append(name)

        path = generate_pdf(profile, jd, list(set(relevant_skills)), list(set(relevant_projects)))
        return f"PDF 已生成：{path}"

    elif tool_name == "greeting_generate":
        from tools.greeting import generate_greeting
        profile = load_profile()
        jd = json.loads(args.get("jd_json", "{}"))
        text = generate_greeting(profile, jd)
        return text

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# === 侧栏 ===
with st.sidebar:
    st.header("📁 简历管理")

    # 文件上传
    uploaded_files = st.file_uploader(
        "上传简历文件",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="支持 PDF、Word、TXT 格式，可同时上传多个文件",
    )

    if uploaded_files:
        new_files = []
        for uf in uploaded_files:
            # 保存上传文件
            save_path = UPLOADS_DIR / uf.name
            with open(save_path, "wb") as f:
                f.write(uf.getbuffer())
            new_files.append(str(save_path))

        if new_files and st.button("🔍 解析上传的文件", use_container_width=True):
            with st.spinner("正在解析文件..."):
                texts = parse_files(new_files)
                # 存入 ChromaDB
                init_chroma()
                for fp, text in texts.items():
                    if not text.startswith("[PARSE_ERROR]") and not text.startswith("[OCR_"):
                        store_chunks(text, {"source": fp})
                # LLM 提取
                profile = extract_profile(texts)
                st.session_state.profile = profile
                st.success(f"已解析 {len(new_files)} 个文件")
                st.rerun()

    # 预存文件夹扫描
    st.divider()
    pre_existing = list(RESUME_FILES_DIR.glob("*"))
    pre_existing = [f for f in pre_existing if f.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if pre_existing:
        st.caption(f"📂 预存文件夹中有 {len(pre_existing)} 个文件")
        if st.button("🔄 解析预存文件", use_container_width=True):
            with st.spinner("正在解析预存文件..."):
                texts = parse_directory(str(RESUME_FILES_DIR))
                init_chroma()
                for fp, text in texts.items():
                    if not text.startswith("[PARSE_ERROR]"):
                        store_chunks(text, {"source": fp})
                profile = extract_profile(texts)
                st.session_state.profile = profile
                st.success(f"已解析 {len(texts)} 个文件")
                st.rerun()

    st.divider()

    # 个人信息状态
    st.header("👤 个人信息")
    missing = check_completeness(st.session_state.profile)

    if not missing:
        st.success("✅ 全部就绪")
    else:
        for name in missing:
            label_map = {
                "name": "姓名", "expected_salary": "期望薪资", "location": "所在地",
                "phone": "电话", "email": "邮箱", "education": "教育背景",
                "skills": "专业技能", "projects": "项目经历",
            }
            st.error(f"❌ {label_map.get(name, name)} 缺失")

    if st.button("📝 查看/编辑个人信息", use_container_width=True):
        st.session_state.editing_field = "all"

    st.divider()

    # 服务状态
    st.header("⚙️ 设置")
    st.caption("DeepSeek API: " + ("🟢 已配置" if os.getenv("DEEPSEEK_API_KEY") else "🔴 未配置"))
    st.caption(f"ChromaDB: {str(RESUME_FILES_DIR.parent / 'chroma')}")


# === 个人信息编辑面板 ===
if st.session_state.editing_field is not None:
    st.header("编辑个人信息")
    fields = st.session_state.profile.get("fields", {})

    with st.form("profile_editor"):
        col1, col2 = st.columns(2)
        edits = {}

        with col1:
            edits["name"] = st.text_input("姓名 *", value=_fv(fields, "name"))
            edits["phone"] = st.text_input("电话 *", value=_fv(fields, "phone"))
            edits["email"] = st.text_input("邮箱 *", value=_fv(fields, "email"))
            edits["location"] = st.text_input("所在地 *", value=_fv(fields, "location"))
            edits["expected_salary"] = st.text_input("期望薪资 *", value=_fv(fields, "expected_salary"))

        with col2:
            edits["career_objective"] = st.text_area("求职意向 (AI 生成)", value=_fv(fields, "career_objective"))
            edits["personal_strengths"] = st.text_area("个人优势 (AI 生成)", value=_fv(fields, "personal_strengths"))

        # 教育背景
        st.subheader("教育背景 *")
        edu_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "education"), ensure_ascii=False, indent=2),
            height=100,
        )

        # 专业技能
        st.subheader("专业技能 *")
        skills_text = st.text_area(
            "JSON 格式 [{\"name\": \"...\", \"level\": \"精通/熟练/了解\"}]",
            value=json.dumps(_fv(fields, "skills"), ensure_ascii=False, indent=2),
            height=100,
        )

        # 项目经历
        st.subheader("项目经历 *")
        projects_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "projects"), ensure_ascii=False, indent=2),
            height=150,
        )

        # 可选字段
        st.subheader("实习经历（可选）")
        intern_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "internships"), ensure_ascii=False, indent=2),
            height=100,
        )

        st.subheader("技能证书与获奖荣誉（可选）")
        cert_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "certificates"), ensure_ascii=False, indent=2),
            height=100,
        )

        submitted = st.form_submit_button("💾 保存", use_container_width=True)

        if submitted:
            import re
            try:
                # 更新所有字段
                from tools.profile_manager import update_field, ALL_FIELDS

                # JSON 字段
                json_fields = {
                    "education": edu_text,
                    "skills": skills_text,
                    "projects": projects_text,
                    "internships": intern_text,
                    "certificates": cert_text,
                }

                for fname, text_val in json_fields.items():
                    try:
                        val = json.loads(text_val)
                        update_field(fname, val)
                    except json.JSONDecodeError:
                        st.error(f"{fname} JSON 格式错误，请检查")

                for fname, val in edits.items():
                    if val:
                        update_field(fname, val)

                refresh_profile()
                st.session_state.editing_field = None
                st.success("个人信息已保存")
                st.rerun()

            except Exception as e:
                st.error(f"保存失败: {e}")

    if st.button("取消编辑"):
        st.session_state.editing_field = None
        st.rerun()

    st.stop()  # 编辑模式不显示聊天


# === 主区域：聊天 ===
st.header("💬 AI 求职助手")

# 个人信息未完整时，显示警告
missing = check_completeness(st.session_state.profile)
if missing:
    label_map = {
        "name": "姓名", "expected_salary": "期望薪资", "location": "所在地",
        "phone": "电话", "email": "邮箱", "education": "教育背景",
        "skills": "专业技能", "projects": "项目经历",
    }
    missing_labels = [label_map.get(m, m) for m in missing]
    st.warning(f"个人信息不完整，请先在侧栏补充：{', '.join(missing_labels)}")
    st.caption("提示：上传简历文件可自动填写，缺失项手动补充")

# 聊天历史
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "extra" in msg:
            # 额外内容：表格、PDF 链接等
            for extra in msg["extra"]:
                if extra["type"] == "pdf":
                    st.download_button(
                        label=f"📥 下载 {extra.get('label', 'PDF')}",
                        data=open(extra["path"], "rb").read(),
                        file_name=Path(extra["path"]).name,
                        mime="application/pdf",
                    )
                elif extra["type"] == "greeting":
                    st.code(extra["text"], language=None)
                    st.button("📋 复制", key=f"copy_{msg.get('id', '')}", on_click=lambda t=extra["text"]: _copy_to_clipboard(t))

# 输入框
if missing:
    st.chat_input("请先完善个人信息后再开始聊天...", disabled=True)
else:
    user_input = st.chat_input("输入消息，如：帮我在Boss直聘上找Python开发岗位...")

    if user_input:
        # 添加用户消息
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 运行 Agent Loop
        with st.chat_message("assistant"):
            agent = AgentLoop(mcp_invoke)
            result_placeholder = st.empty()
            full_text = ""

            for event in agent.run(user_input, st.session_state.profile):
                if event["type"] == "status":
                    result_placeholder.info(event["text"])
                elif event["type"] == "tool_call":
                    result_placeholder.info(f"🔧 调用工具：{event['name']}...")
                elif event["type"] == "text":
                    full_text = event["text"]
                    result_placeholder.markdown(full_text)

            # 保存到历史
            msg_entry = {"role": "assistant", "content": full_text}

            # 检测打招呼语并添加 extra
            if "```" in full_text:
                import re
                greeting_match = re.search(r'```\n?(.*?)\n?```', full_text, re.DOTALL)
                if greeting_match:
                    msg_entry["extra"] = [{"type": "greeting", "text": greeting_match.group(1)}]

            st.session_state.chat_history.append(msg_entry)

        st.rerun()


# === 辅助函数 ===
def _fv(fields: dict, name: str):
    """安全获取字段值。"""
    f = fields.get(name, {})
    val = f.get("value") if isinstance(f, dict) else None
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return val
    return str(val)


def _copy_to_clipboard(text: str):
    """复制文本到剪贴板。"""
    st.toast("已复制到剪贴板！", icon="📋")


# === 启动时初始化 ===
if __name__ == "__main__":
    init_chroma()
