# AI 求职简历优化助手 — 设计文档

> 日期：2026-07-20
> 状态：待审批

---

## 1. 概述

一个 AI 驱动的求职辅助工具。用户上传简历文件，系统自动解析提取结构化个人信息，然后通过 DeepSeek LLM + MCP 工具编排，实现 Boss 直聘岗位搜索、简历-JD 匹配推理、定制化 PDF 简历生成、打招呼语生成。

### 1.1 核心用户流程

1. 上传简历文件（PDF/DOCX/TXT）→ 自动解析 → 提取个人信息 → 用户审阅补充
2. 聊天式交互：告诉 AI 找什么岗位
3. AI 自动搜索 Boss 直聘 → 推理匹配度 → 展示岗位列表
4. 对高匹配岗位生成定制 PDF 简历 + 招呼语

---

## 2. 架构

```
┌──────────────────────┐     Tool Calls via SSE     ┌──────────────────────┐
│   Streamlit 前端      │ ◄────────────────────────► │   MCP Server         │
│                      │                             │   localhost:8765      │
│  • 聊天 UI            │                             │                      │
│  • 侧栏个人信息管理    │    ┌──────────────────┐    │  • profile_*          │
│  • 文件上传/解析       │    │   Agent Loop      │    │  • resume_*           │
│  • PDF 预览/下载      │    │   (ReAct 模式)    │    │  • boss_search_list   │
│  • 招呼语复制         │    │                   │    │  • boss_job_detail    │
│                      │    │  DeepSeek API     │    │  • pdf_generate       │
│                      │    │  tool_calls 机制   │    │  • greeting_generate  │
│                      │    └──────────────────┘    │                      │
└──────────┬───────────┘                             └──────────┬───────────┘
           │                                                    │
           ▼                                                    ▼
    ┌─────────────┐                                     ┌──────────────┐
    │  DeepSeek   │                                     │  Zhipu API   │
    │  (LLM)      │                                     │  OCR + Emb   │
    └─────────────┘                                     └──────┬───────┘
                                                               │
                                                               ▼
                                                        ┌──────────────┐
                                                        │   ChromaDB   │
                                                        │  (本地持久化)  │
                                                        └──────────────┘
```

### 2.1 目录结构

```
resume_agent/
├── app.py                     # Streamlit 入口
├── agent/
│   ├── __init__.py
│   └── loop.py                # Agent 循环 (ReAct)
├── mcp_server/
│   ├── __init__.py
│   └── server.py              # MCP Server SSE 入口
├── tools/
│   ├── __init__.py
│   ├── resume_parser.py       # 文件解析 (TXT/DOCX/PDF→OCR)
│   ├── resume_store.py        # ChromaDB 向量化存储
│   ├── resume_search.py       # 向量检索
│   ├── profile_manager.py     # profile.json 读写校验
│   ├── profile_extractor.py   # LLM 结构化提取
│   ├── boss_search.py         # Boss 搜索列表爬取
│   ├── boss_detail.py         # Boss JD 详情爬取
│   ├── pdf_generator.py       # fpdf2 定制 PDF 生成
│   └── greeting.py            # 招呼语生成
├── fonts/
│   └── NotoSansSC-Regular.ttf
├── data/
│   ├── chroma/                # ChromaDB 持久化
│   ├── uploads/               # 用户上传的简历文件
│   ├── resume_files/          # 预存简历文件夹
│   └── outputs/               # 生成的 PDF
├── prompts/
│   └── system.md              # Agent 系统提示词
├── requirements.txt
├── .env
└── .gitignore
```

---

## 3. 个人信息模型

### 3.1 固定模块（10 个，必须存在）

| 字段 | 来源 |
|------|------|
| name | 文件解析 → LLM 提取 |
| career_objective | **LLM 生成** |
| expected_salary | 文件解析 → LLM 提取 |
| location | 文件解析 → LLM 提取 |
| phone | 文件解析 → LLM 提取 |
| email | 文件解析 → LLM 提取 |
| education | 文件解析 → LLM 提取 |
| skills | 文件解析 → LLM 提取 |
| projects | 文件解析 → LLM 提取 |
| personal_strengths | **LLM 生成** |

### 3.2 可选模块（2 个，有则保留）

| 字段 | 来源 |
|------|------|
| internships | 文件解析 → LLM 提取 |
| certificates | 文件解析 → LLM 提取 |

### 3.3 规则

- 仅 career_objective 和 personal_strengths 可由 LLM 生成，其余字段提取不到标记 missing，不脑补
- 模块有严格边界，无多余模块
- 生成 PDF 前检查固定模块完整性

### 3.4 profile.json 结构

