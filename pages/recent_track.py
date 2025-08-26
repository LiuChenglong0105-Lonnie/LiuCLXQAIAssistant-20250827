import streamlit as st
from track_spider import crawl_user_articles, load_id_name_map
from utils import render_block, custom_paginate_and_render
from storage import save_recent_track, load_recent_track
from recent_track_llm import analyze_from_json_file
from datetime import datetime
import json
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

ID_NAME_FILE = 'id_name_match.txt'
id_name_map = load_id_name_map(ID_NAME_FILE)

def render():
    st.header("关注用户近期跟踪")
    user_options = [(name, uid) for uid, name in id_name_map.items()]
    
    # 初始化用户选择
    if "selected_users" not in st.session_state:
        st.session_state.selected_users = []
    
    # 创建multiselect，直接绑定到session_state
    st.multiselect(
        "请选择要爬取的用户（可多选）", 
        options=user_options, 
        format_func=lambda x: x[0],
        key="selected_users"
    )
    
    selected_user_ids = [uid for name, uid in st.session_state.selected_users]
    start_date = st.date_input("选择起始日期", value=datetime.now(), key="track_date")
    
    # 将四个按钮放在同一行，位于日期选择下方
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("全选所有用户", use_container_width=True, key="select_all_btn"):
            st.session_state.selected_users = user_options
    with col2:
        if st.button("清空选择", use_container_width=True, key="clear_btn"):
            st.session_state.selected_users = []
    with col3:
        if st.button("开始爬取（勿点！爬虫无法线上进行！）", use_container_width=True, key="crawl_btn"):
            if not selected_user_ids or not start_date:
                st.warning("请先选择用户和日期！")
            else:
                with st.spinner("正在爬取中，请耐心等待（爬虫速度取决于用户数量和网络环境）..."):
                    results = crawl_user_articles(selected_user_ids, str(start_date))
                if results and "recent" in results:
                    # 删除旧的AI分析结果文件
                    ai_analysis_file = "history_track/recent_ai_analysis.json"
                    if os.path.exists(ai_analysis_file):
                        try:
                            os.remove(ai_analysis_file)
                            logger.info(f"已删除旧的AI分析结果文件: {ai_analysis_file}")
                            # 清除session中的AI分析结果
                            if "ai_results" in st.session_state:
                                del st.session_state["ai_results"]
                        except Exception as e:
                            logger.error(f"删除旧的AI分析结果文件失败: {e}")
                    
                    from utils import auto_disappear_notification
                    auto_disappear_notification("爬取完毕！请及时保存需要的内容，或关闭本应用。", "success")
                    st.session_state.recent_results = results["recent"]
                    st.session_state.recent_user_ids = selected_user_ids.copy()
                    st.session_state.recent_date = str(start_date)
                    save_recent_track(results["recent"])
                else:
                    st.warning("未获取到任何内容，请检查爬虫配置或网络环境。")
                    st.session_state.recent_results = None
                    st.session_state.recent_user_ids = []
                    st.session_state.recent_date = None
    with col4:
        if st.button("AI分析", use_container_width=True, key="ai_analysis_btn"):
            recent_blocks = load_recent_track()
            if not recent_blocks:
                st.warning("暂无爬取内容，请先爬取数据！")
            else:
                # 首先尝试加载已有的AI分析结果文件
                with st.spinner("正在检查AI分析结果文件..."):
                    ai_results = load_ai_analysis_results()
                
                # 如果没有已有的分析结果，进行新的AI分析
                if not ai_results:
                    with st.spinner("AI智能分析中，请稍候..."):
                        # 调用AI分析函数，使用默认的recent_user_track.json
                        ai_results = analyze_from_json_file()
                    
                    # 检查AI分析结果
                    if not ai_results or not isinstance(ai_results, dict):
                        st.error("AI分析失败：未返回有效结果，请检查日志。")
                        return
                
                # 保存分析结果到session_state
                st.session_state.ai_results = ai_results
    
    # 展示
    recent_blocks = load_recent_track()
    if recent_blocks:
        if "ai_results" not in st.session_state:
            st.session_state.ai_results = None
        st.info("展示最近一次爬取存档内容：")
        tabs = st.tabs([id_name_map.get(uid, uid) for uid in recent_blocks.keys()])
        for i, uid in enumerate(recent_blocks.keys()):
            with tabs[i]:
                blocks = recent_blocks[uid]
                ai_block_list = []
                is_ai_mode = False
                if st.session_state.get("ai_results"):
                    ai_block_list = st.session_state["ai_results"].get(uid, {}).get("blocks", [])
                    is_ai_mode = True
                if not blocks:
                    st.write("没有爬到内容")
                else:
                    # 替换为新的分页函数
                    custom_paginate_and_render(blocks, f"recent_{uid}_page", render_block, page_size=20, ai_blocks=ai_block_list, summary_type='ai' if is_ai_mode else None)
    else:
        st.info("暂无最近爬取内容，请选择用户和日期后点击“开始爬取”")

def load_ai_analysis_results(file_path=None):
    """加载已有的AI分析结果文件"""
    if file_path is None:
        file_path = "history_track/recent_ai_analysis.json"
    
    if not os.path.exists(file_path):
        logger.info(f"AI分析结果文件不存在: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            results = json.load(f)
        logger.info(f"成功加载AI分析结果文件: {file_path}")
        return results
    except json.JSONDecodeError as e:
        logger.error(f"AI分析结果文件格式错误: {e}")
        return None
    except Exception as e:
        logger.error(f"加载AI分析结果文件时发生错误: {e}")
        return None


# 从utils.py导入parse_article_block函数
