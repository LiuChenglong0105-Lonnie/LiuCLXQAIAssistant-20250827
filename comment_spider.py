import re
import sys
import time
import random
import hashlib
import logging
import json
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, InvalidSessionIdException,
    ElementClickInterceptedException
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# ==== 配置 ====
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
COOKIE_FILE = 'cookie.txt'
OUTPUT_DIR = 'history_comments'  # JSON文件存储目录
TXT_OUTPUT_DIR = 'history_comments_txt'  # TXT文件存储目录
PAUSE_EVERY_N_PAGES = 10
PAUSE_SECONDS = (30, 120)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_cookie_str_from_file(cookie_file):
    """从文件中读取cookie字符串"""
    if not os.path.exists(cookie_file):
        logger.warning(f"Cookie文件未找到: {cookie_file}")
        return ""
    with open(cookie_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    cookie_str = ''.join([line.strip() for line in lines if line.strip()])
    cookie_str = cookie_str.replace('\n', '').replace('\r', '')
    return cookie_str

def parse_cookie_str(cookie_str):
    """将cookie字符串解析为Selenium可用的格式"""
    cookies = []
    if not cookie_str:
        return cookies
    for item in cookie_str.strip().split(';'):
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '.xueqiu.com',
                'path': '/'
            })
    return cookies

def detect_wind_control(driver):
    """检测是否触发风控"""
    page = driver.page_source
    if ("访问异常" in page) or ("请滑动验证" in page):
        logger.warning("[WARNING] 触发风控页面，暂停或终止本次采集！")
        return True
    return False

def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)

def remove_modified_text(text):
    """移除文本中的'修改于'和'发布于'三个字"""
    return text.replace('修改于', '').replace('发布于', '').strip()

def remove_from_text(text):
    """移除文本中的'来自XXX'或'· 来自XXX'部分"""
    return re.sub(r'·?\s*来自.*$', '', text).strip()

def normalize_datetime(text):
    """统一雪球的时间字符串为 YYYY-MM-DD HH:MM 格式"""
    now = datetime.now()
    text = text.strip()
    try:
        if '刚刚' in text or '秒前' in text or '分钟前' in text or '小时前' in text:
            return now.strftime("%Y-%m-%d %H:%M")
        # 昨天 HH:MM
        m = re.match(r'昨天\s*(\d{2}):(\d{2})', text)
        if m:
            yest = now - timedelta(days=1)
            return f"{yest.strftime('%Y-%m-%d')} {m.group(1)}:{m.group(2)}"
        # YYYY-MM-DD HH:MM
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})[^\d]*(\d{2}):(\d{2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
        # YYYY-MM-DD
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00"
        # MM-DD HH:MM
        m = re.match(r'(\d{2})-(\d{2})[^\d]*(\d{2}):(\d{2})', text)
        if m:
            return f"{now.year}-{m.group(1)}-{m.group(2)} {m.group(3)}:{m.group(4)}"
        # MM-DD
        m = re.match(r'(\d{2})-(\d{2})', text)
        if m:
            return f"{now.year}-{m.group(1)}-{m.group(2)} 00:00"
        # 只有时间，没有日期
        if len(text) == 5 and ':' in text:
            today = now.strftime('%Y-%m-%d')
            return f'{today} {text}'
    except Exception as e:
        logger.error(f"时间格式化异常: {e}, 文本: {text}")
    return text

def extract_username_and_time(text):
    """从文本中提取用户名和时间"""
    text = remove_modified_text(text)
    text = remove_from_text(text)

    time_patterns = [
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})',  # YYYY-MM-DD HH:MM
        r'(\d{4}-\d{2}-\d{2})',              # YYYY-MM-DD
        r'(\d{2}-\d{2} \d{2}:\d{2})',       # MM-DD HH:MM
        r'(\d{2}-\d{2})',                     # MM-DD
        r'(昨天 \d{2}:\d{2})',                # 昨天 HH:MM
        r'(刚刚|\d+秒前|\d+分钟前|\d+小时前)'   # 相对时间
    ]

    for pattern in time_patterns:
        m = re.search(pattern, text)
        if m:
            timestamp_str = m.group(1)
            username = text[:m.start()].strip()
            normalized_time = normalize_datetime(timestamp_str)
            return username, normalized_time

    return text.strip(), ''

