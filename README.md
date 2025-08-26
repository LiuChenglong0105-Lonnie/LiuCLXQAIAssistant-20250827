# 雪球智能研究助手

这是一个基于Streamlit和AI技术的雪球智能研究助手，能够帮助投资者更高效地分析雪球平台上的用户跟踪和股票评论信息。

## 功能特性

- **关注用户近期跟踪**：实时获取和分析关注用户的最新动态
- **关注跟踪历史存档**：查看和搜索历史跟踪记录
- **股票评论现时抓取**：实时抓取指定股票的评论信息
- **股评抓取历史存档**：查看和搜索历史股评信息
- **AI智能分析**：利用AI技术对内容进行摘要、评分和相关性分析

## 技术栈

- Python 3.10+
- Streamlit - 用于构建Web界面
- OpenAI API (Qwen API) - 用于AI分析和嵌入计算
- Selenium - 用于网页爬虫
- NumPy, pandas - 用于数据处理
- scikit-learn - 用于向量相似度计算

## 安装部署

### 本地开发环境

1. 克隆仓库

```bash
# 克隆仓库（假设你已经在GitHub上创建了仓库）
git clone https://github.com/your-username/rsapp.git
cd rsapp
```

2. 创建虚拟环境并安装依赖

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

3. 配置环境变量

复制`.env.example`文件并重命名为`.env`，然后填入你的API密钥：

```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

编辑`.env`文件，添加你的Qwen API密钥：

```
QWEN_API_KEY="your_api_key_1,your_api_key_2"
QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

4. 运行应用

```bash
streamlit run streamlit_app.py
```

### 部署到Streamlit Cloud

1. 在GitHub上创建仓库并上传代码

确保你的仓库包含以下文件：
- streamlit_app.py (主应用文件)
- requirements.txt (依赖列表)
- .gitignore (忽略规则)
- .env.example (环境变量示例)
- 其他所有必要的代码文件

2. 登录Streamlit Cloud

访问 [Streamlit Cloud](https://share.streamlit.io/) 并使用GitHub账号登录。

3. 创建新应用

- 点击 "New app" 按钮
- 选择你的仓库、分支和主文件 (streamlit_app.py)
- 点击 "Advanced settings"，在 "Secrets" 部分添加你的环境变量：
  ```
  QWEN_API_KEY="your_api_key_1,your_api_key_2"
  QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
  ```
- 点击 "Deploy!"

4. 等待部署完成

Streamlit Cloud会自动构建和部署你的应用。部署完成后，你将获得一个公开的URL，可以访问你的应用。

## 项目结构

```
├── .env.example           # 环境变量配置示例
├── .gitignore            # Git忽略规则
├── requirements.txt      # 项目依赖
├── streamlit_app.py      # 主应用程序
├── pages/                # 各功能页面
│   ├── history_comment.py  # 历史评论页面
│   ├── history_track.py    # 历史跟踪页面
│   ├── recent_comment.py   # 近期评论页面
│   └── recent_track.py     # 近期跟踪页面
├── history_comment_llm.py  # 评论AI分析模块
├── history_track_llm.py    # 跟踪AI分析模块
├── recent_track_llm.py     # 近期跟踪AI分析模块
├── utils.py              # 工具函数
├── comment_spider.py     # 评论爬虫
├── track_spider.py       # 跟踪爬虫
├── history_comments/     # 历史评论数据目录
└── history_track/        # 历史跟踪数据目录
```

## 注意事项

1. 本项目需要使用Qwen API进行AI分析，确保你已配置有效的API密钥。
2. 爬虫功能可能会受到雪球平台的限制，请合理使用。
3. 在部署到Streamlit Cloud时，请妥善保管你的API密钥，不要将其提交到代码仓库中。
4. 首次运行时，可能需要等待一段时间来生成嵌入向量和缓存数据。

## 许可证

[MIT License](LICENSE)