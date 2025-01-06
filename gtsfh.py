import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QFrame, QTextEdit, QSpinBox
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QEvent
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json
from pynput import keyboard
import time
from datetime import datetime

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
            # デフォルトの設定を返す
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
        # Windowsの標準ウィンドウバーを非表示にする
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

        # リサイズイベントでボタンの位置を更新するメソッドを追加
        def update_button_positions():
            title_bar_width = title_bar.width()
            close_button.move(title_bar_width - button_width - right_margin, 0)
            maximize_button.move(title_bar_width - (button_width * 2) - right_margin, 0)
            minimize_button.move(title_bar_width - (button_width * 3) - right_margin, 0)

        # タイトルバーのリサイズイベントを設定
        title_bar.resizeEvent = lambda e: update_button_positions()

        # 初期位置の設定
        update_button_positions()

        # タイトルラベル
        title_label = QLabel("Gemini Translation & Summarize", parent=title_bar)
        title_label.setStyleSheet("color: #FFFFFF")
        title_label.move(10, 5)

        # ウィンドウのドラッグ移動を可能にする
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

        # モデル選択コンボボックス
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

        # モデルリストの設定
        models = self.get_available_models()
        if models:
            self.model_var.addItems(models)
        else:
            self.model_var.addItem('gemini-2.0-flash-exp')

        # 保存されているモデルを選択
        self.model_var.setCurrentText(self.config.get('selected_model', 'gemini-2.0-flash-exp'))
        self.model_var.currentTextChanged.connect(self.save_selected_model)
        control_layout.addWidget(self.model_var)

        # 入力エリア
        source_frame = QFrame(self)
        source_frame.setStyleSheet("background-color: #2B2B2B")
        layout.addWidget(source_frame)
        source_layout = QVBoxLayout()
        source_frame.setLayout(source_layout)
        source_label = QLabel("Source", parent=source_frame)
        source_label.setStyleSheet("color: #FFFFFF")
        source_layout.addWidget(source_label)
        self.source_text_box = QTextEdit(parent=source_frame)
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
        translate_button.setFixedSize(45, 45)  # ボタンサイズを60x60に設定
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

        # 要約ボタン
        summarize_button = QPushButton("✒️", parent=button_frame)
        summarize_button.setFixedSize(45, 45)  # ボタンサイズを60x60に設定
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

        # 初期化時にフォントサイズを適用
        self.apply_font_size()

        self.show()

    def save_selected_model(self):
        selected_model = self.model_var.currentText()
        self.config['selected_model'] = selected_model
        self.save_config()
        self.setup_gemini()  # モデルを再設定

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # リサイズ時にウィンドウの設定を保存
        self.save_window_config()

    def paintEvent(self, event):
        # 右下にリサイズハンドルを描画
        from PyQt5.QtGui import QPainter, QPen
        painter = QPainter(self)
        pen = QPen(QColor("#555555"))
        painter.setPen(pen)
        
        # 右下の角に斜線を描画
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
            # リサイズハンドル領域の判定
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
                # リサイズ処理
                diff = event.pos() - self.resize_start_pos
                new_width = max(self.minimumWidth(), self.resize_start_geometry.width() + diff.x())
                new_height = max(self.minimumHeight(), self.resize_start_geometry.height() + diff.y())
                self.resize(new_width, new_height)
            else:
                # ウィンドウの移動
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
                selected_model = self.model_var.currentText()  # 現在選択されているモデルを取得
                self.config['selected_model'] = selected_model  # configに保存
                
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
                }
                
                self.model = genai.GenerativeModel(selected_model, safety_settings=safety_settings)
                self.save_config()  # 設定を保存
            except Exception as e:
                print(f"Gemini設定エラー: {str(e)}")
                self.model = None
        else:
            self.model = None

    def start_hotkey_listener(self):
        def on_activate():
            if self.model:
                # キーボードコントローラーを作成
                kb = keyboard.Controller()
                # キーを解放
                kb.release(keyboard.Key.ctrl)
                kb.release(keyboard.Key.alt)
                kb.release('t')
                # メインスレッドでクリップボード処理を実行
                QApplication.instance().postEvent(self, QEvent(QEvent.Type.User))
            else:
                print("No API key set.")

        self.hotkey = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+t': on_activate
        })
        self.hotkey.start()

    def _process_clipboard_content(self):
        try:
            # クリップボードの古い内容を保存
            clipboard = QApplication.clipboard()
            old_text = clipboard.text()
            
            # キーボードコントローラーを作成
            kb = keyboard.Controller()
            
            # 選択テキストを再度コピー
            with kb.pressed(keyboard.Key.ctrl):
                kb.tap('c')
            
            # コピーの完了を待つ
            time.sleep(0.2)
            
            # 新しいクリップボードのテキストを取得
            text = clipboard.text()
            
            # 新しいテキストが取得できた場合のみ処理
            if text and text != old_text:
                # テキストボックスをクリアしてから新しいテキストを設定
                self.source_text_box.clear()
                self.source_text_box.setText(text)
                
                # 強制的に更新を実行
                QApplication.processEvents()
                
                # 翻訳を実行
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
        return self.available_models  # 必ずリストを返す

    def open_settings_dialog(self):
        settings_window = QWidget()
        settings_window.setWindowTitle("Settings")
        settings_window.setGeometry(100, 100, 500, 400)
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
        translate_prompt_entry.setMinimumHeight(80)
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
        summarize_prompt_entry.setMinimumHeight(80)
        summarize_layout.addWidget(summarize_prompt_entry)

        layout.addWidget(summarize_frame)

        # 保存ボタン
        save_button = QPushButton("Save")
        save_button.setStyleSheet("background-color: #1E90FF; color: #FFFFFF; padding: 5px;")

        def save_settings():
            self.config['api_key'] = api_key_entry.text()
            self.config['translate_prompt'] = translate_prompt_entry.toPlainText()
            self.config['summarize_prompt'] = summarize_prompt_entry.toPlainText()
            self.save_config()
            self.setup_gemini()
            settings_window.close()

        save_button.clicked.connect(save_settings)
        layout.addWidget(save_button)

        settings_window.show()

        def save_settings():
            self.config['api_key'] = api_key_entry.text()
            self.save_config()
            self.setup_gemini()
            settings_window.close()

        save_button.clicked.connect(save_settings)
        settings_window.show()

    def save_config(self):
        with open('config.json', 'w', encoding='utf-8') as config_file:
            json.dump(self.config, config_file, indent=4, ensure_ascii=False)

    def apply_font_size(self):
        font_size = self.config.get('font_size', 12)
        style = f"background-color: #3C3F41; color: #FFFFFF; font-size: {font_size}pt;"
        
        # フォントサイズをQFontを使用して直接設定
        font = QFont()
        font.setPointSize(font_size)
        
        # スタイルシートとフォントの両方を設定
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
                if hasattr(part, 'text'):  # partがtext属性を持つか確認
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
                if hasattr(part, 'text'):  # partがtext属性を持つか確認
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
                'summarize_prompt': "Summarize the following text in Japanese:\n{text}"
            }
            # デフォルト設定が存在しない場合は追加
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
        except FileNotFoundError:
            # 設定ファイルが存在しない場合はデフォルト設定を作成
            default_config = {
                'api_key': '',
                'font_size': 12,
                'selected_model': 'gemini-2.0-flash-exp',
                'translate_prompt': "Translate the following English text to Japanese:\n{text}",
                'summarize_prompt': "Summarize the following text in Japanese:\n{text}"
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
