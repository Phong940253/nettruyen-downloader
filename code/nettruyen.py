import base64
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from os import mkdir, path
from os.path import abspath, dirname, isdir, join
from urllib.parse import urlparse

import cloudscraper
import requests
import src
from bs4 import BeautifulSoup, ResultSet, Tag
from PyQt5.QtCore import (
    QMetaObject,
    QObject,
    QRect,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
)
from traceback import format_exc
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "DNT": "1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,image/svg+xml,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
}

list_error_403 = []


class MangaInfo:

    def __init__(self):
        self.thumbnail = ""
        self.manga_url = ""
        self.manga_name = ""
        self.author = ""
        self.categories = ""
        self.viewed = ""
        self.description = ""
        self.last_updated = ""
        self.latest_chapter = ""
        self.chapter_name_list = []
        self.chapter_url_list = []
        self.save_path = ""
        self.list_of_download_chapter = []


class MessageBox(QMessageBox):

    def __init__(self, noti_text=""):
        super(MessageBox, self).__init__()
        self.setWindowTitle("Notification")
        self.setWindowIcon(QIcon((resource_path("icon.ico"))))
        self.setText(noti_text)
        self.exec_()


class WaitingDialog(QDialog):

    stop_signal = pyqtSignal()

    def init_ui(self):
        # Dialog
        self.Dialog = QDialog()
        self.Dialog.resize(500, 200)
        self.Dialog.setWindowFlags(Qt.MSWindowsFixedSizeDialogHint)
        self.Dialog.setWindowIcon(QIcon((resource_path("icon.ico"))))
        font = QFont()
        font.setFamily("Verdana")
        self.Dialog.setFont(font)
        self.Dialog.setModal(True)
        self.Dialog.setWindowTitle("Please Wait ...")
        self.Dialog.setWindowFlags(Qt.WindowTitleHint)

        # Progress Bar
        self.progressBar = QProgressBar(self.Dialog)
        self.progressBar.setGeometry(QRect(30, 80, 451, 31))
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)

        # Status
        self.label = QLabel(self.Dialog)
        self.label.setEnabled(True)
        self.label.setGeometry(QRect(30, 25, 441, 41))
        font = QFont()
        font.setFamily("Verdana")
        font.setPointSize(9)
        self.label.setFont(font)
        self.label.setText("Preparing ...")

        # Cancel/Close Button
        self.cancelButton = QPushButton("Cancel", self.Dialog)
        self.cancelButton.setGeometry(QRect(190, 140, 111, 31))
        self.cancelButton.clicked.connect(self.cancel)

    def run(self):
        self.Dialog.exec_()

    def cancel(self):
        self.stop_signal.emit()
        self.label.setText("Please wait ...")
        self.cancelButton.setEnabled(False)

    @pyqtSlot(int)
    def update_progress_bar(self, num):
        self.progressBar.setValue(num)

    @pyqtSlot(str)
    def update_chapter_name(self, chapter_name):
        self.label.setText(chapter_name)

    @pyqtSlot(int)
    def set_max_progess_bar_value(self, max_value):
        self.progressBar.setMaximum(max_value)

    @pyqtSlot()
    def close_when_done(self):
        self.cancelButton.setText("Close")
        self.label.setText("Download Finished!")
        self.cancelButton.clicked.connect(self.Dialog.close)
        self.cancelButton.setEnabled(True)


