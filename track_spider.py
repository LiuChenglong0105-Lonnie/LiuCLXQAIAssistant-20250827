import os
import re
import time
import random
import hashlib
import logging
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    TimeoutException,
    InvalidSessionIdException
)
from selenium.webdriver.chrome.options import Options

# ==== 配置 ====
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
COOKIE_FILE = 'cookie.txt'
USER_URLS_FILE = 'user_urls.txt'
ID_NAME_FILE = 'id_name_match.txt'
OUTPUT_DIR = 'history_track_txt'
HISTORY_DIR = 'history_track'
PAUSE_INTERVAL = 5
PAUSE_SECONDS = (30, 60)
DRIVER_RESET_INTERVAL = 10

# 从storage模块导入RECENT_TRACK_FILE常量
from storage import RECENT_TRACK_FILE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_cookie_str_from_file(cookie_file):
    with open(cookie_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    cookie_str = ''.join([line.strip() for line in lines if line.strip()])
    cookie_str = cookie_str.replace('\n', '').replace('\r', '')
    return cookie_str

def parse_cookie_str(cookie_str):
    cookies = []
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

def remove_modified_text(text):
    return text.replace('修改于', '').replace('发布于', '').strip()

def normalize_datetime(text):
    text = remove_modified_text(text)
    now = datetime.now()
    text = text.strip()
    try:
        if '刚刚' in text or '秒前' in text or '分钟前' in text or '小时前' in text:
            return now.strftime("%Y-%m-%d %H:%M")
        m = re.match(r'昨天\s*(\d{2}):(\d{2})', text)
        if m:
            yest = now - timedelta(days=1)
            return f"{yest.strftime('%Y-%m-%d')} {m.group(1)}:{m.group(2)}"
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})[^\d]*(\d{2}):(\d{2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00"
        m = re.match(r'(\d{2})-(\d{2})[^\d]*(\d{2}):(\d{2})', text)
        if m:
            return f"{now.year}-{m.group(1)}-{m.group(2)} {m.group(3)}:{m.group(4)}"
        m = re.match(r'(\d{2})-(\d{2})', text)
        if m:
            return f"{now.year}-{m.group(1)}-{m.group(2)} 00:00"
    except Exception:
        pass
    return text

def parse_date_from_text(text):
    text = remove_modified_text(text)
    now = datetime.now()
    try:
        if '刚刚' in text or '秒前' in text or '分钟前' in text or '小时前' in text:
            return now
        elif '昨天' in text:
            yest = now - timedelta(days=1)
            return yest
        elif '-' in text:
            parts = text.strip().split()
            date_part = parts[0]
            if len(date_part.split('-')) == 3:
                return datetime.strptime(date_part, '%Y-%m-%d')
            elif len(date_part.split('-')) == 2:
                return datetime.strptime(f"{now.year}-{date_part}", "%Y-%m-%d")
    except Exception:
        pass
    return None

def get_user_id_from_url(url):
    match = re.search(r'/u/(\d+)', url)
    if match:
        return match.group(1)
    return "unknown"

def load_id_name_map(filename):
    id_name_map = {}
    if not os.path.exists(filename):
        return id_name_map
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line:
                continue
            uid, uname = line.split(',', 1)
            id_name_map[uid.strip()] = uname.strip()
    return id_name_map

def load_user_urls(filename):
    urls = {}
    if not os.path.exists(filename):
        return urls
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url:
                uid = get_user_id_from_url(url)
                urls[uid] = url
    return urls

def is_date_line(line):
    line = line.strip()
    pattern = r'#\s*(昨天|今天|\d{2,4}-\d{2}-\d{2}|\d{2}-\d{2})\s+\d{2}:\d{2}'
    return re.match(pattern, line) is not None

def is_pinned_block(block):
    if not block:
        return False
    first_line = block[0] if isinstance(block, list) else block.split('\n', 1)[0]
    return first_line.strip().startswith('# ') and not is_date_line(first_line)

def split_blocks(lines):
    blocks = []
    block = []
    for line in lines:
        if line.strip().startswith('# '):
            if block:
                blocks.append(block)
            block = [line.rstrip()]
        else:
            block.append(line.rstrip())
    if block:
        blocks.append(block)
    return blocks

def article_hash(title, content):
    base = (title or '') + (content or '')
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def parse_article_block(block):
    title = ''
    content = ''
    if not block:
        return title, content
    title = block[0].replace('# ', '').strip()
    if is_date_line(block[0]):
        content = ''.join(block[1:]).strip()
    else:
        content = ''.join(block[2:]).strip() if len(block) > 1 else ''
    return title, content

def block_to_dict(block):
    title, content = parse_article_block(block)
    art_hash = article_hash(title, content)
    return {
        "hash": art_hash,
        "title": title,
        "content": content,
        "is_pinned": is_pinned_block(block)
    }

def preprocess_lines(lines):
    processed = []
    for line in lines:
        if line.strip().startswith('# '):
            cleaned_line = remove_modified_text(line) + '\n'
            processed.append(cleaned_line)
        else:
            processed.append(line)
    return processed

def create_driver():
    options = Options()
    options.add_argument(f'user-agent={UA}')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 使用本地ChromeDriver，避免在线下载
    import os
    chromedriver_path = os.path.join(os.path.dirname(__file__), 'chromedriver-win64', 'chromedriver.exe')
    
    try:
        driver = webdriver.Chrome(service=webdriver.chrome.service.Service(chromedriver_path), options=options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            '''
        })
        logger.info("成功创建新的WebDriver实例")
        return driver
    except Exception as e:
        logger.error(f"创建WebDriver实例失败: {e}")
        raise

def crawl_user_articles(user_ids, start_date):
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    cookie_str = get_cookie_str_from_file(COOKIE_FILE)
    cookie_list = parse_cookie_str(cookie_str)
    id_name_map = load_id_name_map(ID_NAME_FILE)
    user_url_map = load_user_urls(USER_URLS_FILE)
    ensure_dir(OUTPUT_DIR)
    ensure_dir(HISTORY_DIR)

    results = {}
    driver = None
    user_count = 0
    max_processed_idx = -1

    try:
        progress_file = 'crawl_progress.txt'
        start_index = 0
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                start_index = int(f.read().strip())
                logger.info(f"从索引 {start_index} 开始爬取")

        driver = create_driver()

        for idx, user_id in enumerate(user_ids[start_index:]):
            actual_idx = start_index + idx
            with open(progress_file, 'w') as f:
                f.write(str(actual_idx))
            # 更新最大处理索引
            if actual_idx > max_processed_idx:
                max_processed_idx = actual_idx

            # driver重启逻辑
            if user_count % DRIVER_RESET_INTERVAL == 0 and user_count > 0:
                logger.info(f"已处理{user_count}个用户，重置WebDriver实例...")
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"关闭旧驱动时出错: {e}")
                driver = create_driver()

            url = user_url_map.get(user_id)
            if not url:
                results[user_id] = ["[未找到该用户主页URL]"]
                logger.warning(f"用户{user_id}未找到主页URL")
                user_count += 1
                continue

            user_name = id_name_map.get(user_id, 'unknown')
            user_articles = []
            logger.info(f"开始爬取用户: {user_name} (ID: {user_id})")

            retry_count = 0
            while retry_count < 2:
                try:
                    driver.get("https://xueqiu.com")
                    time.sleep(2)
                    for c in cookie_list:
                        try:
                            driver.add_cookie(c)
                        except Exception as e:
                            logger.warning(f"添加cookie失败: {e}")
                    driver.refresh()
                    time.sleep(2)
                    driver.get(url)
                    time.sleep(3)

                    try:
                        button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.LINK_TEXT, "全部"))
                        )
                        button.click()
                    except ElementClickInterceptedException:
                        button = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.LINK_TEXT, "全部"))
                        )
                        driver.execute_script("arguments[0].click();", button)
                    except TimeoutException:
                        user_articles.append("[未找到'全部'按钮，跳过该用户。]")
                        results[user_id] = user_articles
                        logger.warning(f"用户{user_name}未找到'全部'按钮，跳过")
                        break

                    page_num = 0
                    stop_flag = False
                    while not stop_flag:
                        page_num += 1
                        logger.info(f"爬取用户{user_name}的第{page_num}页")
                        try:
                            content_area = WebDriverWait(driver, 15).until(
                                EC.presence_of_element_located((By.CLASS_NAME, 'profiles__timeline__bd'))
                            )
                        except TimeoutException:
                            user_articles.append("[内容区域加载超时，退出。]")
                            logger.warning(f"用户{user_name}内容区域加载超时")
                            break
                        except InvalidSessionIdException as e:
                            user_articles.append(f"[ERROR] 驱动会话失效：{e}")
                            logger.error(f"驱动会话失效: {e}")
                            try:
                                driver.quit()
                                logger.info("成功关闭WebDriver实例")
                            except Exception as quit_e:
                                logger.warning(f"关闭WebDriver时出错: {quit_e}")
                            driver = create_driver()
                            retry_count += 1
                            if retry_count >= 2:
                                results[user_id] = [f"[FATAL] driver session失效，重试2次失败：{e}"]
                                logger.error(f"用户{user_name} driver失效，重试2次失败")
                                break
                            continue

                        articles = content_area.find_elements(By.XPATH, "./*")
                        lines = []
                        for idx2 in range(1, len(articles)):
                            try:
                                article = content_area.find_elements(By.XPATH, "./*")[idx2]
                            except Exception as e:
                                lines.append(f"[WARN] 重新获取article失败：{e}\n")
                                continue

                            try:
                                longtext_list = article.find_elements(
                                    By.CLASS_NAME, "timeline__item__content.timeline__item__content--longtext"
                                )
                                if longtext_list:
                                    longtext = longtext_list[0]
                                    try:
                                        aref = longtext.find_element(By.XPATH, './*[1]')
                                        new_url = aref.get_attribute('href')
                                        driver.execute_script(f"window.open('{new_url}', 'tmp_window');")
                                        driver.switch_to.window(driver.window_handles[-1])
                                        WebDriverWait(driver, 10).until(
                                            EC.presence_of_element_located((By.CLASS_NAME, "article__bd"))
                                        )
                                        info = driver.find_element(By.CLASS_NAME, "time")
                                        cleaned_time_text = remove_modified_text(info.text)
                                        norm_time = normalize_datetime(cleaned_time_text)
                                        art_date = parse_date_from_text(cleaned_time_text)
                                        if art_date is not None and art_date < start_dt:
                                            stop_flag = True
                                            driver.close()
                                            driver.switch_to.window(driver.window_handles[0])
                                            break
                                        article_area = driver.find_element(By.CLASS_NAME, 'article__bd')
                                        title = article_area.find_element(By.XPATH, './*[1]')
                                        lines.append(f"# {title.text} ")
                                        lines.append(f"{norm_time}\n")
                                        try:
                                            main_text_elements = article_area.find_element(
                                                By.CLASS_NAME, "article__bd__detail"
                                            ).find_elements(By.XPATH, './*')
                                            for text_elem in main_text_elements:
                                                tmp_text = text_elem.text.replace('\n', '')
                                                lines.append(tmp_text + '\n\n')
                                        except NoSuchElementException:
                                            lines.append("[正文未找到]\n")
                                    except Exception as e:
                                        lines.append(f"[长文处理异常: {e}]\n")
                                    finally:
                                        try:
                                            driver.close()
                                        except Exception:
                                            pass
                                        try:
                                            driver.switch_to.window(driver.window_handles[0])
                                        except Exception:
                                            pass
                                else:
                                    try:
                                        info = WebDriverWait(article, 10).until(
                                            EC.presence_of_element_located((By.CLASS_NAME, "date-and-source"))
                                        )
                                        cleaned_time_text = remove_modified_text(info.text)
                                        norm_time = normalize_datetime(cleaned_time_text)
                                        art_date = parse_date_from_text(cleaned_time_text)
                                        if art_date is not None and art_date < start_dt:
                                            stop_flag = True
                                            break
                                    except TimeoutException:
                                        lines.append("[短文信息获取超时]\n")
                                        continue

                                    lines.append(f"# {norm_time}\n")

                                    try:
                                        expand_button_list = article.find_elements(By.CLASS_NAME, "timeline__expand__control")
                                        if expand_button_list:
                                            expand_button = expand_button_list[0]
                                            try:
                                                expand_button.click()
                                                time.sleep(1)
                                                main_text = article.find_element(By.CLASS_NAME, "content.content--detail")
                                                lines.append(main_text.text + "\n\n")
                                            except Exception as e:
                                                lines.append(f"[展开内容异常: {e}]\n")
                                        else:
                                            try:
                                                main_text = article.find_element(By.CLASS_NAME, "content.content--description")
                                                lines.append(main_text.text + "\n")
                                            except NoSuchElementException:
                                                lines.append("[内容未找到]\n")
                                    except Exception as e:
                                        lines.append(f"[短文处理异常: {e}]\n")
                            except Exception as e:
                                lines.append(f"[文章处理异常: {e}]\n")

                        processed_lines = preprocess_lines(lines)
                        user_articles.extend(processed_lines)

                        if stop_flag:
                            break

                        try:
                            next_page_btn = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CLASS_NAME, "pagination__next"))
                            )
                            if 'disabled' in next_page_btn.get_attribute('class'):
                                break
                            next_page_btn.click()
                            time.sleep(2)
                        except Exception:
                            break

                    results[user_id] = user_articles if user_articles else ["[未抓取到内容]"]
                    logger.info(f"完成爬取用户: {user_name}，获取{len(user_articles)}条内容")
                    break  # 当前用户爬取成功，跳出重试循环

                except InvalidSessionIdException as e:
                    retry_count += 1
                    logger.warning(f"用户{user_name} driver失效, 第{retry_count}次重试: {e}")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = create_driver()
                    if retry_count >= 2:
                        results[user_id] = [f"[FATAL] driver session失效，重试2次失败：{e}"]
                        logger.error(f"用户{user_name} driver失效，重试2次失败")
                        break
                    continue
                except Exception as e:
                    results[user_id] = [f"[ERROR] 爬取异常：{e}"]
                    logger.error(f"用户{user_name}爬取异常: {e}")
                    break

            user_count += 1

            if (idx + 1) % PAUSE_INTERVAL == 0 and (idx + 1) < len(user_ids):
                pause_time = random.randint(*PAUSE_SECONDS)
                logger.info(f"已爬取{idx + 1}个用户，暂停{pause_time}秒...")
                time.sleep(pause_time)

    finally:
        try:
            if driver:
                driver.quit()
                logger.info("成功关闭WebDriver实例")
        except Exception as e:
            logger.warning(f"关闭WebDriver时出错: {e}")
        
        # 检查是否完成了所有用户的爬取，如果是则重置进度为0
        progress_file = 'crawl_progress.txt'
        if os.path.exists(progress_file):
            try:
                # 如果实际爬取的用户数量等于总用户数，则重置进度
                if len(user_ids) > 0 and max_processed_idx >= len(user_ids) - 1:
                    with open(progress_file, 'w') as f:
                        f.write('0')
                    logger.info("所有用户爬取完成，已重置爬取进度为0")
            except Exception as e:
                logger.warning(f"重置爬取进度时出错: {e}")

    recent_results = {}
    history_results = {}

    for user_id in user_ids:
        user_name = id_name_map.get(user_id, 'unknown')
        user_history_file = os.path.join(OUTPUT_DIR, f"{user_name}_{user_id}_all.txt")
        user_history_json = os.path.join(HISTORY_DIR, f"{user_name}_all.json")

        if os.path.exists(user_history_file):
            with open(user_history_file, 'r', encoding='utf-8') as f:
                old_lines = f.readlines()
            old_blocks = split_blocks(old_lines)
        else:
            old_blocks = []

        user_articles = results.get(user_id, [])
        new_blocks = split_blocks(user_articles)

        def block_hash(block):
            return hashlib.md5('\n'.join(block).strip().encode('utf-8')).hexdigest()

        old_pinned = old_blocks[0] if old_blocks and is_pinned_block(old_blocks[0]) else None
        new_pinned = new_blocks[0] if new_blocks and is_pinned_block(new_blocks[0]) else None

        old_body_blocks = old_blocks[1:] if old_pinned else old_blocks
        new_body_blocks = new_blocks[1:] if new_pinned else new_blocks

        final_blocks = []
        if new_pinned:
            new_pinned_text = '\n'.join(new_pinned).strip()
            old_pinned_text = '\n'.join(old_pinned).strip() if old_pinned else None
            if not old_pinned or old_pinned_text != new_pinned_text:
                final_blocks.append(new_pinned)
            else:
                final_blocks.append(old_pinned)
        elif old_pinned:
            final_blocks.append(old_pinned)

        history_hashes = set()
        for b in new_body_blocks:
            h = block_hash(b)
            if h not in history_hashes:
                final_blocks.append(b)
                history_hashes.add(h)
        for b in old_body_blocks:
            h = block_hash(b)
            if h not in history_hashes:
                final_blocks.append(b)
                history_hashes.add(h)

        with open(user_history_file, 'w', encoding='utf-8') as f:
            for block in final_blocks:
                for l in block:
                    f.write(l+'\n')
                f.write('\n')

        recent_dicts = [block_to_dict(b) for b in new_body_blocks]
        history_dicts = [block_to_dict(b) for b in final_blocks]

        import json
        with open(user_history_json, 'w', encoding='utf-8') as f_json:
            json.dump(history_dicts, f_json, ensure_ascii=False, indent=2)

        recent_results[user_id] = recent_dicts
        history_results[user_id] = history_dicts

    # 保存近期跟踪数据到recent_user_track.json
    try:
        from storage import save_recent_track
        save_recent_track(recent_results)
        logger.info(f"成功保存近期跟踪数据到 {RECENT_TRACK_FILE}")
    except Exception as e:
        logger.error(f"保存近期跟踪数据失败: {str(e)}")
        
    return {
        "recent": recent_results,
        "history": history_results
    }

if __name__ == "__main__":
    id_name_map = load_id_name_map(ID_NAME_FILE)
    user_ids = list(id_name_map.keys())
    today = datetime.now().strftime("%Y-%m-%d")
    results = crawl_user_articles(user_ids, today)

    # 新增：保存近期跟踪数据到recent_user_track.json
    from storage import save_recent_track
    save_recent_track(results["recent"])

    for uid, articles in results["recent"].items():
        print(f"\n用户 {id_name_map.get(uid, uid)}（近期跟踪去除置顶）：")
        for i, art in enumerate(articles, 1):
            print(f"\n文章 {i}:")
            print(f"标题: {art['title']}")
            print(f"哈希: {art['hash']}")
            print(f"是否置顶: {art['is_pinned']}")
            print(f"正文: {art['content'][:100]}...")

    for uid, articles in results["history"].items():
        print(f"\n用户 {id_name_map.get(uid, uid)}（历史存档）：")
        for i, art in enumerate(articles, 1):
            print(f"\n文章 {i}:")
            print(f"标题: {art['title']}")
            print(f"哈希: {art['hash']}")
            print(f"是否置顶: {art['is_pinned']}")
            print(f"正文: {art['content'][:100]}...")
