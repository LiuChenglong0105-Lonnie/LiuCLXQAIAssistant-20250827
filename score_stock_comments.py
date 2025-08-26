import re
import os
import json
import numpy as np
from datetime import datetime
import openai
from sklearn.metrics.pairwise import cosine_similarity
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import time
import random
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("并行股票评论评分服务")

# 降低requests库的日志级别，减少HTTP请求日志的输出
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

class StockCommentScorer:
    def __init__(self):
        # 初始化API密钥
        env_api_key = os.getenv('QWEN_API_KEY')
        if env_api_key:
            self.api_keys = [key.strip() for key in env_api_key.split(',') if key.strip()]
            logger.info(f"使用环境变量中的{len(self.api_keys)}个API密钥")
        else:
            # 不使用默认API密钥，而是提示用户配置环境变量
            self.api_keys = []
            logger.error("未找到环境变量QWEN_API_KEY，请在.env文件中配置API密钥。")
            logger.error("请参考.env.example文件创建.env文件并添加您的API密钥。")

        self.embeddings_cache = {}
        self.cache_file = "embeddings_cache.json"
        self.max_retries = 3
        self.retry_delay = 2
        
        # 加载缓存
        self._load_cache()

    def _load_cache(self):
        """加载嵌入缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.embeddings_cache = json.load(f)
            except Exception as e:
                logger.warning(f"加载缓存失败: {e}")

    def _save_cache(self):
        """保存嵌入缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.embeddings_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    def _preprocess_text(self, text):
        """预处理文本：去除冗余符号，标准化格式"""
        if not text:
            return ""
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 去除特殊符号
        text = re.sub(r'[\r\n]+', ' ', text)
        return text

    def _get_embedding(self, text, api_key):
        """获取文本嵌入向量"""
        # 检查缓存
        if text in self.embeddings_cache:
            return np.array(self.embeddings_cache[text])

        try:
            client = openai.OpenAI(
                api_key=api_key,
                base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            )
            response = client.embeddings.create(
                model="text-embedding-v4",
                input=text
            )
            embedding = response.data[0].embedding
            # 存入缓存
            self.embeddings_cache[text] = embedding
            self._save_cache()
            return np.array(embedding)
        except Exception as e:
            logger.debug(f"获取嵌入失败: {e}")
            return np.zeros(1536)  # 返回零向量作为默认值

    def load_archived_comments(self):
        """从存档文件加载评论"""
        archive_file = os.path.join("history_comments", "recent_stock_comment_archive.json")
        if not os.path.exists(archive_file):
            logger.error(f"存档文件不存在: {archive_file}")
            return []

        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)

            # 存档文件是评论列表，每个评论包含username、timestamp、content三个键
            comments = []
            for item in archive_data:
                username = item.get('username', '未知')
                timestamp = item.get('timestamp', '未知')
                content = item.get('content', '')

                # 预处理内容
                content_clean = self._preprocess_text(content)

                comments.append({
                    'author': username,
                    'publish_time': timestamp,
                    'content': content,
                    'content_clean': content_clean
                })

            return comments
        except Exception as e:
            logger.error(f"加载存档评论失败: {e}")
            return []

    def _calculate_base_score(self, comment):
        """计算基础分数（非LLM部分）"""
        score = 0
        
        # 内容长度分数（越长越可能有深度）
        content_length = len(comment.get('content_clean', ''))
        score += min(content_length / 500, 3)  # 最多3分

        # 是否包含具体信息（如数字、专业术语）
        has_numbers = bool(re.search(r'\d+', comment.get('content_clean', '')))
        has_terms = bool(re.search(r'[A-Za-z]{3,}|[\u4e00-\u9fa5]{3,}', comment.get('content_clean', '')))
        score += (1 if has_numbers else 0) + (1 if has_terms else 0)
        
        return score

    def _llm_score_comment(self, comment, api_key):
        """使用LLM对单个评论进行评分"""
        base_score = self._calculate_base_score(comment)
        
        try:
            client = openai.OpenAI(
                api_key=api_key,
                base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            )
            
            prompt = (
                "你是一个资深股票分析师，请根据以下股票评论的质量进行评分（1-5分）。\n"
                "评分标准：\n"
                "1. 研究深度：是否有深入的行业或公司分析\n"
                "2. 信息质量：是否包含有价值的信息或数据\n"
                "3. 逻辑清晰度：分析是否有条理、逻辑清晰\n"
                "4. 客观性：是否客观公正，避免主观臆断\n"
                "5. 投资参考价值：对投资决策是否有参考意义\n"
                "请只返回一个数字分数，不要解释或添加其他内容。\n\n"
                f"评论内容：{comment['content_clean'][:1000]}"
            )
            messages = [{"role": "user", "content": prompt}]
            
            for attempt in range(self.max_retries):
                try:
                    response = client.chat.completions.create(
                        model="qwen-plus",
                        messages=messages,
                        temperature=0.1,
                        timeout=60
                    )
                    llm_response = response.choices[0].message.content.strip()
                    
                    # 使用正则表达式提取数字
                    match = re.search(r'\d+\.?\d*', llm_response)
                    if match:
                        llm_score = float(match.group())
                        # 将LLM评分标准化到1-5分
                        llm_score = max(1, min(5, llm_score))
                        # 综合基础分数和LLM分数
                        combined_score = (base_score / 5) * 0.4 + (llm_score / 5) * 0.6
                        return combined_score * 5  # 转换回0-5分
                    else:
                        logger.warning(f"LLM评分格式错误: {llm_response}")
                        return min(5, base_score)
                        
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.debug(f"API调用失败，重试 {attempt + 1}/{self.max_retries}: {e}")
                        time.sleep(self.retry_delay)
                    else:
                        logger.debug(f"LLM评分失败: {e}")
                        return min(5, base_score)
                        
        except Exception as e:
            logger.debug(f"LLM评分异常: {e}")
            return min(5, base_score)

    def _batch_score_comments(self, comments_batch, api_key):
        """使用LLM对批量评论进行评分"""
        results = []
        
        try:
            client = openai.OpenAI(
                api_key=api_key,
                base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            )
            
            # 构建批量评分的提示词
            batch_prompt = "你是一个资深股票分析师，请根据以下股票评论的质量进行评分（1-5分）。\n"
            batch_prompt += "评分标准：\n"
            batch_prompt += "1. 研究深度：是否有深入的行业或公司分析\n"
            batch_prompt += "2. 信息质量：是否包含有价值的信息或数据\n"
            batch_prompt += "3. 逻辑清晰度：分析是否有条理、逻辑清晰\n"
            batch_prompt += "4. 客观性：是否客观公正，避免主观臆断\n"
            batch_prompt += "5. 投资参考价值：对投资决策是否有参考意义\n"
            batch_prompt += "请按以下格式返回每个评论的评分，不要添加任何额外解释：\n"
            batch_prompt += "评论ID: 分数\n"
            batch_prompt += "\n\n"
            
            # 添加每个评论到批量提示词
            for i, comment in enumerate(comments_batch):
                base_score = self._calculate_base_score(comment)
                batch_prompt += f"评论{i+1}: {comment['content_clean'][:500]}\n"
                # 保存基础分数，用于后续计算
                comment['base_score'] = base_score
            
            messages = [{"role": "user", "content": batch_prompt}]
            
            for attempt in range(self.max_retries):
                try:
                    response = client.chat.completions.create(
                        model="qwen-plus",
                        messages=messages,
                        temperature=0.1,
                        timeout=120  # 批量处理超时时间更长
                    )
                    llm_response = response.choices[0].message.content.strip()
                    
                    # 解析批量评分结果
                    score_pattern = re.compile(r'评论(\d+):\s*(\d+\.?\d*)')
                    matches = score_pattern.findall(llm_response)
                    
                    # 创建分数映射
                    score_mapping = {int(match[0]): float(match[1]) for match in matches}
                    
                    # 为每个评论计算最终分数
                    for i, comment in enumerate(comments_batch):
                        comment_id = i + 1
                        if comment_id in score_mapping:
                            llm_score = score_mapping[comment_id]
                            # 标准化LLM评分
                            llm_score = max(1, min(5, llm_score))
                            # 综合基础分数和LLM分数
                            combined_score = (comment['base_score'] / 5) * 0.4 + (llm_score / 5) * 0.6
                            final_score = combined_score * 5
                            results.append({
                                'comment': comment,
                                'score': final_score,
                                'success': True
                            })
                        else:
                            # 未能获取到评分，使用基础分数
                            logger.warning(f"未能获取评论{comment_id}的批量评分，使用基础分数")
                            results.append({
                                'comment': comment,
                                'score': min(5, comment['base_score']),
                                'success': False
                            })
                    
                    return results
                    
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.debug(f"批量API调用失败，重试 {attempt + 1}/{self.max_retries}: {e}")
                        time.sleep(self.retry_delay * 2)  # 批量处理重试间隔更长
                    else:
                        logger.debug(f"批量LLM评分失败: {e}")
                        # 批量处理失败，回退到单个处理
                        fallback_results = []
                        for comment in comments_batch:
                            try:
                                score = self._llm_score_comment(comment, api_key)
                                fallback_results.append({
                                    'comment': comment,
                                    'score': score,
                                    'success': True
                                })
                            except Exception:
                                fallback_results.append({
                                    'comment': comment,
                                    'score': min(5, comment.get('base_score', 0)),
                                    'success': False
                                })
                        return fallback_results
                        
        except Exception as e:
            logger.debug(f"批量LLM评分异常: {e}")
            # 异常情况下也回退到单个处理
            fallback_results = []
            for comment in comments_batch:
                try:
                    score = self._llm_score_comment(comment, api_key)
                    fallback_results.append({
                        'comment': comment,
                        'score': score,
                        'success': True
                    })
                except Exception:
                    fallback_results.append({
                        'comment': comment,
                        'score': min(5, comment.get('base_score', 0)),
                        'success': False
                    })
            return fallback_results

    def _score_single_comment(self, task):
        """处理单个评论评分的任务"""
        comment, api_key = task
        try:
            score = self._llm_score_comment(comment, api_key)
            return {
                'comment': comment,
                'score': score,
                'success': True
            }
        except Exception as e:
            logger.error(f"评论评分失败: {e}")
            return {
                'comment': comment,
                'score': 0,
                'success': False
            }

    def score_and_rank_comments(self, top_n=30, percentage=None, comments=None, use_batch_processing=True, batch_size=10):
        """并行对股票评论进行评分并排序
    
        Args:
            top_n: 返回的top评论数量
            percentage: 可选，返回评论的百分比(0-100)
            comments: 可选，自定义评论数据
            use_batch_processing: 是否使用批量处理模式
            batch_size: 批量处理时每个批次的评论数量
    
        Returns:
            tuple: (top_comments, top_authors)
        """
        # 如果没有提供自定义评论数据，则从存档文件加载
        if comments is None:
            comments = self.load_archived_comments()

        if not comments:
            return [], {}

        logger.info(f"开始{'批量' if use_batch_processing else '并行'}评分，共{len(comments)}条评论，使用{len(self.api_keys)}个API密钥")

        # 并行处理所有评论
        scored_comments = []
        
        if use_batch_processing and len(comments) >= batch_size:
            # 批量处理模式
            # 将评论分成多个批次
            batches = []
            for i in range(0, len(comments), batch_size):
                batch = comments[i:i + batch_size]
                # 为每个批次分配API密钥
                api_key_idx = i % len(self.api_keys)
                api_key = self.api_keys[api_key_idx]
                batches.append((batch, api_key))
            
            # 使用ThreadPoolExecutor进行并行处理
            max_workers = min(len(self.api_keys), len(batches))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='BatchCommentScorer') as executor:
                # 提交所有批次任务并收集结果
                future_to_batch = {executor.submit(self._batch_score_comments, batch, api_key): (batch, api_key) 
                                 for batch, api_key in batches}
                
                # 收集结果并显示进度
                completed_comments = 0
                for future in as_completed(future_to_batch):
                    batch_results = future.result()
                    for result in batch_results:
                        if result['success']:
                            scored_comments.append({
                                'comment': result['comment'],
                                'score': result['score']
                            })
                    
                    batch_size_completed = len(batch_results)
                    completed_comments += batch_size_completed
                    progress_percent = min(100, int(completed_comments / len(comments) * 100))
                    logger.info(f"进度: {completed_comments}/{len(comments)} 条评论已处理 ({progress_percent}%)")
        else:
            # 单条处理模式（原有的实现）
            # 创建任务列表，均匀分配API密钥
            tasks = []
            for i, comment in enumerate(comments):
                api_key = self.api_keys[i % len(self.api_keys)]
                tasks.append((comment, api_key))
            
            # 使用ThreadPoolExecutor进行并行处理
            max_workers = min(len(self.api_keys), len(comments))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='CommentScorer') as executor:
                # 提交所有任务并收集结果
                future_to_task = {executor.submit(self._score_single_comment, task): task for task in tasks}
                
                # 收集结果并显示进度
                completed = 0
                for future in as_completed(future_to_task):
                    result = future.result()
                    if result['success']:
                        scored_comments.append({
                            'comment': result['comment'],
                            'score': result['score']
                        })
                    
                    completed += 1
                    if completed % 10 == 0 or completed == len(tasks):
                        logger.info(f"进度: {completed}/{len(tasks)} 条评论已处理")

        # 按分数排序
        scored_comments.sort(key=lambda x: x['score'], reverse=True)

        # 确定返回数量
        total_comments = len(scored_comments)
        if percentage is not None and 0 < percentage <= 100:
            # 按百分比计算，确保至少返回1条
            return_count = max(1, int(total_comments * percentage / 100))
        else:
            return_count = top_n

        # 获取前return_count个结果
        top_comments = scored_comments[:return_count]

        # 找出研究深入的大V
        author_scores = defaultdict(float)
        author_counts = defaultdict(int)
        for item in scored_comments:
            author = item['comment']['author']
            author_scores[author] += item['score']
            author_counts[author] += 1

        # 计算平均分数
        author_avg_scores = {}
        for author, total_score in author_scores.items():
            if author_counts[author] >= 2:  # 至少需要2条评论才考虑
                author_avg_scores[author] = total_score / author_counts[author]

        # 按平均分数排序
        top_authors = sorted(author_avg_scores.items(), key=lambda x: x[1], reverse=True)

        logger.info(f"{'批量' if use_batch_processing and len(comments) >= batch_size else '并行'}评分完成，成功处理{len(scored_comments)}/{len(comments)}条评论")
        
        return top_comments, dict(top_authors[:15])  # 返回前15个大V