class IndputChapterDialog(QDialog):

    chapterInput = pyqtSignal(str, str)

    def init_ui(self):
        # Dialog
        self.Dialog = QDialog()
        self.Dialog.setWindowModality(Qt.NonModal)
        self.Dialog.resize(410, 190)
        self.Dialog.setWindowFlags(Qt.MSWindowsFixedSizeDialogHint)
        self.Dialog.setWindowIcon(QIcon((resource_path("icon.ico"))))
        font = QFont()
        font.setFamily("Verdana")
        self.Dialog.setFont(font)
        self.Dialog.setModal(True)
        self.Dialog.setWindowTitle("Please Input Chapter ...")

        # Button Box
        self.buttonBox = QDialogButtonBox(self.Dialog)
        self.buttonBox.setGeometry(QRect(190, 140, 201, 32))
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)

        # From Chapter
        self.labelFromChapter = QLabel(self.Dialog)
        self.labelFromChapter.setGeometry(QRect(20, 30, 121, 31))
        font = QFont()
        font.setFamily("Verdana")
        font.setPointSize(9)
        self.labelFromChapter.setFont(font)
        self.labelFromChapter.setText("From Chapter:")

        self.inputFromChapter = QLineEdit(self.Dialog)
        self.inputFromChapter.setGeometry(QRect(140, 30, 251, 31))

        # To Chapter
        self.labelToChapter = QLabel(self.Dialog)
        self.labelToChapter.setGeometry(QRect(20, 80, 91, 31))
        font = QFont()
        font.setFamily("Verdana")
        font.setPointSize(9)
        self.labelToChapter.setFont(font)
        self.labelToChapter.setText("To Chapter:")

        self.inputToChapter = QLineEdit(self.Dialog)
        self.inputToChapter.setGeometry(QRect(140, 80, 251, 31))

        # Signal
        self.buttonBox.accepted.connect(self.get_chapter_input)
        self.buttonBox.rejected.connect(self.Dialog.reject)
        QMetaObject.connectSlotsByName(self.Dialog)

    def start(self):
        self.init_ui()
        self.Dialog.exec_()

    def get_chapter_input(self):
        self.chapterInput.emit(self.inputFromChapter.text(), self.inputToChapter.text())
        self.Dialog.close()


