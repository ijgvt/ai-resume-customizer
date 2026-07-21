"""AI简历定制助手"""
import json
import os
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from config import RESUME_FILES_DIR, UPLOADS_DIR, PHOTOS_DIR
from tools.profile_manager import load_profile, check_completeness, update_field
from tools.resume_parser import parse_files, parse_directory
from tools.profile_extractor import extract_profile
from tools.html_resume_generator import generate_html_resume
from tools.greeting import generate_greeting

st.set_page_config(page_title="AI简历定制助手", page_icon="📄", layout="wide")

FIELD_LABELS = {
    "name": "姓名", "expected_salary": "期望薪资", "location": "所在地",
    "phone": "电话", "email": "邮箱", "education": "教育背景",
    "skills": "专业技能", "projects": "项目经历",
}

if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
if "page" not in st.session_state:
    st.session_state.page = "home"


def refresh_profile():
    st.session_state.profile = load_profile()


def process_resume_files(file_paths: list[str]):
    with st.spinner("正在解析文件..."):
        texts = parse_files(file_paths)
        st.session_state.profile = extract_profile(texts)


def _fv(fields: dict, name: str):
    f = fields.get(name, {})
    val = f.get("value") if isinstance(f, dict) else None
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return val
    return str(val)


# ════════════════════ 侧栏 ════════════════════
with st.sidebar:
    st.header("📁 简历管理")

    uploaded_files = st.file_uploader(
        "上传简历文件", type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="支持 PDF、Word、TXT 格式，可同时上传多个文件",
    )

    if uploaded_files:
        new_files = []
        for uf in uploaded_files:
            save_path = UPLOADS_DIR / uf.name
            with open(save_path, "wb") as f:
                f.write(uf.getbuffer())
            new_files.append(str(save_path))

        if new_files and st.button("🔍 解析上传的文件", use_container_width=True):
            process_resume_files(new_files)
            st.success(f"已解析 {len(new_files)} 个文件")
            st.rerun()

    st.divider()
    pre_existing = [f for f in RESUME_FILES_DIR.glob("*") if f.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if pre_existing:
        st.caption(f"📂 预存文件夹中有 {len(pre_existing)} 个文件")
        if st.button("🔄 解析预存文件", use_container_width=True):
            with st.spinner("正在解析..."):
                texts = parse_directory(str(RESUME_FILES_DIR))
                st.session_state.profile = extract_profile(texts)
                st.success(f"已解析 {len(texts)} 个文件")
                st.rerun()

    st.divider()

    st.header("📷 证件照")
    current_photo = _fv(st.session_state.profile.get("fields", {}), "photo")
    if current_photo and Path(current_photo).exists():
        st.image(current_photo, width=150)
        st.caption(f"当前：{Path(current_photo).name}")
        if st.button("❌ 移除照片", use_container_width=True):
            update_field("photo", "", status="extracted")
            refresh_profile()
            st.rerun()
    else:
        uploaded_photo = st.file_uploader(
            "上传证件照", type=["jpg", "jpeg", "png"],
            accept_multiple_files=False, help="支持 JPG/PNG",
            key="photo_uploader",
        )
        if uploaded_photo:
            save_path = PHOTOS_DIR / uploaded_photo.name
            with open(save_path, "wb") as f:
                f.write(uploaded_photo.getbuffer())
            update_field("photo", str(save_path), status="extracted")
            refresh_profile()
            st.success("照片已保存")
            st.rerun()

    pre_photos = [f for f in PHOTOS_DIR.glob("*") if f.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if pre_photos:
        with st.expander(f"📂 预存照片（{len(pre_photos)} 张）"):
            for p in pre_photos:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.caption(p.name)
                with c2:
                    if st.button("使用", key=f"use_{p.name}"):
                        update_field("photo", str(p), status="extracted")
                        refresh_profile()
                        st.rerun()

    st.divider()

    st.header("👤 个人信息")
    missing = check_completeness(st.session_state.profile)
    if not missing:
        st.success("✅ 全部就绪")
    else:
        for name in missing:
            st.error(f"❌ {FIELD_LABELS.get(name, name)} 缺失")

    if st.button("📝 查看/编辑个人信息", use_container_width=True):
        st.session_state.page = "edit_profile"
        st.rerun()

    st.divider()
    if st.session_state.page != "home":
        if st.button("🏠 返回首页", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

    st.divider()
    st.header("⚙️ 设置")
    st.caption("DeepSeek API: " + ("🟢" if os.getenv("DEEPSEEK_API_KEY") else "🔴"))
    st.caption("智谱 OCR API: " + ("🟢" if os.getenv("ZHIPU_OCR_API_KEY") else "🔴"))


# ════════════════════ 首页 ════════════════════
if st.session_state.page == "home":
    st.title("📄 AI简历定制助手")
    st.caption("上传简历 → 粘贴 JD → 一键生成专业 HTML 简历 + 招呼语")

    missing = check_completeness(st.session_state.profile)
    if missing:
        labels = [FIELD_LABELS.get(m, m) for m in missing]
        st.warning(f"⚠️ 个人信息不完整：{', '.join(labels)}。请先在侧栏上传简历或手动编辑补充。")

    st.markdown("---")

    with st.form("jd_form"):
        jd_text_input = st.text_area(
            "将岗位 JD 粘贴到下方", height=300,
            placeholder="粘贴完整的职位描述（JD），包括岗位要求、职责、技能要求等...",
            disabled=bool(missing),
        )
        col1, col2 = st.columns(2)
        with col1:
            jd_title = st.text_input("岗位名称（可选）", placeholder="如：Python 后端开发工程师")
        with col2:
            jd_company = st.text_input("公司名称（可选）", placeholder="如：XX科技有限公司")

        generate_greeting_too = st.checkbox("同时生成招呼语", value=True)
        submitted = st.form_submit_button("🚀 生成 HTML 简历", use_container_width=True, type="primary", disabled=bool(missing))

    if submitted and jd_text_input.strip():
        jd = {"title": jd_title or "定制简历", "company": jd_company or "", "jd_text": jd_text_input.strip()}

        with st.spinner("AI 正在分析 JD 并重写简历..."):
            html_path = generate_html_resume(st.session_state.profile, jd)

        greeting = None
        if generate_greeting_too:
            with st.spinner("正在生成招呼语..."):
                greeting = generate_greeting(st.session_state.profile, jd)

        st.markdown("---")
        st.success("生成完成！")

        st.subheader("📄 HTML 简历预览")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        st.html(html_content)

        st.download_button(
            label="📥 下载 HTML 简历（浏览器 Ctrl+P 打印 PDF）",
            data=html_content, file_name=Path(html_path).name,
            mime="text/html", use_container_width=True,
        )
        st.caption(f"文件路径：{html_path}")

        if greeting:
            st.markdown("---")
            st.subheader("💬 打招呼语")
            st.code(greeting, language=None)

    elif submitted and not jd_text_input.strip():
        st.error("请粘贴 JD 内容后再生成")

    st.stop()


# ════════════════════ 个人信息编辑 ════════════════════
if st.session_state.page == "edit_profile":
    st.header("📝 编辑个人信息")
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
            edits["career_objective"] = st.text_area(
                "求职意向 (AI 生成)", value=json.dumps(_fv(fields, "career_objective"), ensure_ascii=False, indent=2),
                height=80, help='JSON数组，如 ["Python开发", "数据分析师"]',
            )
            edits["personal_strengths"] = st.text_area("个人优势 (AI 生成)", value=_fv(fields, "personal_strengths"), height=80)

        st.subheader("教育背景 *")
        edu_text = st.text_area("JSON", value=json.dumps(_fv(fields, "education"), ensure_ascii=False, indent=2), height=80)
        st.subheader("专业技能 *")
        skills_text = st.text_area("JSON [name/level]", value=json.dumps(_fv(fields, "skills"), ensure_ascii=False, indent=2), height=80)
        st.subheader("项目经历 *")
        projects_text = st.text_area("JSON", value=json.dumps(_fv(fields, "projects"), ensure_ascii=False, indent=2), height=120)
        st.subheader("实习经历（可选）")
        intern_text = st.text_area("JSON", value=json.dumps(_fv(fields, "internships"), ensure_ascii=False, indent=2), height=80)
        st.subheader("技能证书与获奖荣誉（可选）")
        cert_text = st.text_area("JSON", value=json.dumps(_fv(fields, "certificates"), ensure_ascii=False, indent=2), height=80)

        st.markdown("---")
        st.caption("以下为 HTML 简历生成所需内容（粘贴JD后自动填充，也可手动编辑）")
        st.subheader("STAR 经历")
        star_exp_text = st.text_area(
            "JSON [{section, company, role, period, bullets: [{label, text}]}]",
            value=json.dumps(_fv(fields, "star_experiences"), ensure_ascii=False, indent=2), height=200,
        )
        st.subheader("技能标签")
        star_skills_text = st.text_area(
            "JSON [{label, text}]", value=json.dumps(_fv(fields, "star_skills"), ensure_ascii=False, indent=2), height=100,
        )
        st.subheader("自我评价")
        self_eval_text = st.text_area("纯文本，60-100字", value=_fv(fields, "self_evaluation"), height=80)

        submitted = st.form_submit_button("💾 保存", use_container_width=True)

        if submitted:
            json_fields = {
                "education": edu_text, "skills": skills_text,
                "projects": projects_text, "internships": intern_text,
                "certificates": cert_text, "career_objective": edits.get("career_objective", "[]"),
                "star_experiences": star_exp_text, "star_skills": star_skills_text,
            }
            for fname, text_val in json_fields.items():
                try:
                    status = "generated" if fname.startswith("star_") else "extracted"
                    update_field(fname, json.loads(text_val), status=status)
                except json.JSONDecodeError:
                    st.error(f"{fname} JSON 格式错误")
            update_field("self_evaluation", self_eval_text, status="generated")
            for fname, val in edits.items():
                if val:
                    update_field(fname, val)
            refresh_profile()
            st.session_state.page = "home"
            st.success("个人信息已保存")
            st.rerun()

    if st.button("取消", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
    st.stop()
