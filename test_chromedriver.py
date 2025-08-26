import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_chromedriver():
    """测试本地ChromeDriver是否正常工作"""
    try:
        logger.info("开始测试ChromeDriver...")
        
        # 设置Chrome选项
        options = Options()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # 使用本地ChromeDriver路径
        chromedriver_path = os.path.join(os.path.dirname(__file__), 'chromedriver-win64', 'chromedriver.exe')
        logger.info(f"使用ChromeDriver路径: {chromedriver_path}")
        
        # 检查ChromeDriver文件是否存在
        if not os.path.exists(chromedriver_path):
            logger.error(f"ChromeDriver文件不存在: {chromedriver_path}")
            return False
        
        # 创建WebDriver实例
        driver = webdriver.Chrome(
            service=webdriver.chrome.service.Service(chromedriver_path), 
            options=options
        )
        
        # 访问简单网页
        logger.info("访问测试网页...")
        driver.get("https://www.google.com")
        time.sleep(2)  # 等待页面加载
        
        # 验证页面标题
        page_title = driver.title
        logger.info(f"页面标题: {page_title}")
        
        # 截取屏幕截图
        screenshot_path = os.path.join(os.path.dirname(__file__), "chromedriver_test_screenshot.png")
        driver.save_screenshot(screenshot_path)
        logger.info(f"屏幕截图已保存至: {screenshot_path}")
        
        # 关闭浏览器
        driver.quit()
        logger.info("ChromeDriver测试成功完成！")
        return True
        
    except Exception as e:
        logger.error(f"ChromeDriver测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_chromedriver()
    print(f"\n测试结果: {'成功' if success else '失败'}")
    print("\n提示：")
    print("1. 如果测试失败，请检查chromedriver.exe文件是否存在于chromedriver-win64目录中")
    print("2. 确保chromedriver版本与您安装的Chrome浏览器版本兼容")
    print("3. 如需下载兼容的ChromeDriver，请访问: https://chromedriver.chromium.org/downloads")