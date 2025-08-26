import streamlit as st
from track_spider import load_id_name_map
from pages.recent_track import render as render_track_recent
from pages.history_track import render as render_track_history
from pages.recent_comment import render as render_recent_comment
from pages.history_comment import render as render_history_comment

# 设置页面配置
st.set_page_config(page_title="雪球智能研究助手", layout="wide")

# 加载ID-名称映射
ID_NAME_FILE = 'id_name_match.txt'
id_name_map = load_id_name_map(ID_NAME_FILE)

# 侧边栏功能选择
with st.sidebar:
    st.title("雪球智能研究助手")
    # 可以添加或修改这里的内容
    main_func = st.radio(
        "功能选择",
        ["关注用户近期跟踪", "关注跟踪历史存档", "股票评论现时抓取", "股评抓取历史存档"],
        key="main_func_radio"
    )

# 根据选择的功能渲染相应页面
if st.session_state.main_func_radio == "关注用户近期跟踪":
    render_track_recent()
elif st.session_state.main_func_radio == "关注跟踪历史存档":
    render_track_history()
elif st.session_state.main_func_radio == "股票评论现时抓取":
    render_recent_comment()
elif st.session_state.main_func_radio == "股评抓取历史存档":
    render_history_comment()
