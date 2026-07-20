"""Boss 直聘搜索列表爬取，使用 Selenium 自动化浏览器。"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BOSS_BASE_URL = "https://www.zhipin.com"


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


def search_boss(keyword: str, city: str, max_pages: int = 3) -> list[dict]:
    """在 Boss 直聘搜索岗位列表。

    Args:
        keyword: 搜索关键词，如 "Python开发"
        city: 城市编码，如 "101280600"（深圳），"100010000"（北京）
        max_pages: 最大翻页数

    Returns:
        [{title, company, salary, description, url, city}, ...]
    """
    driver = _create_driver()
    jobs: list[dict] = []

    try:
        # 构造搜索 URL
        search_url = f"{BOSS_BASE_URL}/web/geek/job?query={keyword}&city={city}"
        driver.get(search_url)
        time.sleep(3)  # 等待页面加载

        for page in range(max_pages):
            # 等待岗位卡片加载
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".job-card-body, .job-card-wrap"))
                )
            except Exception:
                break  # 页面结构可能变化，中断翻页

            time.sleep(2)
            cards = driver.find_elements(By.CSS_SELECTOR, ".job-card-body, .job-card-wrap")

            for card in cards:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, ".job-name, .job-title")
                    company_el = card.find_element(By.CSS_SELECTOR, ".company-name, .company-text")
                    salary_el = card.find_element(By.CSS_SELECTOR, ".salary, .red")
                    link_el = card.find_element(By.CSS_SELECTOR, "a")

                    title = title_el.text.strip()
                    company = company_el.text.strip()
                    salary = salary_el.text.strip() if salary_el else ""
                    url = link_el.get_attribute("href") or ""

                    # 尝试获取简要描述
                    desc_el = card.find_elements(By.CSS_SELECTOR, ".job-info, .tag-list, .job-tag")
                    desc = " ".join([d.text.strip() for d in desc_el if d.text.strip()])

                    if title and company:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "salary": salary,
                            "description": desc,
                            "url": url,
                            "city": city,
                        })
                except Exception:
                    continue  # 单个卡片解析失败不影响整体

            # 翻页
            if page < max_pages - 1:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, ".page .next, .next-page")
                    if "disabled" in (next_btn.get_attribute("class") or ""):
                        break
                    next_btn.click()
                    time.sleep(3)
                except Exception:
                    break

        return jobs

    finally:
        driver.quit()