if __name__ == "__main__":
    # 测试批量/并行股票评论评分服务
    scorer = StockCommentScorer()
    
    # 测试批量处理模式
    print("\n=== 测试批量处理模式（推荐）===")
    start_time_batch = time.time()
    top_comments_batch, top_authors_batch = scorer.score_and_rank_comments(
        use_batch_processing=True, 
        batch_size=10
    )
    end_time_batch = time.time()
    
    print(f"\n批量分析完成！")
    print(f"总耗时: {end_time_batch - start_time_batch:.2f}秒")
    print(f"研究质量最高的{len(top_comments_batch)}条评论:")
    
    # 只显示前5条结果以避免输出过多
    for i, item in enumerate(top_comments_batch[:5], 1):
        print(f"{i}. 作者: {item['comment']['author']}")
        print(f"   分数: {item['score']:.2f}")
        print(f"   内容: {item['comment']['content'][:100]}...")
        print()

    # 测试传统并行模式（用于对比）
    # 注意：只有当评论数量较多时才运行，否则会重复计算
    if len(scorer.load_archived_comments()) > 50:
        print("\n=== 测试传统并行模式（用于对比）===")
        start_time_parallel = time.time()
        top_comments_parallel, top_authors_parallel = scorer.score_and_rank_comments(
            use_batch_processing=False
        )
        end_time_parallel = time.time()
        
        print(f"\n并行分析完成！")
        print(f"总耗时: {end_time_parallel - start_time_parallel:.2f}秒")
        
        # 计算性能提升
        speedup = (end_time_parallel - start_time_parallel) / (end_time_batch - start_time_batch)
        print(f"\n性能对比: 批量处理比传统并行处理快约{speedup:.2f}倍")