# AI简历定制助手

上传简历 → 粘贴 JD → 一键生成专业 HTML 简历 + 招呼语。

## 功能特性

- **多格式简历解析**：支持 PDF（自动 OCR 识别）、Word、TXT，可同时上传多个文件
- **智能信息提取**：AI 自动从简历中提取 18 项结构化个人信息，缺失字段提醒补充
- **JD 深度分析**：提取岗位核心能力要求、隐藏招聘偏好、关键词
- **STAR 法则重写**：按情境-任务-行动-结果四要素重构项目/实习经历，突出与 JD 的匹配度
- **专业 HTML 简历**：商务风排版，自动嵌入证件照，浏览器 Ctrl+P 一键打印标准 A4 PDF，JS 自动缩放保证单页
- **招呼语生成**：基于 JD 和用户背景，生成简洁有针对性的一对一沟通文案
- **个人信息库**：一次解析，永久复用。换 JD 只需重新生成，无需重复上传简历

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key 和智谱 OCR API Key

# 启动
streamlit run app.py
```

浏览器打开 http://localhost:8501。

## 使用流程

1. **上传简历** — 侧栏拖拽 PDF/Word/TXT（支持多文件，PDF 自动 OCR），或提前放入 `data/resume_files/` 目录
2. **审核信息** — AI 自动提取后展示个人信息状态，缺失字段标红，点"编辑"手动补充
3. **上传证件照**（可选）— 侧栏上传或预存到 `data/photos/`，自动嵌入简历右上角
4. **粘贴 JD** — 把目标岗位的职位描述粘贴到输入框
5. **生成** — 点击按钮，等待 AI 分析 JD、STAR 重写、输出 HTML 简历和招呼语
6. **下载/打印** — 预览 HTML，点击下载或用浏览器 Ctrl+P 打印为标准 A4 PDF

## 项目结构

```
ai-resume-customizer/
├── app.py                         # Streamlit 前端界面（侧栏管理 + 首页生成 + 信息编辑）
├── config.py                      # 配置中心（路径、环境变量、API 客户端工厂）
├── requirements.txt               # Python 依赖
├── .env.example                   # 环境变量模板
│
├── tools/
│   ├── resume_parser.py           # 文件解析：PDF(OCR) / DOCX / TXT → 纯文本
│   ├── profile_extractor.py       # AI 提取：多文件文本 → 18 项结构化个人信息
│   ├── profile_manager.py         # 数据管理：profile.json 读写、完整性校验、字段更新
│   ├── html_resume_generator.py   # 简历生成：JD分析 + STAR重写 + 拼装JSON + 调build脚本
│   ├── _build_html.py             # HTML 模板与渲染引擎（CSS排版 + JS单页保障）
│   └── greeting.py                # 招呼语：背景+JD → AI生成沟通文案
│
├── tests/
│   └── test_integration.py        # 集成测试（个人信息 CRUD + 文件解析）
│
└── data/                          # 运行时数据（内容不上传Git）
    ├── outputs/                   # 生成的 HTML 简历
    ├── photos/                    # 证件照
    ├── resume_files/              # 预存简历文件
    └── uploads/                   # 上传的简历文件
```

## 个人信息模型（18 项）

上传简历后 AI 自动提取以下字段，支持手动编辑补充：

| 类别 | 字段 | 来源 |
|------|------|------|
| 基本信息 | 姓名、电话、邮箱、所在地、期望薪资 | 文件提取 |
| 教育 | 学校、标签(211/985)、专业、学历、时间段、GPA | 文件提取 |
| 技能 | 技能列表(name/level)、技能标签(label/text) | 文件提取 + AI 分类 |
| 经历 | 项目经历、实习经历 | 文件提取 |
| AI 生成 | 求职岗位列表、个人优势、自我评价、主修课程 | AI 推导 |
| STAR 重写 | 定制经历(bullets)、定制技能标签 | JD 触发 |
| 其他 | 证书荣誉、证件照路径 | 文件提取 + 手动上传 |

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | Streamlit |
| LLM | DeepSeek（信息提取 + STAR重写 + 招呼语） |
| OCR | 智谱 OCR API（PDF 文字识别） |
| 文件解析 | PyMuPDF（PDF渲染）、python-docx（Word提取） |
| HTML 渲染 | 原生 CSS + JS（自适应缩放、A4 打印） |

## License

MIT
