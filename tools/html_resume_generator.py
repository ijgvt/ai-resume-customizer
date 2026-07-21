# -*- coding: utf-8 -*-
"""HTML 简历生成器：STAR 重写 → profile.json → skill build 脚本 → HTML。"""
import json
import subprocess
from pathlib import Path
from config import OUTPUT_DIR, get_deepseek_client
from tools.profile_manager import load_profile, save_star_result

BUILD_SCRIPT = Path(__file__).parent / "_build_html.py"

# ── STAR 重写提示词（用 __PLACEHOLDER__ 替代 .format() 避免花括号冲突）──
STAR_PROMPT = """你是拥有10年经验的简历优化专家。根据用户个人信息和目标JD，按STAR法则重写项目经历和实习经历，并生成技能标签和自我评价。

## 铁律
- 只基于下面提供的用户信息，不编造经历、数据、证书
- 经历里没写的技能不要出现在技能标签里
- 不夸大角色
- 缺少量化数据时保留原有描述，不要猜测数字

## 用户个人信息
__PROFILE__

## 目标岗位 JD
__JD__

## JSON 字段要求

### star_experiences
将项目经历和实习经历合并，选与JD最相关的**最多3段**。每段包含:
- section: "实习经历" 或 "项目经历"
- company: 项目名或公司名
- role: 你的角色
- period: 时间范围
- bullets: 数组，每个元素含 label(中文动作标签) 和 text(1-2句STAR描述)

### star_skills
按能力类别分组，数组，每个元素含 label(能力类别) 和 text(具体技能名)。只写用户信息里有的技能。

### enriched_projects
原项目经历的STAR润色版，保持原有字段结构(name/role/start_date/end_date/description)，把description按STAR法则改写得更具体。

### enriched_internships
原实习经历的STAR润色版，保持原有字段结构，把description按STAR法则改写得更具体。

### self_evaluation（60-100字）
三个维度: 我有什么 / 我擅长什么 / 为什么适合。不写空泛的"性格开朗""吃苦耐劳"。

### courses（主修课程，4-6门）
从教育背景中提取与JD相关的课程。如果原始信息没有课程则写空数组。

## 输出（只输出JSON）
{"star_experiences":[...],"star_skills":[...],"enriched_projects":[...],"enriched_internships":[...],"self_evaluation":"...","courses":[...]}"""


def do_star_rewrite(profile: dict, jd: dict) -> dict:
    """STAR 重写并存入 profile.json。同时回写 enriched_projects/enriched_internships。"""
    fields = profile.get("fields", {})

    def _v(key):
        f = fields.get(key, {})
        return f.get("value") if isinstance(f, dict) else None

    # ── 构建用户信息文本 ──
    lines = []
    for key, label in [
        ("name", "姓名"), ("phone", "电话"), ("email", "邮箱"),
        ("location", "所在地"), ("expected_salary", "期望薪资"),
    ]:
        v = _v(key)
        if v:
            lines.append(f"{label}: {v}")

    obj = _v("career_objective")
    if obj:
        lines.append(f"求职方向: {', '.join(str(x) for x in obj) if isinstance(obj, list) else obj}")

    for key, label in [
        ("education", "教育背景"), ("skills", "专业技能"),
        ("projects", "项目经历"), ("internships", "实习经历"),
        ("certificates", "证书"), ("personal_strengths", "个人优势"),
    ]:
        v = _v(key)
        if v:
            if isinstance(v, list) and v:
                items = []
                for x in v:
                    if isinstance(x, dict):
                        items.append(" | ".join(f"{k}={val}" for k, val in x.items()))
                    else:
                        items.append(str(x))
                lines.append(f"\n{label}:\n" + "\n".join(f"  - {i}" for i in items))
            elif isinstance(v, str) and v:
                lines.append(f"\n{label}:\n{v}")

    profile_text = "\n".join(lines)
    jd_text = jd.get("jd_text", "") or ""
    if jd.get("title"):
        jd_text = f"岗位: {jd.get('title', '')}\n公司: {jd.get('company', '')}\n{jd_text}"

    # ── 调 LLM ──
    prompt = STAR_PROMPT.replace("__PROFILE__", profile_text).replace("__JD__", jd_text)
    client = get_deepseek_client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    if not raw:
        raise ValueError("LLM returned empty")
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])

    result = json.loads(raw)

    # ── 存入 STAR 字段 ──
    profile = save_star_result(
        star_experiences=result.get("star_experiences", []),
        star_skills=result.get("star_skills", []),
        self_evaluation=result.get("self_evaluation", ""),
    )

    # ── 回写 enriched 版本到原始字段 ──
    from tools.profile_manager import update_field
    enriched_projects = result.get("enriched_projects")
    if enriched_projects and isinstance(enriched_projects, list) and len(enriched_projects) > 0:
        update_field("projects", enriched_projects, status="enriched")

    enriched_internships = result.get("enriched_internships")
    if enriched_internships and isinstance(enriched_internships, list) and len(enriched_internships) > 0:
        update_field("internships", enriched_internships, status="enriched")

    # ── 存 courses ──
    courses = result.get("courses")
    if courses and isinstance(courses, list) and len(courses) > 0:
        update_field("courses", courses, status="generated")

    return profile


