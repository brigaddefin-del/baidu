import sys
import time
import threading
import random
import requests
import json
import os
import re
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from bs4 import BeautifulSoup

class TaskThread(QThread):
    log_signal = pyqtSignal(str)
    task_complete = pyqtSignal(int)
    
    def __init__(self, keyword, url, optimize_count, proxy_ip="", ua_list=None):
        super().__init__()
        self.keyword = keyword
        self.url = url
        self.optimize_count = optimize_count
        self.proxy_ip = proxy_ip
        self.ua_list = ua_list if ua_list else self.load_default_ua()
        self.running = True
        # 默认代理API地址（新的订单号）
        self.proxy_api_url = "http://route.xiongmaodaili.com/xiongmao-web/api/glip?secret=e7df6f68d2764bf5a08ad313cfe299ad&orderNo=GL20260605150136W84aG6XF&count=5&isTxt=1&proxyType=1&returnAccount=1"
        self.last_proxy_time = 0  # 上次获取代理的时间
    
    def load_default_ua(self):
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
    
    def get_random_ua(self):
        return random.choice(self.ua_list).strip()
    
    def get_new_proxy(self):
        """
        从代理API获取新的代理IP（每次调用获取一个新IP）
        """
        # 频率限制：至少间隔1秒
        current_time = time.time()
        if current_time - self.last_proxy_time < 1:
            time.sleep(1 - (current_time - self.last_proxy_time))
        
        self.last_proxy_time = time.time()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.proxy_api_url, headers=headers, timeout=10)
            text = response.text.strip()
            
            if not text:
                return self.proxy_ip
            
            # 尝试JSON格式解析
            try:
                data = response.json()
                if data.get('code') == 0 and data.get('data'):
                    # 熊猫代理JSON格式
                    proxy_list = data['data']
                    if proxy_list and isinstance(proxy_list, list):
                        for proxy in proxy_list:
                            if isinstance(proxy, dict):
                                ip = proxy.get('ip')
                                port = proxy.get('port')
                                if ip and port:
                                    return f"{ip}:{port}"
                            elif isinstance(proxy, str):
                                if ':' in proxy:
                                    return proxy
            except ValueError:
                pass
            
            # 尝试文本格式解析（isTxt=1 格式）
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # 跳过空行和注释
                    if line.startswith('#'):
                        continue
                    # 支持 ip:port 格式
                    if ':' in line and not line.startswith('{'):
                        return line
                    # 支持 ip,port 格式
                    elif ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            return f"{parts[0].strip()}:{parts[1].strip()}"
            
            return self.proxy_ip  # 如果解析失败，返回原代理
        except Exception as e:
            print(f"获取新代理失败：{e}")
            return self.proxy_ip  # 如果获取失败，返回原代理
    
    def format_url(self, url):
        if not url.startswith('http://') and not url.startswith('https://'):
            return 'http://' + url
        return url
    
    def run(self):
        formatted_url = self.format_url(self.url)
        
        for i in range(self.optimize_count):
            if not self.running:
                break
            try:
                # 使用缓存的代理（循环使用），不再每次调用API
                current_proxy = self.proxy_ip
                
                proxies = None
                if current_proxy and current_proxy.strip():
                    # 验证代理格式
                    proxy_match = re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', current_proxy.strip())
                    if proxy_match:
                        proxies = {'http': 'http://' + current_proxy.strip(), 'https': 'http://' + current_proxy.strip()}
                    else:
                        self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - 警告：代理格式无效: {current_proxy}")
                        proxies = None  # 格式无效时不使用代理
                
                # URL编码中文关键词
                encoded_keyword = requests.utils.quote(self.keyword, encoding='utf-8')
                
                headers = {
                    'User-Agent': self.get_random_ua(),
                    'Referer': f'https://www.baidu.com/s?wd={encoded_keyword}',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Connection': 'keep-alive'
                }
                
                # 增加超时时间到30秒
                response = requests.get(formatted_url, headers=headers, proxies=proxies, timeout=30, verify=False)
                status = response.status_code
                
                # 处理不同状态码
                if status == 200:
                    self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - {self.url} 第{i+1}/{self.optimize_count}次 - 百度sp3发包参数成功")
                    time.sleep(random.uniform(0.5, 1.5))
                elif status == 503:
                    self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - {self.url} 第{i+1}/{self.optimize_count}次 - 状态：{503} (服务暂时不可用，等待重试)")
                    time.sleep(random.uniform(5, 10))  # 503时增加等待时间
                else:
                    self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - {self.url} 第{i+1}/{self.optimize_count}次 - 状态：{status}")
                    time.sleep(random.uniform(0.5, 1.5))
            except requests.exceptions.Timeout:
                self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - 错误：代理超时，跳过本次")
                time.sleep(random.uniform(2, 3))
            except requests.exceptions.ProxyError:
                self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - 错误：代理连接失败，跳过本次")
                time.sleep(random.uniform(2, 3))
            except Exception as e:
                self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 优化 '{self.keyword}' - 错误：{str(e)}")
                time.sleep(random.uniform(0.5, 1.5))
        self.task_complete.emit(1)
    
    def stop(self):
        self.running = False