```json
{
  "meta": {
    "created_at": "...",
    "updated_at": "...",
    "source_files": ["resume.pdf", "certs.docx"]
  },
  "fields": {
    "name":       {"value": "张三", "type": "fixed", "status": "extracted"},
    "career_objective": {"value": "...", "type": "fixed", "status": "generated"},
    "expected_salary":  {"value": "20K-30K", "type": "fixed", "status": "extracted"},
    "location":   {"value": "深圳", "type": "fixed", "status": "extracted"},
    "phone":      {"value": "13800138000", "type": "fixed", "status": "extracted"},
    "email":      {"value": "z@example.com", "type": "fixed", "status": "extracted"},
    "education":  {"value": [{...}], "type": "fixed", "status": "extracted"},
    "skills":     {"value": [{...}], "type": "fixed", "status": "extracted"},
    "projects":   {"value": [{...}], "type": "fixed", "status": "extracted"},
    "personal_strengths": {"value": "...", "type": "fixed", "status": "generated"},
    "internships":{"value": [{...}], "type": "optional", "status": "extracted"},
    "certificates":{"value": [{...}], "type": "optional", "status": "extracted"}
  }
}
```

---

## 4. 文件解析流程

```
上传/预存文件
      │
      ▼
 TXT → 直接读取
 DOCX → python-docx 提取纯文本
 PDF → 统一走智谱 OCR API（逐页转图 → OCR，不区分电子/扫描版）
      │
      ▼
 完整文本保留（供 LLM 结构化提取）
      │
      ▼
 文本分 chunk（300-500字，重叠50字）
 → 智谱 Embedding-2 向量化
 → 存入 ChromaDB
      │
      ▼
 LLM 分析完整文本 → 逐字段提取 → 写入 profile.json
      │
      ▼
 校验完整性 → 缺失字段提示用户手动补充
```

### 4.1 多文件合并

- 多文件内容合并分析，信息互补
- 冲突字段以最新修改时间文件为准

---

## 5. MCP 工具清单

### 个人信息管理
| 工具 | 说明 |
|------|------|
| `profile_get` | 读取 profile.json，返回全部字段+状态 |
| `profile_update` | 手动更新指定字段 |
| `profile_check` | 校验固定模块完整性，返回缺失列表 |

### 简历处理
| 工具 | 说明 |
|------|------|
| `resume_parse` | 解析文件(TXT/DOCX/PDF)，PDF 走智谱 OCR |
| `resume_store` | 文本分块 → Embedding → ChromaDB |
| `resume_extract` | LLM 结构化提取个人信息 → 写 profile.json |
| `resume_search` | ChromaDB 向量检索，JD 关键词 → 最相关片段 |

### Boss 直聘
| 工具 | 说明 |
|------|------|
| `boss_search_list` | Selenium 搜索列表（关键词+城市） |
| `boss_job_detail` | Selenium 爬取单个岗位 JD |

### 生成
| 工具 | 说明 |
|------|------|
| `pdf_generate` | 按模板 + profile.json 拼装生成 PDF |
| `greeting_generate` | 生成 Boss 直聘风格招呼语 |

---

## 6. Agent Loop（ReAct 模式）

基于 DeepSeek 原生 tool_calls 机制：

```
用户消息 → 预处理(判断模式) → profile_check()
    │
    ▼
┌─ Tool-Calling Loop ──────────────────────────┐
│                                               │
│  while True (max 15):                         │
│    response = deepseek.chat(                  │
│      model="deepseek-chat",                   │
│      messages=[system.md + history],          │
│      tools=[MCP 工具列表]                      │
│    )                                          │
│                                               │
│    if tool_calls:                             │
│      执行 MCP 工具 → 结果 push 进 messages     │
│    else:                                      │
│      最终回复 → 渲染到聊天 UI                   │
│      break                                    │
└───────────────────────────────────────────────┘
```

### 关键规则
- 搜索岗位前必须先检索个人信息
- 用户未指定城市时，默认用 location + 临近城市群扩展
- 仅 career_objective 和 personal_strengths 由 LLM 生成，其余不许脑补

### 城市扩展规则

| 用户城市 | 扩展城市群 |
|---------|-----------|
| 深圳 | + 广州、东莞、珠海、惠州、佛山 |
| 北京 | + 天津、石家庄 |
| 上海 | + 杭州、苏州、南京、宁波 |
| 成都 | + 重庆、绵阳 |
| 武汉 | + 长沙、郑州 |
| 西安 | + 咸阳、宝鸡 |
| 其他 | + 同省省会 + 临近省省会 |

---

## 7. PDF 生成

### 模板结构（固定顺序）
1. 个人信息区（姓名、电话、邮箱、地点、求职意向、薪资）
2. 教育背景区
3. 专业技能区（按 JD 匹配度排序）
4. 项目经历区（STAR 法则，JD 相关内容加重）
5. 实习经历区（如有）
6. 证书荣誉区（如有）
7. 个人优势区

