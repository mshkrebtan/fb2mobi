#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import cssutils
import codecs
import time
import subprocess
import webbrowser
import logging
import shutil

from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QTreeWidgetItem, QMessageBox, QDialog, QWidget, 
                            QLabel, QAbstractItemView, QSizePolicy)
from PyQt5.QtGui import QIcon, QPixmap 
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QEvent, Qt, QTranslator, QLocale, QCoreApplication, QTimer

from ui.MainWindow import Ui_MainWindow
from ui.AboutDialog import Ui_AboutDialog
from ui.SettingsDialog import Ui_SettingsDialog

from ui.gui_config import GuiConfig
import ui.images_rc
import ui.ui_version
from ui.fb2meta import Fb2Meta
from ui.fontdb import FontDb

from modules.config import ConverterConfig
import modules.default_css
import fb2mobi
import synccovers
import version


TREE_LIST_CSS_ACTIVE = "selection-color: white; selection-background-color: #386CDA; alternate-background-color: #F3F6FA;"
TREE_LIST_CSS_UNACTIVE = "selection-color: black; selection-background-color: #D4D4D4; alternate-background-color: #F3F6FA;"

SUPPORT_URL = u'http://www.the-ebook.org/forum/viewtopic.php?t=30380'

_translate = QCoreApplication.translate


class CopyThread(QThread):
    copyBegin = pyqtSignal(object)
    copyDone = pyqtSignal()
    copyAllDone = pyqtSignal()

    def __init__(self, files, dest_path, synccovers):
        super(CopyThread, self).__init__()
        self.files = files
        self.dest_path = dest_path
        self.thumbnail_path = ''
        self.synccovers = synccovers

        # Определим и проверим путь до иниатюр обложек на Kindle
        if self.dest_path:
            self.thumbnail_path = os.path.join(os.path.dirname(os.path.abspath(dest_path)), 'system', 'thumbnails')
            if not os.path.isdir(self.thumbnail_path):
                self.thumbnail_path = ''


    def run(self):
        for file in self.files:
            self.copyBegin.emit(file)
            try:
                if os.path.exists(self.dest_path):                    
                    shutil.copy2(file, self.dest_path)
                    src_sdr_dir = '{0}.{1}'.format(os.path.splitext(file)[0], 'sdr')
                    dest_sdr_dir = os.path.join(self.dest_path, os.path.split(src_sdr_dir)[1])

                    # Обработка apnx-файла, он находится в каталоге <имя файла книги>.sdr
                    if os.path.isdir(src_sdr_dir):
                        if os.path.isdir(dest_sdr_dir):
                           shutil.rmtree(dest_sdr_dir)

                        shutil.copytree(src_sdr_dir, dest_sdr_dir)

                    # Создадим миниатюру обложки, если оперделили путь и установлен признак
                    if self.thumbnail_path and self.synccovers:
                        dest_file = os.path.join(self.dest_path, os.path.split(file)[1])
                        if os.path.exists(dest_file):
                            synccovers.process_file(dest_file, self.thumbnail_path, 330, 470, False, False)
            except:
                pass
            self.copyDone.emit()

        self.copyAllDone.emit()


