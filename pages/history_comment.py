import os
import json
import re
import streamlit as st
from datetime import datetime
from utils import custom_paginate_and_render, render_block, list_stock_files_by_type
from storage import OUTPUT_STOCK_COMMENTS
from score_stock_comments import StockCommentScorer
from history_comment_llm import ai_smart_search

# 配置日志
import logging
logger = logging.getLogger(__name__)

# 创建StockCommentScorer的单例实例
_scorer_instance = None
def get_scorer():
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = StockCommentScorer()
    return _scorer_instance

def render():
    st.header("股评抓取历史存档")

    # 初始化会话状态
    if "history_reading_mode" not in st.session_state:
        st.session_state.history_reading_mode = "full"
    if "history_search_keyword" not in st.session_state:
        st.session_state.history_search_keyword = ""
    if "history_ai_result" not in st.session_state:
        st.session_state.history_ai_result = None
    if "history_selected_code" not in st.session_state:
        st.session_state.history_selected_code = ""

    # 股票代码选择逻辑
    stock_class_dict = list_stock_files_by_type(OUTPUT_STOCK_COMMENTS)
    stock_type = st.selectbox("请选择市场板块", ["A股", "港股", "美股"])
    codes = stock_class_dict.get(stock_type, [])

    if not codes:
        st.info(f"{stock_type}暂无历史评论存档")
    else:
        code = st.selectbox("请选择股票代码", codes, key="history_code_select")
        filepath = os.path.join(OUTPUT_STOCK_COMMENTS, f"{code}.json")
        st.markdown(f"**{stock_type} {code} 历史评论内容**")

        # 检测股票代码变化，重置AI结果
        if code != st.session_state.history_selected_code:
            st.session_state.history_selected_code = code
            st.session_state.history_ai_result = None
            st.session_state.history_search_keyword = ""

        # 模式切换按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("全部存档浏览模式", key="history_full_mode", use_container_width=True):
                st.session_state.history_reading_mode = "full"
        with col2:
            if st.button("AI浏览模式", key="history_ai_mode", use_container_width=True):
                st.session_state.history_reading_mode = "ai"

        # 加载评论数据
        if not os.path.exists(filepath):
            st.write("暂无评论内容")
        else:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    comments = json.load(f)

                # 全部存档浏览模式
                if st.session_state.history_reading_mode == "full":
                    blocks = []
                    for comment in comments:
                        if 'username' in comment and 'timestamp' in comment and 'content' in comment:
                            # 直接使用JSON中的字典结构，不需要添加type字段
                            blocks.append(comment)

                    if not blocks:
                        st.write("暂无有效评论内容")
                    else:
                        custom_paginate_and_render(blocks, f"history_comment_page_{code}", render_block, page_size=20)

                # AI浏览模式
                else:
                    # 关键词搜索
                    keyword = st.text_input("关键词搜索", value=st.session_state.history_search_keyword, key="history_keyword_input")
                    st.session_state.history_search_keyword = keyword

                    col_search, col_ai = st.columns(2)
                    with col_search:
                        search_button = st.button("AI智能搜索", use_container_width=True)
                    with col_ai:
                        ai_search_button = st.button("优质用户与内容推荐", use_container_width=True)

                    # 处理搜索请求
                    if search_button and keyword:
                        # 使用基于embedding的AI智能搜索
                        st.info("正在进行AI智能搜索，请稍候...")
                        try:
                            with st.spinner("正在计算评论相关性..."):
                                # 使用AI智能搜索
                                results = ai_smart_search(comments, keyword, custom_api_keys=None)

                            # 格式化显示结果
                                blocks = []
                                for result in results:
                                    comment = result['comment']
                                    block = {
                                        'username': comment.get('username', '未知'),
                                        'timestamp': comment.get('timestamp', '未知'),
                                        'content': comment.get('content', ''),
                                        'similarity_score': result.get('similarity_score', 0),
                                        'quality_score': result.get('quality_score', 0),
                                        'combined_score': result.get('combined_score', 0)
                                    }
                                    blocks.append(block)

                            # 保存搜索结果到session state
                            st.session_state.history_search_results = blocks
                            st.session_state.history_last_search_keyword = keyword
                             
                            if not blocks:
                                from utils import auto_disappear_notification
                                auto_disappear_notification(f"未找到与'{keyword}'相关的评论")
                            else:
                                from utils import auto_disappear_notification
                                auto_disappear_notification(f"找到 {len(blocks)} 条与'{keyword}'相关的评论")
                                custom_paginate_and_render(blocks, f"history_keyword_search_{code}_{keyword}", render_block, page_size=20)
                        except Exception as e:
                                st.error(f"AI智能搜索失败: {str(e)}")
                    # 非搜索按钮点击，但有历史搜索结果
                    elif st.session_state.get('history_search_results') and st.session_state.get('history_last_search_keyword') == keyword:
                        # 显示历史搜索结果
                        blocks = st.session_state.history_search_results
                        custom_paginate_and_render(blocks, f"history_keyword_search_{code}_{keyword}", render_block, page_size=20)

                    elif ai_search_button and comments:
                        # AI智能搜索逻辑
                        if st.session_state.history_ai_result is None:
                            st.info("正在进行AI分析，请稍候...")
                            try:
                                # 使用评分器分析
                                with st.spinner("AI正在分析评论质量..."):
                                    # 直接调用score_stock_comments中的功能
                                    scorer = get_scorer()
                                     
                                    # 预处理评论数据为评分器需要的格式
                                    processed_comments = []
                                    for comment in comments:
                                        if 'username' in comment and 'timestamp' in comment and 'content' in comment:
                                            # 预处理内容
                                            content_clean = re.sub(r'\s+', ' ', comment['content']).strip()
                                            content_clean = re.sub(r'[\r\n]+', ' ', content_clean)
                                             
                                            processed_comments.append({
                                                'author': comment['username'],
                                                'publish_time': comment['timestamp'],
                                                'content': comment['content'],
                                                'content_clean': content_clean
                                            })
                                     
                                    top_comments, top_authors = scorer.score_and_rank_comments(
                                        percentage=10,
                                        comments=processed_comments,
                                        use_batch_processing=True
                                    )
                                    st.session_state.history_ai_result = (top_comments, top_authors)

                            except Exception as e:
                                st.error(f"AI分析失败: {str(e)}")
                                st.session_state.history_ai_result = None

                        # 显示AI分析结果
                        if st.session_state.history_ai_result is not None:
                            top_comments, top_authors = st.session_state.history_ai_result
                              
                            # 格式化显示结果
                            blocks = []
                            for idx, item in enumerate(top_comments):
                                # 访问item['comment']以获取真正的评论数据
                                comment = item['comment']
                                block = {
                                    'username': comment.get('author', '未知'),
                                    'timestamp': comment.get('publish_time', '未知'),
                                    'content': comment.get('content', '')
                                }
                                blocks.append(block)
                              
                            # 显示顶尖作者 - 移到评论上方
                            st.subheader("推荐作者")
                            if isinstance(top_authors, dict):
                                for author, score in top_authors.items():
                                    st.write(f"- {author}: 平均评分 {score:.2f}")
                            else:
                                st.info("暂无作者数据")
                              
                            custom_paginate_and_render(blocks, f"history_ai_search_{code}", render_block, page_size=20)

            except Exception as e:
                st.error(f"加载评论数据出错: {str(e)}")