class DownloadEngine(QThread):

    stop_signal = 0

    valueProgress = pyqtSignal(int)
    maxProgressValue = pyqtSignal(int)
    chapterName = pyqtSignal(str)
    isDone = pyqtSignal()

    def __init__(self, parent=None):
        super(DownloadEngine, self).__init__(parent)

    def set_manga(self, manga):
        self.current_manga = manga
        self.image_formats = [".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp"]
        self.stop_signal = 0
        self.error403_signal = 0
        self.error403_chapters = []

    def reset_error_403(self):
        self.error403_signal = 0
        self.error403_chapters = []

    @pyqtSlot()
    def stop_download(self):
        self.stop_signal = 1

    def run(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "firefox", "platform": "windows", "mobile": False},
            sess=self.session,
        )
        self.crawl_chapter_data_list()

    def crawl_chapter_data_list(self):
        chapter_list = []

        # Get each chapter info
        for index in self.current_manga.list_of_download_chapter:
            chapter_detail = {}
            try:
                chapter_detail["chapter_url"] = self.current_manga.chapter_url_list[
                    index
                ]
            except Exception:
                print("Error get chapter url: " + str(index))
            chapter_detail["chapter_name"] = self.current_manga.chapter_name_list[index]
            if ":" in chapter_detail["chapter_name"]:
                chapter_detail["chapter_name"] = chapter_detail["chapter_name"].split(
                    ":"
                )[0]
            chapter_list.append(chapter_detail)

        # Remove downloaded chapters | if not create directory
        chapter_list = [
            i_chapter
            for i_chapter in chapter_list
            if not isdir(self.current_manga.save_path + "/" + i_chapter["chapter_name"])
        ]
        chapter_list = list(reversed(chapter_list))

        if chapter_list:
            # Set progress bar max value at 100%
            self.maxProgressValue.emit(len(chapter_list))

            # Create directory and start to download
            index = 0
            for chapter_data in chapter_list:

                if self.stop_signal:
                    break

                chapter_dir_path = (
                    self.current_manga.save_path + "/" + chapter_data["chapter_name"]
                )
                mkdir(
                    chapter_dir_path.replace('"', "")
                    .replace("'", "")
                    .replace("?", "")
                    .replace("!", "")
                )
                chapter_data["chapter_dir_path"] = chapter_dir_path
                self.get_chapter_contents(chapter_data)
                index += 1
                self.valueProgress.emit(index)  # Update progress bar

        # Error 403 Dialog
        if self.error403_signal:
            chapters_403 = ", ".join(self.error403_chapters)
            MessageBox("Can not download some images: " + chapters_403)
            self.reset_error_403()
        # Save error 403 to json file
        if list_error_403:
            # process with unicode language
            with open(f"{self.current_manga.save_path}/error_403.json", "w", encoding="utf-8") as f:
                json.dump(list_error_403, f, ensure_ascii=False)

        # Update download Finish Dialog
        self.isDone.emit()
        if chapter_list:
            self.valueProgress.emit(len(chapter_list))
        else:
            self.valueProgress.emit(100)
        print("Download Done")

    def get_image_urls(self, soup):
        contents = []
        # Get image urls
        list_img = soup.select("div.reading-detail.box_doc>div.page-chapter>img")

        for content_url in list_img:
            if content_url not in contents:
                if content_url.has_attr("src") and any(
                    img_fm in content_url["src"] for img_fm in self.image_formats
                ):
                    img_url = content_url["src"]
                elif content_url.has_attr("data-original"):
                    img_url = content_url["data-original"]
                elif content_url.has_attr("data-cdn") and any(
                    img_fm in content_url["data-cdn"] for img_fm in self.image_formats
                ):
                    img_url = content_url["data-cdn"]
                elif content_url.has_attr("data-src"):
                    img_url = content_url["data-src"]
                else:
                    img_url = content_url["src"]
                contents.append(self.format_img_url(img_url))
        return contents

    def format_img_url(self, url):
        # replace if url not start with http
        return (
            url.replace("https://", "//")
            .replace("http://", "//")
            .replace("//", "https://")
        )

    def get_image_paths(self, chapter_dir_path, contents):
        img_path_list = []
        image_index = 1

        for img_url in contents:
            img_name = img_url.split("/")[-1]
            img_path_name = (
                chapter_dir_path + "/image_" + "{0:0=3d}".format(image_index) + ".jpg"
            )
            img_path_list.append(img_path_name)
            image_index += 1

        return img_path_list

    def get_chapter_contents(self, chapter_data):
        get_chapter_done = False
        while not get_chapter_done:
            try:
                # Request chapter url
                request = self.scraper.get(
                    chapter_data["chapter_url"], headers=HEADERS, timeout=10
                )
                soup = BeautifulSoup(request.text, "html.parser")

                # Get image url
                contents = self.get_image_urls(soup)

                # Get image name
                img_path_list = self.get_image_paths(
                    chapter_data["chapter_dir_path"], contents
                )

                image_data_list = list(
                    map(lambda x, y: (x, y), img_path_list, contents)
                )

                # Update Dialog
                chapter_name = "Downloading " + chapter_data["chapter_name"] + " ....."
                print(chapter_name)
                self.chapterName.emit(chapter_name)

                # Threading for download each image
                with ThreadPoolExecutor(max_workers=10) as executor:
                    executor.map(self.download_image, image_data_list)

                # Save error chapter
                if self.error403_signal:
                    self.error403_chapters.append(chapter_data["chapter_name"])

                get_chapter_done = True
            except Exception as e:
                # MessageBox(repr(e))
                # MessageBox('Error get chapter info. Please try again later.')
                print("Error Get Chapter Info: " + chapter_data["chapter_url"])

        print("Finish " + chapter_data["chapter_name"])

    def download_image(self, image_data_list):
        if not self.stop_signal:
            img_path_name, img_url = image_data_list

            # Limit download time of an image is 5 secs
            start = time.time()
            timeout = 10
            while True:
                try:
                    img_data = self.scraper.get(img_url, headers=HEADERS, timeout=10)
                    if img_data.status_code == 403:
                        self.error403_signal = 1
                    else:
                        with open(img_path_name, "wb") as handler:
                            handler.write(img_data.content)
                    break
                except Exception as e:
                    print(format_exc())
                    if time.time() - start > timeout:
                        list_error_403.append(
                            {"img_url": img_url, "img_path_name": img_path_name}
                        )
                        # MessageBox('Error download image: ' + img_path_name)
                        break
                    print("Retry: download image: " + img_url)
                    time.sleep(1)
                    continue


