import json
import re
import numpy as np
import time
import random
import logging
import openai
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.metrics.pairwise import cosine_similarity
import tqdm
from queue import Queue, Empty
import score_stock_comments

# 配置日志
logger = logging.getLogger(__name__)

# 配置嵌入模型
EMBEDDING_MODEL = "text-embedding-v4"

# 默认嵌入向量维度，与history_track_llm.py保持一致
DEFAULT_EMBEDDING_DIM = 1536

class CommentLLMSearch:
    """
    评论AI智能搜索类
    使用与history_track_llm类似的实现方式
    添加多API并行支持
    """
    def __init__(self, custom_api_keys=None):
        self.embeddings_cache = {}
        self.cache_file = "comment_embeddings_cache.json"
        
        # 初始化API密钥
        env_api_key = os.getenv('QWEN_API_KEY')
        
        if custom_api_keys and isinstance(custom_api_keys, list):
            self.api_keys = [key.strip() for key in custom_api_keys if key.strip()]
            logger.info(f"使用自定义API密钥，共{len(self.api_keys)}个")
        elif env_api_key:
            self.api_keys = [key.strip() for key in env_api_key.split(',') if key.strip()]
            logger.info(f"使用环境变量中的{len(self.api_keys)}个API密钥")
        else:
            # 不使用默认API密钥，而是提示用户配置环境变量
            self.api_keys = []
            logger.warning("未找到环境变量QWEN_API_KEY，请在.env文件中配置API密钥。")
            logger.warning("请参考.env.example文件创建.env文件并添加您的API密钥。")
            logger.warning("在未配置API密钥的情况下，部分功能可能无法正常使用。")
        
        self.max_retries = 3
        self.retry_delay = 2
        self.base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # 加载缓存
        self._load_cache()

    def _load_cache(self):
        """加载嵌入缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.embeddings_cache = json.load(f)
            except Exception as e:
                logger.debug(f"加载缓存失败: {e}")

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

    def _create_openai_client(self, api_key):
        """创建OpenAI客户端"""
        return openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url
        )
    
    def _get_embedding_single(self, text, api_key):
        """使用指定API密钥获取单个文本嵌入向量"""
        # 检查缓存
        if text in self.embeddings_cache:
            cached_embedding = np.array(self.embeddings_cache[text])
            # 确保缓存的嵌入向量形状一致
            if cached_embedding.shape == (DEFAULT_EMBEDDING_DIM,):
                return cached_embedding, True
            else:
                # 如果缓存的形状不正确，重新计算
                logger.warning(f"缓存的嵌入向量形状不正确: {cached_embedding.shape}，重新计算")

        try:
            client = self._create_openai_client(api_key)
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            embedding = response.data[0].embedding
            # 确保嵌入向量形状正确
            embedding_array = np.array(embedding)
            if embedding_array.shape != (DEFAULT_EMBEDDING_DIM,):
                logger.warning(f"获取的嵌入向量形状不正确: {embedding_array.shape}，调整为标准形状")
                # 调整形状或创建零向量
                if len(embedding_array) > DEFAULT_EMBEDDING_DIM:
                    embedding_array = embedding_array[:DEFAULT_EMBEDDING_DIM]  # 截断过长的向量
                else:
                    # 填充零到标准长度
                    padded_embedding = np.zeros(DEFAULT_EMBEDDING_DIM)
                    padded_embedding[:len(embedding_array)] = embedding_array
                    embedding_array = padded_embedding
            # 存入缓存
            self.embeddings_cache[text] = embedding_array.tolist()
            self._save_cache()
            return embedding_array, True
        except Exception as e:
            logger.error(f"使用API密钥...{api_key[-4:]}获取嵌入失败: {e}")
            return np.zeros(DEFAULT_EMBEDDING_DIM), False
    
    def _get_embedding(self, text):
        """获取文本嵌入向量"""
        # 检查缓存
        if text in self.embeddings_cache:
            cached_embedding = np.array(self.embeddings_cache[text])
            # 确保缓存的嵌入向量形状一致
            if cached_embedding.shape == (DEFAULT_EMBEDDING_DIM,):
                return cached_embedding
            else:
                # 如果缓存的形状不正确，重新计算
                logger.warning(f"缓存的嵌入向量形状不正确: {cached_embedding.shape}，重新计算")
                return self._get_embedding_single(text, random.choice(self.api_keys))[0]
        
        # 对于单个文本，使用随机API密钥重试获取
        for attempt in range(self.max_retries):
            api_key = random.choice(self.api_keys)
            try:
                embedding, success = self._get_embedding_single(text, api_key)
                if success and embedding.shape == (DEFAULT_EMBEDDING_DIM,):
                    return embedding
                elif success:
                    logger.warning(f"获取的嵌入向量形状不正确: {embedding.shape}，调整为标准形状")
                    # 调整形状或创建零向量
                    if len(embedding) > DEFAULT_EMBEDDING_DIM:
                        return embedding[:DEFAULT_EMBEDDING_DIM]  # 截断过长的向量
                    else:
                        # 填充零到标准长度
                        padded_embedding = np.zeros(DEFAULT_EMBEDDING_DIM)
                        padded_embedding[:len(embedding)] = embedding
                        return padded_embedding
            except Exception as e:
                logger.error(f"获取嵌入尝试 {attempt+1} 失败: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error(f"获取文本嵌入失败，已达最大重试次数")
        return np.zeros(DEFAULT_EMBEDDING_DIM)  # 返回零向量作为默认值

    def calculate_quality_score(self, comment):
        """计算评论质量分数"""
        # 基础分数
        score = 0

        try:
            # 内容长度分数（越长越可能有深度）
            content_clean = comment.get('content_clean', '')
            # 确保content_clean是字符串
            if not isinstance(content_clean, str):
                content_clean = str(content_clean)
            
            content_length = len(content_clean)
            score += min(content_length / 500, 3)  # 最多3分

            # 是否包含具体信息（如数字、专业术语）
            has_numbers = bool(re.search(r'\d+', content_clean))
            has_terms = bool(re.search(r'[A-Za-z]{3,}|[\u4e00-\u9fa5]{3,}', content_clean))
            score += (1 if has_numbers else 0) + (1 if has_terms else 0)
            
            return min(5, score)  # 最高5分
        except Exception as e:
            logger.error(f"计算质量分数时出错: {e}")
            # 如果出现任何错误，返回最低分数
            return 1.0


class HistoryCommentLLM:
    """
    历史股票评论AI分析工具类
    用于对历史股票评论进行智能分析和筛选
    """
    
    def __init__(self):
        """初始化历史评论AI分析器"""
        self.scorer = None
        
    def _initialize_scorer(self):
        """延迟初始化评分器"""
        if self.scorer is None:
            self.scorer = score_stock_comments.StockCommentScorer()
        return self.scorer
    
    def preprocess_comments(self, comments):
        """
        预处理评论数据，转换为评分器所需格式
        
        Args:
            comments: 原始评论数据列表
            
        Returns:
            list: 预处理后的评论数据列表
        """
        scorer = self._initialize_scorer()
        processed_comments = []
        
        for comment in comments:
            content = comment.get('content', '')
            processed_comment = {
                'author': comment.get('username', '未知'),
                'publish_time': comment.get('timestamp', '未知'),
                'content': content,
                'content_clean': scorer._preprocess_text(content)
            }
            processed_comments.append(processed_comment)
        
        return processed_comments
    
    def analyze_comments(self, comments, top_n=20, use_batch_processing=True, batch_size=10):
        """
        分析评论质量并排序
        
        Args:
            comments: 评论数据列表
            top_n: 返回的高质量评论数量
            use_batch_processing: 是否使用批量处理模式
            batch_size: 批量处理时的批次大小
            
        Returns:
            tuple: (top_comments, top_authors)
        """
        try:
            # 初始化评分器
            scorer = self._initialize_scorer()
            
            # 预处理评论数据
            processed_comments = self.preprocess_comments(comments)
            
            # 进行评论评分和排序
            start_time = time.time()
            top_comments, top_authors = scorer.score_and_rank_comments(
                top_n=top_n, 
                comments=processed_comments, 
                use_batch_processing=use_batch_processing, 
                batch_size=batch_size
            )
            
            end_time = time.time()
            logger.info(f"历史评论AI分析完成，耗时: {end_time - start_time:.2f}秒")
            
            return top_comments, top_authors
            
        except Exception as e:
            logger.error(f"历史评论AI分析失败: {str(e)}")
            raise
    
    def create_temp_archive(self, comments, temp_archive_path):
        """
        创建临时存档文件
        
        Args:
            comments: 评论数据列表
            temp_archive_path: 临时文件路径
        """
        try:
            # 准备临时存档数据
            temp_archive = [{
                'username': comment.get('username', '未知'),
                'timestamp': comment.get('timestamp', '未知'),
                'content': comment.get('content', '')
            } for comment in comments]
            
            # 保存临时存档
            with open(temp_archive_path, 'w', encoding='utf-8') as f:
                json.dump(temp_archive, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"创建临时存档失败: {str(e)}")
            return False
    
    def delete_temp_archive(self, temp_archive_path):
        """
        删除临时存档文件
        
        Args:
            temp_archive_path: 临时文件路径
        """
        try:
            if os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            return True
        except Exception as e:
            logger.error(f"删除临时存档失败: {str(e)}")
            return False
    
    def search_by_keyword(self, comments, keyword):
        """
        根据关键词搜索评论
        
        Args:
            comments: 评论数据列表
            keyword: 搜索关键词
            
        Returns:
            list: 包含关键词的评论列表
        """
        filtered_comments = [
            comment for comment in comments
            if 'content' in comment and keyword in comment['content']
        ]
        
        # 格式化结果
        formatted_results = []
        for comment in filtered_comments:
            if 'username' in comment and 'timestamp' in comment and 'content' in comment:
                formatted_results.append(comment)
        
        return formatted_results
    
    def format_ai_results_for_display(self, top_comments):
        """
        格式化AI分析结果，用于前端展示
        
        Args:
            top_comments: AI分析出的高质量评论列表
            
        Returns:
            list: 格式化后的评论数据列表
        """
        blocks = []
        for item in top_comments:
            # 访问item['comment']以获取真正的评论数据
            comment = item['comment']
            block = {
                'username': comment.get('author', '未知'),
                'timestamp': comment.get('publish_time', '未知'),
                'content': comment.get('content', '')
            }
            blocks.append(block)
        
        return blocks

# 提供便捷的函数接口
_history_llm_instance = None

def get_history_llm():
    """
    获取HistoryCommentLLM的单例实例
    
    Returns:
        HistoryCommentLLM: 历史评论AI分析器实例
    """
    global _history_llm_instance
    if _history_llm_instance is None:
        _history_llm_instance = HistoryCommentLLM()
    return _history_llm_instance

def analyze_history_comments(comments, top_n=20):
    """
    分析历史评论的便捷函数
    
    Args:
        comments: 评论数据列表
        top_n: 返回的高质量评论数量
        
    Returns:
        tuple: (top_comments, top_authors)
    """
    llm = get_history_llm()
    return llm.analyze_comments(comments, top_n)

def search_history_comments(comments, keyword):
    """
    搜索历史评论的便捷函数
    
    Args:
        comments: 评论数据列表
        keyword: 搜索关键词
        
    Returns:
        list: 包含关键词的评论列表
    """
    llm = get_history_llm()
    return llm.search_by_keyword(comments, keyword)


# 创建CommentLLMSearch的单例实例
_comment_llm_instance = None

def get_comment_llm(custom_api_keys=None):
    global _comment_llm_instance
    # 如果提供了不同的API密钥列表，重新创建实例
    if _comment_llm_instance is None or (custom_api_keys and _comment_llm_instance.api_keys != custom_api_keys):
        _comment_llm_instance = CommentLLMSearch(custom_api_keys=custom_api_keys)
    return _comment_llm_instance

def clear_embedding_cache():
    """清除嵌入向量缓存"""
    global _comment_llm_instance
    if _comment_llm_instance:
        _comment_llm_instance.embeddings_cache = {}
        try:
            if os.path.exists(_comment_llm_instance.cache_file):
                os.remove(_comment_llm_instance.cache_file)
            logger.info("嵌入向量缓存已清除")
        except Exception as e:
            logger.error(f"清除缓存文件失败: {e}")
    return True

# 基于embedding的AI智能搜索功能，与history_track_llm类似
def ai_smart_search(comments, keywords, top_k=50, custom_api_keys=None):
    """使用embedding搜索相关性高的评论，与history_track_llm类似的实现方式"""
    try:
        llm_search = get_comment_llm(custom_api_keys=custom_api_keys)
        
        # 预处理关键词
        keywords_clean = llm_search._preprocess_text(keywords)
        
        # 获取关键词嵌入
        keyword_embedding = llm_search._get_embedding(keywords_clean)
        
        # 准备评论数据
        processed_comments = []
        for comment in comments:
            if 'username' in comment and 'timestamp' in comment and 'content' in comment:
                # 预处理内容
                content_clean = llm_search._preprocess_text(comment['content'])
                processed_comments.append({
                    'username': comment['username'],
                    'timestamp': comment['timestamp'],
                    'content': comment['content'],
                    'content_clean': content_clean
                })
        
        if not processed_comments:
            return []
        
        # 计算所有评论的嵌入和相似度（使用并行处理）
        comment_embeddings = []
        
        # 筛选需要计算嵌入的评论（不在缓存中的）
        texts_to_process = []
        indices_to_process = []
        
        for i, comment in enumerate(processed_comments):
            text = comment['content_clean']
            if text in llm_search.embeddings_cache:
                # 直接从缓存获取
                comment_embeddings.append(np.array(llm_search.embeddings_cache[text]))
            else:
                texts_to_process.append(text)
                indices_to_process.append(i)
                # 先占位，后续会填充
                comment_embeddings.append(None)
        
        # 如果有需要计算的文本，使用并行处理
        if texts_to_process:
            logger.info(f"需要计算嵌入的文本数量: {len(texts_to_process)}")
            
            # 创建任务队列
            task_queue = Queue()
            for i, text in enumerate(texts_to_process):
                task_queue.put({
                    'text': text,
                    'index': i
                })
            
            results = [None] * len(texts_to_process)
            
            def worker(api_key):
                """工作线程，使用独立API密钥处理任务"""
                while not task_queue.empty():
                    try:
                        task = task_queue.get_nowait()
                    except Empty:
                        break
                    
                    text = task['text']
                    idx = task['index']
                    
                    try:
                        # 先再次检查缓存，避免重复计算
                        if text in llm_search.embeddings_cache:
                            results[idx] = np.array(llm_search.embeddings_cache[text])
                        else:
                            embedding, success = llm_search._get_embedding_single(text, api_key)
                            if success:
                                results[idx] = embedding
                            else:
                                results[idx] = np.zeros(DEFAULT_EMBEDDING_DIM)
                    except Exception as e:
                        logger.error(f"处理文本 {idx} 时出错: {e}")
                        results[idx] = np.zeros(DEFAULT_EMBEDDING_DIM)
                    finally:
                        task_queue.task_done()
            
            # 启动线程池
            num_workers = min(len(llm_search.api_keys), len(texts_to_process))
            with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix='Embedding_Worker') as executor:
                executor.map(worker, llm_search.api_keys[:num_workers])
            
            # 填充计算结果到comment_embeddings
            for i, idx in enumerate(indices_to_process):
                comment_embeddings[idx] = results[i]
        
        # 计算相似度
        similarities = cosine_similarity([keyword_embedding], comment_embeddings)[0]
        
        # 按相似度排序，先筛选出相关性高于0.4的评论
        sorted_indices = np.argsort(similarities)[::-1]
        relevant_indices = [idx for idx in sorted_indices if similarities[idx] > 0.4]
        
        # 如果没有评论满足阈值，返回空列表
        if not relevant_indices:
            return []
        
        # 再从相关评论中选取前30%（至少1篇）
        top_30_percent_count = max(1, int(len(relevant_indices) * 0.3))
        top_indices = relevant_indices[:top_30_percent_count]
        
        # 对筛选后的评论计算质量分数并综合排序
        results = []
        for idx in tqdm.tqdm(top_indices, desc="计算质量分数"):
            try:
                comment = processed_comments[idx]
                quality_score = llm_search.calculate_quality_score(comment)
                # 确保分数是浮点数
                if not isinstance(quality_score, (int, float)):
                    quality_score = 0.0
                # 综合相似度和质量分数，权重各占50%
                combined_score = similarities[idx] * 0.5 + float(quality_score) * 0.5
                results.append({
                    'comment': comment,
                    'similarity_score': float(similarities[idx]),  # 确保是浮点数
                    'quality_score': float(quality_score),          # 确保是浮点数
                    'combined_score': float(combined_score)         # 确保是浮点数
                })
            except Exception as e:
                logger.error(f"处理评论时出错: {e}")
                continue
        
        # 按综合分数排序
        try:
            results.sort(key=lambda x: x['combined_score'], reverse=True)
        except Exception as e:
            logger.error(f"排序结果时出错: {e}")
            # 如果排序失败，使用原始顺序
        
        # 返回前top_k个结果
        return results[:top_k]
    except Exception as e:
        logger.error(f"AI智能搜索失败: {e}")
        return []