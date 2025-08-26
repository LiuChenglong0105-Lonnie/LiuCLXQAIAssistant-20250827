import openai
import json
import re
import os
import numpy as np
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
import tqdm  # 用于显示进度条
import openai  # 添加缺失的openai导入

# 从环境变量获取API密钥和基础URL，与recent_track_llm.py保持一致
import logging
logger = logging.getLogger(__name__)

# 导入并调用环境变量加载函数
from utils import load_environment_variables
load_environment_variables()

# 处理多个API密钥的情况
api_key_str = os.getenv("QWEN_API_KEY", "")
api_keys = [key.strip() for key in api_key_str.split(",")] if api_key_str else []

if not api_keys:
    logger.warning("未找到环境变量QWEN_API_KEY，请在.env文件中配置API密钥。")
    logger.warning("请参考.env.example文件创建.env文件并添加您的API密钥。")
    logger.warning("在未配置API密钥的情况下，部分功能可能无法正常使用。")
    api_key = ""
else:
    # 选择第一个有效的API密钥使用
    api_key = api_keys[0]
    logger.info(f"使用API密钥: {api_key[:6]}...{api_key[-4:]}")

# 初始化OpenAI客户端
client = openai.OpenAI(
    api_key=api_key,
    base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)

# 配置嵌入模型
EMBEDDING_MODEL = "text-embedding-v4"