# ── HTML 构建提示词（同样用 .replace()）──
BUILD_PROMPT = """根据用户信息和JD，输出用于HTML简历生成的完整JSON。

## 用户背景(profile.json)
__PROFILE__

## 目标JD
__JD__

## 输出JSON格式
{
  "name": "姓名",
  "phone": "手机",
  "email": "邮箱",
  "objective": "目标岗位",
  "education": {"school":"","school_tag":"","major":"","degree":"","period":"","gpa":"","courses":["课程1"]},
  "experience": [{"section":"项目经历","company":"项目名","role":"角色","period":"时间","bullets":[{"label":"标签","text":"描述"}]}],
  "skills": [{"label":"类别","text":"技能描述"}],
  "self_evaluation": "60-100字自我评价"
}

## 规则
- experience用star_experiences内容，skills用star_skills内容
- education.courses用courses字段
- 不编造任何信息
- 只输出JSON"""


def build_html_from_profile(profile: dict, jd: dict) -> str:
    """从 profile.json 的 STAR 字段拼 JSON → build 脚本 → HTML。"""
    fields = profile.get("fields", {})

    def _v(key, default=None):
        f = fields.get(key, {})
        return f.get("value") if isinstance(f, dict) else default

    name = str(_v("name", ""))
    phone = str(_v("phone", ""))
    email = str(_v("email", ""))

    objective = jd.get("title", "")
    if not objective:
        obj = _v("career_objective")
        if isinstance(obj, list) and obj:
            objective = str(obj[0])
        elif obj:
            objective = str(obj)

    # 教育背景（取第一条，skill 模板只支持一条）
    edu_list = _v("education") or []
    education = {}
    if isinstance(edu_list, list) and len(edu_list) > 0:
        e = edu_list[0] if isinstance(edu_list[0], dict) else {}

        # 清理空值/占位值（"无", "N/A", "", null 等）
        def _clean_str(val):
            if not val or str(val).strip() in ("", "无", "N/A", "null", "None"):
                return ""
            return str(val).strip()

        courses_raw = _v("courses") or []
        courses_clean = [c for c in courses_raw if _clean_str(c)] if isinstance(courses_raw, list) else []

        education = {
            "school": _clean_str(e.get("school")),
            "school_tag": _clean_str(e.get("school_tag")),
            "major": _clean_str(e.get("major")),
            "degree": _clean_str(e.get("degree")),
            "period": _clean_str(e.get("period")) or _clean_str(e.get("graduation_year")),
            "gpa": _clean_str(e.get("gpa")),
            "courses": courses_clean,
        }

    # 经历用 STAR 重写结果，没有则用原始数据兜底
    star_experiences = _v("star_experiences") or []
    # 技能用 STAR 结果，没有则用 skill_tags（提取时生成的），再没有则兜底
    star_skills = _v("star_skills") or _v("skill_tags") or []
    self_eval = _v("self_evaluation") or ""
    photo_path = _v("photo") or ""

    resume_data = {
        "name": name,
        "phone": phone,
        "email": email,
        "photo": photo_path,
        "objective": objective,
        "education": education,
        "experience": star_experiences,
        "skills": star_skills,
        "self_evaluation": self_eval,
    }

    import time
    json_path = OUTPUT_DIR / f"_temp_resume_{int(time.time())}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resume_data, f, ensure_ascii=False, indent=2)

    safe_obj = objective.replace("/", "_").replace(" ", "_").replace("\\", "_")
    html_filename = f"{name}_resume_{safe_obj}.html"
    html_path = OUTPUT_DIR / html_filename

    result = subprocess.run(
        ["python", str(BUILD_SCRIPT), "build", str(json_path), str(html_path)],
        capture_output=True, text=True, timeout=30, encoding="utf-8",
    )
    json_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"HTML build failed: {result.stderr}")

    return str(html_path)


def generate_html_resume(profile: dict, jd: dict) -> str:
    """一步完成：STAR 重写 + 存 profile + build HTML。"""
    profile = do_star_rewrite(profile, jd)
    return build_html_from_profile(profile, jd)



def _find_msedge() -> str | None:
    import shutil
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    found = shutil.which("msedge")
    return found if found else None


def generate_pdf(html_path: str) -> str | None:
    msedge = _find_msedge()
    if not msedge:
        raise RuntimeError("微软 Edge 浏览器未找到，无法生成 PDF。")
    pdf_path = Path(html_path).with_suffix(".pdf")
    abs_html = Path(html_path).resolve().as_uri()
    result = subprocess.run(
        [msedge, "--headless", "--disable-gpu", "--no-sandbox",
         "--disable-software-rasterizer",
         f"--print-to-pdf={pdf_path}",
         "--no-pdf-header-footer", abs_html],
        capture_output=True, text=True, timeout=30, encoding="utf-8",
    )
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"PDF 生成失败: {result.stderr or "文件未创建"}")
    return str(pdf_path)