def parse_history_comments(file_path):
    """解析历史评论文件，用于去重"""
    seen_hashes = set()
    blocks = []
    comments = []
    if not os.path.exists(file_path):
        return seen_hashes, blocks, comments
    with open(file_path, 'r', encoding='utf-8') as f:
        block = []
        current_comment = None
        for line in f:
            if line.startswith("======"):
                if block:
                    block_text = ''.join(block).strip()
                    h = hashlib.md5(block_text.encode('utf-8')).hexdigest()
                    seen_hashes.add(h)
                    blocks.append(block)
                    if current_comment:
                        comments.append(current_comment)
                block = [line]
                current_comment = {}
            elif current_comment is not None and not current_comment.get('username'):
                line = line.strip()
                if line:
                    username, timestamp = extract_username_and_time(line)
                    current_comment['username'] = username
                    current_comment['timestamp'] = timestamp
                    current_comment['content'] = ''
            elif current_comment is not None:
                if 'content' not in current_comment:
                    current_comment['content'] = ''
                current_comment['content'] += line
        if block:
            block_text = ''.join(block).strip()
            h = hashlib.md5(block_text.encode('utf-8')).hexdigest()
            seen_hashes.add(h)
            blocks.append(block)
            if current_comment:
                comments.append(current_comment)
    for comment in comments:
        if 'content' in comment:
            comment['content'] = comment['content'].strip()
    return seen_hashes, blocks, comments

def format_stock_code_for_xueqiu(stock_code):
    """将股票代码格式化为雪球网站的标准格式"""
    stock_code = str(stock_code).strip()
    if re.match(r'^\d{6}$', stock_code):
        if re.match(r'^(60|68|50|51)\d{4}$', stock_code):
            return f"SH{stock_code}"
        elif re.match(r'^(00|30|15|16)\d{4}$', stock_code):
            return f"SZ{stock_code}"
        else:
            # 默认为深圳市场代码，可根据实际情况调整
            return f"SZ{stock_code}"
    elif re.match(r'^\d{4,5}$', stock_code):
        return stock_code
    elif re.match(r'^[A-Z]{1,5}$', stock_code.upper()):
        return stock_code.upper()
    else:
        return stock_code

