"""fpdf2 定制化 PDF 简历生成，内容 100% 来自 profile.json，按固定模板拼装。"""
from datetime import datetime
from fpdf import FPDF
from config import FONT_PATH, OUTPUT_DIR


class ResumePDF(FPDF):
    """中文简历 PDF 生成器。"""

    def __init__(self):
        super().__init__()
        self.add_font("NotoSansSC", "", str(FONT_PATH), uni=True)
        # 注册粗体变体（如果没有粗体文件，用 regular 替代）
        self.add_font("NotoSansSC", "B", str(FONT_PATH), uni=True)

    def header(self):
        pass  # 不显示页眉

    def footer(self):
        pass  # 不显示页脚


def generate_pdf(
    profile: dict,
    jd: dict | None = None,
    relevant_skills: list[str] | None = None,
    relevant_projects: list[str] | None = None,
) -> str:
    """生成定制化 PDF 简历。

    Args:
        profile: 从 profile.json 加载的用户信息 dict
        jd: 岗位 JD 信息（用于排序和加重），可为 None
        relevant_skills: RAG 检索到的最相关技能名列表
        relevant_projects: RAG 检索到的最相关项目名列表

    Returns:
        生成的 PDF 文件绝对路径
    """
    fields = profile.get("fields", {})
    jd = jd or {}
    relevant_skills = relevant_skills or []
    relevant_projects = relevant_projects or []

    pdf = ResumePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 颜色设置
    SECTION_BG = (240, 240, 240)  # 节标题背景灰
    LINE_COLOR = (200, 200, 200)   # 分隔线灰
    TEXT_DARK = (30, 30, 30)
    TEXT_GRAY = (100, 100, 100)

    # ===== 1. 个人信息区 =====
    _section_title(pdf, "个人信息")
    name = _f(fields, "name")
    phone = _f(fields, "phone")
    email = _f(fields, "email")
    location = _f(fields, "location")
    objective = _f(fields, "career_objective")
    salary = _f(fields, "expected_salary")

    pdf.set_font("NotoSansSC", "B", 16)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 10, name, ln=True)

    pdf.set_font("NotoSansSC", "", 10)
    pdf.set_text_color(*TEXT_GRAY)
    info_line = f"{phone}  |  {email}  |  {location}"
    pdf.cell(0, 7, info_line, ln=True)
    if objective:
        pdf.cell(0, 7, f"求职意向：{objective}    期望薪资：{salary}", ln=True)
    pdf.ln(3)

    # ===== 2. 教育背景区 =====
    _section_title(pdf, "教育背景")
    edu_list = _v(fields, "education")
    if isinstance(edu_list, list):
        for edu in edu_list:
            if isinstance(edu, dict):
                line = f"{edu.get('school', '')}  |  {edu.get('major', '')}  |  {edu.get('degree', '')}  |  {edu.get('graduation_year', '')}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
    pdf.ln(3)

    # ===== 3. 专业技能区（按 JD 匹配度排序）=====
    _section_title(pdf, "专业技能")
    skills = _v(fields, "skills")
    if isinstance(skills, list):
        # 排序：RAG 命中 → 前置
        def _skill_sort_key(s):
            name = s.get("name", "") if isinstance(s, dict) else str(s)
            relevant = name in relevant_skills or any(
                kw in name for kw in (jd.get("jd_text", "") + jd.get("title", ""))
            )
            return 0 if relevant else 1

        sorted_skills = sorted(skills, key=_skill_sort_key)
        for sk in sorted_skills:
            if isinstance(sk, dict):
                name = sk.get("name", "")
                level = sk.get("level", "")
                line = f"• {name}"
                if level:
                    line += f"（{level}）"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
    pdf.ln(3)

    # ===== 4. 项目经历区（JD 相关加重）=====
    _section_title(pdf, "项目经历")
    projects = _v(fields, "projects")
    if isinstance(projects, list):
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pname = proj.get("name", "")
            is_relevant = pname in relevant_projects or any(
                kw in str(proj) for kw in (jd.get("jd_text", "") + jd.get("title", ""))
            )

            # 项目标题
            pdf.set_font("NotoSansSC", "B" if is_relevant else "", 11 if is_relevant else 10)
            pdf.set_text_color(*TEXT_DARK)
            role = proj.get("role", "")
            dates = f"{proj.get('start_date', '')} - {proj.get('end_date', '')}"
            pdf.cell(0, 7, f"• {pname}  |  {role}  |  {dates}", ln=True)

            # 项目描述
            desc = proj.get("description", "")
            if desc:
                pdf.set_font("NotoSansSC", "", 9)
                pdf.set_text_color(*TEXT_GRAY)
                # 处理长文本换行
                desc_lines = _wrap_text(pdf, desc, 170)
                for dl in desc_lines:
                    pdf.cell(0, 5, f"  {dl}", ln=True)
            pdf.ln(2)

    pdf.ln(2)

    # ===== 5. 实习经历区（如有）=====
    internships = _v(fields, "internships")
    if isinstance(internships, list) and len(internships) > 0:
        _section_title(pdf, "实习经历")
        for inter in internships:
            if isinstance(inter, dict):
                line = f"• {inter.get('company', '')}  |  {inter.get('position', '')}  |  {inter.get('start_date', '')} - {inter.get('end_date', '')}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
                desc = inter.get("description", "")
                if desc:
                    pdf.set_font("NotoSansSC", "", 9)
                    pdf.set_text_color(*TEXT_GRAY)
                    for dl in _wrap_text(pdf, desc, 170):
                        pdf.cell(0, 5, f"  {dl}", ln=True)
        pdf.ln(3)

    # ===== 6. 证书荣誉区（如有）=====
    certs = _v(fields, "certificates")
    if isinstance(certs, list) and len(certs) > 0:
        _section_title(pdf, "技能证书与获奖荣誉")
        for cert in certs:
            if isinstance(cert, dict):
                line = f"• {cert.get('name', '')}"
                if cert.get("issuer"):
                    line += f"  |  {cert['issuer']}"
                if cert.get("year"):
                    line += f"  |  {cert['year']}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
        pdf.ln(3)

    # ===== 7. 个人优势区 =====
    strengths = _f(fields, "personal_strengths")
    if strengths:
        _section_title(pdf, "个人优势")
        pdf.set_font("NotoSansSC", "", 10)
        pdf.set_text_color(*TEXT_DARK)
        for line in strengths.split("\n"):
            line = line.strip()
            if line:
                pdf.cell(0, 7, line, ln=True)

    # ===== 保存 =====
    # 生成文件名
    job_title = jd.get("title", "定制简历").replace("/", "_").replace(" ", "_")
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"resume_{job_title}_{date_str}.pdf"
    output_path = str(OUTPUT_DIR / filename)

    pdf.output(output_path)
    return output_path


def _section_title(pdf: ResumePDF, title: str):
    """绘制节标题（带背景条）。"""
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("NotoSansSC", "B", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, f"  {title}", ln=True, fill=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _f(fields: dict, name: str) -> str:
    """安全获取字段的字符串值。"""
    f = fields.get(name, {})
    val = f.get("value", "") if isinstance(f, dict) else ""
    return str(val) if val else ""


def _v(fields: dict, name: str):
    """安全获取字段的原始值。"""
    f = fields.get(name, {})
    return f.get("value") if isinstance(f, dict) else None


def _wrap_text(pdf: ResumePDF, text: str, max_width: float) -> list[str]:
    """简单中文换行：按宽度估算每行字符数。"""
    # 中文字符约 5pt 宽度（9pt 字体），170mm 宽约 34 个中文字符
    chars_per_line = int(max_width / 5)  # 约 34
    lines = []
    remaining = text
    while len(remaining) > chars_per_line:
        lines.append(remaining[:chars_per_line])
        remaining = remaining[chars_per_line:]
    if remaining:
        lines.append(remaining)
    return lines
