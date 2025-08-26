import os
import json
from storage import save_recent_track

# 测试数据
test_data = {
    "test_user_id": [
        {
            "title": "测试标题",
            "hash": "test_hash",
            "is_pinned": False,
            "content": "这是测试内容",
            "timestamp": "2023-11-11 11:11"
        }
    ]
}

# 测试保存功能
try:
    save_recent_track(test_data)
    print("测试数据保存成功！")
    # 验证文件是否存在并读取内容
    if os.path.exists('history_track/recent_user_track.json'):
        with open('history_track/recent_user_track.json', 'r', encoding='utf-8') as f:
            content = json.load(f)
        print(f"文件内容: {content}")
    else:
        print("文件不存在，保存失败！")
except Exception as e:
    print(f"保存过程中出错: {str(e)}")