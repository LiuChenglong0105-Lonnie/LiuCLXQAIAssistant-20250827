# 声明

本项目仅供本人求职展示使用，请勿用于商业用途或违反XQ网用户协议的行为。

Streamlit链接：https://liucl-xq-ai-assistant-20250827-jlnucaddghksg499yi5cer.streamlit.app/

# XQ智能爬虫与AI研究助手

该项目是本人独立开发的一款基于XQ网的跟踪、阅读、研究的辅助工具，支持从XQ网爬取用户文章、股票评论，并通过 AI 能力进行文章摘要生成、内容质量评分、优质用户筛选、信息检索等功能，帮助用户快速筛选有价值的投资人和参考信息。

## 我为什么要做这个应用？

XQ是我个人投资体系的根基，我需要大量使用XQ。然而在使用XQ的过程中，我有一些个性化需求是无法得到满足的：
1. 由于工作日繁忙无法全面跟踪大佬的动态，我需要每周集中翻阅回顾。但是在关注tab页我要是想回刷上周的帖子需要无限下拉，且一旦退出页面或者程序进程被清理，我需要再回刷到上次阅读位置。这给我带来了非常痛苦且恶心的使用体验！因此我需要一个定期爬虫+优化展示+阅读友好的工具解决我的痛点。
2. 我不仅需要对大佬日常跟踪，还需要不断积攒大佬的历史发言，方便自己做专题研究。由于大佬历史发言众多，而XQ仅支持关键词搜索，所以我需要再开发一个智能搜索功能。另外，XQ的大佬语料极其有投研价值，非常适合做RAG知识库，我需要不断积累，以待未来建立更完善的个人智能投研工具。
3. 我有时候对一个股票感兴趣，需要查看某个股票下方的热帖，以及找到对该股票研究非常深入的用户。但是热帖数量众多且质量鱼龙混杂，给我的阅读识别工作带来非常大困扰，我需要AI帮我提效，找出高质量帖子和高质量用户。
4. XQ的股票下方评论是智能显示100页，无法对历史所有评论进行回溯的，因此对于热门股票，我需要定期爬取做历史存档，形成针对个股的评论合集，搭配AI实现具体话题的智能搜索。

如果能实现上述几个功能，我个人的研究侧需求的闭环就能更高效地实现了：
1. 对某个股票感兴趣，找到相关的高质量内容与用户，实现对个股的研究和大佬用户的发掘。
2. 后续对大佬用户进行跟踪，了解其所有的股票研究动态，学习投资理念，发掘新股票，发掘新大佬。
3. 如此下来，该研究助手的功能就可以实现联动互助，让我的研究基础系统持续流动起来。

## 项目功能

| 核心模块                | 功能描述                                                                 |
|-------------------------|--------------------------------------------------------------------------|
| 关注用户近期跟踪        | 爬取选定日期之后的XQ用户的近期发文，自动去重与存档，支持AI生成摘要辅助阅读    |
| 关注跟踪历史存档        | 查看历史爬取的用户文章，支持关键词搜索与AI智能搜索    |
| 股票评论现时抓取        | 实时爬取指定股票的XQ评论，自动去重存档，支持AI评分，筛选高质量内容与用户       |
| 股评抓取历史存档        | 查看历史评论数据，支持AI智能搜索，以及AI筛选高质量内容与用户 |

## 应用功能与开发流程图

### 整体应用运行总流程
<img width="2379" height="1128" alt="d3e78ea1fb94ea06bd3ade57bfe008f" src="https://github.com/user-attachments/assets/8ea254e4-058a-4d85-8066-2f9d26f6ed92" />

### 关注用户近期跟踪
<img width="2539" height="1078" alt="5f3e9e85960118c21faf6f209a1f015" src="https://github.com/user-attachments/assets/aaafa4e7-fb8c-4f33-ba1f-9a29bea45e31" />

### 关注跟踪历史存档
<img width="1681" height="1735" alt="65ebed766c181c146d4a70878ddb94d" src="https://github.com/user-attachments/assets/d22135ad-6fac-48dc-b5b4-6ed6daaf032c" />

### 股票评论现时抓取
<img width="3172" height="1206" alt="deabcf63946d1bfca36bb9021f9c700" src="https://github.com/user-attachments/assets/fa3e6aee-7949-4306-98eb-152c628adba8" />

### 股评抓取历史存档
<img width="1396" height="1483" alt="c44e1b17d83aa61de1775e257a0d837" src="https://github.com/user-attachments/assets/a444da10-ddcd-4299-86ff-79dbd99f7522" />

### 通用支撑模块流程
<img width="2115" height="769" alt="323884f7226558485ac71562b4880cc" src="https://github.com/user-attachments/assets/7bd16cab-d049-44f3-81d8-444d7f4b7343" />


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


## 安装部署指南

### 1. 环境准备

#### 1.1 基础依赖
- **Python 3.8+**（推荐3.10版本，兼容性最佳）
- **Chrome浏览器**（爬虫依赖ChromeDriver，需与浏览器版本匹配）
- **Git**（用于克隆仓库，可选）


#### 1.2 克隆仓库
```bash
# 克隆项目到本地
git clone https://github.com/yourusername/rsapp.git
cd rsapp  # 进入项目根目录
```

若未安装Git，可直接从GitHub下载ZIP压缩包并解压。


### 2. 配置虚拟环境（推荐）

#### 2.1 创建虚拟环境
```bash
# 创建虚拟环境（Windows/macOS/Linux通用）
python -m venv .venv
```

#### 2.2 激活虚拟环境
- **Windows（PowerShell）**：
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Windows（CMD）**：
  ```cmd
  .venv\Scripts\activate.bat
  ```
- **macOS/Linux**：
  ```bash
  source .venv/bin/activate
  ```