### 拼装逻辑
- **内容唯一源**：100% 来自 profile.json
- **RAG 角色**：选择器，非内容提供者。用 JD 检索 Chunk，目的是找到 profile.json 中哪些技能/项目最相关
- JD 相关内容加重详写，无关内容删减
- 一页为主，最多两页
- 禁止虚构

### 技术
- fpdf2 + NotoSansSC 字体
- 输出路径：`data/outputs/resume_{岗位简称}_{日期}.pdf`

---

## 8. 打招呼语

- Boss 直聘风格，100-200 字
- 结构：称呼 + 匹配点 + 表达兴趣 + 期待回复
- 至少一个 JD 直接相关的技能/项目亮点

---

## 9. Streamlit UI 布局

```
┌─ Sidebar ──────────────────────────────┐
│ 📁 简历管理                              │
│   ├── 上传文件（多文件拖拽）               │
│   ├── 已上传列表                         │
│   └── [重新解析]                         │
│                                         │
│ 👤 个人信息                              │
│   ├── 状态摘要（✅⚠️❌）                  │
│   ├── [查看/编辑]                        │
│   └── 缺失字段红色标注                    │
│                                         │
│ ⚙️ 设置                                 │
│   └── 服务状态指示灯                      │
├─────────────────────────────────────────┤
│ 💬 聊天区                                │
│   • 流式消息                             │
│   • 搜索结果表格（名称/公司/薪资/匹配度）   │
│   • PDF 下载 + 预览                      │
│   • 招呼语代码块 + 一键复制               │
│                                         │
│ ┌──────────────────────────────┐ [发送] │
│ │ 输入消息或粘贴 JD...           │        │
│ └──────────────────────────────┘        │
└─────────────────────────────────────────┘
```

### 状态机

```
打开应用
  ├── 无 profile.json → 引导上传简历
  │     └── 解析 → 提取 → 审阅补充 → 聊天就绪
  └── profile.json 已就绪 → 直接进入聊天

聊天中
  ├── 个人信息不完整 → 输入框禁用，提示补充
  └── 个人信息完整 → 正常使用
```

---

## 10. 错误处理

| 场景 | 处理 |
|------|------|
| DeepSeek API 不可用 | 提示重试，保留已发送消息 |
| MCP Server 断连 | 提示 + 重连按钮 |
| ChromaDB 空库 | 引导上传简历 |
| Selenium 反爬/验证码 | 引导手动操作浏览器 |
| Selenium 页面结构变化 | 建议手动输入 JD |
| OCR API 超时 | 标记失败页，汇总告知 |
| 多文件冲突 | 以最新文件为准 |
| profile.json 损坏 | 提示重新上传解析 |

### 工具超时

| 工具 | 超时 |
|------|------|
| resume_parse (含OCR) | 60s |
| resume_search | 5s |
| boss_search_list | 30s/页 |
| boss_job_detail | 20s |
| pdf_generate | 15s |
| greeting_generate | 10s |

---

## 11. 依赖

```
streamlit>=1.50.0
openai>=2.0.0
python-dotenv>=1.0.0
python-docx>=1.1.0
zhipuai>=2.0.0
chromadb>=0.5.0
fpdf2>=2.7.0
selenium>=4.20.0
beautifulsoup4>=4.12.0
mcp>=1.0.0
```

### 外部服务

| 服务 | 用途 | API |
|------|------|-----|
| DeepSeek | LLM 对话 + Tool Calling | OpenAI 兼容协议 |
| 智谱 Embedding-2 | 文本向量化 | 智谱 SDK |
| 智谱 OCR | PDF 图片文字识别 | 智谱 SDK |

---

## 12. 启动步骤

```bash
# 1. 虚拟环境
python -m venv .venv
source .venv/Scripts/activate

# 2. 依赖
pip install -r requirements.txt

# 3. 配置 .env（DeepSeek + 智谱 API Keys）

# 4. 准备简历文件 → data/resume_files/（或启动后上传）

# 5. 终端1：启动 MCP Server
python -m mcp_server.server

# 6. 终端2：启动 Streamlit
streamlit run app.py
```

---

## 13. 自审

- 无 TBD / TODO 占位符
- 架构与功能描述一致：Streamlit + MCP Server 分离
- 个人信息模型边界明确：10 固定 + 2 可选，不脑补
- PDF 统一走 OCR，无 PyPDF2/pdfplumber 依赖
- RAG 角色明确：选择器非内容源
- 范围可控：单次实现，无子项目拆分需求
- 所有 API Key 通过 .env 注入，不硬编码
