import sys
import os
import base64
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QFrame, 
                             QTextEdit, QSpinBox, QGroupBox)
from PyQt5.QtGui import QFont, QColor, QPixmap
from PyQt5.QtCore import Qt, QEvent, QThread, pyqtSignal
import json
from pynput import keyboard
import time
from datetime import datetime
import requests

# 条件付きインポート
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import PIL.Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# プロバイダー設定
PROVIDERS = {
    "Gemini": {
        "base_url": None,
        "api_type": "gemini",
        "default_models": ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"],
        "vision_keywords": ["vision", "pro", "flash", "2.0"],
    },
    "GitHub Models": {
        "base_url": "https://models.inference.ai.azure.com",
        "api_type": "openai",
        "default_models": ["gpt-4o", "gpt-4o-mini", "o1", "o1-mini", "o1-preview"],
        "vision_keywords": ["gpt-4o", "gpt-4-turbo", "o1"],
        "models_endpoint": None,
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_type": "openai",
        "default_models": [
            "google/gemini-2.0-flash-exp:free",
            "google/gemini-exp-1206:free",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        "vision_keywords": ["vision", "gpt-4", "claude-3", "gemini"],
        "models_endpoint": "https://openrouter.ai/api/v1/models",
    },
    "Cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_type": "openai",
        "default_models": ["llama-3.3-70b", "llama3.1-70b", "llama3.1-8b"],
        "vision_keywords": [],
        "models_endpoint": "https://api.cerebras.ai/v1/models",
    },
}