def create_driver():
    """创建并配置WebDriver实例"""
    options = Options()
    options.add_argument(f'user-agent={UA}')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')
    # 增加一些反爬措施
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    
    try:
        # 确保chromedriver路径正确
        service = Service(r'G:\RSapp\chromedriver-win64\chromedriver.exe')
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            '''
        })
        logger.info("成功创建WebDriver实例")
        return driver
    except Exception as e:
        logger.error(f"创建WebDriver实例失败: {e}")
        raise

def get_xueqiu_comments_rich(stock_code, max_pages=10, cookie_file=COOKIE_FILE, detect_duplicates_during_crawl=False):
    """
    获取雪球股票评论，使用修复后的登录逻辑
    """
    ensure_dir(OUTPUT_DIR)
    ensure_dir(TXT_OUTPUT_DIR)
    
    output_file = os.path.join(TXT_OUTPUT_DIR, f"{stock_code}.txt")
    json_output_file = os.path.join(OUTPUT_DIR, f"{stock_code}.json")
    
    formatted_code = format_stock_code_for_xueqiu(stock_code)
    stock_url = f"https://xueqiu.com/S/{formatted_code}"
    
    cookie_str = get_cookie_str_from_file(cookie_file)
    cookie_list = parse_cookie_str(cookie_str)

    global_stop = False
    comment_index = 1

    seen_hashes, history_blocks, history_comments = parse_history_comments(output_file)
    new_blocks = []
    new_comments = []
    all_new_blocks = []

    driver = None
    try:
        driver = create_driver()
        
        # === 优化后的访问逻辑 - 支持有/无Cookie情况下都能抓取评论 ===
        # 1. 直接访问雪球首页
        logger.info("正在访问雪球首页...")
        driver.get("https://xueqiu.com")
        time.sleep(random.uniform(2, 4))
        
        # 2. 尝试添加Cookie (如果有)
        login_status = False
        if cookie_list:
            logger.info(f"尝试添加 {len(cookie_list)} 个Cookie...")
            driver.delete_all_cookies()  # 添加前先清空，避免干扰
            for cookie in cookie_list:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加Cookie {cookie.get('name')} 失败: {e}")
            
            # 3. 刷新页面让Cookie生效
            driver.refresh()
            time.sleep(random.uniform(3, 5))

            # 4. 验证登录状态（如果验证失败，程序会继续运行）
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".nav__user-info"))
                )
                logger.info("✅ Cookie登录已生效！")
                login_status = True
            except TimeoutException:
                logger.warning("⚠️ 登录验证失败，将以未登录状态继续操作。")
        else:
            logger.info("⚠️ 未提供Cookie，将以未登录状态进行抓取")
        
        # === 无论是否登录，都尝试访问股票页面并抓取评论 ===
        logger.info(f"{'已登录状态' if login_status else '未登录状态'}下访问股票页面: {stock_url}")
        driver.get(stock_url)
        time.sleep(random.uniform(3, 5))
        
        # 6. 检查风控
        if detect_wind_control(driver):
            logger.error("❌ 触发风控，停止采集")
            return None
            
        # 7. 验证股票页面加载
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("✅ 股票页面加载成功")
        except TimeoutException:
            logger.error("❌ 股票页面加载失败")
            return None

        page = 1
        while page <= max_pages:
            logger.info(f"\n==== 正在采集第 {page} 页评论 ====")
            if detect_wind_control(driver):
                global_stop = True
                break

            # 等待评论区出现
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "timeline__item__main"))
                )
            except TimeoutException:
                logger.warning("评论区加载超时，跳过本页。")
                break
            except InvalidSessionIdException:
                logger.error("[FATAL] driver session失效，终止采集。")
                global_stop = True
                break

            comment_blocks = driver.find_elements(By.XPATH, '//div[contains(@class,"timeline__item__main")]')

            for block in comment_blocks:
                time.sleep(random.uniform(0.5, 1.2))
                nickname, date = "", ""
                content = ""

                # 获取用户信息
                try:
                    info_elem = block.find_element(By.XPATH, './/div[contains(@class,"timeline__item__info")]')
                    info_text = info_elem.text.strip()
                    nickname, date = extract_username_and_time(info_text)
                except Exception as e:
                    logger.error(f"提取用户信息异常: {e}")

                # 处理评论内容
                try:
                    # 优先查找并点击“展开”按钮
                    expand_btns = block.find_elements(By.XPATH, './/a[contains(@class, "timeline__expand__control")]')
                    if expand_btns:
                        expand_btn = expand_btns[0]
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", expand_btn)
                            time.sleep(random.uniform(0.3, 0.8))
                            driver.execute_script("arguments[0].click();", expand_btn)
                            time.sleep(random.uniform(0.8, 1.5))
                        except Exception:
                            # 备用点击方法
                            expand_btn.click()
                            time.sleep(random.uniform(0.8, 1.5))
                    
                    content_elem = block.find_element(By.XPATH, './/div[contains(@class,"timeline__item__content")]')
                    content = content_elem.text.strip()
                except Exception as e:
                    logger.error(f"评论处理异常: {e}")

                if content:
                    block_lines = [
                        f"======\n",
                        f"{nickname} {date}\n",
                        f"{content}\n\n"
                    ]
                    block_text = ''.join(block_lines).strip()
                    h = hashlib.md5(block_text.encode('utf-8')).hexdigest()
                      
                    # 动态去重或全部收集后去重
                    if detect_duplicates_during_crawl:
                        if h not in seen_hashes:
                            new_blocks.append(block_lines)
                            seen_hashes.add(h)
                            new_comment = {
                                'username': nickname,
                                'timestamp': date,
                                'content': content.strip()
                            }
                            new_comments.append(new_comment)
                    else:
                        all_new_blocks.append((h, block_lines, content.strip(), nickname, date))

                comment_index += 1

            # 翻页处理
            try:
                next_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[contains(@class,"pagination__next")]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                time.sleep(random.uniform(0.6, 1.5))
                try:
                    next_btn.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", next_btn)
                page += 1
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.info("已到最后一页或翻页失败，爬取完成。")
                break

            # 定时暂停
            if page % PAUSE_EVERY_N_PAGES == 0 and page < max_pages:
                pause_time = random.randint(*PAUSE_SECONDS)
                logger.info(f"已爬取{page}页，休息{pause_time}秒以防风控...")
                time.sleep(pause_time)

        # 爬取后去重
        if not detect_duplicates_during_crawl and all_new_blocks:
            logger.info("开始爬取后去重处理...")
            for h, block_lines, content, nickname, date in all_new_blocks:
                if h not in seen_hashes:
                    new_blocks.append(block_lines)
                    seen_hashes.add(h) # 更新seen_hashes以防重复添加
                    new_comment = {
                        'username': nickname,
                        'timestamp': date,
                        'content': content
                    }
                    new_comments.append(new_comment)
            logger.info(f"去重完成，共新增{len(new_blocks)}条评论")
        
        if not new_blocks:
            logger.info("本次运行没有采集到新的评论。")
            return None

        logger.info(f"全部主评论数据已采集，准备写入文件：{output_file}")

        # 写入TXT文件
        all_blocks = history_blocks + new_blocks
        with open(output_file, "w", encoding="utf-8") as f:
            for block in all_blocks:
                f.writelines(block)
        logger.info(f"已去重合并写入TXT文件：{output_file}")

        # 写入JSON文件
        all_comments = history_comments + new_comments
        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(all_comments, f, ensure_ascii=False, indent=2)
        logger.info(f"已写入JSON文件：{json_output_file}")

        # # 如果有存档函数，则调用
        # if 'save_stock_comment_archive' in globals():
        #     save_stock_comment_archive(stock_code)
        #     logger.info(f"已更新评论存档：recent_stock_comment_archive.json")

        return output_file

    except Exception as e:
        logger.error(f"爬取过程中发生严重错误: {e}")
        return None
    finally:
        try:
            if driver:
                driver.quit()
                logger.info("浏览器已关闭。")
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")

def is_valid_stock_code(code):
    """验证股票代码格式"""
    code = code.strip().upper()
    # A股：6位数字
    if bool(re.match(r'^\d{6}$', code)):
        return True
    # 港股：5位数字
    if bool(re.match(r'^\d{5}$', code)):
        return True
    # 美股：1-5位字母
    if bool(re.match(r'^[A-Z]{1,5}$', code)):
        return True
    return False

def crawl_stock_comments(stock_code: str, pages: int):
    """
    统一的股票评论爬取方法，适用于A股、港股、美股
    stock_code: 股票代码（A股6位数字，港股5位数字，美股代码字母）
    pages: 要采集的评论页数
    返回: 采集结果描述字符串
    """
    stock_code = stock_code.strip().upper()
    if not is_valid_stock_code(stock_code):
        return "股票代码格式不正确，请检查后重新输入！"
    
    # 统一使用港美股爬取方法
    result = get_xueqiu_comments_rich(stock_code, max_pages=pages)
    if result:
        return f"股票 {stock_code} 爬取完成，共{pages}页。"
    else:
        return f"股票 {stock_code} 爬取失败，请检查网络或股票代码。"

# 保留命令行入口方便测试
if __name__ == '__main__':
    # 示例用法:
    # 1. 确保同目录下有 'cookie.txt' 文件，且内容为从浏览器复制的雪球Cookie字符串。
    # 2. 确保 'chromedriver.exe' 的路径在 create_driver 函数中配置正确。
    # 3. 可根据需要选择使用crawl_stock_comments或get_xueqiu_comments_rich函数
    
    # 命令行测试方式1: 使用统一的股票评论爬取方法
    stock_code = input("请输入股票代码（A股6位数字，港股5位数字，美股代码字母）: ").strip().upper()
    if is_valid_stock_code(stock_code):
        max_pages = int(input("请输入想要采集的评论页数：").strip())
        result = get_xueqiu_comments_rich(stock_code, max_pages=max_pages)
        if result:
            print(f"股票 {stock_code} 爬取完成！")
        else:
            print("爬取失败，请检查网络或股票代码！")
    else:
        print("股票代码格式不正确，请检查后重新输入！")
        sys.exit(1)