激活后终端前缀会显示 `(.venv)`，表示虚拟环境已生效。


### 3. 安装项目依赖

通过 `requirements.txt` 一键安装所有依赖：
```bash
pip install -r requirements.txt
```

#### 依赖说明（关键包）
- `streamlit==1.48.1`：Web应用框架
- `selenium==4.35.0`：网页爬取核心库
- `beautifulsoup4==4.13.5`：HTML解析库
- `openai==1.101.0`：AI接口（评论评分/摘要生成）
- `dashscope==1.24.2`：阿里云通义千问API适配
- `scikit-learn==1.7.1`：文本相似度计算（余弦相似度）


### 4. 核心配置（必做）

#### 4.1 配置XQCookie（`cookie.txt`）
爬虫需要登录态才能爬取完整内容，需手动获取XQCookie并填入 `cookie.txt`：
1. 打开Chrome浏览器，访问 [XQ网](https://xueqiu.com) 并登录账号
2. 按 `F12` 打开「开发者工具」→ 切换到「Application」标签
3. 在左侧「Storage」→「Cookies」→「https://xueqiu.com」中，复制所有Cookie的 `Name=Value` 对
4. 将复制的内容粘贴到项目根目录的 `cookie.txt` 中，格式示例：
   ```
   cookiesu=831756047811132;
   Hm_lpvt_1db88642e346389874251b5a1eded6e3=1756114684;
   xq_a_token=f3bac259ef51ec4acc3e6a4fa34209a442df9e20;
   ```


#### 4.2 配置ChromeDriver（自动适配）
项目已集成 `webdriver-manager`，无需手动下载ChromeDriver，运行时会自动匹配本地Chrome版本并安装。

若出现「ChromeDriver版本不匹配」错误，需手动更新Chrome浏览器到最新版本。


#### 4.3 配置待爬取用户（可选）
若需爬取指定XQ用户的文章，可修改 `user_urls.txt`，每行填入一个用户主页URL，示例：
```
https://xueqiu.com/u/9430706524
https://xueqiu.com/u/7305934056
https://xueqiu.com/u/8414744881
```


#### 4.4 配置AI API密钥（可选）
若需使用AI评分、摘要生成功能，需配置通义千问API密钥：
1. 前往 [阿里云通义千问控制台](https://dashscope.aliyun.com/) 获取API密钥（`QWEN_API_KEY`）
2. 设置环境变量（临时生效）：
   - **Windows（PowerShell）**：
     ```powershell
     $env:QWEN_API_KEY="sk-你的API密钥"
     ```
   - **macOS/Linux**：
     ```bash
     export QWEN_API_KEY="sk-你的API密钥"
     ```
3. （可选）若需多密钥负载均衡，可将多个密钥用英文逗号分隔：
   ```bash
   export QWEN_API_KEY="sk-key1,sk-key2,sk-key3"
   ```


### 5. 本地运行应用

完成上述配置后，执行以下命令启动Streamlit应用：
```bash
streamlit run streamlit_app.py
```

启动成功后，终端会显示本地访问地址（通常是 `http://localhost:8501`），打开浏览器访问即可使用。


### 6. 部署到Streamlit Cloud（在线访问）

#### 6.1 准备工作
1. 将项目代码推送到GitHub仓库（确保包含所有必要文件，`cookie.txt` 可忽略，部署后在Cloud中重新配置）
2. 注册/登录 [Streamlit Cloud](https://streamlit.io/cloud)


#### 6.2 部署步骤
1. 在Streamlit Cloud控制台点击「New app」
2. 填写仓库信息：
   - **Repository**：选择你的GitHub仓库（如 `yourusername/rsapp`）
   - **Branch**：选择主分支（通常是 `main` 或 `master`）
   - **Main file path**：填写 `streamlit_app.py`
3. （可选）配置环境变量：
   - 点击「Advanced settings」→「Secrets」
   - 添加 `QWEN_API_KEY`：值为你的通义千问API密钥
4. 点击「Deploy!」，等待部署完成（约1-3分钟）


## 使用说明

### 1. 核心功能入口
应用启动后，通过左侧边栏选择功能：
- **关注用户近期跟踪**：爬取并查看指定用户的近期发文
- **关注跟踪历史存档**：查看历史爬取的用户文章，支持AI摘要
- **股票评论现时抓取**：输入股票代码（如A股600036、港股00700、美股BABA），抓取评论
- **股评抓取历史存档**：查看历史评论，支持AI评分与优质评论筛选


### 2. 注意事项
- **反爬风险**：爬虫内置随机暂停（每爬10页休息30-120秒），请勿频繁爬取或修改暂停参数，避免触发XQ风控
- **Cookie有效期**：XQCookie有效期约7-14天，若出现「登录失效」提示，需重新更新 `cookie.txt`
- **AI功能限制**：API密钥有调用额度限制，批量分析时建议控制单次处理数量（如评论≤100条/次）


## 常见问题

### Q1：爬虫启动后提示「ChromeDriver不存在」？
A1：确保Chrome浏览器已安装并更新到最新版本，`webdriver-manager` 会自动下载匹配的ChromeDriver，无需手动配置。

### Q2：AI功能提示「API密钥无效」？
A2：检查 `QWEN_API_KEY` 环境变量是否正确设置，或前往阿里云控制台确认密钥是否有效（未过期、有剩余额度）。

### Q3：爬取评论时提示「触发风控」？
A3：暂停爬取10-15分钟后重试，或更换IP（如使用代理），避免短时间内高频访问。

### Q4：Streamlit应用启动后页面空白？
A4：检查Python版本是否≥3.8，依赖是否完整安装（可重新执行 `pip install -r requirements.txt`），或清除浏览器缓存后重试。

