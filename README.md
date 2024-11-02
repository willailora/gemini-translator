# gemini-translator
A Python app that uses Gemini's API for translation and summarization
Please see below for the English version of the read me.

# Gemini 翻訳 & 要約アプリ
![スクリーンショット 2024-11-02 083900](https://github.com/user-attachments/assets/8425671c-43d5-44b5-9942-f2991d748bb1)

Google の Gemini AI モデルを使用したテキスト翻訳と要約のデスクトップアプリケーションです。モダンなダークテーマUIと、カスタマイズ可能な設定、ホットキー機能を備えています。

## 主な機能

- Gemini AI による高精度なリアルタイム翻訳
- テキスト要約機能
- モダンなダークテーマUI
- フォントサイズのカスタマイズ
- クイック翻訳用のホットキー対応
- ウィンドウ位置の記憶機能
- ログ機能
- APIの設定カスタマイズ

## 動作要件

- Python 3.8以上
- Google Gemini APIキー

## インストール方法

1. リポジトリをクローン:
```bash
git clone https://github.com/willailora/gemini-translator
cd gemini-translator
```

2. 必要なパッケージのインストール:
```bash
pip install PyQt5 google-generativeai pynput
```

## 必要なライブラリ

- **PyQt5**: Pythonアプリケーション用のモダンなGUIフレームワーク
- **google.generativeai**: Google生成AIモデルにアクセスするための公式ライブラリ
- **pynput**: キーボードやマウスなどの入力デバイスを監視・制御するためのライブラリ

## セットアップ手順

1. Google AI StudioからGemini APIキーを取得
2. アプリケーションを起動
3. 「⚙️ API」ボタンをクリック
4. 設定ダイアログでAPIキーを入力
5. 設定を保存

## 使用方法

1. ソーステキストボックスにテキストを入力またはペースト
2. 翻訳は🌎️、要約は✒️ボタンをクリック
3. 結果が結果テキストボックスに表示されます

## ホットキー

- `Ctrl + Alt + T`: 選択したテキストをクイック翻訳

## 設定ファイル

アプリケーションは2つのJSONファイルで設定を管理:

- `config.json`: APIキー、フォントサイズ、プロンプト設定を保存
- `window_config.json`: ウィンドウの位置とサイズを保存

## ログ機能

翻訳と要約の履歴は自動的に`log`ディレクトリにタイムスタンプ付きで保存されます。

## 開発情報

本アプリケーションは以下の技術で構築:
- PyQt5によるGUI実装
- Google Generative AI APIによる翻訳・要約処理
- カスタムウィンドウ管理（ドラッグ＆リサイズ機能）

## 注意事項

- API通信のため、インターネット接続が必要です
- Google Cloudの設定によってはAPI使用料が発生する場合があります
- ウィンドウの位置とサイズは終了時に自動保存されます

## ドネーションをしてくれる方は以下のURLからお願いします。
https://ko-fi.com/ailorawill
<a href='https://ko-fi.com/M4M1WZ04Y' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi2.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

連絡先
プロジェクトに関する質問やコメントがある場合は、https://x.com/plionplionか、Discordで@willlionまでご連絡ください。

# Gemini Translation & Summarize

A desktop application that provides translation and text summarization using Google's Gemini AI model. Features a modern dark-themed UI with customizable settings and hotkey support.

## Features

- Real-time translation using Gemini AI
- Text summarization capabilities
- Modern dark-themed UI
- Customizable font size
- Hotkey support for quick translation
- Window position memory
- Logging functionality
- Customizable API settings

## Requirements

- Python 3.8+
- Google Gemini API key

## Installation

1. Clone this repository:
```bash
git clone https://github.com/willailora/gemini-translator
cd gemini-translator
```

2. Install required packages:
```bash
pip install PyQt5 google-generativeai pynput
```

## Required Libraries

- **PyQt5**: Modern GUI framework for Python applications[1]
- **google.generativeai**: Official Google Generative AI library for accessing Gemini models
- **pynput**: Library for monitoring and controlling input devices (keyboard/mouse)

## Setup

1. Get a Google Gemini API key from the Google AI Studio
2. Launch the application
3. Click the "⚙️ API" button
4. Enter your API key in the settings dialog
5. Save the settings

## Usage

1. Enter or paste text in the source text box
2. Click 🌎️ for translation or ✒️ for summarization
3. Results will appear in the result text box

## Hotkeys

- `Ctrl + Alt + T`: Quick translate selected text

## Configuration

The application stores configurations in two JSON files:

- `config.json`: Stores API key, font size, and prompt settings
- `window_config.json`: Stores window position and size

## Logs

Translation and summarization logs are automatically saved in the `log` directory with timestamps.

## Development

The application is built using:
- PyQt5 for the GUI
- Google Generative AI API for translations and summarizations
- Custom window management with drag and resize capabilities

## Notes

- Requires a stable internet connection for API communication
- API usage may incur charges depending on your Google Cloud setup
- The application remembers window position and size between sessions

## If you would like to make a donation, please do so from the following URL:
https://ko-fi.com/ailorawill
<a href='https://ko-fi.com/M4M1WZ04Y' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi2.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

Contact
If you have any questions or comments about the project, please contact me at https://x.com/plionplion or on Discord at @willlion.
