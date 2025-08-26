import json
import os
import json
from datetime import datetime
import streamlit as st

# 存档相关
RECENT_TRACK_FILE = 'history_track/recent_user_track.json'

def save_recent_track(recent_results):
    with open(RECENT_TRACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(recent_results, f, ensure_ascii=False, indent=2)

def load_recent_track():
    if not os.path.exists(RECENT_TRACK_FILE):
        return {}
    with open(RECENT_TRACK_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            st.warning("近期跟踪文件格式错误，将返回空数据")
            return {}

# 股票评论存档相关
OUTPUT_STOCK_COMMENTS = 'history_comments'  # JSON文件存储目录
TXT_OUTPUT_DIR = 'history_comments_txt'  # TXT文件存储目录
RECENT_STOCK_COMMENT_FILE = os.path.join(OUTPUT_STOCK_COMMENTS, 'recent_stock_comment.txt')
STOCK_COMMENT_ARCHIVE_FILE = os.path.join(OUTPUT_STOCK_COMMENTS, 'recent_stock_comment_archive.json')
# 添加历史存档目录和索引文件
HISTORY_ARCHIVE_DIR = os.path.join(OUTPUT_STOCK_COMMENTS, 'history_archive')
HISTORY_INDEX_FILE = os.path.join(HISTORY_ARCHIVE_DIR, 'history_index.json')

# 修改从txt文件加载股票评论的函数
def load_stock_comments_from_txt(stock_code):
    txt_file = os.path.join(TXT_OUTPUT_DIR, f'{stock_code}.txt')
    if not os.path.exists(txt_file):
        return None
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 解析txt文件内容
        comments = []
        for block in content.split('======'):
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            if len(lines) < 2:
                continue
            # 提取作者和时间
            author_time_line = lines[0]
            author = author_time_line.split(' ')[0]
            publish_time = ' '.join(author_time_line.split(' ')[1:])
            # 提取内容
            content_lines = lines[1:]
            # 查找股票代码行
            stock_code_line = next((line for line in content_lines if line.startswith('$') and line.endswith('$')), None)
            if stock_code_line:
                content_lines.remove(stock_code_line)
            content = '\n'.join(content_lines).strip()
            comments.append({
                'author': author,
                'publish_time': publish_time,
                'content': content
            })
        return comments
    except Exception as e:
        st.warning(f"加载股票评论txt文件出错: {str(e)}")
        return None

def save_recent_stock_comment(stock_code):
    os.makedirs(OUTPUT_STOCK_COMMENTS, exist_ok=True)
    with open(RECENT_STOCK_COMMENT_FILE, 'w', encoding='utf-8') as f:
        f.write(stock_code)

def load_recent_stock_comment():
    if not os.path.exists(RECENT_STOCK_COMMENT_FILE):
        return None
    try:
        with open(RECENT_STOCK_COMMENT_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        st.warning(f"加载最近股票评论文件出错: {str(e)}")
        return None

def save_stock_comment_archive(stock_code):
    # 读取股票代码.json文件
    json_file = os.path.join(OUTPUT_STOCK_COMMENTS, f'{stock_code}.json')
    if not os.path.exists(json_file):
        print(f"警告：JSON文件 {json_file} 不存在，无法更新存档")
        return
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            comments = json.load(f)
        
        # 筛选有效的评论（确保包含必要字段）
        valid_comments = []
        for comment in comments:
            if 'username' in comment and 'timestamp' in comment and 'content' in comment:
                # 保留原始字段，不拼接title
                valid_comment = {
                    'username': comment['username'],
                    'timestamp': comment['timestamp'],
                    'content': comment['content']
                }
                valid_comments.append(valid_comment)
        
        # 直接将有效评论列表写入存档文件
        with open(STOCK_COMMENT_ARCHIVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_comments, f, ensure_ascii=False, indent=2)
        
        # 删除AI分析结果文件，以便重新分析
        ai_analysis_file = os.path.join(OUTPUT_STOCK_COMMENTS, 'recent_ai_analysis.json')
        if os.path.exists(ai_analysis_file):
            os.remove(ai_analysis_file)
            print(f"已删除AI分析结果文件：{ai_analysis_file}")
        
        print(f"已更新评论存档：{STOCK_COMMENT_ARCHIVE_FILE}")
    except Exception as e:
        print(f"更新评论存档失败: {e}")

def load_stock_comment_archive():
    if not os.path.exists(STOCK_COMMENT_ARCHIVE_FILE):
        return None
    try:
        with open(STOCK_COMMENT_ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载股票评论存档失败: {e}")
        return None

def init_history_archive():
    """初始化历史存档目录和索引文件"""
    os.makedirs(HISTORY_ARCHIVE_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_INDEX_FILE):
        with open(HISTORY_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def save_comment_to_history(stock_code):
    """将当前评论存档保存到历史存档"""
    # 确保历史存档目录已初始化
    init_history_archive()

    # 加载当前存档
    current_archive = load_stock_comment_archive()
    if not current_archive:
        print(f"当前存档为空，无法保存到历史存档")
        return False

    # 创建历史存档文件名（包含时间戳）
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    history_file = os.path.join(HISTORY_ARCHIVE_DIR, f'{stock_code}_{timestamp}.json')

    # 保存历史存档
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(current_archive, f, ensure_ascii=False, indent=2)

        # 更新历史索引
        with open(HISTORY_INDEX_FILE, 'r', encoding='utf-8') as f:
            history_index = json.load(f)

        # 添加新条目
        history_index.append({
            'stock_code': stock_code,
            'timestamp': timestamp,
            'file_path': history_file,
            'comment_count': len(current_archive),
            'archive_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        # 保存更新后的索引
        with open(HISTORY_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_index, f, ensure_ascii=False, indent=2)

        print(f"已保存历史存档: {history_file}")
        return True
    except Exception as e:
        print(f"保存历史存档失败: {e}")
        return False

def get_history_archive_list(stock_code=None):
    """获取历史存档列表，可以按股票代码过滤"""
    init_history_archive()
    if not os.path.exists(HISTORY_INDEX_FILE):
        return []

    try:
        with open(HISTORY_INDEX_FILE, 'r', encoding='utf-8') as f:
            history_index = json.load(f)

        # 如果指定了股票代码，则过滤
        if stock_code:
            history_index = [item for item in history_index if item['stock_code'] == stock_code]

        # 按时间倒序排列
        history_index.sort(key=lambda x: x['timestamp'], reverse=True)
        return history_index
    except Exception as e:
        print(f"加载历史存档索引失败: {e}")
        return []

def load_history_archive(archive_file):
    """加载指定的历史存档文件"""
    if not os.path.exists(archive_file):
        print(f"历史存档文件不存在: {archive_file}")
        return None

    try:
        with open(archive_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载历史存档文件失败: {e}")
        return None