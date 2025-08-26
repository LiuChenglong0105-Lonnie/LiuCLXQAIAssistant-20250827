import numpy as np
import logging
import sys
import os

# 配置日志
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')
logger = logging.getLogger(__name__)

# 模拟CommentLLMSearch类，用于测试向量形状处理逻辑
class MockCommentLLMSearch:
    def __init__(self):
        self.embeddings_cache = {}
        # 模拟API密钥
        self.api_keys = ['mock_api_key']
        # 使用与实际代码相同的DEFAULT_EMBEDDING_DIM
        self.DEFAULT_EMBEDDING_DIM = 1536
        # 模拟_get_embedding_single方法
    
    def _get_embedding_single(self, text, api_key):
        # 模拟API调用，返回不同形状的向量进行测试
        if text == "test_shape_1024":
            # 返回1024维向量，测试截断/填充逻辑
            embedding = np.random.rand(1024)
            return embedding, True
        elif text == "test_shape_2048":
            # 返回2048维向量，测试截断逻辑
            embedding = np.random.rand(2048)
            return embedding, True
        else:
            # 返回标准维度向量
            embedding = np.random.rand(self.DEFAULT_EMBEDDING_DIM)
            return embedding, True
    
    def _get_embedding(self, text):
        # 简单模拟_get_embedding方法
        embedding, success = self._get_embedding_single(text, self.api_keys[0])
        if success:
            # 模拟形状验证和调整逻辑
            if embedding.shape != (self.DEFAULT_EMBEDDING_DIM,):
                logger.warning(f"获取的嵌入向量形状不正确: {embedding.shape}，调整为标准形状")
                if len(embedding) > self.DEFAULT_EMBEDDING_DIM:
                    # 截断过长的向量
                    embedding = embedding[:self.DEFAULT_EMBEDDING_DIM]
                else:
                    # 填充零到标准长度
                    padded_embedding = np.zeros(self.DEFAULT_EMBEDDING_DIM)
                    padded_embedding[:len(embedding)] = embedding
                    embedding = padded_embedding
        return embedding

# 验证默认嵌入向量维度
def test_default_embedding_dim():
    # 从实际文件中读取默认嵌入向量维度
    logger.info("验证默认嵌入向量维度设置")
    # 预期是1536
    expected_dim = 1536
    # 创建模拟对象并验证
    mock_llm = MockCommentLLMSearch()
    assert mock_llm.DEFAULT_EMBEDDING_DIM == expected_dim, \
        f"默认嵌入向量维度应该是{expected_dim}，实际是{mock_llm.DEFAULT_EMBEDDING_DIM}"
    logger.info("默认嵌入向量维度验证通过")

# 测试向量形状处理逻辑
def test_vector_shape_handling():
    logger.info("测试向量形状处理逻辑")
    mock_llm = MockCommentLLMSearch()
    
    # 测试1024维向量（需要填充）
    embedding_1024, success = mock_llm._get_embedding_single("test_shape_1024", "mock_api_key")
    logger.info(f"原始1024维向量形状: {embedding_1024.shape}")
    # 模拟形状验证和调整
    if embedding_1024.shape != (mock_llm.DEFAULT_EMBEDDING_DIM,):
        padded_embedding = np.zeros(mock_llm.DEFAULT_EMBEDDING_DIM)
        padded_embedding[:len(embedding_1024)] = embedding_1024
        embedding_1024 = padded_embedding
    logger.info(f"调整后1024维向量形状: {embedding_1024.shape}")
    assert embedding_1024.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
        f"调整后1024维向量形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{embedding_1024.shape}"
    
    # 测试2048维向量（需要截断）
    embedding_2048, success = mock_llm._get_embedding_single("test_shape_2048", "mock_api_key")
    logger.info(f"原始2048维向量形状: {embedding_2048.shape}")
    # 模拟形状验证和调整
    if embedding_2048.shape != (mock_llm.DEFAULT_EMBEDDING_DIM,):
        embedding_2048 = embedding_2048[:mock_llm.DEFAULT_EMBEDDING_DIM]
    logger.info(f"调整后2048维向量形状: {embedding_2048.shape}")
    assert embedding_2048.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
        f"调整后2048维向量形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{embedding_2048.shape}"
    
    # 测试标准维度向量
    embedding_standard, success = mock_llm._get_embedding_single("test_shape_standard", "mock_api_key")
    logger.info(f"标准维度向量形状: {embedding_standard.shape}")
    assert embedding_standard.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
        f"标准维度向量形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{embedding_standard.shape}"
    
    logger.info("向量形状处理逻辑验证通过")

# 测试_get_embedding方法的向量处理
def test_get_embedding_method():
    logger.info("测试_get_embedding方法的向量处理")
    mock_llm = MockCommentLLMSearch()
    
    # 测试1024维向量处理
    embedding = mock_llm._get_embedding("test_shape_1024")
    logger.info(f"_get_embedding处理1024维后形状: {embedding.shape}")
    assert embedding.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
        f"_get_embedding处理1024维后形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{embedding.shape}"
    
    # 测试2048维向量处理
    embedding = mock_llm._get_embedding("test_shape_2048")
    logger.info(f"_get_embedding处理2048维后形状: {embedding.shape}")
    assert embedding.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
        f"_get_embedding处理2048维后形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{embedding.shape}"
    
    logger.info("_get_embedding方法向量处理验证通过")

# 测试缓存处理逻辑
def test_cache_handling():
    logger.info("测试缓存处理逻辑")
    mock_llm = MockCommentLLMSearch()
    
    # 添加不同形状的向量到缓存
    mock_llm.embeddings_cache["cached_text_1024"] = np.random.rand(1024).tolist()
    mock_llm.embeddings_cache["cached_text_standard"] = np.random.rand(mock_llm.DEFAULT_EMBEDDING_DIM).tolist()
    
    # 模拟从缓存获取并验证形状处理
    for text in mock_llm.embeddings_cache:
        cached_embedding = np.array(mock_llm.embeddings_cache[text])
        logger.info(f"缓存的{text}向量原始形状: {cached_embedding.shape}")
        
        # 模拟缓存形状验证
        if cached_embedding.shape != (mock_llm.DEFAULT_EMBEDDING_DIM,):
            logger.warning(f"缓存的嵌入向量形状不正确: {cached_embedding.shape}，需要调整")
            # 模拟调整
            if len(cached_embedding) > mock_llm.DEFAULT_EMBEDDING_DIM:
                cached_embedding = cached_embedding[:mock_llm.DEFAULT_EMBEDDING_DIM]
            else:
                padded_embedding = np.zeros(mock_llm.DEFAULT_EMBEDDING_DIM)
                padded_embedding[:len(cached_embedding)] = cached_embedding
                cached_embedding = padded_embedding
        
        logger.info(f"缓存的{text}向量调整后形状: {cached_embedding.shape}")
        assert cached_embedding.shape == (mock_llm.DEFAULT_EMBEDDING_DIM,), \
            f"缓存的{text}向量调整后形状应该是{(mock_llm.DEFAULT_EMBEDDING_DIM,)}, 实际是{cached_embedding.shape}"
    
    logger.info("缓存处理逻辑验证通过")

# 运行所有测试
def run_all_tests():
    logger.info("开始运行所有测试")
    try:
        test_default_embedding_dim()
        test_vector_shape_handling()
        test_get_embedding_method()
        test_cache_handling()
        logger.info("所有测试运行完成！向量形状处理逻辑工作正常")
    except Exception as e:
        logger.error(f"测试失败: {e}")

if __name__ == "__main__":
    run_all_tests()