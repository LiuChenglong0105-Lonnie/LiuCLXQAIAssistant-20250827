import re
import os
import json  # 添加JSON模块导入
import streamlit as st  # 添加streamlit导入
from comment_spider import get_xueqiu_comments_rich
from utils import custom_paginate_and_render, render_block
from storage import save_recent_stock_comment, load_recent_stock_comment, save_stock_comment_archive, load_stock_comment_archive
from datetime import datetime

OUTPUT_STOCK_COMMENTS = 'history_comments'
ARCHIVE_FILE = os.path.join(OUTPUT_STOCK_COMMENTS, 'recent_stock_comment_archive.json')
AI_ANALYSIS_FILE = os.path.join(OUTPUT_STOCK_COMMENTS, 'recent_ai_analysis.json')
from storage import save_comment_to_history, get_history_archive_list, load_history_archive

def render():
    st.header("股票评论现时抓取")
    # 状态管理
    if "stock_code" not in st.session_state:
        st.session_state.stock_code = load_recent_stock_comment() or ""
    if "stock_comments" not in st.session_state:
        st.session_state.stock_comments = None
    if "stock_score_result" not in st.session_state:
        st.session_state.stock_score_result = None
    if "stock_archive" not in st.session_state:
        st.session_state.stock_archive = None
    if "archive_stock_code" not in st.session_state:
        st.session_state.archive_stock_code = ""
    if "history_archive_list" not in st.session_state:
        st.session_state.history_archive_list = []
    if "selected_history_archive" not in st.session_state:
        st.session_state.selected_history_archive = None
    if "reading_mode" not in st.session_state:
        st.session_state.reading_mode = "full"
    if "history_mode" not in st.session_state:
        st.session_state.history_mode = False

    # 加载存档文件
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
                # 直接使用存档数据作为评论列表
                st.session_state.stock_archive = archive_data
                # 从最近股票评论文件获取股票代码
                st.session_state.archive_stock_code = load_recent_stock_comment() or ''
                if st.session_state.stock_archive and not st.session_state.stock_comments:
                    st.session_state.stock_comments = st.session_state.stock_archive
        except Exception as e:
            st.warning(f"加载存档文件失败: {str(e)}")

    stock_code = st.text_input("请输入股票代码（A股6位数字，港股5位数字，美股代码字母）", value=st.session_state.stock_code).strip().upper()
    pages = st.number_input("采集评论页数", min_value=1, max_value=100, value=5)

    # 确保股票代码已设置
    if stock_code and stock_code != st.session_state.stock_code:
        st.session_state.stock_code = stock_code
        st.session_state.stock_comments = None
        st.session_state.stock_score_result = None

    # 创建三列布局放置按钮
    col1, col2, col3 = st.columns(3)

    # 第一列放置采集按钮
    with col1:
        if st.button("开始采集评论"):
            if not stock_code:
                st.warning("请正确输入股票代码")
            else:
                st.session_state.stock_code = stock_code
                save_recent_stock_comment(stock_code)
                
                # 统一使用港美股爬取方法，适用于所有股票类型
                with st.spinner(f"正在采集{stock_code}的评论..."):
                    out_file = get_xueqiu_comments_rich(stock_code, max_pages=int(pages))
                
                if not out_file or not os.path.exists(out_file):
                    st.session_state.stock_comments = []
                    st.write("暂无评论内容或采集失败")
                else:
                    try:
                        # 统一从JSON文件读取
                        json_file = f"history_comments/{stock_code}.json"
                        if os.path.exists(json_file):
                            with open(json_file, 'r', encoding='utf-8') as f:
                                blocks = json.load(f)
                            st.session_state.stock_comments = blocks
                            ## 保存到存档
                            save_stock_comment_archive(stock_code)
                            ## 加载到stock_archive
                            st.session_state.stock_archive = blocks
                            st.session_state.archive_stock_code = stock_code
                            st.session_state.stock_score_result = None  # 清空分析缓存
                            st.session_state.reading_mode = "full"  # 采集后默认切换到全量阅读模式
                            from utils import auto_disappear_notification
                            auto_disappear_notification(f"采集成功，已保存到: {json_file}", "success")
                        else:
                            st.warning("未找到采集的评论数据")
                            st.session_state.stock_comments = []
                    except Exception as e:
                        st.error(f"处理评论数据时出错: {str(e)}")
                        st.session_state.stock_comments = []

    # 第二列放置全量阅读模式按钮
    with col2:
        if st.button("全量阅读模式", key="full_reading_mode", use_container_width=True):
            st.session_state.reading_mode = "full"
            # 全量阅读模式下，显示存档文件内容
            if st.session_state.stock_archive:
                st.session_state.stock_comments = st.session_state.stock_archive
            else:
                st.warning("存档文件为空或不存在")

    # 第三列放置AI筛选阅读模式按钮
    with col3:
        if st.button("AI筛选阅读模式", key="ai_reading_mode", use_container_width=True):
            st.session_state.reading_mode = "ai"
            st.session_state.stock_score_result = None  # 清空之前的分析结果

            # 先检查AI分析文件是否存在
            if os.path.exists(AI_ANALYSIS_FILE):
                try:
                    with open(AI_ANALYSIS_FILE, 'r', encoding='utf-8') as f:
                        ai_result = json.load(f)
                        # 检查分析结果是否有效
                        if 'top_comments' in ai_result and 'top_authors' in ai_result:
                            st.session_state.stock_score_result = (ai_result['top_comments'], ai_result['top_authors'])
                            st.info("已加载最近的AI分析结果")
                        else:
                            st.warning("AI分析结果格式无效，将重新分析")
                except Exception as e:
                    st.warning(f"加载AI分析文件失败: {str(e)}")
            
            # 如果没有有效的AI分析结果，则获取最新的存档股票代码并进行分析
            latest_archive_code = load_recent_stock_comment() or ''
            if not latest_archive_code:
                st.warning("无法获取最新的股票代码，请先采集评论")
                return
            
            # 检查stock_archive是否存在，如果不存在则尝试加载
            if not st.session_state.stock_archive:
                if os.path.exists(ARCHIVE_FILE):
                    try:
                        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                            archive_data = json.load(f)
                            st.session_state.stock_archive = archive_data
                            st.session_state.archive_stock_code = latest_archive_code
                        st.info(f"已加载存档文件，共{len(archive_data)}条评论")
                    except Exception as e:
                        st.warning(f"加载存档文件失败: {str(e)}")
                        return
                else:
                    st.warning("请先采集评论并存档")
                    return

            # 如果没有有效的AI分析结果，则进行新的分析
            if not st.session_state.stock_score_result:
                try:
                    import score_stock_comments
                    scorer = score_stock_comments.StockCommentScorer()
                    with st.spinner("正在进行AI分析..."):
                        # 计算评论总数的10%
                        total_comments = len(st.session_state.stock_archive) if st.session_state.stock_archive else 0
                        percentage_value = 10  # 10%
                        percentage_count = max(1, int(total_comments * percentage_value / 100))
                        fixed_count = 30  # 固定30条
                        
                        # 取较大的那个值
                        if percentage_count > fixed_count:
                            # 如果10%的数量大于30，则使用百分比
                            top_comments, top_authors = scorer.score_and_rank_comments(percentage=percentage_value)
                        else:
                            # 否则使用固定的30条
                            top_comments, top_authors = scorer.score_and_rank_comments(top_n=fixed_count)
                        
                        st.session_state.stock_score_result = (top_comments, top_authors)
                        # 保存新的AI分析结果
                        new_ai_result = {
                            'top_comments': top_comments,
                            'top_authors': top_authors,
                            'timestamp': datetime.now().timestamp(),
                            'stock_code': latest_archive_code
                        }
                        with open(AI_ANALYSIS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(new_ai_result, f, ensure_ascii=False, indent=2)
                        from utils import auto_disappear_notification
                        auto_disappear_notification("AI分析结果已更新", "success")
                except Exception as e:
                    st.error(f"AI分析过程中发生错误: {str(e)}")
                    st.session_state.stock_score_result = None

    # 展示评论或分析结果
    if st.session_state.reading_mode == "full":
        if st.session_state.stock_archive:
            st.info(f"当前为全量阅读模式，展示存档文件中的{len(st.session_state.stock_archive)}条评论 (股票代码: {st.session_state.archive_stock_code})")
            custom_paginate_and_render(
                st.session_state.stock_archive,
                "stock_comment_page",
                render_block,
                page_size=20
            )
        else:
            st.warning("没有找到存档的评论，请先采集评论")
    elif st.session_state.reading_mode == "ai":
        if st.session_state.stock_score_result:
            # 确保结果是预期的格式
            if isinstance(st.session_state.stock_score_result, tuple) and len(st.session_state.stock_score_result) == 2:
                top_comments, top_authors = st.session_state.stock_score_result
                # 确保top_comments是列表类型
                if isinstance(top_comments, list) and isinstance(top_authors, dict):
                    st.info(f"当前为AI筛选阅读模式，共筛选出{len(top_comments)}条高质量评论")
                    
                    st.subheader('对该股票研究比较深入的大V')
                    for author, score in top_authors.items():
                        st.write(f"**{author}**: 平均分数 {score:.2f}")
                    
                    st.subheader('研究质量最高的评论')
                    # 转换top_comments为与抓取评论相同的格式，并添加分数信息
                    formatted_comments = []
                    for i, item in enumerate(top_comments, 1):
                        if isinstance(item, dict) and 'comment' in item and isinstance(item['comment'], dict):
                            comment = item['comment']
                            # 获取用户名和时间
                            username = comment.get('author', '未知用户')
                            publish_time = comment.get('publish_time', '未知时间')
                            # 创建与抓取评论相同的格式，并在内容前添加排名和分数
                            formatted_block = {
                                'author': username,
                                'publish_time': publish_time,
                                'content': f"【排名: {i} 分数: {item['score']:.2f}】\n{comment.get('content', '')}",
                                'title': f"第{i}篇 · {username} - {publish_time}"
                            }
                            formatted_comments.append(formatted_block)
                    
                    # 使用custom_paginate_and_render函数展示
                    custom_paginate_and_render(
                        formatted_comments,
                        "ai_comment_page",
                        render_block,
                        page_size=20
                    )
                else:
                    st.warning("评论数据格式不正确")
            else:
                st.warning("评分结果格式不正确")
        else:
            st.warning("暂无AI分析结果，请点击'AI筛选阅读模式'按钮进行分析")
    else:
        recent_code = load_recent_stock_comment()
        if recent_code:
            # 移除这里的AI分析结果加载逻辑，已在前面统一处理
            json_file = os.path.join(OUTPUT_STOCK_COMMENTS, f"{recent_code}.json")
            if os.path.exists(json_file):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        blocks = json.load(f)
                    if blocks:
                        st.session_state.stock_code = recent_code
                        st.session_state.stock_comments = blocks
                        st.info(f"自动加载最近爬取的股票评论: {recent_code}，当前为全量阅读模式")
                        custom_paginate_and_render(blocks, "stock_comment_page", render_block, page_size=20)
                except Exception as e:
                    st.error(f"加载评论数据时出错: {str(e)}")
            else:
                # 兼容旧的txt文件
                txt_file = os.path.join(OUTPUT_STOCK_COMMENTS, f"{recent_code}.txt")
                if os.path.exists(txt_file):
                    st.warning("检测到旧的txt格式文件，建议重新采集以获取JSON格式数据")


    # 展示历史存档列表
    if st.session_state.history_mode:
        st.subheader("历史存档列表")
        if not st.session_state.history_archive_list:
            st.info("暂无历史存档")
        else:
            # 创建一个选择框来选择历史存档
            archive_options = [
                f"{item['stock_code']} - {item['archive_time']} ({item['comment_count']}条评论)"
                for item in st.session_state.history_archive_list
            ]
            selected_index = st.selectbox(
                "选择历史存档",
                range(len(archive_options)),
                format_func=lambda i: archive_options[i]
            )

            # 加载选中的历史存档
            selected_archive = st.session_state.history_archive_list[selected_index]
            if st.button("加载选中的历史存档"):
                history_comments = load_history_archive(selected_archive['file_path'])
                if history_comments:
                    st.session_state.stock_archive = history_comments
                    st.session_state.archive_stock_code = selected_archive['stock_code']
                    st.session_state.stock_comments = history_comments
                    st.session_state.reading_mode = "full"
                    st.session_state.history_mode = False
                    from utils import auto_disappear_notification
                    auto_disappear_notification(f"已加载 {selected_archive['stock_code']} 的历史存档", "success")
                else:
                    st.error("加载历史存档失败")