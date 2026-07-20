"""端到端集成测试：验证核心流程。"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestProfileManager:
    """测试个人信息管理模块。"""

    def setup_method(self):
        """每个测试前清理 profile.json，确保测试隔离。"""
        from config import PROFILE_PATH
        if PROFILE_PATH.exists():
            PROFILE_PATH.unlink()

    def test_create_and_load(self):
        from tools.profile_manager import create_empty_profile, save_profile, load_profile

        p = create_empty_profile()
        assert "meta" in p
        assert len(p["fields"]) == 12
        assert p["fields"]["name"]["status"] == "missing"

    def test_check_completeness_empty(self):
        from tools.profile_manager import create_empty_profile, check_completeness

        p = create_empty_profile()
        missing = check_completeness(p)
        assert len(missing) == 8  # 8 个非 LLM 生成的固定字段

    def test_check_completeness_full(self):
        from tools.profile_manager import merge_extracted_fields, check_completeness

        data = {
            "name": "张三",
            "career_objective": "Python 开发",
            "expected_salary": "20K",
            "location": "深圳",
            "phone": "13800138000",
            "email": "test@test.com",
            "education": [{"school": "XX大学", "major": "CS", "degree": "本科", "graduation_year": "2020"}],
            "skills": [{"name": "Python", "level": "精通"}],
            "projects": [{"name": "项目A", "role": "开发", "start_date": "2021", "end_date": "2022", "description": "test"}],
            "personal_strengths": "优点",
        }
        profile = merge_extracted_fields(data, ["test.pdf"])
        missing = check_completeness(profile)
        assert len(missing) == 0

    def test_merge_extracted_fields_preserves_existing(self):
        from tools.profile_manager import merge_extracted_fields, load_profile

        # 先写入部分数据
        data1 = {"name": "张三", "phone": "13800138000"}
        merge_extracted_fields(data1, ["v1.pdf"])

        # 再追加（不同文件）
        data2 = {"email": "test@test.com"}
        profile = merge_extracted_fields(data2, ["v2.pdf"])

        assert profile["fields"]["name"]["value"] == "张三"
        assert profile["fields"]["email"]["value"] == "test@test.com"
        assert len(profile["meta"]["source_files"]) == 2


class TestResumeParser:
    """测试文件解析模块。"""

    def test_parse_txt(self):
        from tools.resume_parser import parse_file

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
            f.write("姓名：张三\n技能：Python, Java")
            path = f.name

        text = parse_file(path)
        assert "张三" in text
        assert "Python" in text
        os.unlink(path)

    def test_parse_docx(self):
        from tools.resume_parser import parse_file
        from docx import Document

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            doc = Document()
            doc.add_paragraph("姓名：李四")
            doc.add_paragraph("技能：Django, React")
            doc.save(f.name)
            path = f.name

        text = parse_file(path)
        assert "李四" in text
        assert "Django" in text
        os.unlink(path)

    def test_unsupported_format(self):
        from tools.resume_parser import parse_file
        import pytest

        with pytest.raises(ValueError, match="Unsupported"):
            parse_file("test.xyz")


class TestPdfGenerator:
    """测试 PDF 生成模块。"""

    def test_generate_pdf(self):
        from tools.profile_manager import merge_extracted_fields
        from tools.pdf_generator import generate_pdf

        data = {
            "name": "王五",
            "career_objective": "全栈工程师",
            "expected_salary": "25K-35K",
            "location": "北京",
            "phone": "13900139000",
            "email": "wang@test.com",
            "education": [{"school": "清华", "major": "软件工程", "degree": "硕士", "graduation_year": "2022"}],
            "skills": [{"name": "Python", "level": "精通"}, {"name": "Vue", "level": "熟练"}],
            "projects": [{"name": "管理后台", "role": "全栈", "start_date": "2022", "end_date": "2023", "description": "从零搭建"}],
            "personal_strengths": "1. 全栈能力\n2. 快速学习",
            "internships": [],
            "certificates": [{"name": "PMP", "issuer": "PMI", "year": "2023"}],
        }
        profile = merge_extracted_fields(data, ["test.pdf"])
        jd = {"title": "全栈工程师", "company": "XX科技", "jd_text": "需要Python和Vue", "salary": "25K-35K"}

        path = generate_pdf(profile, jd)
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        assert "全栈工程师" in path


class TestMCPTools:
    """测试 MCP 工具层（直接调用，不经过 SSE）。"""

    def test_profile_tools(self):
        from tools.profile_manager import merge_extracted_fields, load_profile, check_completeness, update_field

        # 设置测试数据
        data = {
            "name": "测试用户",
            "expected_salary": "15K",
            "location": "深圳",
            "phone": "123",
            "email": "a@b.com",
            "education": [{"school": "XX", "major": "CS", "degree": "本科", "graduation_year": "2020"}],
            "skills": [{"name": "Python", "level": "精通"}],
            "projects": [{"name": "P", "role": "DEV", "start_date": "2021", "end_date": "2022", "description": "T"}],
            "career_objective": "开发",
            "personal_strengths": "1. x",
        }
        merge_extracted_fields(data, ["test.pdf"])

        profile = load_profile()
        assert profile["fields"]["name"]["value"] == "测试用户"

        missing = check_completeness()
        assert len(missing) == 0

        update_field("phone", "999")
        profile = load_profile()
        assert profile["fields"]["phone"]["value"] == "999"

    def test_search_empty_db(self):
        from tools.resume_search import search
        results = search("Python", top_k=3)
        # 即使空也应该返回 []
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
