"""Boss 直聘岗位详情页爬取，提取完整 JD。"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def _create_driver() -> webdriver.Chrome:
    """创建使用用户 Chrome Profile 的 WebDriver（保留登录态）。

    注意：使用前必须关闭所有 Chrome 窗口，否则 Chrome 会锁定 Profile 导致启动失败。
    """
    import os
    options = Options()

    # 使用用户已有的 Chrome Profile 保留登录态
    user_data_dir = os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\User Data"
    )
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--profile-directory=Default")

    # 去掉自动化检测标记
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationEnabled", False)

    driver = webdriver.Chrome(options=options)
    return driver


def get_job_detail(url: str) -> dict:
    """爬取单个 Boss 直聘岗位详情页。

    Args:
        url: 岗位详情页完整 URL

    Returns:
        {
            "title": 岗位名称,
            "company": 公司名,
            "salary": 薪资,
            "location": 工作地点,
            "experience": 经验要求,
            "education": 学历要求,
            "jd_text": 完整职位描述,
            "tags": 标签列表,
            "url": 原始 URL,
        }
    """
    driver = _create_driver()
    detail: dict = {"url": url}

    try:
        driver.get(url)
        time.sleep(3)

        # 尝试多种 CSS selector 适配页面变化
        selectors = {
            "title": ".name, .job-name, h1",
            "company": ".company-name, .company-info .name",
            "salary": ".salary, .salary-bar .salary",
            "jd_text": ".job-detail, .job-sec, .text, .detail-text",
            "location": ".job-location, .location-address",
            "experience": ".job-experience, .experience-request",
        }

        for field, selector in selectors.items():
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                detail[field] = el.text.strip()
            except Exception:
                detail[field] = ""

        # 提取标签
        try:
            tag_els = driver.find_elements(By.CSS_SELECTOR, ".job-tag, .tag-item, .tags .tag")
            detail["tags"] = [t.text.strip() for t in tag_els if t.text.strip()]
        except Exception:
            detail["tags"] = []

        # 综合 JD 文本：job-detail + job-sec 两个区域
        all_text_parts = []
        try:
            sections = driver.find_elements(By.CSS_SELECTOR, ".job-sec, .job-detail, .detail-section")
            for sec in sections:
                text = sec.text.strip()
                if text:
                    all_text_parts.append(text)
        except Exception:
            pass

        if all_text_parts:
            detail["jd_text"] = "\n\n".join(all_text_parts)

        return detail

    except Exception as e:
        detail["error"] = str(e)
        return detail

    finally:
        driver.quit()
