global SOURCE_FOLDER
import os
import time
import requests
import shutil
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit, QLineEdit, QProgressBar, QFileDialog, QHBoxLayout
from PyQt6.QtCore import Qt, QMetaObject, QThread, pyqtSignal
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
DEFAULT_EMAIL = 'username'
DEFAULT_PASSWORD = 'password'
UPLOAD_URL = 'https://easytoyou.eu/decoder/ic11php74'
LOGIN_URL = 'https://easytoyou.eu/login'
SOURCE_FOLDER = os.getcwd()
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'tmp')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

class EasyToYouDecoder(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.driver = None
        self.running = False

    def log(self, message):
        self.log_signal.emit(message)

    def start_browser(self):
        self.log('🚀 Iniciando Selenium...')
        chrome_prefs = {'download.default_directory': DOWNLOAD_FOLDER, 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': True}
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920x1080')
        options.add_experimental_option('prefs', chrome_prefs)
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def login_easytoyou(self, email, password):
        self.log('🔄 A abrir a página de login...')
        self.driver.get(LOGIN_URL)
        time.sleep(3)
        self.log('🔑 A inserir credenciais...')
        self.driver.find_element(By.NAME, 'loginname').send_keys(email)
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.NAME, 'password').send_keys(Keys.RETURN)
        start_time = time.time()
        if time.time() - start_time < 5:
            QApplication.processEvents()
            time.sleep(0.5)
        if 'Logout' not in self.driver.page_source:
            self.log('❌ Erro ao autenticar!')
            return False
        self.log('✔ Login bem-sucedido!')
        return True

    def find_encoded_php_files(self, source_folder):
        php_files = []
        for root, _, files in os.walk(source_folder):
            for file in files:
                if not file.endswith('.php'):
                    continue
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    content = f.read()
                    if b'ionCube Loader' in content:
                        php_files.append(file_path)
        return php_files

    def upload_php_file(self, file_path):
        self.log(f'⬆️ A fazer upload do ficheiro: {os.path.basename(file_path)}')
        self.driver.get(UPLOAD_URL)
        time.sleep(3)
        try:
            file_input = self.driver.find_element(By.ID, 'uploadfileblue')
            file_input.send_keys(os.path.abspath(file_path))
            decode_button = self.driver.find_element(By.NAME, 'submit')
            decode_button.click()
            time.sleep(10)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            link_element = soup.find('a', href=True, string=lambda text: text and 'https://easytoyou.eu/download' in text)
            if link_element:
                download_link = link_element['href']
                self.log('✔ Upload e decode bem-sucedidos!')
                return download_link
            self.log('❌ Falha ao obter link de download!')
        except Exception as e:
            self.log(f'❌ Erro no upload com Selenium: {e}')

    def download_file(self, download_link, filename):
        self.log(f'⬇️ A descarregar: {download_link}')
        self.driver.get(download_link)
        start_time = time.time()
        if time.time() - start_time < 5:
            QApplication.processEvents()
            time.sleep(0.5)
        downloaded_file = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(downloaded_file):
            self.log(f'✔ Download concluído: {downloaded_file}')
            return downloaded_file
        self.log(f'❌ Erro: O ficheiro {filename} não foi encontrado!')

    def replace_file(self, original, new):
        if os.path.exists(new):
            shutil.move(new, original)
            self.log(f'✔ Substituído com sucesso: {original}')
        else:
            self.log(f'❌ Erro: O ficheiro {new} não existe para substituir!')

    def run(self):
        self.running = True
        self.start_browser()
        self.login_easytoyou(DEFAULT_EMAIL, DEFAULT_PASSWORD)
        php_files = self.find_encoded_php_files(SOURCE_FOLDER)
        if not php_files:
            self.log('✔ Nenhum ficheiro codificado encontrado.')
            return None
        total_files = len(php_files)
        self.log(f'🔎 {total_files} ficheiro(s) codificado(s) encontrado(s).')
        for index, file_path in enumerate(php_files):
            if not self.running:
                self.log('❌ Processo interrompido pelo utilizador.')
                return None
            download_link = self.upload_php_file(file_path)
            if download_link:
                filename = os.path.basename(file_path)
                downloaded_file = self.download_file(download_link, filename)
                if downloaded_file:
                    self.replace_file(file_path, downloaded_file)
            self.progress_signal.emit(int((index + 1) / total_files * 100))
        else:
            self.log('🎉 Todos os ficheiros foram processados!')

    def stop(self):
        self.running = False

class DecoderApp(QWidget):

    def __init__(self):
        super().__init__()
        self.decoder = EasyToYouDecoder()
        self.decoder.log_signal.connect(self.log)
        self.decoder.progress_signal.connect(self.update_progress)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QVBoxLayout()
        self.email_input = QLineEdit(DEFAULT_EMAIL)
        self.password_input = QLineEdit(DEFAULT_PASSWORD)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.source_folder_btn = QPushButton('📂 Pasta de Origem')
        form_layout.addWidget(QLabel('✉️ Username:'))
        form_layout.addWidget(self.email_input)
        form_layout.addWidget(QLabel('🔒 Password:'))
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(self.source_folder_btn)
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton('🚀 Start')
        self.stop_btn = QPushButton('🛑 Parar')
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet('background-color: #f4f4f4; color: #333; font-size: 12px;')
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(QLabel('📜 Logs:'))
        main_layout.addWidget(self.log_area)
        self.source_folder_btn.clicked.connect(self.select_source_folder)
        self.start_btn.clicked.connect(self.start_decoding)
        self.stop_btn.clicked.connect(self.stop_decoding)
        self.setLayout(main_layout)
        self.setWindowTitle('EasyToYou Decoder')
        self.setFixedSize(500, 450)
        self.setStyleSheet('\n            QPushButton {\n                padding: 8px;\n                font-size: 14px;\n                border-radius: 5px;\n            }\n            QPushButton:hover {\n                background-color: #0078D7;\n                color: white;\n            }\n            QLineEdit, QTextEdit {\n                border: 1px solid #ccc;\n                border-radius: 5px;\n                padding: 5px;\n            }\n            QLabel {\n                font-weight: bold;\n            }\n        ')

    def log(self, message):
        self.log_area.append(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def select_source_folder(self):
        global SOURCE_FOLDER
        SOURCE_FOLDER = QFileDialog.getExistingDirectory(self, 'Selecionar Pasta de Origem')
        self.log(f'📂 Pasta selecionada: {SOURCE_FOLDER}')

    def start_decoding(self):
        self.decoder.start()

    def stop_decoding(self):
        self.decoder.stop()
app = QApplication([])
window = DecoderApp()
window.show()
app.exec()
