#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 30 10:54:18 2021

@author: il_palmi
"""
import logging
import sys
import traceback
from typing import Union

import PyQt5.QtWidgets
from PyQt5 import uic, QtGui
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtCore import Qt
from client import *
from utilites import *
from queue import Queue

SPACE = 5

REQUIREMENTS = ["Model Family",
                "Device Model",
                "Serial Number",
                "Power_On_Hours",
                "Power_Cycle_Count",
                "SSD_Life_Left",
                "Lifetime_Writes_GiB",
                "Reallocated_Sector_Ct",
                "LU WWN Device Id",
                "Rotation Rate",
                "Current Pending Sector Count",
                "Model Number",
                "Firmware Version"]

SMARTCHECK = ["Power_On_Hours",
              "Reallocated_Sector_Cd",
              "Current Pending Sector Count"]

PATH = {"UI": "/assets/interface.ui",
        "REQUIREMENTS": "/requirements_client.txt",
        "CRASH": "/crashreport.txt",
        "ASD": "/assets/asd.gif",
        "RELOAD": "/assets/reload.png",
        "VAPORWAVERELOAD": "/assets/vapman.png",
        "PENDING": "/assets/pending.png",
        "ICON": "/assets/icon.png",
        "PROGRESS": "/assets/progress.png",
        "OK": "/assets/ok.png",
        "WARNING": "/assets/warning.png",
        "ERROR": "/assets/error.png",
        "STOP": "/assets/stop.png",
        "SERVER": "/basilico.py",
        "LOGFILE": "/tmp/crashreport.py",
        "DARKTHEME": "/themes/darkTheme.ssh",
        "VAPORTHEME": "/themes/vaporwaveTheme.ssh",
        "ASDTHEME": "/themes/asdTheme.ssh",
        "WINVAPORTHEME": "/themes/vaporwaveWinTheme.ssh",
        "ASDWINTHEME": "/themes/asdWinTheme.ssh"}

QUEUE_TABLE = ["ID",
               "Process",
               "Disk",
               "Status",
               "Progress"
               ]

CLIENT_COMMAND = {"PING": "===PING===",
                  "GET_DISK": "===GET_DISK===",
                  "GET_DISK_WIN": "GET_DISK_WIN",
                  "CONNECT": "===CONNECT==="}

CURRENT_PLATFORM = sys.platform

initialize_path(CURRENT_PLATFORM, PATH)

logging.basicConfig(level=logging.DEBUG, filename=PATH["LOGFILE"])


# UI class
class Ui(QtWidgets.QMainWindow):
    def __init__(self, gui_queue: Queue, client_queue: Queue, server_queue: Queue, app: QtWidgets.QApplication) -> None:
        super(Ui, self).__init__()
        uic.loadUi(PATH["UI"], self)
        self.gui_queue = gui_queue          # Command queue for gui
        self.client_queue = client_queue    # Command queue for client
        self.server_queue = server_queue    # Command queue for server
        self.app = app
        self.running = True
        self.host = None
        self.port = None
        self.remoteMode = False
        self.settings = QtCore.QSettings("WEEE-Open", "PESTO")
        self.client = None
        self.client: ReactorThread

        """ Defining all items in GUI """
        self.globalTab = self.findChild(QtWidgets.QTabWidget, 'globalTab')
        self.gif = QMovie(PATH["ASD"])
        self.diskTable = self.findChild(QtWidgets.QTableWidget, 'tableWidget')
        self.queueTable = self.findChild(QtWidgets.QTableWidget, 'queueTable')
        self.reloadButton = self.findChild(QtWidgets.QPushButton, 'reloadButton')
        self.eraseButton = self.findChild(QtWidgets.QPushButton, 'eraseButton')
        self.smartButton = self.findChild(QtWidgets.QPushButton, 'smartButton')
        self.cannoloButton = self.findChild(QtWidgets.QPushButton, 'cannoloButton')
        self.stdProcedureButton = self.findChild(QtWidgets.QPushButton, 'stdProcButton')
        self.localRadioBtn = self.findChild(QtWidgets.QRadioButton, 'localRadioBtn')
        self.remoteRadioBtn = self.findChild(QtWidgets.QRadioButton, 'remoteRadioBtn')
        self.hostInput = self.findChild(QtWidgets.QLineEdit, 'remoteIp')
        self.portInput = self.findChild(QtWidgets.QLineEdit, 'remotePort')
        self.restoreButton = self.findChild(QtWidgets.QPushButton, "restoreButton")
        self.defaultButton = self.findChild(QtWidgets.QPushButton, "defaultButton")
        self.saveButton = self.findChild(QtWidgets.QPushButton, "saveButton")
        self.ipList = self.findChild(QtWidgets.QListWidget, "ipList")
        self.findButton = self.findChild(QtWidgets.QPushButton, "findButton")
        self.cannoloLabel = self.findChild(QtWidgets.QLabel, "cannoloLabel")
        self.themeSelector = self.findChild(QtWidgets.QComboBox, 'themeSelector')
        self.directoryText = self.findChild(QtWidgets.QLineEdit, "directoryText")
        self.smartLayout = self.findChild(QtWidgets.QVBoxLayout, 'smartLayout')
        self.smartTabs = SmartTabs()
        self.smartLayout.addWidget(self.smartTabs)

        """ Initialization operations """
        self.set_items_functions()
        self.localServer = LocalServer(self.server_queue)
        if CURRENT_PLATFORM == 'win32':
            message = "Cannot run local server on windows machine."
            if critical_dialog(message=message, dialog_type='ok_dna'):
                self.settings.setValue("win32ServerStartupDialog", 1)
            self.app.setStyle("Windows")
        self.show()
        self.setup()
        # self.queueTable.installEventFilter(self)

        self.queueTable.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.stop_action = QtWidgets.QAction("Stop", self)
        self.stop_action.triggered.connect(self.queue_stop)
        self.queueTable.addAction(self.stop_action)
        self.remove_action = QtWidgets.QAction("Remove", self)
        self.remove_action.triggered.connect(self.queue_remove)
        self.queueTable.addAction(self.remove_action)
        self.remove_all_action = QtWidgets.QAction("Remove All", self)
        self.remove_all_action.triggered.connect(self.queue_clear)
        self.queueTable.addAction(self.remove_all_action)
        self.info_action = QtWidgets.QAction("Info", self)
        self.info_action.triggered.connect(self.queue_info)
        self.queueTable.addAction(self.info_action)
        self.queueTable.itemSelectionChanged.connect(self.on_table_select)

        self.stop_action.setEnabled(False)
        self.remove_action.setEnabled(False)
        self.remove_all_action.setEnabled(True)
        self.info_action.setEnabled(False)

    def on_table_select(self):
        sel = self.queueTable.currentRow()
        if sel == -1:
            self.stop_action.setEnabled(False)
            self.remove_action.setEnabled(False)
            self.info_action.setEnabled(False)
        else:
            self.stop_action.setEnabled(True)
            self.remove_action.setEnabled(True)
            self.info_action.setEnabled(True)

    def set_items_functions(self):
        # set icon
        self.setWindowIcon(QIcon(PATH["ICON"]))

        # get latest configuration
        self.latest_conf()

        # disks table
        self.diskTable.setHorizontalHeaderItem(0, QTableWidgetItem("Drive"))
        self.diskTable.setHorizontalHeaderItem(1, QTableWidgetItem("Dimension"))
        self.diskTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.diskTable.setColumnWidth(0, 65)
        self.diskTable.horizontalHeader().setStretchLastSection(True)
        self.diskTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)

        # queue table
        self.queueTable.setRowCount(0)
        table_setup(self.queueTable, QUEUE_TABLE)
        self.queueTable.horizontalHeader().setStretchLastSection(True)
        self.queueTable.setColumnWidth(0,125)
        self.queueTable.setColumnWidth(2,65)
        self.queueTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)

        # reload button
        self.reloadButton.clicked.connect(self.refresh)
        self.reloadButton.setIcon(QIcon(PATH["RELOAD"]))

        # erase button
        self.eraseButton.clicked.connect(self.erase)

        # smart button
        self.smartButton.clicked.connect(self.smart)

        # cannolo button
        self.cannoloButton.clicked.connect(self.cannolo)

        # standard procedure button
        self.stdProcedureButton.clicked.connect(self.std_procedure)

        # text field
        # self.textField.setReadOnly(True)
        # font = self.textField.document().defaultFont()
        # font.setFamily("Monospace")
        # font.setStyleHint(QtGui.QFont.Monospace)
        # self.textField.document().setDefaultFont(font)
        # self.textField.setCurrentFont(font)
        # self.textField.setFontPointSize(10)

        # local radio button
        if not self.remoteMode:
            self.localRadioBtn.setChecked(True)
        self.localRadioBtn.clicked.connect(self.set_remote_mode)

        # remote radio button
        if self.remoteMode:
            self.remoteRadioBtn.setChecked(True)
        self.remoteRadioBtn.clicked.connect(self.set_remote_mode)

        # host input
        self.hostInput.setText(self.host)

        # port input
        if self.port is not None:
            self.portInput.setText(str(self.port))

        # restore button
        self.restoreButton.clicked.connect(self.restore)

        # default values button
        self.defaultButton.clicked.connect(self.default_config)

        # remove config button
        self.defaultButton = self.findChild(QtWidgets.QPushButton, "removeButton")
        self.defaultButton.clicked.connect(self.remove_config)

        # save config button
        self.saveButton.clicked.connect(self.save_config)

        # configuration list
        for key in self.settings.childKeys():
            if "saved" in key:
                values = self.settings.value(key)
                self.ipList.addItem(values[0])
        self.ipList.clicked.connect(self.load_config)

        # find button
        self.findButton.clicked.connect(self.find_directory)
        if self.remoteMode:
            self.findButton.setEnabled(False)

        # directory text
        for key in self.settings.childKeys():
            if "cannoloDir" in key:
                self.directoryText.setText(str(self.settings.value(key)))
        if self.remoteMode:
            self.directoryText.setReadOnly(False)

        # cannolo label
        self.cannoloLabel.setStyleSheet('color: blue')
        if self.remoteMode:
            self.cannoloLabel.setText("When in remote mode, the user must insert manually the cannolo image directory.")
        else:
            self.cannoloLabel.setText("")

        # theme selector
        for key in self.settings.childKeys():
            if "theme" in key:
                self.themeSelector.setCurrentText(self.settings.value(key))
                self.set_theme()
        self.themeSelector.currentTextChanged.connect(self.set_theme)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.ContextMenu:
            asd = self.queueTable.itemClicked
            if source is self.queueTable and self.queueTable.selectedItems() != -1:
                menu = QtWidgets.QMenu()
                menu.addAction("asd")
                menu.addAction("bsd")
                menu.addAction("csd")
                if menu.exec_(event.globalPos()):
                    print("asd")
                return True
        return super().eventFilter(source, event)

    def latest_conf(self):
        self.remoteMode = self.settings.value("remoteMode")
        if self.remoteMode == 'False':
            self.remoteMode = False
            self.host = "127.0.0.1"
            self.port = 1030
        else:
            self.remoteMode = True
            try:
                self.host = self.settings.value("remoteIp")
                self.port = int(self.settings.value("remotePort"))
            except ValueError:
                self.port = None

    def setup(self):
        self.set_remote_mode()

        # check if the host and port field are set
        if self.host is None and self.port is None:
            message = "The host and port combination is not set.\nPlease visit the settings section."
            warning_dialog(message, dialog_type='ok')

        """
        The client try to connect to the BASILICO. If it can't and the client is in remote mode, then 
        a critical error is shown and the client goes in idle. If the client is in local mode and it cannot reach a
        BASILICO server, a new BASILICO process is instantiated.
        """
        self.client = ReactorThread(self.host, self.port)
        self.client.updateEvent.connect(self.gui_update)
        self.client.start()

    def deselect(self):
        self.queueTable.clearSelection()
        self.queueTable.clearFocus()

    def queue_stop(self):
        pid = self.queueTable.item(self.queueTable.currentRow(), 0).text()
        message = 'Do you want to stop the process?\nID: ' + pid
        if warning_dialog(message, dialog_type='yes_no') == QtWidgets.QMessageBox.Yes:
            self.client.send(f"stop {pid}")
        self.deselect()

    def queue_remove(self):
        pid = self.queueTable.item(self.queueTable.currentRow(), 0).text()
        message = 'With this action you will also stop the process (ID: ' + pid + ")\n"
        message += 'Do you want to proceed?'
        if warning_dialog(message, dialog_type='yes_no') == QtWidgets.QMessageBox.Yes:
            self.client.send("remove")
            self.queueTable.removeRow(self.queueTable.currentRow())
        self.deselect()

    def queue_clear(self):
        self.queueTable.setRowCount(0)
        self.client.send("remove all")

    def queue_info(self):
        process = self.queueTable.item(self.queueTable.currentRow(), 1).text()
        message = ''
        if process == "Smart check":
            message += "Process type: " + process + "\n"
            message += "Get SMART data from the selected drive\n"
            message += "and print the output to the console."
        elif process == "Erase":
            message += "Process type: " + process + "\n"
            message += "Wipe off all data in the selected drive."
        info_dialog(message)
        self.deselect()

    def std_procedure(self):
        message = "Do you want to wipe all disk's data and load a fresh system image?"
        dialog = warning_dialog(message, dialog_type='yes_no_chk')
        if dialog[0] == QtWidgets.QMessageBox.Yes:
            self.erase(std=True)
            self.smart(std=True)
            if dialog[1]:
                self.cannolo(std=True)
            self.sleep()

    def erase(self, std=False):
        # noinspection PyBroadException
        try:
            selected_drive = self.diskTable.item(self.diskTable.currentRow(), 0)
            if selected_drive is None:
                message = "There are no selected drives."
                warning_dialog(message, dialog_type='ok')
                return
            else:
                selected_drive = selected_drive.text().lstrip("Disk ")
            if not std:
                message = "Do you want to wipe all disk's data?\nDisk: " + selected_drive
                if critical_dialog(message, dialog_type='yes_no') != QtWidgets.QMessageBox.Yes:
                    return
            self.client.send("queued_badblocks " + selected_drive)

        except BaseException:
            print("Error in erase Function")

    def smart(self, std=False):
        # noinspection PyBroadException
        try:
            selected_drive = self.diskTable.item(self.diskTable.currentRow(), 0)
            if selected_drive is None:
                if not std:
                    message = "There are no selected drives."
                    warning_dialog(message, dialog_type='ok')
                    return
                return
            # TODO: Add new tab for every smart requested. If drive tab exist, use it.
            drive = selected_drive.text().lstrip("Disk ")
            self.client.send("queued_smartctl " + drive)

        except BaseException:
            print("Error in smart function.")

    def cannolo(self, std=False):
        # noinspection PyBroadException
        try:
            selected_drive = self.diskTable.item(self.diskTable.currentRow(), 0)
            if selected_drive is None:
                if not std:
                    message = "There are no selected drives."
                    warning_dialog(message, dialog_type='ok')
                    return
                return
            else:
                selected_drive = selected_drive.text().lstrip("Disk ")
            if not std:
                message = "Do you want to load a fresh system installation in disk " + selected_drive + "?"
                if warning_dialog(message, dialog_type='yes_no') != QtWidgets.QMessageBox.Yes:
                    return
            self.client.send("queued_cannolo " + selected_drive)

        except BaseException:
            print("Error in cannolo function.")

    def sleep(self, std=False):
        # noinspection PyBroadException
        try:
            selected_drive = self.diskTable.item(self.diskTable.currentRow(), 0)
            if selected_drive is None:
                if not std:
                    message = "There are no selected drives."
                    warning_dialog(message, dialog_type='ok')
                    return
                return
            else:
                selected_drive = selected_drive.text().lstrip("Disk ")
            self.client.send("queued_sleep " + selected_drive)

        except BaseException:
            print("Error in cannolo function.")

    def set_remote_mode(self):
        # if CURRENT_PLATFORM == 'win32':
        #     self.remoteRadioBtn.setChecked(True)
        #     self.localRadioBtn.setCheckable(False)
        if self.localRadioBtn.isChecked():
            self.remoteMode = False
            self.remoteMode = False
            self.settings.setValue("latestHost", self.host)
            self.settings.setValue("latestPort", self.port)
            self.host = "127.0.0.1"
            self.port = 1030
            self.hostInput.setText(self.host)
            self.portInput.setText(str(self.port))
            self.hostInput.setReadOnly(True)
            self.portInput.setReadOnly(True)
            self.saveButton.setEnabled(False)
            self.findButton.clicked.connect(self.find_directory)
            self.directoryText.setReadOnly(True)
            self.cannoloLabel.setText("")
        elif self.remoteRadioBtn.isChecked():
            if not self.remoteMode:
                self.host = self.settings.value("latestHost")
                self.port = int(self.settings.value("latestPort"))
            self.remoteMode = True
            self.hostInput.setReadOnly(False)
            self.hostInput.setText(self.host)
            self.portInput.setReadOnly(False)
            self.portInput.setText(str(self.port))
            self.saveButton.setEnabled(True)
            self.findButton.clicked.connect(self.find_image)
            self.directoryText.setReadOnly(False)
            self.cannoloLabel.setText("When in remote mode, the user must insert manually the cannolo image directory.")

    def refresh(self):
        self.host = self.hostInput.text()
        self.port = int(self.portInput.text())
        self.diskTable.setRowCount(0)
        self.queueTable.setRowCount(0)
        self.client.reconnect(self.host, self.port)

    def restore(self):
        self.hostInput.setText(self.host)
        self.portInput.setText(str(self.port))

    def update_queue(self, pid, drive, mode):
        # self.queueTable.setRowCount(self.queueTable.rowCount() + 1)
        row = self.queueTable.rowCount()
        self.queueTable.insertRow(row)
        for idx, entry in enumerate(QUEUE_TABLE):
            label: object
            label = object()
            if entry == "ID":  # ID
                label = pid
            elif entry == "Process":  # PROCESS
                if mode == 'queued_badblocks':
                    label = "Erase"
                elif mode == 'queued_smartctl' or mode == 'smartctl':
                    label = "Smart check"
                elif mode == 'queued_cannolo':
                    label = "Cannolo"
                else:
                    label = "Unknown"
            elif entry == "Disk":  # DISK
                label = drive
            elif entry == "Status":  # STATUS
                if self.queueTable.rowCount() != 0:
                    label = QtWidgets.QLabel()
                    label: QtWidgets.QLabel
                    label.setPixmap(QtGui.QPixmap(PATH["PENDING"]).scaled(25, 25, QtCore.Qt.KeepAspectRatio))
                else:
                    label: QtWidgets.QLabel
                    label.setPixmap(QtGui.QPixmap(PATH["PROGRESS"]).scaled(25, 25, QtCore.Qt.KeepAspectRatio))
            elif entry == "Progress":  # PROGRESS
                label = QtWidgets.QProgressBar()
                label: QtWidgets.QProgressBar
                label.setValue(0)

            if entry in ["ID", "Process", "Disk"]:
                label = QTableWidgetItem(label)
                label: QtWidgets.QTableWidgetItem
                label.setTextAlignment(Qt.AlignCenter)
                self.queueTable.setItem(row, idx, label)
            else:
                label.setAlignment(Qt.AlignCenter)
                self.queueTable.setCellWidget(row, idx, label)

    def save_config(self):
        ip = self.hostInput.text()
        port = self.portInput.text()
        if self.ipList.findItems(ip, Qt.MatchExactly):
            message = "Do you want to overwrite the old configuration?"
            if warning_dialog(message, dialog_type='yes_no') == QtWidgets.QMessageBox.Yes:
                self.settings.setValue("saved-" + ip, [ip, port])
        else:
            self.ipList.addItem(ip)
            self.settings.setValue("saved-" + ip, [ip, port])

    def remove_config(self):
        ip = self.ipList.currentItem().text()
        message = "Do you want to remove the selected configuration?"
        if warning_dialog(message, dialog_type='yes_no') == QtWidgets.QMessageBox.Yes:
            for key in self.settings.childKeys():
                if ip in key:
                    self.ipList.takeItem(self.ipList.row(self.ipList.currentItem()))
                    self.settings.remove(key)

    def load_config(self):
        ip = self.ipList.currentItem().text()
        for key in self.settings.childKeys():
            if ip in key:
                values = self.settings.value(key)
                port = values[1]
                self.hostInput.setText(ip)
                self.portInput.setText(port)

    def default_config(self):
        message = "Do you want to restore all settings to default?\nThis action is unrevocable."
        if critical_dialog(message, dialog_type="yes_no") == QtWidgets.QMessageBox.Yes:
            self.settings.clear()
            self.ipList.clear()
            self.setup()

    def find_directory(self):
        dialog = QtWidgets.QFileDialog()
        directory = dialog.getExistingDirectory(self, "Open Directory", "/home", QtWidgets.QFileDialog.ShowDirsOnly)
        self.directoryText.setText(directory)

    def find_image(self):
        # noinspection PyBroadException
        try:
            self.client.send("img_dir " + self.directoryText.text())

        except BaseException:
            print("Error in smart function.")

    def set_theme(self):
        if self.themeSelector.currentText() == "Dark":
            with open(PATH["DARKTHEME"], "r") as file:
                self.app.setStyleSheet(file.read())
            self.reloadButton.setIcon(QIcon(PATH["RELOAD"]))
            self.backgroundLabel.clear()
            self.reloadButton.setIconSize(QtCore.QSize(25,25))
        elif self.themeSelector.currentText() == "Vaporwave":
            if CURRENT_PLATFORM == 'win32':
                with open(PATH["WINVAPORTHEME"]) as file:
                    self.app.setStyleSheet(file.read())
            else:
                with open(PATH["VAPORTHEME"], "r") as file:
                    self.app.setStyleSheet(file.read())
            self.reloadButton.setIcon(QIcon(PATH["VAPORWAVERELOAD"]))
            self.reloadButton.setIconSize(QtCore.QSize(50,50))
            self.backgroundLabel.clear()
        elif self.themeSelector.currentText() == "Asd":
            if CURRENT_PLATFORM == 'win32':
                with open(PATH["ASDWINTHEME"]) as file:
                    self.app.setStyleSheet(file.read())
            else:
                with open(PATH["ASDTHEME"], "r") as file:
                    self.app.setStyleSheet(file.read())
            self.backgroundLabel = self.findChild(QtWidgets.QLabel, "backgroundLabel")
            self.movie = QMovie(PATH["ASD"])
            self.movie.setScaledSize(QtCore.QSize().scaled(400, 400, Qt.KeepAspectRatio))
            self.movie.start()
            self.reloadButton.setIcon(QIcon(PATH["RELOAD"]))
            self.backgroundLabel.setMovie(self.movie)
            self.reloadButton.setIconSize(QtCore.QSize(25,25))
        else:
            self.app.setStyleSheet("")
            self.backgroundLabel.clear()
            self.reloadButton.setIcon(QIcon(PATH["RELOAD"]))
            self.reloadButton.setIconSize(QtCore.QSize(25,25))

    def gui_update(self, cmd: str, params: str):
        """
        Typical param str is:
            cmd [{param_1: 'text'}, {param_2: 'text'}, {param_3: 'text'}, ...]
        Possible cmd are:
            get_disks --> drives information for disks table
            queue_status --> Information about badblocks process

        """
        try:
            params = json.loads(params)
            params: Union[dict, list]
        except json.decoder.JSONDecodeError:
            print(f"Ignored exception while parsing {cmd}, expected JSON but this isn't: {params}")

        if cmd == 'queue_status' or cmd == 'get_queue':
            if cmd == 'queue_status':
                params = [params]
            for param in params:
                param: dict
                row = 0
                rows = self.queueTable.rowCount()
                for row in range(rows + 1):
                    # Check if we already have that id
                    item = self.queueTable.item(row, 0)
                    if item is not None and item.text() == param["id"]:
                        break
                    elif item is None:
                        self.update_queue(pid=param["id"], drive=param["target"], mode=param["command"])
                        rows += 1
                progress_bar = self.queueTable.cellWidget(row, 4)
                status_cell = self.queueTable.cellWidget(row, 3)
                progress_bar.setValue(int(param["percentage"]))
                if param["stale"]:
                    pass
                elif param["stopped"]:
                    # TODO: we don't have an icon for this, maybe we should
                    status_cell.setPixmap(QtGui.QPixmap(PATH["STOP"]).scaledToHeight(25, Qt.SmoothTransformation))
                elif param["error"]:
                    status_cell.setPixmap(QtGui.QPixmap(PATH["ERROR"]).scaledToHeight(25, Qt.SmoothTransformation))
                elif param["finished"]:  # and not error
                    status_cell.setPixmap(QtGui.QPixmap(PATH["OK"]).scaledToHeight(25, Qt.SmoothTransformation))
                elif param["started"]:
                    status_cell.setPixmap(QtGui.QPixmap(PATH["PROGRESS"]).scaledToHeight(25, Qt.SmoothTransformation))
                else:
                    status_cell.setPixmap(QtGui.QPixmap(PATH["PENDING"]).scaledToHeight(25, Qt.SmoothTransformation))

        elif cmd == 'get_disks':
            drives = params
            if len(drives) <= 0:
                self.diskTable.clear()
                self.diskTable.setRowCount(0)
                return
            # compile disks table with disks list
            rows = 0
            for d in drives:
                d: dict
                if "[BOOT]" in d["mountpoint"]:
                    continue
                rows += 1
                self.diskTable.setRowCount(rows)
                if sys.platform == 'win32':
                    self.diskTable.setItem(rows - 1, 0, QTableWidgetItem("Disk " + d["path"]))
                else:
                    self.diskTable.setItem(rows - 1, 0, QTableWidgetItem(d["path"]))
                self.diskTable.setItem(rows - 1, 1, QTableWidgetItem(str(int(int(d["size"]) / 1000000000)) + " GB"))

        elif cmd == 'smartctl' or cmd == 'queued_smartctl':
            text = ("Smartctl output:\n " + params["output"]).splitlines()
            tab_count = self.smartTabs.count()
            tab = 0
            for tab in range(tab_count + 1):
                if self.smartTabs.tabText(tab) == params["disk"]:
                    message= "Il tab per il dosco esiste già asd.\nVuoi sovrascrivere l'output?"
                    if warning_dialog(message, dialog_type="yes_no") == QtWidgets.QMessageBox.Yes:
                        for line in text:
                            self.smartTabs.text_boxes[tab].append(line)
                elif tab == tab_count:
                    self.smartTabs.add_tab(params["disk"])
                    for line in text:
                        self.smartTabs.text_boxes[tab].append(line)

        elif cmd == 'connection_failed':
            message = params["reason"]
            if "Connection was refused by other side" in message:
                message = "Cannot find BASILICO server.\nCheck if it's running in the " \
                          "targeted machine."
            warning_dialog(message, dialog_type="ok")

        elif cmd == 'connection_made':
            self.statusBar().showMessage(f"Connected to {params['host']}:{params['port']}")

        elif cmd == 'img_found':
            for img in params:
                print(params[img])

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.settings.setValue("remoteMode", str(self.remoteMode))
        self.settings.setValue("remoteIp", self.hostInput.text())
        self.settings.setValue("remotePort", self.portInput.text())
        self.settings.setValue("cannoloDir", self.directoryText.text())
        self.settings.setValue("theme", self.themeSelector.currentText())
        self.client.stop()


class LocalServer:
    update = QtCore.pyqtSignal(str, str, name="update")

    def __init__(self, server_queue: Queue):
        self.server_queue = server_queue
        self.server: subprocess.Popen
        self.running = False
        self.server = None

    def load_server(self):
        if not self.running:
            self.server = subprocess.Popen(["python", PATH["SERVER"]], stderr=subprocess.PIPE,
                                           stdout=subprocess.PIPE)
            self.running = True
            while "Listening on" not in self.server.stderr.readline().decode('utf-8'):
                pass
            self.server_queue.put("SERVER_READY")
        else:
            self.server_queue.put("SERVER_READY")

    def stop(self):
        if self.running:
            self.server.terminate()
        self.running = False


def main():
    # noinspection PyBroadException
    try:
        check_requirements(PATH["REQUIREMENTS"])
        gui_bg_queue = Queue()
        client_queue = Queue()
        server_queue = Queue()
        app = QtWidgets.QApplication(sys.argv)
        window = Ui(gui_bg_queue, client_queue, server_queue, app)
        app.exec_()

    except KeyboardInterrupt:
        print("KeyboardInterrupt")

    except BaseException:
        logging.exception(traceback.print_exc(file=sys.stdout))


if __name__ == "__main__":
    main()