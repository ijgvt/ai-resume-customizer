"""个人信息存储与校验。profile.json 是用户信息的唯一真相源。"""
import json
from datetime import datetime
from pathlib import Path
from config import PROFILE_PATH

# 固定模块（8 个基础 + 2 个 LLM 生成）
FIXED_FIELDS = [
    "name", "career_objective", "expected_salary", "location",
    "phone", "email", "education", "skills", "projects", "personal_strengths"
]

# LLM 生成的字段（提取时自动生成，不阻止用户）
GENERATED_FIELDS = {"career_objective", "personal_strengths", "self_evaluation", "skill_tags"}

# 用户必须提供（从文件提取或手动填写）的字段
EXTRACTABLE_FIXED = [f for f in FIXED_FIELDS if f not in GENERATED_FIELDS]

# 可选模块
OPTIONAL_FIELDS = ["internships", "certificates"]

# HTML 构建额外需要的字段
HTML_FIELDS = ["photo", "skill_tags", "star_experiences", "star_skills", "self_evaluation", "courses"]

ALL_FIELDS = FIXED_FIELDS + OPTIONAL_FIELDS + HTML_FIELDS

# 类型标记
FIELD_TYPES = {f: "fixed" for f in FIXED_FIELDS}
FIELD_TYPES.update({f: "optional" for f in OPTIONAL_FIELDS})
FIELD_TYPES.update({f: "generated" for f in HTML_FIELDS})

# 初始化为空列表的字段
LIST_FIELDS = {"education", "skills", "projects", "internships", "certificates",
               "career_objective", "star_experiences", "star_skills", "skill_tags", "courses"}


def create_empty_profile(source_files: list[str] | None = None) -> dict:
    """创建空的 profile 模板，所有字段标记为 missing。"""
    fields = {}
    for name in ALL_FIELDS:
        fields[name] = {
            "value": [] if name in LIST_FIELDS else None,
            "type": FIELD_TYPES[name],
            "status": "missing",
        }
    return {
        "meta": {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source_files": source_files or [],
        },
        "fields": fields,
    }


def load_profile() -> dict:
    """读取 profile.json，如果文件不存在则返回空模板。自动补全缺失的字段。"""
    if not PROFILE_PATH.exists():
        return create_empty_profile()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    # 自动补全新版本新增的字段
    changed = False
    for name in ALL_FIELDS:
        if name not in profile.get("fields", {}):
            profile["fields"][name] = {
                "value": [] if name in LIST_FIELDS else None,
                "type": FIELD_TYPES[name],
                "status": "missing",
            }
            changed = True
    if changed:
        save_profile(profile)
    return profile


def save_profile(profile: dict) -> None:
    """写入 profile.json，自动更新 updated_at。"""
    profile["meta"]["updated_at"] = datetime.now().isoformat()
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def check_completeness(profile: dict | None = None) -> list[str]:
    """检查固定模块完整性，返回缺失的字段名列表。

    固定模块中，除 LLM 生成的字段外，其余字段 status 不能是 'missing'。
    career_objective 虽然由 LLM 生成但是必须的功能字段，也会一起检查。
    personal_strengths 由 LLM 生成且非必须，不阻止。
    """
    if profile is None:
        profile = load_profile()

    missing = []
    fields = profile.get("fields", {})

    for name in EXTRACTABLE_FIXED:
        field = fields.get(name, {})
        status = field.get("status", "missing")
        value = field.get("value")

        if status == "missing" or value is None or value == "":
            missing.append(name)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(name)

    # career_objective 虽然是 LLM 生成的，但是搜索功能的核心依赖
    car = fields.get("career_objective", {})
    car_val = car.get("value")
    if isinstance(car_val, list) and len(car_val) == 0:
        missing.append("career_objective")
    elif car_val is None or (isinstance(car_val, str) and car_val.strip() == ""):
        missing.append("career_objective")

    return missing


def update_field(field_name: str, value: any, status: str = "extracted") -> None:
    """读取 profile.json，更新指定字段后写回。

    Args:
        field_name: 字段名
        value: 新值
        status: 状态标记，默认"extracted"，STAR字段用"generated"
    """
    if field_name not in ALL_FIELDS:
        raise ValueError(f"Unknown field: {field_name}")

    profile = load_profile()
    profile["fields"][field_name]["value"] = value
    profile["fields"][field_name]["status"] = status
    save_profile(profile)


def merge_extracted_fields(extracted: dict, source_files: list[str]) -> dict:
    """将 LLM 提取的结果合并为完整 profile。

    Args:
        extracted: LLM 返回的 {"name": "张三", "skills": [...], ...}
        source_files: 已处理的源文件列表

    Returns:
        合并后的完整 profile dict（已写入文件）
    """
    profile = load_profile()

    # 更新 source_files（追加去重）
    current_sources = set(profile["meta"].get("source_files", []))
    current_sources.update(source_files)
    profile["meta"]["source_files"] = sorted(current_sources)

    fields = profile["fields"]

    for name in ALL_FIELDS:
        if name in extracted and extracted[name] is not None:
            value = extracted[name]
            # 跳过空列表和空字符串
            if isinstance(value, list) and len(value) == 0:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            fields[name]["value"] = value
            if name in GENERATED_FIELDS:
                fields[name]["status"] = "generated"
            else:
                fields[name]["status"] = "extracted"

    save_profile(profile)
    return profile


def save_star_result(star_experiences: list, star_skills: list, self_evaluation: str) -> dict:
    """将 STAR 重写结果存入 profile.json。

    Args:
        star_experiences: [{section, company, role, period, bullets: [{label, text}]}]
        star_skills: [{label, text}]
        self_evaluation: 自我评价字符串

    Returns:
        更新后的 profile dict
    """
    profile = load_profile()
    profile["fields"]["star_experiences"]["value"] = star_experiences
    profile["fields"]["star_experiences"]["status"] = "generated"
    profile["fields"]["star_skills"]["value"] = star_skills
    profile["fields"]["star_skills"]["status"] = "generated"
    profile["fields"]["self_evaluation"]["value"] = self_evaluation
    profile["fields"]["self_evaluation"]["status"] = "generated"
    profile["meta"]["updated_at"] = datetime.now().isoformat()
    save_profile(profile)
    return profile
