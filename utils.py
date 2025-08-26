from datetime import datetime
import re
import streamlit as st
import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
def load_environment_variables():
    """加载.env文件中的环境变量"""
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建.env文件的完整路径
    env_path = os.path.join(current_dir, '.env')
    # 检查.env文件是否存在
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        return True
    else:
        # 如果.env文件不存在，尝试直接加载环境变量
        # 这在Streamlit Cloud等部署环境中很有用
        return False

# 自动加载环境变量
load_environment_variables()

# 工具函数
def parse_article_block(block):
    return block.get('title', ''), block.get('id', ''), block.get('content', '')

def format_timestamp(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"时间戳转换错误: {e}")
        return timestamp

def render_summary(summary):
    if summary:
        st.markdown(f"<div style='color:red;font-size:1.05em'><b>AI摘要：</b>{summary}</div>", unsafe_allow_html=True)

def render_content(content, content_color="#222222"):
    st.markdown(f"<div style='white-space:pre-wrap;font-size:1.05em;color:{content_color}'>{content}</div>", unsafe_allow_html=True)

def render_block(block, idx, ai_block=None, is_ai_mode=False):
    if not block:
        return
    summary = ai_block["summary"] if ai_block and "summary" in ai_block else ""
    # 统一使用黑色显示所有内容
    content_color = "#222222"
    
    # 现在所有数据都是JSON格式，直接处理字典类型
    if isinstance(block, dict):
        # 判断是否为股票评论（根据数据结构特征）
        if 'username' in block and 'timestamp' in block and 'content' in block:
            # 股票评论格式，使用用户名和时间作为标题
            title = f"{block.get('username', '未知用户')} - {block.get('timestamp', '未知时间')}"
        else:
            # 文章格式，使用title字段
            title = block.get('title', '无标题')
            
        render_summary(summary)
        st.markdown(f"**第{idx + 1}篇 · {title}**", unsafe_allow_html=True)
        
        # 显示分数信息（如果存在）
        if 'similarity_score' in block and 'quality_score' in block and 'combined_score' in block:
            similarity_score = block.get('similarity_score', 0)
            quality_score = block.get('quality_score', 0)
            combined_score = block.get('combined_score', 0)
            
            # 使用Streamlit的metrics组件显示分数
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="相关性", value=f"{similarity_score:.2f}")
            with col2:
                st.metric(label="质量分", value=f"{quality_score:.2f}")
            with col3:
                st.metric(label="综合分", value=f"{combined_score:.2f}")
            
        content = block.get('content', '').strip()
        render_content(content, content_color)
        st.markdown("---")
    else:
        # 处理其他类型（理论上不应该出现）
        render_summary(summary)
        st.markdown(f"**第{idx + 1}条**", unsafe_allow_html=True)
        content = str(block) if block else ""
        render_content(content, content_color)
        st.markdown("---")

def load_article_blocks(filename):
    import os
    import json
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            st.warning(f"文件 {filename} 格式错误，无法解析")
            return []

def list_stock_files_by_type(folder):
    import os
    files = os.listdir(folder) if os.path.exists(folder) else []
    a, hk, us = [], [], []
    for fname in files:
        # 使用os.path.splitext正确去除扩展名
        code = os.path.splitext(fname)[0]
        if re.match(r'^\d{6}$', code):
            a.append(code)
        elif re.match(r'^\d{5}$', code):
            hk.append(code)
        elif re.match(r'^[A-Z]{1,5}$', code):
            us.append(code)
    return {"A股": sorted(a), "港股": sorted(hk), "美股": sorted(us)}