class Bridge(QObject):

    current_manga = MangaInfo()

    @pyqtSlot(str, result=str)
    def check_valid_url(self, input_str):
        page = "ErrorPage.qml"

        domain = urlparse(input_str)
        referer_header = "{uri.scheme}://{uri.netloc}/".format(uri=domain)
        HEADERS["Referer"] = referer_header

        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "firefox", "platform": "windows", "mobile": False},
            sess=self.session,
        )
        if any(x in input_str for x in ["nhattruyen", "nettruyen"]):
            try:
                request = self.scraper.get(input_str, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(request.text, "html.parser")
                if soup.find("div", id="nt_listchapter"):
                    self.current_manga.manga_url = str(input_str)
                    self.crawl_manga_home_page()
                    page = "MangaPage.qml"
            except Exception:
                MessageBox("Error in connect manga page. Please try again.")
                print("Error in connect manga page !")
        return page

    @pyqtSlot(result=str)
    def get_manga_thumbnail(self):
        try:
            image_thumnail = self.scraper.get(
                self.current_manga.thumbnail, headers=HEADERS, timeout=10
            )
            return (
                "data:image/png;base64,"
                + str(base64.b64encode(image_thumnail.content))[1:]
            )
        except Exception:
            print("Error: Can not get thumnail image " + self.current_manga.thumbnail)

    def format_img_url(self, url):
        return (
            url.replace("https://", "//")
            .replace("http://", "//")
            .replace("//", "https://")
        )

    @pyqtSlot(result=str)
    def getMangaName(self):
        return self.current_manga.manga_name

    @pyqtSlot(result=str)
    def get_manga_author(self):
        return self.current_manga.author

    @pyqtSlot(result=str)
    def get_manga_categories(self):
        return self.current_manga.categories

    @pyqtSlot(result=str)
    def get_manga_viewed(self):
        return self.current_manga.viewed

    @pyqtSlot(result=str)
    def get_manga_description(self):
        return self.current_manga.description

    @pyqtSlot(result=str)
    def get_manga_last_updated(self):
        return self.current_manga.last_updated

    @pyqtSlot(result=str)
    def get_manga_last_chapter(self):
        return self.current_manga.latest_chapter

    @pyqtSlot(result=list)
    def get_chapter_list(self):
        return self.current_manga.chapter_name_list

    def get_chapter_index(self, chapter_input):
        for chapter in self.current_manga.chapter_name_list:
            chapter_name = chapter.split()[1]
            if ":" in chapter_name:
                chapter_name = chapter_name[:-1]
            if chapter_input == chapter_name:
                return self.current_manga.chapter_name_list.index(chapter)
        return None

    @pyqtSlot(str, str)
    def get_chapter_input(self, from_chapter_input, to_chapter_input):
        from_chapter_index = self.get_chapter_index(from_chapter_input)
        to_chapter_index = self.get_chapter_index(to_chapter_input)

        if from_chapter_index is not None and to_chapter_index is not None:
            if from_chapter_index > to_chapter_index:
                from_chapter_index, to_chapter_index = (
                    to_chapter_index,
                    from_chapter_index,
                )
            self.current_manga.list_of_download_chapter = list(
                range(from_chapter_index, to_chapter_index + 1)
            )

    def get_list_of_download_chapter(self, list_of_chapters):
        if not list_of_chapters:
            inputDialog = IndputChapterDialog()
            inputDialog.chapterInput.connect(self.get_chapter_input)
            inputDialog.start()
        elif list_of_chapters[0] == "all":
            self.current_manga.list_of_download_chapter = list(
                range(len(self.current_manga.chapter_name_list))
            )
        else:
            self.current_manga.list_of_download_chapter = sorted(list_of_chapters)

        return self.current_manga.list_of_download_chapter

    @pyqtSlot(str, list)
    def download_chapter(self, input_str, list_of_chapters):

        if self.get_list_of_download_chapter(list_of_chapters):
            path = input_str[8:] + "/" + self.current_manga.manga_name
            path = (
                path.replace('"', "").replace("'", "").replace("?", "").replace("!", "")
            )
            if not isdir(path):
                mkdir(path)

            self.current_manga.save_path = path

            engine = DownloadEngine(self)
            engine.set_manga(self.current_manga)
            dialog = WaitingDialog()
            dialog.init_ui()
            engine.valueProgress.connect(dialog.update_progress_bar)
            engine.maxProgressValue.connect(dialog.set_max_progess_bar_value)
            engine.chapterName.connect(dialog.update_chapter_name)
            engine.isDone.connect(dialog.close_when_done)
            dialog.stop_signal.connect(engine.stop_download)
            engine.start()
            dialog.run()

    def crawl_manga_home_page(self):
        try:
            print("Start crawling ---------", self.current_manga.manga_url)
            request = self.scraper.get(
                self.current_manga.manga_url, headers=HEADERS, timeout=10
            )
            soup = BeautifulSoup(request.text, "html.parser")

            # Extract manga name
            title_detail = soup.find("h1", class_="title-detail")
            if title_detail:
                self.current_manga.manga_name = title_detail.text.strip()
            else:
                raise ValueError("Error in crawling manga name!")

            # Extract thumbnail
            col_image_div = soup.find("div", class_="col-image")
            img_tag = col_image_div.find("img") if col_image_div else None
            if img_tag and isinstance(img_tag, Tag) and img_tag.has_attr("src"):
                self.current_manga.thumbnail = str(img_tag["src"]).strip()
            else:
                self.current_manga.thumbnail = ""
            if self.current_manga.thumbnail and not self.current_manga.thumbnail.startswith("http"):
                self.current_manga.thumbnail = "http:" + self.current_manga.thumbnail
            if self.current_manga.thumbnail.startswith("http:"):
                self.current_manga.thumbnail = "https" + self.current_manga.thumbnail[4:]

            # Extract author
            author_tag = soup.find("li", class_="author")
            if author_tag:
                author_p = author_tag.find("p", class_="col-xs-8")
                self.current_manga.author = author_p.string.strip() if author_p else ""

            # Extract categories
            categories_tag = soup.find("li", class_="kind")
            if categories_tag:
                category_links = categories_tag.find("p", class_="col-xs-8").find_all("a")
                categories_list = [x.string.strip() for x in category_links if x.string]
                self.current_manga.categories = " - ".join(categories_list)

            # Extract views
            viewed_tag = soup.find("ul", class_="list-info")
            if viewed_tag:
                row_items = viewed_tag.find_all("li", class_="row")
                viewed_p = row_items[-1].find("p", class_="col-xs-8") if row_items else None
                self.current_manga.viewed = viewed_p.text.strip() if viewed_p else ""

            # Extract last updated
            time_tag = soup.find("time", class_="small")
            if time_tag:
                self.current_manga.last_updated = time_tag.string.strip()[15:-1]

            # Extract latest chapter
            chapter_div = soup.find("div", id="nt_listchapter")
            if chapter_div:
                latest_chapter_tag = chapter_div.find_all("li")[1].find("div", class_="chapter").find("a")
                manga_latest_chapter = latest_chapter_tag.text.strip() if latest_chapter_tag else ""
                if ":" in manga_latest_chapter:
                    manga_latest_chapter = manga_latest_chapter.split(":")[0]
                self.current_manga.latest_chapter = manga_latest_chapter

            # Extract description
            detail_content_div = soup.find("div", class_="detail-content")
            if detail_content_div:
                description_div = detail_content_div.find("div")
                self.current_manga.description = description_div.text.strip() if description_div else ""

            # Extract chapter names
            block_chapter = soup.find("ul", id="desc")
            if block_chapter:
                self.current_manga.chapter_name_list = [
                    i.find("a").text.strip()
                    for i in block_chapter.find_all("div", class_="chapter")
                ]

            # Extract chapter URLs
            chapter_url_list = []
            chapter_ul = soup.find("div", id="nt_listchapter").find("ul")
            if chapter_ul:
                for chapter in chapter_ul.find_all("a"):
                    if chapter.has_attr("href"):
                        chapter_url_list.append(chapter["href"].strip())
            self.current_manga.chapter_url_list = chapter_url_list

        except Exception as e:
            print(f"Exception occurred while crawling manga: {repr(e)}")
            # Replace MessageBox call with print or logging if GUI isn't available
            MessageBox(repr(e))


def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", path.abspath("."))
    except Exception:
        base_path = path.abspath(".")

    return path.join(base_path, relative_path)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon((resource_path("icon.ico"))))
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"

    engine = QQmlApplicationEngine()
    engine.load(QUrl("qrc:/resources/view.qml"))

    # Bridge to GUI
    bridge = Bridge()

    # Expose the Python object to QML
    context = engine.rootContext()
    context.setContextProperty("con", bridge)

    app.exec_()