class ImageDropTextEdit(QTextEdit):
    """画像ドロップをサポートするカスタムTextEdit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.dropped_image_path = None
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if self._is_image_file(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return
        event.ignore()
        
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if self._is_image_file(file_path):
                    self.dropped_image_path = file_path
                    self._display_image(file_path)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)
        
    def _is_image_file(self, file_path):
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        _, ext = os.path.splitext(file_path.lower())
        return ext in image_extensions
        
    def _display_image(self, file_path):
        self.clear()
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.setPlainText(f"画像の読み込みに失敗: {file_path}")
            return
            
        max_w = self.width() - 20
        max_h = self.height() - 20
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        cursor = self.textCursor()
        cursor.insertHtml(f'<p><img src="{file_path}" width="{pixmap.width()}" height="{pixmap.height()}"></p>')
        cursor.insertHtml(f'<p style="color: #888;">📷 {os.path.basename(file_path)}</p>')
        
    def get_dropped_image_path(self):
        return self.dropped_image_path
        
    def clear_image(self):
        self.dropped_image_path = None
        self.clear()


class ModelFetchWorker(QThread):
    """モデルリスト取得用ワーカー"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, provider, api_key, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.api_key = api_key
        
    def run(self):
        try:
            models = self._fetch_models()
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(str(e))
            
    def _fetch_models(self):
        provider_config = PROVIDERS[self.provider]
        
        if self.provider == "Gemini":
            return self._fetch_gemini_models()
        elif self.provider == "OpenRouter":
            return self._fetch_openrouter_models()
        elif self.provider == "Cerebras":
            return self._fetch_openai_compatible_models(provider_config)
        elif self.provider == "GitHub Models":
            return provider_config['default_models']
        
        return provider_config.get('default_models', [])
    
    def _fetch_gemini_models(self):
        if not GENAI_AVAILABLE or not self.api_key:
            return PROVIDERS["Gemini"]['default_models']
        
        try:
            genai.configure(api_key=self.api_key)
            models = genai.list_models()
            model_names = []
            for model in models:
                if "generateContent" in model.supported_generation_methods:
                    name = model.name
                    if name.startswith("models/"):
                        name = name[7:]
                    model_names.append(name)
            return model_names if model_names else PROVIDERS["Gemini"]['default_models']
        except Exception:
            return PROVIDERS["Gemini"]['default_models']
    
    def _fetch_openrouter_models(self):
        if not self.api_key:
            return PROVIDERS["OpenRouter"]['default_models']
        
        try:
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                models = [m['id'] for m in data.get('data', [])]
                free_models = [m for m in models if ':free' in m]
                paid_models = [m for m in models if ':free' not in m]
                return free_models + paid_models if models else PROVIDERS["OpenRouter"]['default_models']
        except Exception:
            pass
        return PROVIDERS["OpenRouter"]['default_models']
    
    def _fetch_openai_compatible_models(self, provider_config):
        endpoint = provider_config.get('models_endpoint')
        if not endpoint or not self.api_key:
            return provider_config['default_models']
        
        try:
            response = requests.get(
                endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                models = [m['id'] for m in data.get('data', [])]
                return models if models else provider_config['default_models']
        except Exception:
            pass
        return provider_config['default_models']


class APIWorker(QThread):
    """API呼び出し用ワーカー"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, provider, api_key, model, messages, image_path=None, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.messages = messages
        self.image_path = image_path
        
    def run(self):
        try:
            if PROVIDERS[self.provider]['api_type'] == 'gemini':
                result = self._call_gemini()
            else:
                result = self._call_openai_compatible()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
    
    def _call_gemini(self):
        if not GENAI_AVAILABLE:
            raise Exception("google-generativeai パッケージがインストールされていません")
        
        genai.configure(api_key=self.api_key)
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        model = genai.GenerativeModel(self.model, safety_settings=safety_settings)
        
        prompt_parts = []
        for msg in self.messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                prompt_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get('type') == 'text':
                        prompt_parts.append(part.get('text', ''))
        
        prompt = "\n".join(prompt_parts)
        
        if self.image_path and PIL_AVAILABLE:
            image = PIL.Image.open(self.image_path)
            response = model.generate_content([prompt, image])
        else:
            response = model.generate_content(prompt)
        
        result = ""
        for part in response.parts:
            if hasattr(part, 'text'):
                result += part.text
        return result
    
    def _call_openai_compatible(self):
        if not OPENAI_AVAILABLE:
            raise Exception("openai パッケージがインストールされていません")
        
        provider_config = PROVIDERS[self.provider]
        
        headers = {}
        if self.provider == "OpenRouter":
            headers = {
                "HTTP-Referer": "https://github.com/translator-app",
                "X-Title": "Multi-Provider Translator"
            }
        
        client = OpenAI(
            api_key=self.api_key,
            base_url=provider_config['base_url'],
            default_headers=headers if headers else None
        )
        
        messages = self.messages
        if self.image_path:
            base64_image = self._encode_image()
            mime_type = self._get_mime_type()
            
            text_content = ""
            for msg in self.messages:
                if isinstance(msg.get('content'), str):
                    text_content = msg['content']
                    break
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": text_content},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                    }
                ]
            }]
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
        )
        
        return response.choices[0].message.content
    
    def _encode_image(self):
        with open(self.image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _get_mime_type(self):
        ext = os.path.splitext(self.image_path.lower())[1]
        return {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(ext, 'image/png')


class TranslatorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.window_config = self.load_window_config()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize_corner_size = 20
        self.resizing = False
        self.current_worker = None
        self.model_cache = {}
        
        # ボタン参照を先に初期化
        self.img_translate_btn = None
        self.describe_btn = None
        self.translate_btn = None
        self.summarize_btn = None
        
        self.initUI()
        self.start_hotkey_listener()
        self.refresh_models()

    def load_config(self):
        default_config = {
            'provider': 'Gemini',
            'api_keys': {
                'Gemini': '',
                'GitHub Models': '',
                'OpenRouter': '',
                'Cerebras': '',
            },
            'selected_models': {
                'Gemini': 'gemini-2.0-flash-exp',
                'GitHub Models': 'gpt-4o-mini',
                'OpenRouter': 'google/gemini-2.0-flash-exp:free',
                'Cerebras': 'llama-3.3-70b',
            },
            'font_size': 12,
            'translate_prompt': "Translate the following text to Japanese. Output only the translation:\n\n{text}",
            'summarize_prompt': "Summarize the following text in Japanese:\n\n{text}",
            'image_translate_prompt': "この画像内のテキストを全て抽出し、日本語に翻訳してください。元テキストと翻訳の両方を表示してください。",
            'image_describe_prompt': "この画像の内容を詳しく日本語で説明してください。",
        }
        
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if k not in config[key]:
                            config[key][k] = v
            return config
        except FileNotFoundError:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            return default_config

    def load_window_config(self):
        try:
            with open('window_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'width': 850, 'height': 650, 'x': 100, 'y': 100}

    def save_config(self):
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def save_window_config(self):
        config = {'width': self.width(), 'height': self.height(), 'x': self.x(), 'y': self.y()}
        with open('window_config.json', 'w') as f:
            json.dump(config, f, indent=4)

    def initUI(self):
        self.setStyleSheet("""
            QWidget { background-color: #2B2B2B; color: #FFFFFF; }
            QFrame { border: 1px solid #3C3F41; }
            QTextEdit { background-color: #3C3F41; color: #FFFFFF; border: 1px solid #555; }
            QPushButton { background-color: #4C5052; color: #FFFFFF; border: 1px solid #555; }
            QPushButton:hover { background-color: #5C6062; }
            QPushButton:disabled { background-color: #3C3F41; color: #888; }
            QComboBox { background-color: #3C3F41; color: #FFFFFF; border: 1px solid #555; padding: 5px; }
            QComboBox QAbstractItemView { background-color: #3C3F41; color: #FFFFFF; selection-background-color: #2979ff; }
            QSpinBox { background-color: #3C3F41; color: #FFFFFF; border: 1px solid #555; }
            QLabel { border: none; }
            QGroupBox { color: #FFFFFF; border: 1px solid #555; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        
        self.setWindowTitle("Multi-Provider Translator")
        self.setGeometry(
            self.window_config['x'], self.window_config['y'],
            self.window_config['width'], self.window_config['height']
        )
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)

        # タイトルバー
        self._create_title_bar(layout)
        
        # ボタンフレームを先に作成（ボタン参照が必要なため）
        self._create_button_frame(layout)
        
        # コントロールフレーム
        self._create_control_frame(layout)
        
        # ソースエリア
        self._create_source_area(layout)
        
        # 結果エリア
        self._create_result_area(layout)
        
        # ボタンフレームをレイアウトの最後に移動
        self._move_button_frame_to_bottom(layout)

        self.apply_font_size()
        self.show()

    def _create_title_bar(self, layout):
        title_bar = QFrame(self)
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("background-color: #1E1E1E; border: none;")
        layout.addWidget(title_bar)

        btn_style = "background-color: transparent; color: #FFFFFF; border: none; font-size: 14px;"
        btn_hover = "QPushButton:hover { background-color: #3C3F41; }"
        
        close_btn = QPushButton("✕", title_bar)
        close_btn.setFixedSize(45, 30)
        close_btn.setStyleSheet(btn_style + "QPushButton:hover { background-color: #E81123; }")
        close_btn.clicked.connect(self.close)

        max_btn = QPushButton("□", title_bar)
        max_btn.setFixedSize(45, 30)
        max_btn.setStyleSheet(btn_style + btn_hover)
        max_btn.clicked.connect(self.toggle_maximize)

        min_btn = QPushButton("─", title_bar)
        min_btn.setFixedSize(45, 30)
        min_btn.setStyleSheet(btn_style + btn_hover)
        min_btn.clicked.connect(self.showMinimized)

        def update_positions():
            w = title_bar.width()
            close_btn.move(w - 45, 0)
            max_btn.move(w - 90, 0)
            min_btn.move(w - 135, 0)

        title_bar.resizeEvent = lambda e: update_positions()
        update_positions()

        title_label = QLabel("🌐 Multi-Provider Translator", title_bar)
        title_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        title_label.move(10, 5)

        title_bar.mousePressEvent = self._title_press
        title_bar.mouseMoveEvent = self._title_move

    def _create_button_frame(self, layout):
        """ボタンフレームを作成（参照を先に確立）"""
        self.button_frame = QFrame(self)
        self.button_frame.setFixedHeight(60)
        self.button_frame.setStyleSheet("background-color: #FF8C00; border: none; border-radius: 5px;")
        
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 5, 10, 5)
        self.button_frame.setLayout(button_layout)

        btn_style = """
            QPushButton {
                background-color: rgba(255,255,255,0.1);
                color: #FFFFFF;
                font-size: 20px;
                border-radius: 22px;
                border: 2px solid rgba(255,255,255,0.3);
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.5);
            }
            QPushButton:disabled {
                background-color: rgba(0,0,0,0.3);
                color: rgba(255,255,255,0.5);
            }
        """

        self.translate_btn = QPushButton("🌍")
        self.translate_btn.setFixedSize(45, 45)
        self.translate_btn.setStyleSheet(btn_style)
        self.translate_btn.setToolTip("翻訳 (テキスト)")
        self.translate_btn.clicked.connect(self.translate_text)
        button_layout.addWidget(self.translate_btn)

        self.img_translate_btn = QPushButton("🖼️")
        self.img_translate_btn.setFixedSize(45, 45)
        self.img_translate_btn.setStyleSheet(btn_style)
        self.img_translate_btn.setToolTip("画像翻訳")
        self.img_translate_btn.clicked.connect(self.translate_image)
        button_layout.addWidget(self.img_translate_btn)

        self.summarize_btn = QPushButton("📝")
        self.summarize_btn.setFixedSize(45, 45)
        self.summarize_btn.setStyleSheet(btn_style)
        self.summarize_btn.setToolTip("要約")
        self.summarize_btn.clicked.connect(self.summarize_text)
        button_layout.addWidget(self.summarize_btn)

        self.describe_btn = QPushButton("🔍")
        self.describe_btn.setFixedSize(45, 45)
        self.describe_btn.setStyleSheet(btn_style)
        self.describe_btn.setToolTip("画像説明")
        self.describe_btn.clicked.connect(self.describe_image)
        button_layout.addWidget(self.describe_btn)

        button_layout.addStretch()

        shortcut_label = QLabel("Ctrl+Alt+T: クイック翻訳")
        shortcut_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")
        button_layout.addWidget(shortcut_label)

    def _move_button_frame_to_bottom(self, layout):
        """ボタンフレームをレイアウトの最後に配置"""
        layout.addWidget(self.button_frame)

    def _create_control_frame(self, layout):
        control_frame = QFrame(self)
        control_frame.setStyleSheet("border: none;")
        layout.addWidget(control_frame)
        
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_frame.setLayout(control_layout)

        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setFixedWidth(100)
        settings_btn.clicked.connect(self.open_settings_dialog)
        control_layout.addWidget(settings_btn)

        control_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS.keys())
        self.provider_combo.setCurrentText(self.config['provider'])
        self.provider_combo.setFixedWidth(120)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        control_layout.addWidget(self.provider_combo)

        control_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(250)
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._update_model_combo()
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        control_layout.addWidget(self.model_combo)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(35)
        refresh_btn.setToolTip("モデルリストを更新")
        refresh_btn.clicked.connect(self.refresh_models)
        control_layout.addWidget(refresh_btn)

        control_layout.addWidget(QLabel("Font:"))
        self.font_spinner = QSpinBox()
        self.font_spinner.setRange(8, 24)
        self.font_spinner.setValue(self.config.get('font_size', 12))
        self.font_spinner.setFixedWidth(50)
        self.font_spinner.valueChanged.connect(self.update_font_size)
        control_layout.addWidget(self.font_spinner)

        control_layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        control_layout.addWidget(self.status_label)

    def _create_source_area(self, layout):
        source_frame = QFrame(self)
        source_frame.setStyleSheet("border: none;")
        layout.addWidget(source_frame)
        
        source_layout = QVBoxLayout()
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_frame.setLayout(source_layout)

        header = QHBoxLayout()
        header.addWidget(QLabel("📝 Source (テキスト入力 または 画像ドロップ)"))
        
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setFixedSize(80, 25)
        clear_btn.clicked.connect(self.clear_source)
        header.addWidget(clear_btn)
        header.addStretch()
        source_layout.addLayout(header)

        self.source_text = ImageDropTextEdit()
        self.source_text.setMinimumHeight(120)
        source_layout.addWidget(self.source_text)

    def _create_result_area(self, layout):
        result_frame = QFrame(self)
        result_frame.setStyleSheet("border: none;")
        layout.addWidget(result_frame)
        
        result_layout = QVBoxLayout()
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_frame.setLayout(result_layout)

        header = QHBoxLayout()
        header.addWidget(QLabel("📋 Result"))
        
        copy_btn = QPushButton("📋 Copy")
        copy_btn.setFixedSize(80, 25)
        copy_btn.clicked.connect(self.copy_result)
        header.addWidget(copy_btn)
        header.addStretch()
        result_layout.addLayout(header)

        self.result_text = QTextEdit()
        self.result_text.setMinimumHeight(120)
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)

    def _update_model_combo(self):
        provider = self.config['provider']
        
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        
        models = self.model_cache.get(provider, PROVIDERS[provider]['default_models'])
        self.model_combo.addItems(models)
        
        saved = self.config['selected_models'].get(provider, '')
        if saved and saved in models:
            self.model_combo.setCurrentText(saved)
        
        self.model_combo.blockSignals(False)
        self._update_vision_buttons()

    def _update_vision_buttons(self):
        """ビジョン対応ボタンの有効/無効を更新"""
        # ボタンがまだ作成されていない場合は何もしない
        if self.img_translate_btn is None or self.describe_btn is None:
            return
            
        provider = self.config['provider']
        model = self.model_combo.currentText() if hasattr(self, 'model_combo') else ''
        keywords = PROVIDERS[provider].get('vision_keywords', [])
        
        supports_vision = any(kw.lower() in model.lower() for kw in keywords)
        self.img_translate_btn.setEnabled(supports_vision)
        self.describe_btn.setEnabled(supports_vision)

    def on_provider_changed(self, provider):
        self.config['provider'] = provider
        self._update_model_combo()
        self.save_config()
        
        if provider not in self.model_cache:
            self.refresh_models()

    def on_model_changed(self, model):
        if model:
            provider = self.config['provider']
            self.config['selected_models'][provider] = model
            self._update_vision_buttons()
            self.save_config()

    def refresh_models(self):
        provider = self.config['provider']
        api_key = self.config['api_keys'].get(provider, '')
        
        if not api_key:
            self.status_label.setText("⚠️ APIキー未設定")
            return
        
        self.status_label.setText("🔄 モデル取得中...")
        
        self.model_worker = ModelFetchWorker(provider, api_key)
        self.model_worker.finished.connect(self._on_models_fetched)
        self.model_worker.error.connect(self._on_models_error)
        self.model_worker.start()

    def _on_models_fetched(self, models):
        provider = self.config['provider']
        self.model_cache[provider] = models
        self._update_model_combo()
        self.status_label.setText(f"✓ {len(models)} models")

    def _on_models_error(self, error):
        self.status_label.setText(f"⚠️ {error[:30]}")

    def _title_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _title_move(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            br = self.rect().bottomRight()
            if pos.x() >= br.x() - self.resize_corner_size and pos.y() >= br.y() - self.resize_corner_size:
                self.resizing = True
                self.resize_start = pos
                self.resize_geo = self.geometry()
            else:
                self.resizing = False

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.resizing:
            diff = event.pos() - self.resize_start
            self.resize(
                max(self.minimumWidth(), self.resize_geo.width() + diff.x()),
                max(self.minimumHeight(), self.resize_geo.height() + diff.y())
            )

    def mouseReleaseEvent(self, event):
        self.resizing = False
        self.save_window_config()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QPen
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#555")))
        br = self.rect().bottomRight()
        for i in range(3):
            painter.drawLine(
                br.x() - self.resize_corner_size + i*5, br.y(),
                br.x(), br.y() - self.resize_corner_size + i*5
            )

    def toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def update_font_size(self):
        self.config['font_size'] = self.font_spinner.value()
        self.apply_font_size()
        self.save_config()

    def apply_font_size(self):
        size = self.config.get('font_size', 12)
        font = QFont()
        font.setPointSize(size)
        style = f"background-color: #3C3F41; color: #FFFFFF; font-size: {size}pt;"
        
        self.source_text.setStyleSheet(style)
        self.source_text.setFont(font)
        self.result_text.setStyleSheet(style)
        self.result_text.setFont(font)

    def clear_source(self):
        self.source_text.clear_image()

    def copy_result(self):
        text = self.result_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("✓ コピーしました")

    def _set_buttons_enabled(self, enabled):
        if self.translate_btn:
            self.translate_btn.setEnabled(enabled)
        if self.summarize_btn:
            self.summarize_btn.setEnabled(enabled)
        if enabled:
            self._update_vision_buttons()
        else:
            if self.img_translate_btn:
                self.img_translate_btn.setEnabled(False)
            if self.describe_btn:
                self.describe_btn.setEnabled(False)

    def _call_api(self, prompt, image_path=None, operation=""):
        provider = self.config['provider']
        api_key = self.config['api_keys'].get(provider, '')
        model = self.model_combo.currentText()
        
        if not api_key:
            self.result_text.setText("❌ APIキーが設定されていません。\nSettingsでAPIキーを設定してください。")
            return
        
        if not model:
            self.result_text.setText("❌ モデルが選択されていません。")
            return
        
        self.result_text.setText("⏳ 処理中...")
        self._set_buttons_enabled(False)
        self.status_label.setText(f"🔄 {operation}...")
        
        messages = [{"role": "user", "content": prompt}]
        
        self.current_worker = APIWorker(provider, api_key, model, messages, image_path)
        self.current_worker.finished.connect(lambda r: self._on_api_success(r, operation))
        self.current_worker.error.connect(self._on_api_error)
        self.current_worker.start()

    def _on_api_success(self, result, operation):
        self._set_buttons_enabled(True)
        self.result_text.setText(result)
        self.status_label.setText(f"✓ {operation}完了")
        
        source = self.source_text.toPlainText() or "[Image]"
        self.save_log(source, result, operation)

    def _on_api_error(self, error):
        self._set_buttons_enabled(True)
        self.result_text.setText(f"❌ エラー:\n{error}")
        self.status_label.setText("⚠️ エラー")

    def translate_text(self):
        text = self.source_text.toPlainText().strip()
        if not text:
            self.result_text.setText("翻訳するテキストを入力してください。")
            return
        
        prompt = self.config['translate_prompt'].format(text=text)
        self._call_api(prompt, operation="翻訳")

    def summarize_text(self):
        text = self.source_text.toPlainText().strip()
        if not text:
            self.result_text.setText("要約するテキストを入力してください。")
            return
        
        prompt = self.config['summarize_prompt'].format(text=text)
        self._call_api(prompt, operation="要約")

    def translate_image(self):
        image_path = self.source_text.get_dropped_image_path()
        if not image_path:
            self.result_text.setText("画像をドロップしてください。")
            return
        
        prompt = self.config['image_translate_prompt']
        self._call_api(prompt, image_path, "画像翻訳")

    def describe_image(self):
        image_path = self.source_text.get_dropped_image_path()
        if not image_path:
            self.result_text.setText("画像をドロップしてください。")
            return
        
        prompt = self.config['image_describe_prompt']
        self._call_api(prompt, image_path, "画像説明")

    def open_settings_dialog(self):
        dialog = QWidget()
        dialog.setWindowTitle("Settings")
        dialog.setGeometry(200, 200, 600, 750)
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        dialog.setLayout(layout)

        # APIキー設定
        api_group = QGroupBox("🔑 API Keys")
        api_layout = QVBoxLayout()
        api_group.setLayout(api_layout)

        self.api_entries = {}
        for provider in PROVIDERS.keys():
            h = QHBoxLayout()
            label = QLabel(f"{provider}:")
            label.setFixedWidth(120)
            entry = QLineEdit()
            entry.setEchoMode(QLineEdit.Password)
            entry.setText(self.config['api_keys'].get(provider, ''))
            entry.setPlaceholderText(f"Enter {provider} API key...")
            self.api_entries[provider] = entry
            
            show_btn = QPushButton("👁")
            show_btn.setFixedWidth(30)
            show_btn.setCheckable(True)
            show_btn.toggled.connect(lambda checked, e=entry: e.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password))
            
            h.addWidget(label)
            h.addWidget(entry)
            h.addWidget(show_btn)
            api_layout.addLayout(h)

        layout.addWidget(api_group)

        # プロンプト設定
        prompt_group = QGroupBox("💬 Prompts")
        prompt_layout = QVBoxLayout()
        prompt_group.setLayout(prompt_layout)

        prompts = [
            ("translate_prompt", "翻訳 ({text}がソーステキスト):"),
            ("summarize_prompt", "要約:"),
            ("image_translate_prompt", "画像翻訳:"),
            ("image_describe_prompt", "画像説明:"),
        ]

        self.prompt_entries = {}
        for key, label_text in prompts:
            prompt_layout.addWidget(QLabel(label_text))
            entry = QTextEdit()
            entry.setPlainText(self.config.get(key, ''))
            entry.setMaximumHeight(60)
            self.prompt_entries[key] = entry
            prompt_layout.addWidget(entry)

        layout.addWidget(prompt_group)

        # 保存ボタン
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("background-color: #1E90FF; padding: 10px; font-weight: bold;")
        save_btn.clicked.connect(lambda: self._save_settings(dialog))
        layout.addWidget(save_btn)

        dialog.show()
        self.settings_dialog = dialog

    def _save_settings(self, dialog):
        for provider, entry in self.api_entries.items():
            self.config['api_keys'][provider] = entry.text()
        
        for key, entry in self.prompt_entries.items():
            self.config[key] = entry.toPlainText()
        
        self.save_config()
        self.status_label.setText("✓ 設定を保存しました")
        
        self.model_cache.clear()
        self.refresh_models()
        
        dialog.close()

    def save_log(self, source, result, operation):
        try:
            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base_dir, 'log')
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            provider = self.config['provider']
            model = self.model_combo.currentText()
            
            content = f"""[{operation}]
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Provider: {provider}
Model: {model}

=== Source ===
{source}

=== Result ===
{result}
"""
            with open(os.path.join(log_dir, f"{timestamp}_{operation}.txt"), 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Log error: {e}")

    def start_hotkey_listener(self):
        def on_activate():
            kb = keyboard.Controller()
            kb.release(keyboard.Key.ctrl)
            kb.release(keyboard.Key.alt)
            kb.release('t')
            QApplication.instance().postEvent(self, QEvent(QEvent.Type.User))

        self.hotkey = keyboard.GlobalHotKeys({'<ctrl>+<alt>+t': on_activate})
        self.hotkey.start()

    def event(self, event):
        if event.type() == QEvent.Type.User:
            self._quick_translate()
            return True
        return super().event(event)

    def _quick_translate(self):
        try:
            clipboard = QApplication.clipboard()
            old = clipboard.text()
            
            kb = keyboard.Controller()
            with kb.pressed(keyboard.Key.ctrl):
                kb.tap('c')
            
            time.sleep(0.2)
            text = clipboard.text()
            
            if text and text != old:
                self.source_text.clear()
                self.source_text.setPlainText(text)
                self.translate_text()
                self.activateWindow()
                self.raise_()
        except Exception as e:
            print(f"Quick translate error: {e}")

    def closeEvent(self, event):
        self.save_window_config()
        if hasattr(self, 'hotkey'):
            self.hotkey.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    translator = TranslatorApp()
    sys.exit(app.exec_())