class ConvertThread(QThread):
    convertBegin = pyqtSignal(object)
    convertDone = pyqtSignal(object, bool, object)
    convertAllDone = pyqtSignal()

    def __init__(self, files, gui_config):
        super(ConvertThread, self).__init__()
        self.files = files
        self.config = gui_config.converterConfig
        self.cancel = False

        self.config.setCurrentProfile(gui_config.currentProfile)
        self.config.output_format = gui_config.currentFormat
        if gui_config.embedFontFamily:
            css_file = os.path.join(os.path.dirname(gui_config.config_file), 'profiles', '_font.css')
            if os.path.exists(css_file):
                self.config.current_profile['css'] = css_file

        if not gui_config.convertToSourceDirectory:
            self.config.output_dir = gui_config.outputFolder
        else:
            self.config.output_dir = None

        if gui_config.hyphens.lower() == 'yes':
            self.config.current_profile['hyphens']= True
        elif gui_config.hyphens.lower()  == 'no':
            self.config.current_profile['hyphens'] = False


    def run(self):
        dest_file = None

        for file in self.files:
            result = True
            dest_file = None
            if not self.cancel:
                self.convertBegin.emit(file)
                dest_file = self.getDestFileName(file)
                # Перед конвертацией удалим старый файл
                if os.path.exists(dest_file):
                    os.remove(dest_file)

                fb2mobi.process_file(self.config, file, None)

                if not os.path.exists(dest_file):
                    dest_file = None
                    result = False
                else:
                    dest_file = self.getDestFileName(file)

                self.convertDone.emit(file, result, dest_file)
            else:
                break

        self.convertAllDone.emit()


    def getDestFileName(self, file):
        if self.config.output_dir is None:
            output_dir = os.path.abspath(os.path.split(file)[0])
        else:
            output_dir = os.path.abspath(self.config.output_dir)
        file_name = os.path.join(output_dir, os.path.splitext(os.path.split(file)[1])[0])
        if os.path.splitext(file_name)[1].lower() == '.fb2':
            file_name = os.path.splitext(file_name)[0]

        return '{0}.{1}'.format(file_name, self.config.output_format)


    def stop(self):
        self.cancel = True


class SettingsDialog(QDialog, Ui_SettingsDialog):
    def __init__(self, parent, config):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)

        self.config = config

        for p in self.config.converterConfig.profiles:
            self.comboProfile.addItem('{0} ({1})'.format(p, self.config.converterConfig.profiles[p]['description']), p)

        for f in ['mobi', 'azw3', 'epub']:
            self.comboFormat.addItem(f, f)

        self.comboProfile.setCurrentIndex(self.comboProfile.findData(self.config.currentProfile))
        self.comboFormat.setCurrentIndex(self.comboFormat.findData(self.config.currentFormat))        
        self.lineDestPath.setText(self.config.outputFolder)
        self.checkConvertToSrc.setChecked(self.config.convertToSourceDirectory)
        self.checkWriteLog.setChecked(self.config.writeLog)

        if self.config.hyphens.lower() == 'yes':
            self.radioHypYes.setChecked(True)
            self.radioHypNo.setChecked(False)
            self.radioHypProfile.setChecked(False)

        elif self.config.hyphens.lower() == 'no':
            self.radioHypYes.setChecked(False)
            self.radioHypNo.setChecked(True)
            self.radioHypProfile.setChecked(False)

        elif self.config.hyphens.lower() == 'profile':
            self.radioHypYes.setChecked(False)
            self.radioHypNo.setChecked(False)
            self.radioHypProfile.setChecked(True)

        # Строим выбор шрифта
        # для начала обновим список доступных шрифтов
        self.config.fontDb.update_db()
        self.comboFont.addItem('None', _translate('fb2mobi-gui', 'None'))
        for font in self.config.fontDb.families:
            self.comboFont.addItem(font, font)

        if self.config.embedFontFamily is None:
            self.comboFont.setCurrentIndex(self.comboFont.findData('None'))
        else:
            self.comboFont.setCurrentIndex(self.comboFont.findData(self.config.embedFontFamily))

        self.lineKindlePath.setText(self.config.kindlePath)
        self.checkCopyAfterConvert.setChecked(self.config.kindleCopyToDevice)
        self.checkSyncCovers.setChecked(self.config.kindleSyncCovers)
        self.enableCheckSyncCovers(self.config.kindleCopyToDevice)


    def selectDestPath(self):
        self.lineDestPath.setText(self.selectPath(self.lineDestPath.text()))

    def selectKindlePath(self):
        self.lineKindlePath.setText(self.selectPath(self.lineKindlePath.text()))

    def selectPath(self, path):
        if not path:
            path = os.path.expanduser('~')

        dlgPath = QFileDialog(self, _translate('fb2mobi-gui', 'Select folder'), path)
        dlgPath.setFileMode(QFileDialog.Directory)
        dlgPath.setOption(QFileDialog.ShowDirsOnly, True)

        if dlgPath.exec_():
            for d in dlgPath.selectedFiles():
                path = os.path.normpath(d)

        return path


    def checkConvertToSrcClicked(self, state):
        enabled = False
        if state == 0:
            enabled = True

        self.lineDestPath.setEnabled(enabled)
        self.btnSelectDestPath.setEnabled(enabled)

    def checkCopyAfterConvertClicked(self, state):
        checked = False
        if state == 2:
            checked = True

        self.enableCheckSyncCovers(checked)

    def enableCheckSyncCovers(self, enabled):
        if enabled:
            self.checkSyncCovers.setEnabled(True)
        else:
            self.checkSyncCovers.setEnabled(False)
            self.checkSyncCovers.setChecked(False)


    def closeAccept(self):
        self.config.currentProfile = self.comboProfile.currentData()
        self.config.currentFormat = self.comboFormat.currentData()
        self.config.outputFolder = os.path.normpath(self.lineDestPath.text())
        self.config.convertToSourceDirectory = self.checkConvertToSrc.isChecked()
        if self.radioHypYes.isChecked():
           self.config.hyphens = 'Yes'
        elif self.radioHypNo.isChecked():
            self.config.hyphens = 'No'
        else:
            self.config.hyphens = 'Profile'

        if self.lineKindlePath.text():
            self.config.kindlePath = os.path.normpath(self.lineKindlePath.text())
        self.config.kindleCopyToDevice = self.checkCopyAfterConvert.isChecked()
        self.config.kindleSyncCovers = self.checkSyncCovers.isChecked()
        self.config.writeLog = self.checkWriteLog.isChecked()
        if self.comboFont.currentData() == 'None':
            self.config.embedFontFamily = None
        else:
            self.config.embedFontFamily = self.comboFont.currentData()


