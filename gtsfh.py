import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QFrame, 
                             QTextEdit, QSpinBox, QScrollArea)
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage
from PyQt5.QtCore import Qt, QEvent, QMimeData
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
from pynput import keyboard
import time
from datetime import datetime
import PIL.Image


class ImageDropTextEdit(QTextEdit):
    """画像ドロップをサポートするカスタムTextEdit"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_app = None
        self.dropped_image_path = None
        
    def set_parent_app(self, app):
        self.parent_app = app
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # 画像ファイルかどうかを確認
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if self._is_image_file(file_path):
                    event.acceptProposedAction()
                    return
        # テキストの場合も受け入れる
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
        # テキストの場合は通常の処理
        super().dropEvent(event)
        
    def _is_image_file(self, file_path):
        """ファイルが画像かどうかを確認"""
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        _, ext = os.path.splitext(file_path.lower())
        return ext in image_extensions
        
    def _display_image(self, file_path):
        """画像をテキストエリアに表示"""
        self.clear()
        
        # 画像を読み込んでリサイズ
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.setPlainText(f"画像の読み込みに失敗しました: {file_path}")
            return
            
        # テキストエリアのサイズに合わせてスケール
        max_width = self.width() - 20
        max_height = self.height() - 20
        
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, 
                                   Qt.KeepAspectRatio, 
                                   Qt.SmoothTransformation)
        
        # HTMLで画像を表示
        cursor = self.textCursor()
        cursor.insertHtml(f'<p><img src="{file_path}" width="{pixmap.width()}" height="{pixmap.height()}"></p>')
        cursor.insertHtml(f'<p style="color: #888888;">📷 {os.path.basename(file_path)}</p>')
        
    def get_dropped_image_path(self):
        """ドロップされた画像のパスを取得"""
        return self.dropped_image_path
        
    def clear_image(self):
        """画像をクリア"""
        self.dropped_image_path = None
        self.clear()


class TranslatorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.window_config = self.load_window_config()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize_corner_size = 20
        self.resizing = False
        self.initUI()
        self.setup_gemini()
        self.start_hotkey_listener()

    def load_window_config(self):
        try:
            with open('window_config.json', 'r') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            return {
                'width': 800,
                'height': 600,
                'x': 100,
                'y': 100
            }

    def initUI(self):
        # アプリケーション全体のスタイルを設定
        self.setStyleSheet("""
            QWidget {
                background-color: #2B2B2B;
                border: 1px solid #3C3F41;
            }
            QFrame {
                border: 1px solid #3C3F41;
            }
            QTextEdit {
                background-color: #3C3F41;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
            QPushButton {
                background-color: #4C5052;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
            QComboBox {
                background-color: #3C3F41;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
            QSpinBox {
                background-color: #3C3F41;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
        """)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Gemini Translation & Summarize")
        self.setGeometry(self.window_config['x'], self.window_config['y'],
                        self.window_config['width'], self.window_config['height'])

        # メインレイアウトの設定
        layout = QVBoxLayout()
        self.setLayout(layout)

        # タイトルバーの設定
        title_bar = QFrame(self)
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("background-color: #2B2B2B; color: #FFFFFF")
        layout.addWidget(title_bar)

        # ボタンのサイズと余白の設定
        button_width = 30
        button_height = 30
        right_margin = 5

        # 閉じるボタン
        close_button = QPushButton("×", parent=title_bar)
        close_button.setFixedSize(button_width, button_height)
        close_button.setStyleSheet("background-color: #2B2B2B; color: #FFFFFF; border: none;")
        close_button.clicked.connect(self.close)

        # 最大化ボタン
        maximize_button = QPushButton("□", parent=title_bar)
        maximize_button.setFixedSize(button_width, button_height)
        maximize_button.setStyleSheet("background-color: #2B2B2B; color: #FFFFFF; border: none;")
        maximize_button.clicked.connect(self.toggle_maximize)

        # 最小化ボタン
        minimize_button = QPushButton("−", parent=title_bar)
        minimize_button.setFixedSize(button_width, button_height)
        minimize_button.setStyleSheet("background-color: #2B2B2B; color: #FFFFFF; border: none;")
        minimize_button.clicked.connect(self.showMinimized)

        def update_button_positions():
            title_bar_width = title_bar.width()
            close_button.move(title_bar_width - button_width - right_margin, 0)
            maximize_button.move(title_bar_width - (button_width * 2) - right_margin, 0)
            minimize_button.move(title_bar_width - (button_width * 3) - right_margin, 0)

        title_bar.resizeEvent = lambda e: update_button_positions()
        update_button_positions()

        # タイトルラベル
        title_label = QLabel("Gemini Translation & Summarize", parent=title_bar)
        title_label.setStyleSheet("color: #FFFFFF")
        title_label.move(10, 5)

        title_bar.mousePressEvent = self.mousePressEvent
        title_bar.mouseMoveEvent = self.mouseMoveEvent

        # コントロールフレーム
        control_frame = QFrame(self)
        control_frame.setStyleSheet("background-color: #2B2B2B")
        layout.addWidget(control_frame)
        control_layout = QHBoxLayout()
        control_frame.setLayout(control_layout)

        # 設定ボタン
        settings_button = QPushButton("⚙️ API", parent=control_frame)
        settings_button.setStyleSheet("background-color: #4C5052; color: #FFFFFF")
        settings_button.clicked.connect(self.open_settings_dialog)
        control_layout.addWidget(settings_button)

        # フォントサイズ設定
        font_size_label = QLabel("Font Size:", parent=control_frame)
        font_size_label.setStyleSheet("color: #FFFFFF")
        control_layout.addWidget(font_size_label)
        self.font_size_spinner = QSpinBox(parent=control_frame)
        self.font_size_spinner.setStyleSheet("background-color: #3C3F41; color: #FFFFFF")
        self.font_size_spinner.setRange(8, 24)
        self.font_size_spinner.setValue(self.config.get('font_size', 12))
        self.font_size_spinner.valueChanged.connect(self.update_font_size)
        control_layout.addWidget(self.font_size_spinner)

        # モデル選択
        model_label = QLabel("Models:", parent=control_frame)
        model_label.setStyleSheet("color: #FFFFFF")
        control_layout.addWidget(model_label)

        self.model_var = QComboBox(parent=control_frame)
        self.model_var.setStyleSheet("""
        QComboBox {
            background-color: #3C3F41;
            color: #FFFFFF;
            border: 1px solid #555555;
            padding: 5px;
        }
        QComboBox::drop-down {
            border: 0px;
        }
        QComboBox::down-arrow {
            image: url(down_arrow.png);
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #3C3F41;
            color: #FFFFFF;
            selection-background-color: #2979ff;
        }
        """)

        models = self.get_available_models()
        if models:
            self.model_var.addItems(models)
        else:
            self.model_var.addItem('gemini-2.0-flash-exp')

        self.model_var.setCurrentText(self.config.get('selected_model', 'gemini-2.0-flash-exp'))
        self.model_var.currentTextChanged.connect(self.save_selected_model)
        control_layout.addWidget(self.model_var)

        # 入力エリア（カスタムTextEditを使用）
        source_frame = QFrame(self)
        source_frame.setStyleSheet("background-color: #2B2B2B")
        layout.addWidget(source_frame)
        source_layout = QVBoxLayout()
        source_frame.setLayout(source_layout)
        
        # ソースラベルとクリアボタンを横並びに
        source_header_layout = QHBoxLayout()
        source_label = QLabel("Source (テキストまたは画像をドロップ)", parent=source_frame)
        source_label.setStyleSheet("color: #FFFFFF")
        source_header_layout.addWidget(source_label)
        
        # 画像クリアボタン
        clear_image_button = QPushButton("🗑️ Clear", parent=source_frame)
        clear_image_button.setFixedSize(80, 25)
        clear_image_button.setStyleSheet("background-color: #4C5052; color: #FFFFFF; font-size: 10pt;")
        clear_image_button.clicked.connect(self.clear_source)
        source_header_layout.addWidget(clear_image_button)
        source_header_layout.addStretch()
        
        source_layout.addLayout(source_header_layout)
        
        # カスタムTextEditを使用
        self.source_text_box = ImageDropTextEdit(parent=source_frame)
        self.source_text_box.set_parent_app(self)
        self.source_text_box.setMinimumHeight(100)
        self.source_text_box.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; font-size: 12pt;")
        source_layout.addWidget(self.source_text_box)

        # 結果表示エリア
        result_frame = QFrame(self)
        result_frame.setStyleSheet("background-color: #2B2B2B")
        layout.addWidget(result_frame)
        result_layout = QVBoxLayout()
        result_frame.setLayout(result_layout)
        result_label = QLabel("Result", parent=result_frame)
        result_label.setStyleSheet("color: #FFFFFF")
        result_layout.addWidget(result_label)
        self.result_text_box = QTextEdit(parent=result_frame)
        self.result_text_box.setMinimumHeight(100)
        self.result_text_box.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; font-size: 12pt;")
        result_layout.addWidget(self.result_text_box)

        # ボタンフレーム
        button_frame = QFrame(self)
        button_frame.setStyleSheet("background-color: #FF8C00")
        layout.addWidget(button_frame)
        button_layout = QHBoxLayout()
        button_frame.setLayout(button_layout)

        # 翻訳ボタン
        translate_button = QPushButton("🌎️", parent=button_frame)
        translate_button.setFixedSize(45, 45)
        translate_button.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: #FFFFFF;
                font-size: 18pt;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: #FFA500;
            }
        """)
        translate_button.clicked.connect(self.translate_text)
        button_layout.addWidget(translate_button)

        # 画像翻訳ボタン
        image_translate_button = QPushButton("🖼️", parent=button_frame)
        image_translate_button.setFixedSize(45, 45)
        image_translate_button.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: #FFFFFF;
                font-size: 18pt;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: #FFA500;
            }
        """)
        image_translate_button.setToolTip("画像内のテキストを翻訳")
        image_translate_button.clicked.connect(self.translate_image)
        button_layout.addWidget(image_translate_button)

        # 要約ボタン
        summarize_button = QPushButton("✒️", parent=button_frame)
        summarize_button.setFixedSize(45, 45)
        summarize_button.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: #FFFFFF;
                font-size: 18pt;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: #FFA500;
            }
        """)
        summarize_button.clicked.connect(self.summarize_text)
        button_layout.addWidget(summarize_button)

        # 画像説明ボタン
        describe_image_button = QPushButton("🔍", parent=button_frame)
        describe_image_button.setFixedSize(45, 45)
        describe_image_button.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: #FFFFFF;
                font-size: 18pt;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: #FFA500;
            }
        """)
        describe_image_button.setToolTip("画像の内容を説明")
        describe_image_button.clicked.connect(self.describe_image)
        button_layout.addWidget(describe_image_button)

        self.apply_font_size()
        self.show()

    def clear_source(self):
        """ソーステキストボックスをクリア"""
        self.source_text_box.clear_image()

    def translate_image(self):
        """画像内のテキストを翻訳"""
        if not self.model:
            self.result_text_box.setText("APIキーが設定されていません。")
            return
            
        image_path = self.source_text_box.get_dropped_image_path()
        if not image_path:
            self.result_text_box.setText("画像がドロップされていません。\nSourceエリアに画像をドラッグ＆ドロップしてください。")
            return
            
        try:
            self.result_text_box.setText("画像を処理中...")
            QApplication.processEvents()
            
            # 画像を読み込む
            image = PIL.Image.open(image_path)
            
            # 画像翻訳用のプロンプト
            prompt = self.config.get('image_translate_prompt', 
                "この画像に含まれているテキストを全て抽出し、日本語に翻訳してください。\n"
                "元のテキストと翻訳を両方表示してください。\n"
                "テキストが見つからない場合は、その旨を報告してください。")
            
            # Geminiに画像とプロンプトを送信
            response = self.model.generate_content([prompt, image])
            
            result_text = ""
            for part in response.parts:
                if hasattr(part, 'text'):
                    result_text += part.text
                    
            self.result_text_box.setText(result_text)
            self.save_log(f"[Image: {image_path}]", result_text, "Image Translation")
            
        except Exception as e:
            self.result_text_box.setText(f"エラーが発生しました: {str(e)}")

    def describe_image(self):
        """画像の内容を説明"""
        if not self.model:
            self.result_text_box.setText("APIキーが設定されていません。")
            return
            
        image_path = self.source_text_box.get_dropped_image_path()
        if not image_path:
            self.result_text_box.setText("画像がドロップされていません。\nSourceエリアに画像をドラッグ＆ドロップしてください。")
            return
            
        try:
            self.result_text_box.setText("画像を分析中...")
            QApplication.processEvents()
            
            # 画像を読み込む
            image = PIL.Image.open(image_path)
            
            # 画像説明用のプロンプト
            prompt = self.config.get('image_describe_prompt',
                "この画像の内容を詳しく説明してください。日本語で回答してください。")
            
            # Geminiに画像とプロンプトを送信
            response = self.model.generate_content([prompt, image])
            
            result_text = ""
            for part in response.parts:
                if hasattr(part, 'text'):
                    result_text += part.text
                    
            self.result_text_box.setText(result_text)
            self.save_log(f"[Image: {image_path}]", result_text, "Image Description")
            
        except Exception as e:
            self.result_text_box.setText(f"エラーが発生しました: {str(e)}")

    def save_selected_model(self):
        selected_model = self.model_var.currentText()
        self.config['selected_model'] = selected_model
        self.save_config()
        self.setup_gemini()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.save_window_config()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QPen
        painter = QPainter(self)
        pen = QPen(QColor("#555555"))
        painter.setPen(pen)
        
        bottom_right = self.rect().bottomRight()
        for i in range(3):
            painter.drawLine(
                bottom_right.x() - self.resize_corner_size + (i * 5),
                bottom_right.y(),
                bottom_right.x(),
                bottom_right.y() - self.resize_corner_size + (i * 5)
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            bottom_right = self.rect().bottomRight()
            if (pos.x() >= bottom_right.x() - self.resize_corner_size and 
                pos.y() >= bottom_right.y() - self.resize_corner_size):
                self.resizing = True
                self.resize_start_pos = pos
                self.resize_start_geometry = self.geometry()
            else:
                self.resizing = False
                self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if self.resizing:
                diff = event.pos() - self.resize_start_pos
                new_width = max(self.minimumWidth(), self.resize_start_geometry.width() + diff.x())
                new_height = max(self.minimumHeight(), self.resize_start_geometry.height() + diff.y())
                self.resize(new_width, new_height)
            else:
                self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resizing = False
            self.save_window_config()
            event.accept()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def update_font_size(self):
        font_size = self.font_size_spinner.value()
        self.config['font_size'] = font_size
        self.save_config()
        self.apply_font_size()

    def setup_gemini(self):
        if self.config['api_key']:
            try:
                genai.configure(api_key=self.config['api_key'])
                selected_model = self.model_var.currentText()
                self.config['selected_model'] = selected_model
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
                }
                
                self.model = genai.GenerativeModel(selected_model, safety_settings=safety_settings)
                self.save_config()
            except Exception as e:
                print(f"Gemini設定エラー: {str(e)}")
                self.model = None
        else:
            self.model = None

    def start_hotkey_listener(self):
        def on_activate():
            if self.model:
                kb = keyboard.Controller()
                kb.release(keyboard.Key.ctrl)
                kb.release(keyboard.Key.alt)
                kb.release('t')
                QApplication.instance().postEvent(self, QEvent(QEvent.Type.User))
            else:
                print("No API key set.")

        self.hotkey = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+t': on_activate
        })
        self.hotkey.start()

    def _process_clipboard_content(self):
        try:
            clipboard = QApplication.clipboard()
            old_text = clipboard.text()
            
            kb = keyboard.Controller()
            
            with kb.pressed(keyboard.Key.ctrl):
                kb.tap('c')
            
            time.sleep(0.2)
            
            text = clipboard.text()
            
            if text and text != old_text:
                self.source_text_box.clear()
                self.source_text_box.setText(text)
                QApplication.processEvents()
                self.translate_text()
            else:
                print("No new text selected or copied")
        except Exception as e:
            print(f"Error processing clipboard: {e}")

    def event(self, event):
        if event.type() == QEvent.Type.User:
            self._process_clipboard_content()
            return True
        return super().event(event)

    def get_available_models(self):
        try:
            if self.config['api_key']:
                genai.configure(api_key=self.config['api_key'])
                models = genai.list_models()
                self.available_models = [model.name for model in models if "generateContent" in model.supported_generation_methods]
                if not self.available_models:
                    self.available_models = ['gemini-2.0-flash-exp']
            else:
                self.available_models = ['gemini-2.0-flash-exp']
        except Exception as e:
            print(f"モデルリスト取得エラー: {str(e)}")
            self.available_models = ['gemini-2.0-flash-exp']
        return self.available_models

    def open_settings_dialog(self):
        settings_window = QWidget()
        settings_window.setWindowTitle("Settings")
        settings_window.setGeometry(100, 100, 500, 600)
        settings_window.setStyleSheet("background-color: #2B2B2B; color: #FFFFFF")

        layout = QVBoxLayout()
        settings_window.setLayout(layout)

        # APIキー設定
        api_frame = QFrame()
        api_frame.setStyleSheet("background-color: #2B2B2B")
        api_layout = QVBoxLayout()
        api_frame.setLayout(api_layout)

        api_label = QLabel("APIKey:")
        api_label.setStyleSheet("color: #FFFFFF")
        api_layout.addWidget(api_label)

        api_key_entry = QLineEdit()
        api_key_entry.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; padding: 5px;")
        api_key_entry.setText(self.config['api_key'])
        api_layout.addWidget(api_key_entry)

        layout.addWidget(api_frame)

        # 翻訳プロンプト設定
        translate_frame = QFrame()
        translate_frame.setStyleSheet("background-color: #2B2B2B")
        translate_layout = QVBoxLayout()
        translate_frame.setLayout(translate_layout)

        translate_label = QLabel("TranslatePrompt:")
        translate_label.setStyleSheet("color: #FFFFFF")
        translate_layout.addWidget(translate_label)

        translate_prompt_entry = QTextEdit()
        translate_prompt_entry.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; padding: 5px;")
        translate_prompt_entry.setPlainText(self.config['translate_prompt'])
        translate_prompt_entry.setMinimumHeight(60)
        translate_layout.addWidget(translate_prompt_entry)

        layout.addWidget(translate_frame)

        # 要約プロンプト設定
        summarize_frame = QFrame()
        summarize_frame.setStyleSheet("background-color: #2B2B2B")
        summarize_layout = QVBoxLayout()
        summarize_frame.setLayout(summarize_layout)

        summarize_label = QLabel("SummarizePrompt:")
        summarize_label.setStyleSheet("color: #FFFFFF")
        summarize_layout.addWidget(summarize_label)

        summarize_prompt_entry = QTextEdit()
        summarize_prompt_entry.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; padding: 5px;")
        summarize_prompt_entry.setPlainText(self.config['summarize_prompt'])
        summarize_prompt_entry.setMinimumHeight(60)
        summarize_layout.addWidget(summarize_prompt_entry)

        layout.addWidget(summarize_frame)

        # 画像翻訳プロンプト設定
        image_translate_frame = QFrame()
        image_translate_frame.setStyleSheet("background-color: #2B2B2B")
        image_translate_layout = QVBoxLayout()
        image_translate_frame.setLayout(image_translate_layout)

        image_translate_label = QLabel("ImageTranslatePrompt:")
        image_translate_label.setStyleSheet("color: #FFFFFF")
        image_translate_layout.addWidget(image_translate_label)

        image_translate_prompt_entry = QTextEdit()
        image_translate_prompt_entry.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; padding: 5px;")
        image_translate_prompt_entry.setPlainText(self.config.get('image_translate_prompt', 
            "この画像に含まれているテキストを全て抽出し、日本語に翻訳してください。\n"
            "元のテキストと翻訳を両方表示してください。\n"
            "テキストが見つからない場合は、その旨を報告してください。"))
        image_translate_prompt_entry.setMinimumHeight(60)
        image_translate_layout.addWidget(image_translate_prompt_entry)

        layout.addWidget(image_translate_frame)

        # 画像説明プロンプト設定
        image_describe_frame = QFrame()
        image_describe_frame.setStyleSheet("background-color: #2B2B2B")
        image_describe_layout = QVBoxLayout()
        image_describe_frame.setLayout(image_describe_layout)

        image_describe_label = QLabel("ImageDescribePrompt:")
        image_describe_label.setStyleSheet("color: #FFFFFF")
        image_describe_layout.addWidget(image_describe_label)

        image_describe_prompt_entry = QTextEdit()
        image_describe_prompt_entry.setStyleSheet("background-color: #3C3F41; color: #FFFFFF; padding: 5px;")
        image_describe_prompt_entry.setPlainText(self.config.get('image_describe_prompt',
            "この画像の内容を詳しく説明してください。日本語で回答してください。"))
        image_describe_prompt_entry.setMinimumHeight(60)
        image_describe_layout.addWidget(image_describe_prompt_entry)

        layout.addWidget(image_describe_frame)

        # 保存ボタン
        save_button = QPushButton("Save")
        save_button.setStyleSheet("background-color: #1E90FF; color: #FFFFFF; padding: 5px;")

        def save_settings():
            self.config['api_key'] = api_key_entry.text()
            self.config['translate_prompt'] = translate_prompt_entry.toPlainText()
            self.config['summarize_prompt'] = summarize_prompt_entry.toPlainText()
            self.config['image_translate_prompt'] = image_translate_prompt_entry.toPlainText()
            self.config['image_describe_prompt'] = image_describe_prompt_entry.toPlainText()
            self.save_config()
            self.setup_gemini()
            settings_window.close()

        save_button.clicked.connect(save_settings)
        layout.addWidget(save_button)

        settings_window.show()
        self.settings_window = settings_window  # ウィンドウへの参照を保持

    def save_config(self):
        with open('config.json', 'w', encoding='utf-8') as config_file:
            json.dump(self.config, config_file, indent=4, ensure_ascii=False)

    def apply_font_size(self):
        font_size = self.config.get('font_size', 12)
        style = f"background-color: #3C3F41; color: #FFFFFF; font-size: {font_size}pt;"
        
        font = QFont()
        font.setPointSize(font_size)
        
        self.source_text_box.setStyleSheet(style)
        self.source_text_box.setFont(font)
        
        self.result_text_box.setStyleSheet(style)
        self.result_text_box.setFont(font)

    def translate_text(self):
        if not self.model:
            print("No API key set.")
            return
        source_text = self.source_text_box.toPlainText()
        if not source_text:
            self.result_text_box.setText("Please enter text to translate.")
            return
        try:
            prompt = self.config.get('translate_prompt', "Translate the following English text to Japanese:\n{text}").format(text=source_text)
            response = self.model.generate_content(prompt)
            result_text = ""
            for part in response.parts:
                if hasattr(part, 'text'):
                    result_text += part.text
            self.result_text_box.setText(result_text)
            self.save_log(source_text, result_text, "Translation")
        except Exception as e:
            self.result_text_box.setText(f"Error: {str(e)}")

    def summarize_text(self):
        if not self.model:
            print("No API key set.")
            return
        source_text = self.source_text_box.toPlainText()
        if not source_text:
            self.result_text_box.setText("Please enter text to summarize.")
            return
        try:
            prompt = self.config.get('summarize_prompt', "Summarize the following text in Japanese:\n{text}").format(text=source_text)
            response = self.model.generate_content(prompt)
            result_text = ""
            for part in response.parts:
                if hasattr(part, 'text'):
                   result_text += part.text
            self.result_text_box.setText(result_text)
            self.save_log(source_text, result_text, "Summary")
        except Exception as e:
            self.result_text_box.setText(f"Error: {str(e)}")

    def save_log(self, source_text, result_text, operation_type):
        try:
            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base_dir, 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = os.path.join(log_dir, f"{timestamp}.txt")
            log_content = f"[{operation_type}]\nOriginal Text:\n{source_text}\n\nResult Text:\n{result_text}\n"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(log_content)
        except Exception as e:
            print(f"ログの保存中にエラーが発生しました: {str(e)}")

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as config_file:
                config = json.load(config_file)
            default_config = {
                'api_key': '',
                'font_size': 12,
                'selected_model': 'gemini-2.0-flash-exp',
                'translate_prompt': "Translate the following English text to Japanese:\n{text}",
                'summarize_prompt': "Summarize the following text in Japanese:\n{text}",
                'image_translate_prompt': "この画像に含まれているテキストを全て抽出し、日本語に翻訳してください。\n元のテキストと翻訳を両方表示してください。\nテキストが見つからない場合は、その旨を報告してください。",
                'image_describe_prompt': "この画像の内容を詳しく説明してください。日本語で回答してください。"
            }
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except FileNotFoundError:
            default_config = {
                'api_key': '',
                'font_size': 12,
                'selected_model': 'gemini-2.0-flash-exp',
                'translate_prompt': "Translate the following English text to Japanese:\n{text}",
                'summarize_prompt': "Summarize the following text in Japanese:\n{text}",
                'image_translate_prompt': "この画像に含まれているテキストを全て抽出し、日本語に翻訳してください。\n元のテキストと翻訳を両方表示してください。\nテキストが見つからない場合は、その旨を報告してください。",
                'image_describe_prompt': "この画像の内容を詳しく説明してください。日本語で回答してください。"
            }
            with open('config.json', 'w', encoding='utf-8') as config_file:
                json.dump(default_config, config_file, indent=4, ensure_ascii=False)
            return default_config

    def save_window_config(self):
        window_config = {
            'width': self.width(),
            'height': self.height(),
            'x': self.x(),
            'y': self.y()
        }
        with open('window_config.json', 'w') as config_file:
            json.dump(window_config, config_file, indent=4)

    def closeEvent(self, event):
        self.save_window_config()
        if hasattr(self, 'hotkey'):
            self.hotkey.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = TranslatorApp()
    sys.exit(app.exec_())