class ProxyManager:
    def __init__(self):
        self.proxy_list = []  # 缓存的代理列表
        self.current_index = 0  # 当前使用的代理索引
        # 代理 API 接口 - 默认使用熊猫代理（新订单号）
        self.api_url = "http://route.xiongmaodaili.com/xiongmao-web/api/glip?secret=e7df6f68d2764bf5a08ad313cfe299ad&orderNo=GL20260605150136W84aG6XF&count=5&isTxt=1&proxyType=1&returnAccount=1"
    
    def set_api_url(self, url):
        """
        设置代理API地址
        """
        if url and url.strip():
            self.api_url = url.strip()
            return True
        return False
    
    def get_api_url(self):
        """
        获取当前代理API地址
        """
        return self.api_url
    
    def fetch_proxies(self):
        """
        从代理 API 获取多个代理并缓存
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.api_url, headers=headers, timeout=10)
            text = response.text.strip()
            
            if not text:
                return False
            
            # 清空旧的代理列表
            self.proxy_list = []
            self.current_index = 0
            
            # 熊猫代理 isTxt=1 格式：每行一个 ip:port
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # 匹配 ip:port 格式
                    if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', line):
                        self.proxy_list.append(line)
                    # 匹配 ip,port 格式（用逗号分隔）
                    match = re.match(r'^(\d+\.\d+\.\d+\.\d+),(\d+)$', line)
                    if match:
                        self.proxy_list.append(f"{match.group(1)}:{match.group(2)}")
            
            return len(self.proxy_list) > 0
        except Exception as e:
            print(f"获取代理失败：{e}")
            return False
    
    def get_next_proxy(self):
        """
        获取下一个代理（每个代理只使用一次，不循环）
        """
        if not self.proxy_list:
            return None
        
        # 弹出第一个代理，不再循环使用
        proxy = self.proxy_list.pop(0)
        return proxy
    
    def get_proxy_count(self):
        """
        获取缓存的代理数量
        """
        return len(self.proxy_list)
    
    def get_local_ip(self):
        try:
            response = requests.get("http://txt.go.sohu.com/ip/soip", timeout=10)
            ip = re.findall(r'\d+\.\d+\.\d+\.\d+', response.text)[0]
            return ip
        except Exception as e:
            print(f"获取本地 IP 失败：{e}")
            return None

class BaiduClickEngine:
    """百度点击引擎 - 高级点击算法"""
    
    def __init__(self):
        self.ua_list = []
        self.RelKeyword_list = []
        self.HotKeyword_list = []
        self.cookies_list = []
        self.tn_list = ['site888_3_pg', '50000049_hao_pg', '02049043_6_pg', '77092190_pg', 'request_28_pg', 
                        'site5566', '58059073_pg', '56060048_4_pg', 'baijuyi_pg', 'windowstime_pg', 
                        '21002492_17_hao_pg', '50000049_hao_pg']
        self.rlx = 0
        self.rly = 0
        self.grlx = 0
        self.grly = 0
        self.winWidth = 0
        self.winHeight = 0
        self.driver = None
        
    def load_default_ua(self):
        """加载默认UA列表"""
        self.ua_list = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        ]
    
    def randUa(self):
        """随机获取UA"""
        return random.choice(self.ua_list).strip()
    
    def loadRelKeyword(self, keyword):
        """获取相关搜索词"""
        try:
            headers = {'User-Agent': self.randUa()}
            url = f"http://www.baidu.com/s?wd={keyword}"
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.content, 'html.parser')
            a_list = soup.select("#rs a")
            for r in a_list:
                self.RelKeyword_list.append(r.text)
        except Exception as e:
            print(f"获取相关搜索词失败: {e}")
    
    def loadHotKeyword(self):
        """获取热点搜索词"""
        try:
            headers = {'User-Agent': self.randUa()}
            url = "http://top.baidu.com/buzz.php?p=top10"
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.content, 'html.parser')
            a_list = soup.select(".list-title")
            for r in a_list:
                self.HotKeyword_list.append(r.text)
        except Exception as e:
            print(f"获取热点搜索词失败: {e}")
    
    def preBaidu(self, keyword):
        """提前搜索相关词，模拟真实用户行为"""
        try:
            if self.RelKeyword_list or self.HotKeyword_list:
                tarlist = []
                if self.RelKeyword_list:
                    tarlist.append(random.choice(self.RelKeyword_list))
                if self.HotKeyword_list:
                    tarlist.append(random.choice(self.HotKeyword_list))
                
                if tarlist:
                    tarkeyword = random.choice(tarlist)
                    search_box = self.driver.find_element(By.ID, 'kw')
                    search_box.clear()
                    search_box.send_keys(tarkeyword)
                    time.sleep(random.uniform(1, 3))
                    
                    su_btn = self.driver.find_element(By.ID, 'su')
                    su_btn.click()
                    time.sleep(random.uniform(3, 5))
                    
                    # 随机点击一个结果
                    results = self.driver.find_elements(By.XPATH, '//div[@id="content_left"]//h3/a')
                    if results:
                        random_result = random.choice(results[:5])
                        random_result.click()
                        time.sleep(random.uniform(2, 4))
                        self.driver.back()
                        time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"预搜索失败: {e}")
    
    def getElementPos(self, element):
        """获取元素位置信息"""
        pos = element.location_once_scrolled_into_view
        size = element.size
        return {
            'x': pos['x'],
            'y': pos['y'],
            'width': size['width'],
            'height': size['height']
        }
    
    def randElementPosition(self):
        """获取元素内部随机坐标"""
        x = random.randint(5, max(5, self.grlx - 5))
        y = random.randint(5, max(5, self.grly - 5))
        return {'x': x, 'y': y}
    
    def mouseMoveClick(self, x, y, element=None):
        """模拟真实鼠标移动点击"""
        if element:
            self.grlx = element.size['width']
            self.grly = element.size['height']
            pos = self.getElementPos(element)
            grlp = self.randElementPosition()
            final_x = pos['x'] + self.rlx + grlp['x']
            final_y = pos['y'] + self.rly + grlp['y']
        else:
            final_x = x
            final_y = y
        
        # 随机移动几次
        rand_move_times = random.randint(0, 2)
        for _ in range(rand_move_times):
            rand_x = random.randint(0, self.winWidth)
            rand_y = random.randint(0, self.winHeight)
            pyautogui.moveTo(rand_x, rand_y, duration=random.uniform(0.3, 0.8))
            time.sleep(random.uniform(0.1, 0.3))
        
        # 移动到目标位置并点击
        pyautogui.moveTo(final_x, final_y, duration=random.uniform(0.5, 1.2))
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.click()
    
    def clickJingjia(self):
        """点击竞价广告"""
        try:
            jingjia_list = self.driver.find_elements(By.XPATH, "//a[@data-landurl and not(@hidefocus)]")
            if jingjia_list:
                randelement = random.choice(jingjia_list)
                self.mouseMoveClick(0, 0, randelement)
                time.sleep(random.uniform(2, 4))
                self.driver.back()
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"点击竞价失败: {e}")
    
    def randCurClick(self):
        """随机点击当前页的其他链接"""
        try:
            results = self.driver.find_elements(By.XPATH, '//div[@id="content_left"]//h3/a')
            if results:
                randid = random.randint(0, min(9, len(results)-1))
                random_result = results[randid]
                self.mouseMoveClick(0, 0, random_result)
                time.sleep(random.uniform(2, 4))
                self.driver.back()
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"随机点击失败: {e}")
    
    def scrollPage(self):
        """模拟页面滚动"""
        for i in range(random.randint(3, 6)):
            scroll_amount = random.randint(80, 120)
            js = f"var action=document.documentElement.scrollTop={i * scroll_amount}"
            self.driver.execute_script(js)
            time.sleep(random.uniform(0.3, 0.8))
    
    def clickTarget(self, url):
        """点击目标链接"""
        try:
            results = self.driver.find_elements(By.XPATH, '//div[@id="content_left"]//h3/a')
            target_found = False
            
            for result in results[:10]:
                try:
                    href = result.get_attribute('href')
                    if href and (url in href or url.replace('www.', '') in href):
                        self.mouseMoveClick(0, 0, result)
                        time.sleep(random.uniform(3, 6))
                        self.scrollPage()
                        time.sleep(random.uniform(5, 10))
                        target_found = True
                        break
                except Exception as e:
                    continue
            
            return target_found
        except Exception as e:
            print(f"点击目标失败: {e}")
            return False
    
    def run(self, keyword, url, proxy_ip=None, count=1):
        """执行点击任务"""
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import pyautogui
        import chromedriver_autoinstaller
        
        chromedriver_autoinstaller.install()
        
        self.load_default_ua()
        
        results = []
        
        for _ in range(count):
            try:
                options = webdriver.ChromeOptions()
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-extensions')
                options.add_argument('--no-sandbox')
                options.add_argument(f'user-agent={self.randUa()}')
                
                if proxy_ip:
                    options.add_argument(f"--proxy-server=http://{proxy_ip}")
                
                self.driver = webdriver.Chrome(options=options)
                self.driver.maximize_window()
                
                # 获取窗口大小
                self.winWidth = self.driver.execute_script('return window.innerWidth;')
                self.winHeight = self.driver.execute_script('return window.innerHeight;')
                
                # 访问百度搜索
                search_url = f"https://www.baidu.com/s?wd={keyword}&tn={random.choice(self.tn_list)}"
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))
                
                # 预搜索（模拟真实用户行为）
                if random.random() > 0.5:
                    self.loadRelKeyword(keyword)
                    self.loadHotKeyword()
                    self.preBaidu(keyword)
                
                # 重新搜索目标关键词
                search_box = self.driver.find_element(By.ID, 'kw')
                search_box.clear()
                search_box.send_keys(keyword)
                time.sleep(random.uniform(1, 2))
                su_btn = self.driver.find_element(By.ID, 'su')
                su_btn.click()
                time.sleep(random.uniform(3, 5))
                
                # 随机点击竞价或其他链接
                if random.random() > 0.6:
                    self.clickJingjia()
                
                if random.random() > 0.7:
                    self.randCurClick()
                
                # 点击目标链接
                success = self.clickTarget(url)
                results.append(success)
                
                self.driver.quit()
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"执行失败: {e}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                results.append(False)
        
        return results

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("百度发包工具 v3.0")
        self.setGeometry(100, 100, 1100, 700)
        
        self.tasks = []
        self.running_threads = []
        self.ua_list = []
        self.proxy_manager = ProxyManager()
        self.load_ua_list()
        self.init_ui()
    
    def load_ua_list(self):
        ua_path = os.path.join(os.path.dirname(__file__), 'ua.txt')
        if os.path.exists(ua_path):
            try:
                with open(ua_path, 'r', encoding='utf-8') as f:
                    self.ua_list = [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"加载 UA 列表失败：{e}")
        
        if not self.ua_list:
            self.ua_list = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
            ]
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        
        tabs.addTab(self.tab1, "发包任务")
        tabs.addTab(self.tab2, "百度点击")
        tabs.addTab(self.tab3, "任务管理")
        
        self.init_tab1()
        self.init_tab2()
        self.init_tab3()
        
        log_group = QGroupBox("日志记录")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_text_font = self.log_text.font()
        log_text_font.setFamily("Consolas")
        log_text_font.setPointSize(10)
        self.log_text.setFont(log_text_font)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
    
    def init_tab1(self):
        layout = QHBoxLayout(self.tab1)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(3)
        self.task_table.setHorizontalHeaderLabels(["关键字", "网址", "优化次数"])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 添加默认任务
        self.task_table.insertRow(0)
        self.task_table.setItem(0, 0, QTableWidgetItem("seo培训"))
        self.task_table.setItem(0, 1, QTableWidgetItem("jundaoseo8.com"))
        self.task_table.setItem(0, 2, QTableWidgetItem("100"))
        
        left_layout.addWidget(self.task_table)
        
        button_layout = QHBoxLayout()
        self.btn_first = QPushButton("|<<")
        self.btn_prev = QPushButton("<")
        self.btn_next = QPushButton(">")
        self.btn_last = QPushButton(">>|")
        self.btn_add = QPushButton("+")
        self.btn_edit = QPushButton("编辑")
        self.btn_delete = QPushButton("删除")
        self.btn_clear = QPushButton("清空")
        
        button_layout.addWidget(self.btn_first)
        button_layout.addWidget(self.btn_prev)
        button_layout.addWidget(self.btn_next)
        button_layout.addWidget(self.btn_last)
        button_layout.addWidget(self.btn_add)
        button_layout.addWidget(self.btn_edit)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_clear)
        left_layout.addLayout(button_layout)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        control_layout = QVBoxLayout()
        
        self.btn_start = QPushButton("开始任务")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_pause)
        
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("线程数"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setValue(30)
        self.thread_spin.setRange(1, 100)
        thread_layout.addWidget(self.thread_spin)
        control_layout.addLayout(thread_layout)
        
        proxy_layout = QHBoxLayout()
        self.btn_get_proxy = QPushButton("获取代理API")
        self.btn_get_proxy.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        proxy_layout.addWidget(self.btn_get_proxy)
        control_layout.addLayout(proxy_layout)
        
        # 代理状态标签
        self.proxy_status = QLabel("代理状态: 未获取")
        self.proxy_status.setStyleSheet("color: #666; font-size: 12px;")
        control_layout.addWidget(self.proxy_status)
        
        self.check_auto_start = QCheckBox("开机启动软件")
        self.check_auto_run = QCheckBox("启动自动开始")
        control_layout.addWidget(self.check_auto_start)
        control_layout.addWidget(self.check_auto_run)
        
        right_layout.addLayout(control_layout)
        
        batch_group = QGroupBox("批量添加关键字")
        batch_layout = QVBoxLayout(batch_group)
        
        batch_info = QLabel("格式：关键词 | 网址 | 优化次数")
        batch_info.setStyleSheet("color: #666; font-size: 12px;")
        batch_layout.addWidget(batch_info)
        
        self.batch_text = QTextEdit()
        self.batch_text.setPlaceholderText("淘宝|www.taobao.com|100\n百度|www.baidu.com|50")
        batch_layout.addWidget(self.batch_text)
        
        self.btn_batch_add = QPushButton("批量添加任务")
        self.btn_batch_add.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        batch_layout.addWidget(self.btn_batch_add)
        
        right_layout.addWidget(batch_group)
        
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 1)
        
        self.btn_start.clicked.connect(self.start_tasks)
        self.btn_pause.clicked.connect(self.pause_tasks)
        self.btn_add.clicked.connect(self.add_task)
        self.btn_edit.clicked.connect(self.edit_task)
        self.btn_delete.clicked.connect(self.delete_task)
        self.btn_clear.clicked.connect(self.clear_tasks)
        self.btn_batch_add.clicked.connect(self.batch_add_tasks)
        self.btn_get_proxy.clicked.connect(self.get_proxy)
    
    def init_tab2(self):
        layout = QVBoxLayout(self.tab2)
        
        top_layout = QHBoxLayout()
        
        keyword_layout = QHBoxLayout()
        keyword_layout.addWidget(QLabel("关键词:"))
        self.click_keyword = QLineEdit()
        self.click_keyword.setPlaceholderText("输入要搜索的关键词")
        keyword_layout.addWidget(self.click_keyword)
        top_layout.addLayout(keyword_layout)
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("目标网址:"))
        self.click_url = QLineEdit()
        self.click_url.setPlaceholderText("www.example.com")
        url_layout.addWidget(self.click_url)
        top_layout.addLayout(url_layout)
        
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("点击次数:"))
        self.click_count = QSpinBox()
        self.click_count.setValue(10)
        self.click_count.setRange(1, 100)
        count_layout.addWidget(self.click_count)
        top_layout.addLayout(count_layout)
        
        layout.addLayout(top_layout)
        
        # 代理API区域（放在空白处）
        proxy_api_layout = QVBoxLayout()
        
        api_url_layout = QHBoxLayout()
        api_url_layout.addWidget(QLabel("代理API地址:"))
        self.click_proxy_api_url = QLineEdit()
        self.click_proxy_api_url.setPlaceholderText("http://route.xiongmaodaili.com/xiongmao-web/api/glip?...")
        self.click_proxy_api_url.setText(self.proxy_manager.get_api_url())
        self.click_proxy_api_url.setStyleSheet("width: 600px;")
        api_url_layout.addWidget(self.click_proxy_api_url)
        proxy_api_layout.addLayout(api_url_layout)
        
        proxy_btn_layout = QHBoxLayout()
        self.btn_click_get_proxy = QPushButton("获取代理API")
        self.btn_click_get_proxy.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        proxy_btn_layout.addWidget(self.btn_click_get_proxy)
        
        self.click_proxy_status = QLabel("代理状态: 未获取")
        self.click_proxy_status.setStyleSheet("color: #666; font-size: 12px;")
        proxy_btn_layout.addWidget(self.click_proxy_status)
        
        proxy_api_layout.addLayout(proxy_btn_layout)
        layout.addLayout(proxy_api_layout)
        
        button_layout = QHBoxLayout()
        self.btn_start_click = QPushButton("开始点击")
        self.btn_start_click.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_stop_click = QPushButton("停止点击")
        self.btn_stop_click.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        button_layout.addWidget(self.btn_start_click)
        button_layout.addWidget(self.btn_stop_click)
        layout.addLayout(button_layout)
        
        self.btn_start_click.clicked.connect(self.start_baidu_click)
        self.btn_stop_click.clicked.connect(self.stop_baidu_click)
        self.btn_click_get_proxy.clicked.connect(self.get_click_proxy)
    
    def init_tab3(self):
        layout = QVBoxLayout(self.tab3)
        
        info_layout = QHBoxLayout()
        info_label = QLabel("本地任务文件路径:")
        info_layout.addWidget(info_label)
        self.task_file_path = QLineEdit(os.path.join(os.path.dirname(__file__), 'tasklist.txt'))
        info_layout.addWidget(self.task_file_path)
        layout.addLayout(info_layout)
        
        button_layout = QHBoxLayout()
        self.btn_load_task = QPushButton("从本地文件加载任务")
        self.btn_load_task.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        button_layout.addWidget(self.btn_load_task)
        layout.addLayout(button_layout)
        
        self.btn_load_task.clicked.connect(self.load_tasks_from_file)
    
    def get_proxy(self):
        success = self.proxy_manager.fetch_proxies()
        if success:
            count = self.proxy_manager.get_proxy_count()
            self.proxy_status.setText(f"代理状态: 已缓存 {count} 个")
            self.proxy_status.setStyleSheet("color: #4CAF50; font-size: 12px;")
            self.click_proxy_status.setText(f"代理状态: 已缓存 {count} 个")
            self.click_proxy_status.setStyleSheet("color: #4CAF50; font-size: 12px;")
            self.log(f"获取代理成功，已缓存 {count} 个代理")
        else:
            self.proxy_status.setText("代理状态: 获取失败")
            self.proxy_status.setStyleSheet("color: #f44336; font-size: 12px;")
            self.click_proxy_status.setText("代理状态: 获取失败")
            self.click_proxy_status.setStyleSheet("color: #f44336; font-size: 12px;")
            self.log("获取代理失败")
    
    def get_click_proxy(self):
        # 更新代理API地址
        api_url = self.click_proxy_api_url.text().strip()
        if api_url:
            self.proxy_manager.set_api_url(api_url)
            self.log(f"已更新代理API地址")
        self.get_proxy()
    
    def add_task(self):
        dialog = QDialog()
        dialog.setWindowTitle("添加任务")
        dialog.setGeometry(200, 200, 400, 200)
        layout = QFormLayout(dialog)
        
        keyword_edit = QLineEdit()
        url_edit = QLineEdit()
        count_edit = QSpinBox()
        count_edit.setValue(100)
        
        layout.addRow("关键字:", keyword_edit)
        layout.addRow("网址:", url_edit)
        layout.addRow("优化次数:", count_edit)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        
        if dialog.exec_() == QDialog.Accepted:
            keyword = keyword_edit.text().strip()
            url = url_edit.text().strip()
            count = count_edit.value()
            
            if keyword and url:
                row = self.task_table.rowCount()
                self.task_table.insertRow(row)
                self.task_table.setItem(row, 0, QTableWidgetItem(keyword))
                self.task_table.setItem(row, 1, QTableWidgetItem(url))
                self.task_table.setItem(row, 2, QTableWidgetItem(str(count)))
                self.log(f"已添加任务：{keyword} - {url}")
    
    def edit_task(self):
        selected = self.task_table.selectedItems()
        if selected:
            row = selected[0].row()
            keyword = self.task_table.item(row, 0).text()
            url = self.task_table.item(row, 1).text()
            count = int(self.task_table.item(row, 2).text())
            
            dialog = QDialog()
            dialog.setWindowTitle("编辑任务")
            dialog.setGeometry(200, 200, 400, 200)
            layout = QFormLayout(dialog)
            
            keyword_edit = QLineEdit(keyword)
            url_edit = QLineEdit(url)
            count_edit = QSpinBox()
            count_edit.setValue(count)
            
            layout.addRow("关键字:", keyword_edit)
            layout.addRow("网址:", url_edit)
            layout.addRow("优化次数:", count_edit)
            
            btn_layout = QHBoxLayout()
            btn_ok = QPushButton("确定")
            btn_cancel = QPushButton("取消")
            btn_layout.addWidget(btn_ok)
            btn_layout.addWidget(btn_cancel)
            layout.addRow(btn_layout)
            
            btn_ok.clicked.connect(dialog.accept)
            btn_cancel.clicked.connect(dialog.reject)
            
            if dialog.exec_() == QDialog.Accepted:
                self.task_table.setItem(row, 0, QTableWidgetItem(keyword_edit.text()))
                self.task_table.setItem(row, 1, QTableWidgetItem(url_edit.text()))
                self.task_table.setItem(row, 2, QTableWidgetItem(str(count_edit.value())))
                self.log(f"已修改任务：{keyword_edit.text()}")
    
    def delete_task(self):
        selected = self.task_table.selectedItems()
        if selected:
            row = selected[0].row()
            keyword = self.task_table.item(row, 0).text()
            self.task_table.removeRow(row)
            self.log(f"已删除任务：{keyword}")
    
    def clear_tasks(self):
        self.task_table.setRowCount(0)
        self.log("已清空所有任务")
    
    def batch_add_tasks(self):
        text = self.batch_text.toPlainText().strip()
        if not text:
            return
        
        lines = text.split('\n')
        added = 0
        
        for line in lines:
            line = line.strip()
            if line:
                parts = line.replace('｜', '|').replace('||', '|').split('|')
                if len(parts) >= 2:
                    keyword = parts[0].strip()
                    url = parts[1].strip()
                    count = int(parts[2].strip()) if len(parts) > 2 else 100
                    
                    if keyword and url:
                        row = self.task_table.rowCount()
                        self.task_table.insertRow(row)
                        self.task_table.setItem(row, 0, QTableWidgetItem(keyword))
                        self.task_table.setItem(row, 1, QTableWidgetItem(url))
                        self.task_table.setItem(row, 2, QTableWidgetItem(str(count)))
                        added += 1
        
        self.log(f"批量添加完成，共添加 {added} 个任务")
        self.batch_text.clear()
    
    def start_tasks(self):
        if self.running_threads:
            self.log("已有任务在运行中")
            return
        
        row_count = self.task_table.rowCount()
        if row_count == 0:
            self.log("没有任务可执行")
            return
        
        proxy_count = self.proxy_manager.get_proxy_count()
        if proxy_count > 0:
            self.log(f"开始执行任务... 使用缓存的 {proxy_count} 个代理（每个代理使用一次）")
        else:
            self.log("开始执行任务... 无代理")
        
        for row in range(row_count):
            keyword = self.task_table.item(row, 0).text()
            url = self.task_table.item(row, 1).text()
            count = int(self.task_table.item(row, 2).text())
            
            # 循环获取代理
            proxy_ip = self.proxy_manager.get_next_proxy()
            
            thread = TaskThread(keyword, url, count, proxy_ip, self.ua_list)
            thread.log_signal.connect(self.log)
            thread.task_complete.connect(self.on_task_complete)
            self.running_threads.append(thread)
            thread.start()
    
    def pause_tasks(self):
        for thread in self.running_threads:
            thread.stop()
        self.running_threads.clear()
        self.log("任务已暂停")
    
    def on_task_complete(self, result):
        pass
    
    def start_baidu_click(self):
        keyword = self.click_keyword.text().strip()
        url = self.click_url.text().strip()
        count = self.click_count.value()
        
        if not keyword or not url:
            self.log("请输入关键词和目标网址")
            return
        
        proxy_count = self.proxy_manager.get_proxy_count()
        if proxy_count > 0:
            self.log(f"开始百度点击任务：{keyword} -> {url}（使用缓存的 {proxy_count} 个代理）")
        else:
            self.log(f"开始百度点击任务：{keyword} -> {url}（无代理）")
        
        try:
            import traceback
            
            # 使用高级点击引擎
            click_engine = BaiduClickEngine()
            
            for i in range(count):
                try:
                    # 获取代理（循环使用）
                    proxy_ip = self.proxy_manager.get_next_proxy()
                    
                    self.log(f"[{time.strftime('%H:%M:%S')}] 第{i+1}/{count}次 - 开始执行点击")
                    
                    # 使用点击引擎执行点击
                    results = click_engine.run(keyword, url, proxy_ip, count=1)
                    
                    if results[0]:
                        self.log(f"[{time.strftime('%H:%M:%S')}] 第{i+1}/{count}次点击成功")
                    else:
                        self.log(f"[{time.strftime('%H:%M:%S')}] 第{i+1}/{count}次 - 未找到目标链接")
                    
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    self.log(f"[{time.strftime('%H:%M:%S')}] 第{i+1}/{count}次 - 错误：{str(e)}")
                    self.log(f"详细错误：{traceback.format_exc()}")
            
            self.log("百度点击任务完成")
            
        except ImportError as e:
            self.log(f"错误：导入模块失败 - {str(e)}")
            self.log("请确保已安装 selenium 和 pyautogui")
            self.log("安装命令：pip install selenium pyautogui")
            self.log(f"详细错误：{traceback.format_exc()}")
        except Exception as e:
            self.log(f"百度点击任务失败：{str(e)}")
            self.log(f"详细错误：{traceback.format_exc()}")
    
    def stop_baidu_click(self):
        self.log("百度点击任务已停止")
    
    def load_tasks_from_file(self):
        file_path = self.task_file_path.text().strip()
        
        if not os.path.exists(file_path):
            self.log(f"任务文件不存在：{file_path}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            added = 0
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.replace('｜', '|').replace('||', '|').split('|')
                    if len(parts) >= 2:
                        keyword = parts[0].strip()
                        url = parts[1].strip()
                        count = int(parts[2].strip()) if len(parts) > 2 else 100
                        
                        if keyword and url:
                            row = self.task_table.rowCount()
                            self.task_table.insertRow(row)
                            self.task_table.setItem(row, 0, QTableWidgetItem(keyword))
                            self.task_table.setItem(row, 1, QTableWidgetItem(url))
                            self.task_table.setItem(row, 2, QTableWidgetItem(str(count)))
                            added += 1
            
            self.log(f"从本地文件加载了 {added} 个任务")
            
        except Exception as e:
            self.log(f"加载任务文件失败：{str(e)}")
    
    def log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())