"""个人信息存储与校验。profile.json 是用户信息的唯一真相源。"""
import json
from datetime import datetime
from pathlib import Path
from config import PROFILE_PATH

# 10 个固定模块字段名
FIXED_FIELDS = [
    "name", "career_objective", "expected_salary", "location",
    "phone", "email", "education", "skills", "projects", "personal_strengths"
]

# 固定模块中需要 LLM 生成的字段
GENERATED_FIELDS = {"career_objective", "personal_strengths"}

# 固定模块中需要用户提供（从文件提取或手动填写）的字段
EXTRACTABLE_FIXED = [f for f in FIXED_FIELDS if f not in GENERATED_FIELDS]

# 2 个可选模块字段名
OPTIONAL_FIELDS = ["internships", "certificates"]

ALL_FIELDS = FIXED_FIELDS + OPTIONAL_FIELDS

# 每个字段的类型标记
FIELD_TYPES = {f: "fixed" for f in FIXED_FIELDS}
FIELD_TYPES.update({f: "optional" for f in OPTIONAL_FIELDS})


def create_empty_profile(source_files: list[str] | None = None) -> dict:
    """创建空的 profile 模板，所有字段标记为 missing。"""
    fields = {}
    for name in ALL_FIELDS:
        fields[name] = {
            "value": None if name not in ("education", "skills", "projects", "internships", "certificates") else [],
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
    """读取 profile.json，如果文件不存在则返回空模板。"""
    if not PROFILE_PATH.exists():
        return create_empty_profile()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> None:
    """写入 profile.json，自动更新 updated_at。"""
    profile["meta"]["updated_at"] = datetime.now().isoformat()
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def check_completeness(profile: dict | None = None) -> list[str]:
    """检查固定模块完整性，返回缺失的字段名列表。

    固定模块中，除 LLM 生成的字段外，其余字段 status 不能是 'missing'。
    generated 的字段即使 missing 也不阻止（LLM 没机会生成前）。
    非空列表值的字段（education, skills, projects）还需要检查值不为空列表。
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

    return missing


def update_field(field_name: str, value: any) -> None:
    """读取 profile.json，更新指定字段后写回。

    Args:
        field_name: 字段名（必须在 ALL_FIELDS 中）
        value: 新值
    """
    if field_name not in ALL_FIELDS:
        raise ValueError(f"Unknown field: {field_name}")

    profile = load_profile()
    profile["fields"][field_name]["value"] = value
    profile["fields"][field_name]["status"] = "extracted"
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
