import sys
import os
import requests
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                             QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
                             QProgressBar, QComboBox, QTextEdit, QCheckBox, QHBoxLayout,
                             QVBoxLayout, QGroupBox, QGridLayout)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from yt_dlp import YoutubeDL

class QtLogger:
    def __init__(self, signal):
        self.signal = signal

    def debug(self, msg):
        self.signal.emit(str(msg))

    def info(self, msg):
        self.signal.emit(str(msg))

    def warning(self, msg):
        self.signal.emit(f"WARNING: {msg}")

    def error(self, msg):
        self.signal.emit(f"ERROR: {msg}")

class MetadataThread(QThread):
    result_ready = pyqtSignal(object)
    log_signal = pyqtSignal(str)

    def __init__(self, link):
        super().__init__()
        self.link = link

    def run(self):
        logger = QtLogger(self.log_signal)
        ydl_opts = {'noplaylist': False, 'logger': logger}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.link, download=False)
        self.result_ready.emit(info)

class DownloadThread(QThread):
    progress_update = pyqtSignal(int)
    download_finished = pyqtSignal()
    log_signal = pyqtSignal(str)

    def __init__(self, urls, folder, fmt, postprocessors):
        super().__init__()
        self.urls = urls
        self.folder = folder
        self.fmt = fmt
        self.postprocessors = postprocessors
        self.total_videos = len(urls)
        self.current_index = 0

    def hook_progresso(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            try:
                value = float(percent.replace('%', ''))
                total_progress = int(((self.current_index + (value / 100)) / self.total_videos) * 100)
                self.progress_update.emit(total_progress)
            except:
                pass
        elif d['status'] == 'finished':
            self.current_index += 1
            total_progress = int((self.current_index / self.total_videos) * 100)
            self.progress_update.emit(total_progress)

    def run(self):
        logger = QtLogger(self.log_signal)
        ydl_opts = {
            'outtmpl': os.path.join(self.folder, '%(title)s.%(ext)s'),
            'format': self.fmt,
            'progress_hooks': [self.hook_progresso],
            'postprocessors': self.postprocessors,
            'merge_output_format': 'mp4',
            'logger': logger
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(self.urls)
        self.download_finished.emit()

class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JTubeDownloader")
        self.setWindowIcon(QIcon("icon.png"))

        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #ffffff;
                font-family: Arial, sans-serif;
                font-size: 11pt;
            }
            QLineEdit, QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton {
                background-color: #c62828;
                border: none;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QLabel {
                margin: 2px 0;
            }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px;
            }
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
            }
            QProgressBar {
                border: 1px solid #333;
                border-radius: 4px;
                text-align: center;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #00c853;
                border-radius: 4px;
            }
        """)

        main_layout = QGridLayout()
        self.setLayout(main_layout)

        # Left: Video selection
        self.video_list_group = QGroupBox("📄 Seleção de Vídeos")
        left_layout = QVBoxLayout()
        self.video_list = QListWidget()
        left_layout.addWidget(self.video_list)
        self.video_list_group.setLayout(left_layout)
        main_layout.addWidget(self.video_list_group, 0, 0, 2, 1)

        # Right: Controls
        right_layout = QVBoxLayout()

        link_group = QGroupBox("🔗 Link do Vídeo ou Playlist")
        link_layout = QHBoxLayout()
        self.link_input = QLineEdit()
        self.fetch_button = QPushButton("Buscar Detalhes")
        self.fetch_button.clicked.connect(self.buscar_detalhes)
        link_layout.addWidget(self.link_input)
        link_layout.addWidget(self.fetch_button)
        link_group.setLayout(link_layout)
        right_layout.addWidget(link_group)

        config_group = QGroupBox("⚙ Configurações")
        config_layout = QHBoxLayout()
        self.output_folder_button = QPushButton("Escolher Pasta")
        self.output_folder_button.clicked.connect(self.escolher_pasta)
        self.output_folder_label = QLabel(os.path.expanduser("~/Videos"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Vídeo (mp4)", "Apenas áudio (mp3)"])
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["YouTube", "Bandcamp"])
        config_layout.addWidget(self.output_folder_button)
        config_layout.addWidget(self.output_folder_label)
        config_layout.addWidget(QLabel("Formato:"))
        config_layout.addWidget(self.format_combo)
        config_layout.addWidget(QLabel("Plataforma:"))
        config_layout.addWidget(self.platform_combo)
        config_group.setLayout(config_layout)
        right_layout.addWidget(config_group)

        self.download_button = QPushButton("⬇ Baixar Selecionados")
        self.download_button.clicked.connect(self.baixar_selecionados)
        right_layout.addWidget(self.download_button)

        self.progress_bar = QProgressBar()
        right_layout.addWidget(self.progress_bar)

        log_group = QGroupBox("📋 Log")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        metadata_group = QGroupBox("📑 Metadados Detalhados")
        self.metadata_output = QTextEdit()
        self.metadata_output.setReadOnly(True)
        metadata_layout = QVBoxLayout()
        metadata_layout.addWidget(self.metadata_output)
        metadata_group.setLayout(metadata_layout)
        right_layout.addWidget(metadata_group)

        main_layout.addLayout(right_layout, 0, 1)

        self.video_urls = []
        self.download_folder = os.path.expanduser("~/Videos")

    def append_log(self, message):
        self.log_output.append(message)

    def escolher_pasta(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolher Pasta de Destino")
        if folder:
            self.download_folder = folder
            self.output_folder_label.setText(folder)

    def buscar_detalhes(self):
        link = self.link_input.text().strip()
        if not link:
            QMessageBox.warning(self, "Erro", "Por favor, insira um link.")
            return

        plataforma = self.platform_combo.currentText()
        self.append_log(f"Iniciando busca de metadados na plataforma: {plataforma}")

        self.fetch_button.setEnabled(False)
        self.metadata_thread = MetadataThread(link)
        self.metadata_thread.log_signal.connect(self.append_log)
        self.metadata_thread.result_ready.connect(self.exibir_detalhes)
        self.metadata_thread.start()

    def exibir_detalhes(self, info):
        self.fetch_button.setEnabled(True)
        self.video_list.clear()
        self.video_urls = []

        entries = info['entries'] if 'entries' in info else [info]

        for entry in entries:
            title = entry.get('title', 'Sem título')
            url = entry.get('webpage_url')
            thumb_url = entry.get('thumbnail')
            self.add_video_item(title, url, thumb_url)

        import json
        info_to_show = entries[0]
        formatted_metadata = json.dumps(info_to_show, indent=4, ensure_ascii=False)
        self.metadata_output.setPlainText(formatted_metadata)

    def add_video_item(self, title, url, thumb_url):
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        checkbox = QCheckBox()
        checkbox.setChecked(True)
        layout.addWidget(checkbox, 0)

        short_title = title if len(title) <= 40 else title[:37] + "..."
        title_label = QLabel(short_title)
        title_label.setFixedWidth(220)
        layout.addWidget(title_label, 0)

        if thumb_url:
            response = requests.get(thumb_url)
            if response.status_code == 200:
                with open("temp_thumb.jpg", "wb") as f:
                    f.write(response.content)
                pixmap = QPixmap("temp_thumb.jpg").scaled(60, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_label = QLabel()
                thumb_label.setPixmap(pixmap)
                thumb_label.setFixedSize(60, 34)
                layout.addWidget(thumb_label, 0)

        widget.setLayout(layout)
        widget.setFixedHeight(50)
        item = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        self.video_list.addItem(item)
        self.video_list.setItemWidget(item, widget)
        self.video_urls.append((title, url, checkbox))

    def baixar_selecionados(self):
        selecionados = [url for title, url, checkbox in self.video_urls if checkbox.isChecked()]

        if not selecionados:
            QMessageBox.warning(self, "Erro", "Nenhum vídeo selecionado.")
            return

        selected_platform = self.platform_combo.currentText()
        selected_format = self.format_combo.currentText()

        if selected_platform == "Bandcamp":
            ydl_format = 'bestaudio/best'
            postprocessors = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                {'key': 'FFmpegMetadata'},
                {'key': 'EmbedThumbnail'}
            ]
        else:
            if "áudio" in selected_format:
                ydl_format = 'bestaudio/best'
                postprocessors = [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'}
                ]
            else:
                ydl_format = 'bestvideo+bestaudio/best'
                postprocessors = [
                    {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'}
                ]

        self.download_button.setEnabled(False)
        self.progress_bar.setValue(0)

        self.download_thread = DownloadThread(selecionados, self.download_folder, ydl_format, postprocessors)
        self.download_thread.log_signal.connect(self.append_log)
        self.download_thread.progress_update.connect(self.progress_bar.setValue)
        self.download_thread.download_finished.connect(self.download_completo)
        self.download_thread.start()

    def download_completo(self):
        self.download_button.setEnabled(True)
        QMessageBox.information(self, "Sucesso", "Download concluído!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec_())
