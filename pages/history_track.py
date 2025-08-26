import streamlit as st
from history_track_llm import HistoryTrackLLM
from utils import custom_paginate_and_render
from track_spider import load_id_name_map

ID_NAME_FILE = 'id_name_match.txt'
id_name_map = load_id_name_map(ID_NAME_FILE)

def render():
    st.header("关注跟踪历史存档")
    if "history_llm" not in st.session_state:
        st.session_state.history_llm = HistoryTrackLLM()
    if "ai_browse_mode" not in st.session_state:
        st.session_state.ai_browse_mode = False
    
    # 修改按钮设计：使用两列布局和独立按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("全部存档浏览模式", key="history_full_mode", use_container_width=True):
            st.session_state.ai_browse_mode = False
            if "search_results" in st.session_state:
                del st.session_state.search_results
            if "ai_analyzed" in st.session_state:
                del st.session_state.ai_analyzed
    with col2:
        if st.button("AI浏览模式", key="history_ai_mode", use_container_width=True):
            st.session_state.ai_browse_mode = True
            if "search_results" in st.session_state:
                del st.session_state.search_results
            if "ai_analyzed" in st.session_state:
                del st.session_state.ai_analyzed
    
    if st.session_state.ai_browse_mode:
        # 移除AI浏览模式提示
        user_options = [(name, uid) for uid, name in id_name_map.items()]
        selected = st.multiselect(
            "请选择要检索的用户（可多选）", 
            options=user_options, 
            format_func=lambda x: x[0],
            key="history_user_multiselect"
        )
        selected_user_names = [name for name, uid in selected]
        search_content = st.text_input("请输入搜索内容", key="history_search_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("关键词搜索", key="history_search_btn", use_container_width=True):
                if not selected_user_names:
                    st.warning("请先选择用户！")
                elif not search_content:
                    st.warning("请输入搜索内容！")
                else:
                    with st.spinner("正在搜索相关内容，请稍候..."):
                        # 使用load_raw_articles代替search_articles
                        results = st.session_state.history_llm.load_raw_articles(
                            selected_user_names, search_content
                        )
                        if not results:
                            st.warning("未找到相关内容")
                        else:
                            results_by_user = {}
                            for result in results:
                                user_name = result['article']['user_name']
                                if user_name not in results_by_user:
                                    results_by_user[user_name] = []
                                results_by_user[user_name].append(result)
                            st.session_state.search_results = results_by_user
                            st.session_state.ai_analyzed = False
                            from utils import auto_disappear_notification
                            auto_disappear_notification(f"搜索完成，找到 {len(results)} 条相关内容", "success")
        with col2:
            if st.button("AI智能搜索", key="ai_analyze_btn", use_container_width=True):
                if not selected_user_names:
                    st.warning("请先选择用户！")
                elif not search_content:
                    st.warning("请输入搜索内容！")
                else:
                    with st.spinner("正在进行AI分析和排序，请稍候..."):
                        ai_results = st.session_state.history_llm.search_articles(
                            selected_user_names, search_content
                        )
                        if not ai_results:
                            st.warning("未找到相关内容")
                        else:
                            results_by_user = {}
                            for result in ai_results:
                                user_name = result['article']['user_name']
                                if user_name not in results_by_user:
                                    results_by_user[user_name] = []
                                results_by_user[user_name].append(result)
                            st.session_state.search_results = results_by_user
                            st.session_state.ai_analyzed = True
                        from utils import auto_disappear_notification
        if "search_results" in st.session_state and st.session_state.search_results:
            tabs = st.tabs(list(st.session_state.search_results.keys()))
            for i, user_name in enumerate(st.session_state.search_results.keys()):
                with tabs[i]:
                    user_results = st.session_state.search_results[user_name]
                    def render_result(result, idx, **_):
                        article = result['article']
                        st.markdown(f"**第{idx+1}篇 · {article['title']}**", unsafe_allow_html=True)
                        if st.session_state.get("ai_analyzed", False):
                            st.markdown(f"相似度: {result['similarity_score']:.4f} | 质量分: {result['quality_score']:.4f} | 综合分: {result['combined_score']:.4f}")
                        if st.session_state.get(f"summary_{user_name}_{idx}"):
                            st.markdown(f"<div style='color:blue;font-size:1.05em'><b>AI摘要：</b>{st.session_state[f'summary_{user_name}_{idx}']}</div>", unsafe_allow_html=True)
                        content = article.get('content', '').strip()
                        st.markdown(f"<div style='white-space:pre-wrap;font-size:1.05em'>{content}</div>", unsafe_allow_html=True)
                        st.markdown("---")
                    custom_paginate_and_render(user_results, f"search_{user_name}_page", render_result, page_size=20, summary_type="search")
    else:
        # 普通浏览模式
        # 移除普通浏览模式提示
        # 移除用户选择框，自动加载所有用户的历史文章
        all_blocks = []
        for uid, name in id_name_map.items():
            user_blocks = st.session_state.history_llm.load_user_articles(name)  # 修改为使用name
            # 添加用户信息到每个文章块
            for block in user_blocks:
                block['user_name'] = name
            all_blocks.extend(user_blocks)
        if not all_blocks:
            st.warning("未找到任何历史文章")
        else:
            # 按用户分组
            blocks_by_user = {}
            for block in all_blocks:
                user_name = block['user_name']
                if user_name not in blocks_by_user:
                    blocks_by_user[user_name] = []
                blocks_by_user[user_name].append(block)
            # 按照"关注用户近期跟踪"的方式展示标签页
            tabs = st.tabs(list(blocks_by_user.keys()))
            for i, user_name in enumerate(blocks_by_user.keys()):
                with tabs[i]:
                    blocks = blocks_by_user[user_name]
                    def render_normal(block, idx, **_):
                        st.markdown(f"**第{idx+1}篇 · {block['title']}**", unsafe_allow_html=True)   
                        if st.session_state.get(f"normal_summary_{user_name}_{idx}"):
                            st.markdown(f"<div style='color:blue;font-size:1.05em'><b>AI摘要：</b>{st.session_state[f'normal_summary_{user_name}_{idx}']}</div>", unsafe_allow_html=True)
                        content = block.get('content', '').strip()
                        st.markdown(f"<div style='white-space:pre-wrap;font-size:1.05em'>{content}</div>", unsafe_allow_html=True)
                        st.markdown("---")
                    # 调用新的分页函数
                    custom_paginate_and_render(blocks, f"normal_{user_name}_page", render_normal, page_size=20, summary_type="normal")