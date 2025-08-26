import os
import sys
from history_track_llm import HistoryTrackLLM

# 设置日志级别为INFO，以便查看API密钥使用信息
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

print("测试API密钥配置...")

# 创建HistoryTrackLLM实例
try:
    llm = HistoryTrackLLM()
    print("成功创建HistoryTrackLLM实例")
    
    # 尝试获取一个简单文本的嵌入，测试API调用
    simple_text = "这是一个测试文本"
    try:
        embedding = llm._get_embedding(simple_text)
        print(f"成功获取嵌入向量！向量形状: {embedding.shape}")
        print("API密钥配置正确，调用成功！")
    except Exception as e:
        print(f"获取嵌入向量失败: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            print("错误提示: API密钥可能无效或已过期。请检查.env文件中的API密钥。")
        else:
            print("错误提示: 可能是网络问题或其他API调用问题。")

except Exception as e:
    print(f"创建HistoryTrackLLM实例失败: {e}")

print("测试完成")