class AboutDialog(QDialog, Ui_AboutDialog):
    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent)
        self.setupUi(self)

        image  = QPixmap(':/Images/icon128.png')
        self.labelImage.setPixmap(image)
        self.labelVersion.setText(version.VERSION)
        self.labelUIVersion.setText(ui.ui_version.VERSION)

        self.setFixedSize(self.size())
       

class MainAppWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainAppWindow, self).__init__()
        self.setupUi(self)

        self.savedPath = ''
        self.convertRun = False
        self.convertedCount = 0
        self.copyCount = 0
        self.convertedFiles = []

        self.setAcceptDrops(True)

        self.config_file = None
        self.log_file = None
        self.log = None
        self.config = {}

        self.convert_worker = None
        self.copy_worker = None
        self.is_convert_cancel = False

        # Список стилей для встраивания шрифтов
        self.style_rules = ['.titleblock', '.text-author', 'p', 'p.title', '.cite', '.poem', 
               '.table th', '.table td', '.annotation']

        self.rootFileList = self.treeFileList.invisibleRootItem()
        self.iconWhite = QIcon(':/Images/bullet_white.png')
        self.iconRed = QIcon(':/Images/bullet_red.png')
        self.iconGreen = QIcon(':/Images/bullet_green.png')
        self.iconGo = QIcon(':/Images/bullet_go.png')

        self.pixmapConnected = QPixmap(':/Images/bullet_green.png')
        self.pixmapNotConnected = QPixmap(':/Images/bullet_red.png')

        config_file_name = "fb2mobi.config"
        log_file_name = "fb2mobi.log"
        gui_config_file = 'fb2mobi-gui.config'

        # Определяем, где находится файл конфигурации. 
        # Если есть в домашнем каталоге пользователя (для windows ~/2bmobi, для остальных ~/.fb2mobi),
        # то используется он.
        # Иначе - из каталога программы
        application_path = os.path.normpath(fb2mobi.get_executable_path())
        config_path = None
        if sys.platform == 'win32':
            config_path = os.path.normpath(os.path.join(os.path.expanduser('~'), 'fb2mobi'))
        else:
            config_path = os.path.normpath(os.path.join(os.path.expanduser('~'), '.fb2mobi'))

        if not os.path.exists(os.path.join(config_path, config_file_name)):
            config_path = application_path

        self.config_file = os.path.normpath(os.path.join(config_path, config_file_name))
        self.log_file = os.path.normpath(os.path.join(config_path, log_file_name))
        self.gui_config_file = os.path.normpath(os.path.join(config_path, gui_config_file))
        
        self.gui_config = GuiConfig(self.gui_config_file)
        self.gui_config.converterConfig = ConverterConfig(self.config_file)

        log = logging.getLogger('fb2mobi')
        log.setLevel("DEBUG")

        log_stream_handler = logging.StreamHandler()
        log_stream_handler.setLevel(fb2mobi.get_log_level(self.gui_config.converterConfig.console_level))
        log_stream_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        log.addHandler(log_stream_handler)

        if self.gui_config.writeLog:
            log_file_handler = logging.FileHandler(filename=self.log_file, mode='a', encoding='utf-8')
            log_file_handler.setLevel(fb2mobi.get_log_level(self.gui_config.converterConfig.log_level))
            log_file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
            log.addHandler(log_file_handler)

        self.gui_config.converterConfig.log = log
        # Строим базу доступных шрифтов
        self.font_path = os.path.normpath(os.path.join(config_path, 'profiles/fonts'))
        if os.path.exists(self.font_path):
            self.gui_config.fontDb = FontDb(self.font_path)

        if not self.gui_config.outputFolder:
            self.gui_config.outputFolder = os.path.abspath(os.path.expanduser("~/Desktop"))

        if not self.gui_config.currentFormat:
            self.gui_config.currentFormat = 'mobi'

        if not self.gui_config.currentProfile:
            for p in self.gui_config.converterConfig.profiles:
                self.gui_config.currentProfile = p
                break

        if not self.gui_config.convertToSourceDirectory:
            self.gui_config.convertToSourceDirectory = False

        if not self.gui_config.hyphens:
            self.gui_config.hyphens = 'profile'

        if self.gui_config.geometry['x'] and self.gui_config.geometry['y']:
            self.move(self.gui_config.geometry['x'], self.gui_config.geometry['y'])
            self.resize(self.gui_config.geometry['width'], self.gui_config.geometry['height'])

        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)        

        self.setWindowIcon(QIcon(':/Images/icon32.png'))
        self.treeFileList.installEventFilter(self)

        self.labelKindleStatus = QLabel()
        self.labelKindleStatusIcon = QLabel()
        self.labelStatus = QLabel()

        # Для Mac OS небольшой хак UI
        if sys.platform == 'darwin':
            font = self.labelKindleStatus.font()
            font.setPointSize(11)
            self.labelKindleStatus.setFont(font)
            self.labelStatus.setFont(font)
            self.treeFileList.setFont(font)
            self.treeFileList.setAttribute(Qt.WA_MacShowFocusRect, 0)
            self.treeFileList.setStyleSheet(TREE_LIST_CSS_ACTIVE)
            self.labelStatus.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            

        self.statusBar().addWidget(self.labelStatus, 1) 
        self.statusBar().addWidget(self.labelKindleStatusIcon)        
        self.statusBar().addWidget(self.labelKindleStatus)

        if self.gui_config.columns['0']:
            self.treeFileList.setColumnWidth(0, self.gui_config.columns['0']) 
            self.treeFileList.setColumnWidth(1, self.gui_config.columns['1']) 
            self.treeFileList.setColumnWidth(2, self.gui_config.columns['2']) 


        self.timerKindleStatus = QTimer()
        self.timerKindleStatus.timeout.connect(self.checkKindleStatus)
        self.timerKindleStatus.start(1500)


    def event(self, event):
        if event.type() == QEvent.WindowActivate:
            if sys.platform == 'darwin':
               self.treeFileList.setStyleSheet(TREE_LIST_CSS_ACTIVE) 
        elif event.type() == QEvent.WindowDeactivate:
            if sys.platform == 'darwin':
               self.treeFileList.setStyleSheet(TREE_LIST_CSS_UNACTIVE) 

        return super(MainAppWindow, self).event(event)


    def checkKindleStatus(self):
        if self.gui_config.kindleCopyToDevice:
            if os.path.isdir(self.gui_config.kindlePath):
                self.labelKindleStatusIcon.setPixmap(self.pixmapConnected)
                self.labelKindleStatus.setText(_translate('fb2mobi-gui', 'Device connected'))
            else:
                self.labelKindleStatusIcon.setPixmap(self.pixmapNotConnected)
                self.labelKindleStatus.setText(_translate('fb2mobi-gui', 'Device not connected'))

        else:
            self.labelKindleStatus.setText('')
            self.labelKindleStatusIcon.clear()


    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            if (event.key() == Qt.Key_Delete or (event.key() == Qt.Key_Backspace 
                and event.modifiers() == Qt.ControlModifier)):
                self.deleteRecAction()
                return True
                
        return QWidget.eventFilter(self, source, event)


    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()


    def dropEvent(self, event):
        file_list = [u.toLocalFile() for u in event.mimeData().urls()]        
        self.addFiles(file_list)
        event.accept()


    def selectAllAction(self):
        self.treeFileList.selectAll()


    def deleteRecAction(self):
        for item in self.treeFileList.selectedItems():
            self.rootFileList.removeChild(item)
     

    def openLog(self):
        self.openFile(self.log_file)


    def checkDestDir(self):
        filename = os.path.normpath(self.gui_config.outputFolder)
        if not os.path.exists(filename):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText(_translate('fb2mobi-gui', 'Folder does not exist.'))
            msg.setWindowTitle(_translate('fb2mobi-gui', 'Error'))
            msg.exec_()

            return False
        else:
            return True


    def showMessage(self, message):
        self.labelStatus.setText(message)


    def clearMessage(self):
        self.labelStatus.setText('')


    def startConvert(self):
        if self.rootFileList.childCount() > 0:
            if not self.checkDestDir():
                return

            if not self.convertRun:
                self.btnStart.setText(_translate('fb2mobi-gui', 'Cancel'))
                self.actionConvert.setText(_translate('fb2mobi-gui', 'Cancel conversion'))
                self.convertRun = True
                self.is_convert_cancel = False
                self.allControlsEnabled(False)

                files = []
                for i in range(self.rootFileList.childCount()):
                    files.append(self.rootFileList.child(i).text(2))

                self.progressBar.setRange(0, len(files))
                self.progressBar.setValue(0)
                self.progressBar.setVisible(True)
                self.convertedCount = 0
                self.convertedFiles = []
                
                self.convert_worker = ConvertThread(files, self.gui_config)
                self.convert_worker.convertBegin.connect(self.convertBegin)
                self.convert_worker.convertDone.connect(self.convertDone)
                self.convert_worker.convertAllDone.connect(self.convertAllDone)

                if self.gui_config.embedFontFamily:
                    self.generateFontCSS()

                self.convert_worker.start()
            else:
                self.is_convert_cancel = True
                self.convert_worker.stop() 
                self.btnStart.setEnabled(False)
                self.actionConvert.setEnabled(False)


    def generateFontCSS(self):
        css_string = modules.default_css.default_css
        css = cssutils.parseString(css_string)

        font_regular = ''
        font_italic = ''
        font_bold = ''
        font_bolditalic = ''

        print(self.gui_config.embedFontFamily)
        print(self.gui_config.fontDb.families[self.gui_config.embedFontFamily])

        if 'Regular' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_regular = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Regular']

        if 'Italic' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_italic = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Italic']
        else:
            font_italic = font_regular

        if 'Bold' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_bold = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Bold']
        else:
            font_bold = font_regular

        if 'Bold Italic' in self.gui_config.fontDb.families[self.gui_config.embedFontFamily]:
            font_bolditalic = self.gui_config.fontDb.families[self.gui_config.embedFontFamily]['Bold Italic']
        else:
            font_bolditalic = font_italic

        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); }}'.format(font_regular))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-style: italic; }}'.format(font_italic))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-weight: bold; }}'.format(font_bold))
        css.add('@font-face {{ font-family: "para"; src: url("fonts/{0}"); font-style: italic; font-weight: bold; }}'.format(font_bolditalic))

        for rule in css:
            if rule.type == rule.STYLE_RULE:
                if rule.selectorText in self.style_rules:
                    rule.style['font-family'] = '"para"'

        css_path = os.path.join(os.path.dirname(self.config_file), 'profiles')
        if not os.path.exists(css_path):
            os.makedirs(css_path)

        with codecs.open(os.path.join(css_path, '_font.css'), 'w', 'utf-8') as f:
            f.write(str(css.cssText, 'utf-8'))


    def convertAllDone(self):
        self.convertRun = False        
        self.btnStart.setText(_translate('fb2mobi-gui', 'Start'))
        self.actionConvert.setText(_translate('fb2mobi-gui', 'Start conversion'))
        self.allControlsEnabled(True)
        self.clearMessage()

        time.sleep(0.5)    
        self.progressBar.setVisible(False)
        
        if self.gui_config.kindleCopyToDevice and not self.is_convert_cancel:
            if self.gui_config.kindlePath and os.path.exists(self.gui_config.kindlePath):
                self.copy_worker = CopyThread(self.convertedFiles, self.gui_config.kindlePath, 
                                              self.gui_config.kindleSyncCovers)
                self.copy_worker.copyBegin.connect(self.copyBegin)
                self.copy_worker.copyDone.connect(self.copyDone)
                self.copy_worker.copyAllDone.connect(self.copyAllDone)

                self.progressBar.setRange(0, len(self.convertedFiles))
                self.progressBar.setValue(0)
                self.copyCount = 0

                self.progressBar.setVisible(True)
                self.allControlsEnabled(False, True)
                self.copy_worker.start()
            else:
                msg = QMessageBox(QMessageBox.Critical, _translate('fb2mobi-gui', 'Error'), 
                                  _translate('fb2mobi-gui', 'Error when copying files - device not found.'), 
                                  QMessageBox.Ok, self)
                msg.exec_()


    def copyBegin(self, file):
        self.showMessage(_translate('fb2mobi-gui', 'Copying file to device: {0}').format(os.path.split(file)[1]))


    def copyDone(self):
        self.copyCount += 1
        self.progressBar.setValue(self.copyCount)


    def copyAllDone(self):
        time.sleep(0.5)    
        self.progressBar.setVisible(False)
        self.allControlsEnabled(True)
        self.clearMessage()


    def convertBegin(self, file):
        found = False
        item = None

        self.showMessage(_translate('fb2mobi-gui', 'Converting file: {0}').format(os.path.split(file)[1]))

        for i in range(self.rootFileList.childCount()):
            if file == self.rootFileList.child(i).text(2):
                found = True
                item = self.rootFileList.child(i)
                self.treeFileList.scrollToItem(item, QAbstractItemView.EnsureVisible)
                break

        if found:
            item.setIcon(0, self.iconGo)


    def convertDone(self, file, result, dest_file):
        found = False
        item = None

        if result:
            self.convertedFiles.append(dest_file)

        for i in range(self.rootFileList.childCount()):
            if file == self.rootFileList.child(i).text(2):
                found = True
                item = self.rootFileList.child(i)
                break

        if found:
            if result:
                item.setIcon(0, self.iconGreen)
            else:
                item.setIcon(0, self.iconRed)

        self.convertedCount += 1
        self.progressBar.setValue(self.convertedCount)


    def allControlsEnabled(self, enable, disable_all=False):
        self.btnSettings.setEnabled(enable)
        self.actionAddFile.setEnabled(enable)
        self.actionSettings.setEnabled(enable)
        self.actionViewLog.setEnabled(enable)
        self.actionDelete.setEnabled(enable)
        if disable_all and not enable:
            self.actionConvert.setEnabled(enable)
            self.btnStart.setEnabled(enable)
        elif enable:
            self.actionConvert.setEnabled(enable)
            self.btnStart.setEnabled(enable)


    def addFile(self, file):
        if not file.lower().endswith((".fb2", ".fb2.zip", ".zip")):
            return

        found = False

        file = os.path.normpath(file)
        
        for i in range(self.rootFileList.childCount()):
            if file == self.rootFileList.child(i).text(2):
                found = True
                break

        if not found:
            meta = Fb2Meta(file)
            meta.get()

            item = QTreeWidgetItem(0)
            item.setIcon(0, self.iconWhite)
            item.setText(0, meta.book_title)
            item.setText(1, meta.get_autors())
            item.setText(2, file)
            # Установим подсказки
            item.setToolTip(0, meta.book_title)
            item.setToolTip(1, meta.get_autors())
            item.setToolTip(2, file)
            
            self.treeFileList.addTopLevelItem(item)


    def addFiles(self, file_list):
        for item in file_list:
            if os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for f in files:
                        self.addFile(os.path.join(root, f))
            else:
                self.addFile(item)


    def addFilesAction(self):
        if not self.gui_config.lastUsedPath:
            self.gui_config.lastUsedPath = os.path.expanduser('~')

        fileDialog = QFileDialog(self, _translate('fb2mobi-gui', 'Select files'), self.gui_config.lastUsedPath)
        fileDialog.setFileMode(QFileDialog.ExistingFiles)
        fileDialog.setNameFilters([_translate('fb2mobi-gui', 'Fb2 files (*.fb2 *.fb2.zip *.zip)'), 
                                  _translate('fb2mobi-gui', 'All files (*.*)')])

        if fileDialog.exec_():
            self.gui_config.lastUsedPath = os.path.normpath(fileDialog.directory().absolutePath())
            file_list = fileDialog.selectedFiles()
            self.addFiles(file_list)


    def closeApp(self):
        win_x = self.pos().x()
        win_y = self.pos().y()
        win_width = self.size().width()
        win_height = self.size().height()

        self.gui_config.geometry['x'] = win_x
        self.gui_config.geometry['y'] = win_y
        self.gui_config.geometry['width'] = win_width
        self.gui_config.geometry['height'] = win_height 

        self.gui_config.columns['0'] = self.treeFileList.columnWidth(0)   
        self.gui_config.columns['1'] = self.treeFileList.columnWidth(1)   
        self.gui_config.columns['2'] = self.treeFileList.columnWidth(2)   

        self.gui_config.write()

        self.close()


    def openSupportURL(self):
        webbrowser.open(url=SUPPORT_URL)


    def openFile(self, filename):
        if sys.platform == 'win32':
            os.startfile(filename)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', filename])
        else:
            try:
                subprocess.Popen(['xdg-open', filename])
            except:
                pass


    def settings(self):
        settingsDlg = SettingsDialog(self, self.gui_config)
        if settingsDlg.exec_():
            self.gui_config = settingsDlg.config
            self.gui_config.write()


    def about(self):
        aboutDlg = AboutDialog(self)
        aboutDlg.exec_()


    def closeEvent(self, event):
        self.closeApp()


class AppEventFilter(QObject):
    def __init__(self, app_win):
        super(AppEventFilter, self).__init__()
        self.app_win = app_win

    def eventFilter(self, receiver, event):
        if event.type() == QEvent.FileOpen:
            self.app_win.addFiles([event.file()])
            return True
        else:
            return super(AppEventFilter, self).eventFilter(receiver, event)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    app_path = os.path.normpath(fb2mobi.get_executable_path())
    locale_path = os.path.join(app_path, 'ui/locale')
    locale = QLocale.system().name()[:2]

    qt_translator = QTranslator()
    qt_translator.load(os.path.join(locale_path, 'qtbase_' + locale + '.qm'))
    app.installTranslator(qt_translator)

    app_translator = QTranslator()
    app_translator.load(os.path.join(locale_path, 'fb2mobi_' + locale + '.qm'))
    app.installTranslator(app_translator)

    app.setStyleSheet('QStatusBar::item { border: 0px }');

    mainAppWindow = MainAppWindow()
    mainAppWindow.show()

    appEventFilter = AppEventFilter(mainAppWindow)
    app.installEventFilter(appEventFilter)

    sys.exit(app.exec_())