# 分页渲染函数
def custom_paginate_and_render(blocks, prefix, render_func, page_size=10, enable_batch_summary=False, summary_type=None, ai_blocks=None):
    """
    自定义分页渲染函数，确保key的唯一性
    blocks: 要分页的块数据
    prefix: 唯一标识符前缀
    render_func: 渲染单个块的函数
    page_size: 每页显示数量
    enable_batch_summary: 是否启用批量摘要生成
    summary_type: 摘要类型 ('normal' 或 'ai')
    ai_blocks: AI处理后的块数据
    """
    try:
        # 确保blocks是可迭代对象
        if blocks is None:
            blocks = []
        elif not isinstance(blocks, list):
            try:
                blocks = list(blocks)
            except:
                blocks = []
        
        # 确保page_key在session_state中初始化
        page_key = f"{prefix}_page"
        if page_key not in st.session_state:
            st.session_state[page_key] = 1
        # 确保页码是整数
        if not isinstance(st.session_state[page_key], int):
            try:
                st.session_state[page_key] = int(st.session_state[page_key])
            except:
                st.session_state[page_key] = 1

        total_results = len(blocks)
        total_pages = max(1, (total_results + page_size - 1) // page_size)  # 至少1页

        # 确保页码在有效范围内
        st.session_state[page_key] = max(1, min(st.session_state[page_key], total_pages))

        # 计算当前页显示的块
        start_idx = (st.session_state[page_key] - 1) * page_size
        end_idx = min(start_idx + page_size, total_results)
        current_blocks = blocks[start_idx:end_idx]
        
        for idx, block in enumerate(current_blocks, start=start_idx):
            try:
                ai_block = ai_blocks[idx] if ai_blocks and isinstance(ai_blocks, list) and idx < len(ai_blocks) else None
                render_func(block, idx, ai_block=ai_block)
            except Exception as e:
                print(f"渲染第{idx+1}条内容时出错: {e}")
                st.error(f"渲染第{idx+1}条内容时出错，请刷新页面重试")
                continue

        # 分页控件
        if total_pages > 1:
            # 使用容器来组织分页控件
            with st.container():  # 容器确保key的作用域隔离
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.button("上一页", key=f"{prefix}_prev") and st.session_state[page_key] > 1:
                        st.session_state[page_key] -= 1
                        st.rerun()
                with col2:
                    # 使用selectbox代替slider，更稳定且占用空间小
                    try:
                        st.session_state[page_key] = st.selectbox(
                            "选择页码", 
                            range(1, total_pages + 1), 
                            index=st.session_state[page_key] - 1, 
                            key=f"{prefix}_page_select"
                        )
                    except Exception as e:
                        print(f"页码选择出错: {e}")
                        st.session_state[page_key] = 1
                with col3:
                    if st.button("下一页", key=f"{prefix}_next") and st.session_state[page_key] < total_pages:
                        st.session_state[page_key] += 1
                        st.rerun()
                st.write(f"第 {st.session_state[page_key]}/{total_pages} 页，共 {total_results} 条结果")
        else:
            st.write(f"共 {total_results} 条结果")
    except Exception as e:
        print(f"分页渲染时出错: {e}")
        st.error("显示内容时发生错误，请刷新页面重试")

def auto_disappear_notification(message, type="info", duration=5):
    """
    显示自动消失的通知
    message: 通知消息
    type: 通知类型 ("info", "success")
    duration: 显示时长(秒)
    """
    import time
    from datetime import datetime
    
    # 为每个通知创建唯一的key
    notification_key = f"notification_{int(time.time())}"
    
    # 存储通知信息和创建时间
    st.session_state[notification_key] = {
        "message": message,
        "type": type,
        "created_at": datetime.now().timestamp()
    }
    
    # 显示所有未过期的通知
    for key in list(st.session_state.keys()):
        if key.startswith("notification_"):
            notification = st.session_state[key]
            current_time = datetime.now().timestamp()
            
            # 如果通知未过期，则显示
            if current_time - notification["created_at"] < duration:
                if notification["type"] == "success":
                    st.success(notification["message"])
                else:
                    st.info(notification["message"])
            else:
                # 过期则删除
                del st.session_state[key]