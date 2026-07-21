# AI简历定制助手

上传简历 → 粘贴 JD → 一键生成专业 HTML 简历 + 招呼语。

JD 分析 + STAR 法重写 + 专业商务风 HTML 简历，一次性生成。HTML 模板源自 [resume-optimizer](https://github.com/Liliane0310/Resume-Optimizer)。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 .env
cp .env.example .env
# 编辑 .env 填入 DeepSeek + 智谱 API Key

# 启动
streamlit run app.py
```

## 使用流程

1. **上传简历** — 侧栏拖拽上传 PDF/Word/TXT（PDF 自动走 OCR）
2. **审核个人信息** — AI 自动提取，缺失项手动补充
3. **粘贴 JD** — 粘贴目标岗位的职位描述
4. **生成** — 自动 JD 分析 + STAR 重写 + 输出 HTML 简历（浏览器 Ctrl+P 打印 PDF）

## 技术栈

- **Streamlit** — 前端界面
- **DeepSeek** — LLM（个人信息提取 + STAR 重写 + 招呼语）
- **智谱** — PDF OCR + 向量化
- **resume-optimizer** — HTML 简历模板与渲染

## License

MIT