class HistoryTrackLLM:
    def __init__(self, history_dir="history_track"):
        self.history_dir = history_dir
        self.embeddings_cache = {}
        self.cache_file = "embeddings_cache.json"
        # 加载缓存
        self._load_cache()

    def _load_cache(self):
        """加载嵌入缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.embeddings_cache = json.load(f)
            except Exception as e:
                logger.error(f"加载缓存失败: {e}")

    def _save_cache(self):
        """保存嵌入缓存，创建字典副本以避免并发修改问题"""
        try:
            # 创建字典副本，避免并发修改问题
            cache_copy = dict(self.embeddings_cache)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_copy, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def _preprocess_text(self, text):
        """预处理文本：去除冗余符号，标准化格式"""
        if not text:
            return ""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 去除特殊符号
        text = re.sub(r'[\r\n]+', ' ', text)
        return text

    def _get_embedding(self, text):
        """获取文本嵌入向量"""
        # 检查缓存
        if text in self.embeddings_cache:
            cached_embedding = np.array(self.embeddings_cache[text])
            # 确保缓存的嵌入向量形状一致
            if cached_embedding.shape == (1536,):
                return cached_embedding
            else:
                # 如果缓存的形状不正确，重新计算
                logger.warning(f"缓存的嵌入向量形状不正确: {cached_embedding.shape}，重新计算")

        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            embedding = response.data[0].embedding
            # 确保嵌入向量形状正确
            embedding_array = np.array(embedding)
            if embedding_array.shape != (1536,):
                logger.warning(f"获取的嵌入向量形状不正确: {embedding_array.shape}，调整为标准形状")
                # 调整形状或创建零向量
                if len(embedding_array) > 1536:
                    embedding_array = embedding_array[:1536]  # 截断过长的向量
                else:
                    # 填充零到标准长度
                    padded_embedding = np.zeros(1536)
                    padded_embedding[:len(embedding_array)] = embedding_array
                    embedding_array = padded_embedding
            # 存入缓存
            self.embeddings_cache[text] = embedding_array.tolist()
            self._save_cache()
            return embedding_array
        except Exception as e:
            # 更详细的错误信息
            if '401' in str(e) or 'Incorrect API key' in str(e):
                logger.error(f"API密钥无效，请检查.env文件中的QWEN_API_KEY配置: {e}")
            else:
                logger.error(f"获取嵌入失败: {e}")
            return np.zeros(1536)  # 返回零向量作为默认值

    def load_user_articles(self, user_name):
        """加载指定用户的文章"""
        user_file = os.path.join(self.history_dir, f"{user_name}_all.json")
        if not os.path.exists(user_file):
            return []

        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                articles = json.load(f)

            # 预处理文章
            for article in articles:
                # 提取时间（如果有）
                if 'publish_time' in article:
                    try:
                        # 假设时间格式为字符串，尝试解析
                        article['publish_timestamp'] = datetime.strptime(
                            article['publish_time'], '%Y-%m-%d %H:%M:%S').timestamp()
                    except:
                        article['publish_timestamp'] = 0
                else:
                    article['publish_timestamp'] = 0

                # 预处理内容
                article['content_clean'] = self._preprocess_text(article.get('content', ''))
                article['title_clean'] = self._preprocess_text(article.get('title', ''))
                # 合并标题和内容以获得更全面的嵌入
                article['combined_text'] = f"{article['title_clean']} {article['content_clean']}"

            return articles
        except Exception as e:
            print(f"加载用户文章失败: {e}")
            return []

    def calculate_quality_score(self, article):
        """计算文章质量分数，结合基础分数和LLM深度评分"""
        # 基础分数
        score = 0

        try:
            # 内容长度分数（越长越可能有深度）
            content_clean = article.get('content_clean', '')
            # 确保content_clean是字符串
            if not isinstance(content_clean, str):
                content_clean = str(content_clean)
            
            content_length = len(content_clean)
            score += min(content_length / 1000, 2)  # 最多2分

            # 是否包含具体信息（如数字、专业术语）
            has_numbers = bool(re.search(r'\d+', content_clean))
            has_terms = bool(re.search(r'[A-Za-z]{3,}|[\u4e00-\u9fa5]{3,}', content_clean))
            score += (1 if has_numbers else 0) + (1 if has_terms else 0)

            # 使用LLM进行深度评分
            try:
                prompt = (
                    "你是一个资深股票分析师，请根据以下文章的质量进行评分（1-5分）。\n"
                    "评分标准：\n"
                    "1. 研究深度：是否有深入的行业或公司分析\n"
                    "2. 信息质量：是否包含有价值的信息或数据\n"
                    "3. 逻辑清晰度：分析是否有条理、逻辑清晰\n"
                    "4. 客观性：是否客观公正，避免主观臆断\n"
                    "5. 投资参考价值：对投资决策是否有参考意义\n"
                    "请只返回一个数字分数，不要解释或添加其他内容。\n\n"
                    f"文章内容：{content_clean[:3000]}"
                )
                messages = [{"role": "user", "content": prompt}]
                response = client.chat.completions.create(
                    model="qwen-plus",
                    messages=messages,
                    temperature=0.1
                )
                llm_response = response.choices[0].message.content.strip()
                # 使用正则表达式提取数字
                match = re.search(r'\d+\.?\d*', llm_response)
                if match:
                    llm_score = float(match.group())
                    # 将LLM评分标准化到1-5分
                    llm_score = max(1, min(5, llm_score))
                    # 综合基础分数和LLM分数（基础分数最高4分，转换为0-5分范围）
                    normalized_base_score = min(score / 4 * 5, 5)
                    combined_score = (normalized_base_score / 5) * 0.4 + (llm_score / 5) * 0.6
                    return combined_score * 5  # 转换回0-5分
                else:
                    print(f"LLM评分格式错误: {llm_response}")
                    return min(5, score)
            except Exception as e:
                print(f"LLM评分失败: {e}")
                # 如果LLM调用失败，仅返回基础分数
                return min(5, score)
        except Exception as e:
            print(f"计算质量分数时出错: {e}")
            # 如果出现任何错误，返回最低分数
            return 1.0
        
        return score

    def search_articles(self, user_names, keywords, top_k=50):
        """搜索并排序文章：先筛选高相关性帖子，再进行质量分析"""
        try:
            all_articles = []

            # 加载所有选定用户的文章
            for user_name in user_names:
                articles = self.load_user_articles(user_name)
                for article in articles:
                    article['user_name'] = user_name
                    all_articles.append(article)

            if not all_articles:
                return []

            # 获取关键词嵌入
            keyword_embedding = self._get_embedding(self._preprocess_text(keywords))

            # 计算所有文章的嵌入和相似度，确保嵌入向量形状一致
            article_embeddings = []
            valid_articles = []  # 保存有效的文章，与article_embeddings保持同步
            for article in tqdm.tqdm(all_articles, desc="计算嵌入"):
                try:
                    embedding = self._get_embedding(article['combined_text'])
                    # 验证嵌入向量的形状
                    if embedding.shape == (1536,):
                        article_embeddings.append(embedding)
                        valid_articles.append(article)
                    else:
                        logger.warning(f"嵌入向量形状不一致，跳过此文章: {embedding.shape}")
                except Exception as e:
                    logger.error(f"处理文章嵌入时出错: {e}")
                    continue

            if not article_embeddings:
                logger.warning("没有有效的嵌入向量，无法进行相似度计算")
                return []

            # 转换为numpy数组并确保形状一致
            try:
                article_embeddings_array = np.vstack(article_embeddings)
            except ValueError as e:
                logger.error(f"合并嵌入向量时出错: {e}")
                # 尝试修复形状不一致的问题
                fixed_embeddings = []
                for emb in article_embeddings:
                    if emb.shape != (1536,):
                        # 创建标准形状的零向量
                        fixed_emb = np.zeros(1536)
                        # 尽可能填充有效数据
                        valid_length = min(len(emb), 1536)
                        fixed_emb[:valid_length] = emb[:valid_length]
                        fixed_embeddings.append(fixed_emb)
                    else:
                        fixed_embeddings.append(emb)
                article_embeddings_array = np.vstack(fixed_embeddings)

            # 计算相似度
            similarities = cosine_similarity([keyword_embedding], article_embeddings_array)[0]
            
            # 更新all_articles为有效的文章列表
            all_articles = valid_articles

            # 按相似度排序，先筛选出相关性高于0.4的帖子
            sorted_indices = np.argsort(similarities)[::-1]
            relevant_indices = [idx for idx in sorted_indices if similarities[idx] > 0.4]

            # 如果没有帖子满足0.35阈值，则返回空列表
            if not relevant_indices:
                return []

            # 再从相关帖子中选取前20%（至少1篇）
            top_30_percent_count = max(1, int(len(relevant_indices) * 0.3))
            top_indices = relevant_indices[:top_30_percent_count]

            # 对筛选后的帖子计算质量分数并综合排序
            results = []
            for idx in tqdm.tqdm(top_indices, desc="计算质量分数"):
                try:
                    article = all_articles[idx]
                    quality_score = self.calculate_quality_score(article)
                    # 确保分数是浮点数
                    if not isinstance(quality_score, (int, float)):
                        quality_score = 0.0
                    # 综合相似度和质量分数，权重可以调整
                    combined_score = similarities[idx] * 0.5 + float(quality_score) * 0.5
                    results.append({
                        'article': article,
                        'similarity_score': float(similarities[idx]),  # 确保是浮点数
                        'quality_score': float(quality_score),          # 确保是浮点数
                        'combined_score': float(combined_score)         # 确保是浮点数
                    })
                except Exception as e:
                    print(f"处理文章时出错: {e}")
                    continue

            # 按综合分数排序
            try:
                results.sort(key=lambda x: x['combined_score'], reverse=True)
            except Exception as e:
                print(f"排序结果时出错: {e}")
                # 如果排序失败，使用原始顺序

            # 返回前top_k个结果
            return results[:top_k]
        except Exception as e:
            print(f"搜索文章时出错: {e}")
            return []

    def generate_summary(self, article):
        """为文章生成摘要"""
        content = article.get('content_clean', '')
        if not content:
            return "无内容"

        # 根据内容长度决定摘要格式
        content_length = len(content)
        is_long_content = content_length > 200

        # 构建符合用户要求的prompt
        prompt = (
            "摘要要求：\n"
            "1. 只对帖子的主要内容进行客观概括，不包含任何评价、判断、推荐或否定性内容；\n"
            "2. 短内容用简短词句概括，长内容分点列出核心观点（原文两百字以上视为长文）。摘要字数不得少于正文的10%；\n"
            "3. 即使内容不具备投资价值，也要准确说明主要内容，不做主观评价；\n"
            "4. 覆盖原文主要信息点，避免遗漏重要内容。\n\n"
            f"{'长文，需分点列出核心观点：' if is_long_content else '短文，用简短词句概括：'}\n{content[:3000]}"
        )
        messages = [{'role': 'user', 'content': prompt}]

        try:
            response = client.chat.completions.create(
                model="qwen-plus-latest",
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"生成摘要失败: {e}")
            return "生成摘要失败"

    def load_raw_articles(self, user_names, keywords):
        """加载原始文章，不进行AI分析"""
        all_articles = []

        # 加载所有选定用户的文章
        for user_name in user_names:
            articles = self.load_user_articles(user_name)
            for article in articles:
                article['user_name'] = user_name
                # 简单关键词匹配
                if keywords.lower() in article['title_clean'].lower() or keywords.lower() in article['content_clean'].lower():
                    all_articles.append({
                        'article': article
                    })

        return all_articles

    def analyze_and_rank_articles(self, articles, keywords):
        """对文章进行AI分析和排序"""
        try:
            if not articles:
                return []

            # 获取关键词嵌入
            keyword_embedding = self._get_embedding(self._preprocess_text(keywords))

            # 计算所有文章的嵌入和相似度，确保嵌入向量形状一致
            article_embeddings = []
            valid_articles = []  # 保存有效的文章，与article_embeddings保持同步
            for article in tqdm.tqdm(articles, desc="计算嵌入"):
                try:
                    embedding = self._get_embedding(article['combined_text'])
                    # 验证嵌入向量的形状
                    if embedding.shape == (1536,):
                        article_embeddings.append(embedding)
                        valid_articles.append(article)
                    else:
                        logger.warning(f"嵌入向量形状不一致，跳过此文章: {embedding.shape}")
                except Exception as e:
                    logger.error(f"计算文章嵌入时出错: {e}")
                    # 添加零向量作为替代
                    article_embeddings.append(np.zeros(1536))
                    valid_articles.append(article)

            if not article_embeddings:
                logger.warning("没有有效的嵌入向量，无法进行相似度计算")
                return []

            # 转换为numpy数组并确保形状一致
            try:
                article_embeddings_array = np.vstack(article_embeddings)
            except ValueError as e:
                logger.error(f"合并嵌入向量时出错: {e}")
                # 尝试修复形状不一致的问题
                fixed_embeddings = []
                for emb in article_embeddings:
                    if emb.shape != (1536,):
                        # 创建标准形状的零向量
                        fixed_emb = np.zeros(1536)
                        # 尽可能填充有效数据
                        valid_length = min(len(emb), 1536)
                        fixed_emb[:valid_length] = emb[:valid_length]
                        fixed_embeddings.append(fixed_emb)
                    else:
                        fixed_embeddings.append(emb)
                article_embeddings_array = np.vstack(fixed_embeddings)

            # 计算相似度
            similarities = cosine_similarity([keyword_embedding], article_embeddings_array)[0]
            
            # 更新articles为有效的文章列表
            articles = valid_articles

            # 计算质量分数并综合排序
            results = []
            for i, article in enumerate(articles):
                try:
                    quality_score = self.calculate_quality_score(article)
                    # 确保分数是浮点数
                    if not isinstance(quality_score, (int, float)):
                        quality_score = 0.0
                    # 综合相似度和质量分数
                    combined_score = similarities[i] * 0.5 + float(quality_score) * 0.5
                    results.append({
                        'article': article,
                        'similarity_score': float(similarities[i]),  # 确保是浮点数
                        'quality_score': float(quality_score),          # 确保是浮点数
                        'combined_score': float(combined_score)         # 确保是浮点数
                    })
                except Exception as e:
                    print(f"处理文章时出错: {e}")
                    continue

            # 按综合分数排序
            try:
                results.sort(key=lambda x: x['combined_score'], reverse=True)
            except Exception as e:
                print(f"排序结果时出错: {e}")
                # 如果排序失败，使用原始顺序

            return results
        except Exception as e:
            print(f"分析和排序文章时出错: {e}")
            return []

# 示例用法
if __name__ == "__main__":
    # 创建实例
    history_llm = HistoryTrackLLM()

    # 测试搜索
    user_names = ["STH", "modest", "韭菲特漂流记"]
    keywords = "心动公司"
    results = history_llm.search_articles(user_names, keywords)

    # 打印结果
    print(f"找到 {len(results)} 条相关结果")
    for i, result in enumerate(results[:5]):
        article = result['article']
        print(f"\n结果 {i+1} (综合得分: {result['combined_score']:.2f}):")
        print(f"用户: {article['user_name']}")
        print(f"标题: {article['title']}")
        print(f"相似度: {result['similarity_score']:.2f}")
        print(f"质量分: {result['quality_score']:.2f}")
        # 生成并打印摘要
        summary = history_llm.generate_summary(article)
        print(f"摘要: {summary}")