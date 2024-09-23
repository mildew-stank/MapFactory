# TODO: consider the lowering visibity of out of service or not in use rooms
# TODO: ask before an export is overridden
# TODO: have date border be/flash green/red when not representing current system clock day
# TODO: (possible bug) sometimes the drop indicator may get stuck on screen. log it out and see if event.accept()/decline() helps. maybe force a redraw


import sys
import os
import json

from PyQt5 import QtCore, uic
from PyQt5.QtCore import QTimer, QDate, QModelIndex
from PyQt5.QtGui import QColor, QIcon, QStandardItemModel, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QColorDialog,
    QFileDialog,
    QTreeWidgetItem,
    QDialog,
    QSpinBox,
    QComboBox,
    QSystemTrayIcon,
    QShortcut,
)


class QComboBoxNoWheelEvent(QComboBox):
    # has no mouse wheel interaction
    def __init__(self, *args, **kwargs):
        super(QComboBoxNoWheelEvent, self).__init__(*args, **kwargs)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def wheelEvent(self, *args, **kwargs):
        return


class QSpinBoxNoWheelEvent(QSpinBox):
    # has no mouse wheel interaction
    def __init__(self, *args, **kwargs):
        super(QSpinBoxNoWheelEvent, self).__init__(*args, **kwargs)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def wheelEvent(self, *args, **kwargs):
        return


def Data(campaigns, rooms, date):
    return {"campaigns": campaigns, "rooms": rooms, "date": date}


def Campaign(name, color, lots):
    return {"name": name, "color": color, "lots": lots}


def Lot(name, color, status):
    return {"name": name, "color": color, "status": status}


def Room(name, status, shipping, lots):
    return {"name": name, "status": status, "shipping": shipping, "lots": lots}


class Map(QDialog):
    def __init__(self, data, export_path):
        super(Map, self).__init__()
        self.data = data
        self.export_path = export_path
        self.status_colors = {
            "Weighed": "#c62828",
            "Tableted": "#2e7d32",
            "Blended": "#1976d2",
            "Packaging": "#795548",
            "Completed": "#2e7d32",
            "Dirty": "#795548",
            "Clean": "#0277bd",
            "Not in use": "#c62828",
            "Out of service": "#c62828",
        }
        uic.loadUi("map.ui", self)
        icon = QIcon("facbot.ico")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowIcon(icon)
        self.populate_map()
        self.date.setText(self.data["date"])
        self.show()
        # export map
        # TODO: find an onload signal/event. showEvent isn't it
        QTimer.singleShot(250, self.screenshot)
        # show export notification
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(icon)
        self.tray.show()
        self.tray.showMessage("Map Factory", "Image saved", icon, 5000)
        self.tray.messageClicked.connect(self.on_message_clicked)
        self.tray.activated.connect(self.on_message_clicked)
        # i'd like to hide the tray icon or never show it, but these prevent tray/notification signals
        # self.tray.hide()
        # self.tray.setVisible(False)

    def on_message_clicked(self):
        os.startfile(self.export_path)

    def screenshot(self):
        if not os.path.exists("exports"):
            os.makedirs("exports")
        screen = QApplication.primaryScreen()
        export = screen.grabWindow(self.winId())
        date = self.data["date"].replace("/", "-")
        export.save(f"{self.export_path}/ProductionFloor_{date}.png", "png")

    def populate_map(self):
        label_dict = self.labels_to_dict()
        self.populate_rooms(label_dict)
        self.populate_campaigns(label_dict)

    def populate_rooms(self, label_dict):
        for room in self.data["rooms"]:
            lots = room["lots"]
            room_shipping = room["shipping"]
            room_text = ""
            room_status = room["status"]
            campaign_name = ""
            room_name = room["name"]
            if not room_name in label_dict:
                continue
            # add lots to room
            for lot in lots:
                lot_name = lot["name"]
                lot_color = lot["color"]
                # check the campaign these lots are from
                campaign, campaign_lot = self.find_lot_in_campaign(lot_name)
                if not campaign and not campaign_lot:
                    continue
                if not campaign["name"] == campaign_name:
                    campaign_name = campaign["name"]
                    campaign_color = campaign["color"]
                    campaign_words = campaign_name.replace("<br>", " ").split()
                    room_text = f"{room_text}<div style='color:{campaign_color};text-decoration:underline;'>{campaign_words[0]}</div>"
                lot_status = self.get_status_symbol(campaign_lot["status"])
                room_text = f"{room_text}<div style='color:{lot_color};'>{lot_name}{lot_status}</div>"
            # add room status and shipping
            room_status_color = "#000000"
            if room_status in self.status_colors:
                room_status_color = self.status_colors[room_status]
            if room_status and not room_status == "None":
                room_text = f"{room_text}<div style='color:{room_status_color};font-weight:bold;'>{room_status}</div>"
            if room_shipping:
                room_text = f"{room_text}<div style='color:black;text-decoration:underline;'>Shipper: {room_shipping}</div>"
            label_dict[room_name].setText(room_text)

    def populate_campaigns(self, label_dict):
        # start the table
        campaign_text = "<table><tr>"
        for campaign in self.data["campaigns"]:
            campaign_name = campaign["name"]
            campaign_color = campaign["color"]
            campaign_text = campaign_text + "<td style='padding-right:8px;'>"
            # start campaign block
            campaign_text = f"{campaign_text}<div style='color:{campaign_color};text-decoration:underline;'>{campaign_name}</div>"
            for lot in campaign["lots"]:
                lot_name = lot["name"]
                lot_color = lot["color"]
                lot_status = self.get_status_symbol(lot["status"])
                campaign_text = f"{campaign_text}<div style='color:{lot_color};'>{lot_name}{lot_status}</div>"
            # end campaign block
            campaign_text = campaign_text + "</td>"
        # end the table
        campaign_text = campaign_text + "</tr></table>"
        label_dict["campaigns"].setText(campaign_text)

    def get_status_symbol(self, status):
        lot_status_text = status
        lot_status_color = "#000000"
        if lot_status_text in self.status_colors:
            lot_status_color = self.status_colors[lot_status_text]
        lot_status_symbol = "🗸" if lot_status_text == "Completed" else "⬤"
        if not lot_status_text in self.status_colors:
            lot_status_symbol = ""
        return f"<span style='color:{lot_status_color};font-weight:bold;'> {lot_status_symbol}</span>"

    def find_lot_in_campaign(self, lot_name):
        for campaign in self.data["campaigns"]:
            for lot in campaign["lots"]:
                if lot["name"] == lot_name:
                    return (campaign, lot)
        return (None, None)

    def labels_to_dict(self):
        labels = self.findChildren(QLabel)
        label_dict = {}
        for label in labels:
            label_dict[label.text()] = label
            label.setText("")
        return label_dict

    def closeEvent(self, event):
        self.tray.hide()


class Factory(QMainWindow):
    def __init__(self):
        super(Factory, self).__init__()
        # data
        self.version = "1.1.1"
        self.statuses = {
            "room": ["None", "Clean", "Dirty", "Not in use", "Out of service"],
            "lot": ["None", "Blended", "Completed", "Packaging", "Tableted", "Weighed"],
        }
        self.settings = {
            "save_path": "save.json",
            "export_path": "exports",
            "auto_sort_enabled": True,
        }
        self.map_display = None
        self.is_programmed_change = False
        # load from qt designer
        uic.loadUi("map_factory.ui", self)
        # tree headers
        self.left_tree.header().resizeSection(0, 173)
        self.left_tree.header().setSortIndicator(0, 0)
        self.right_tree.header().setSortIndicator(0, 0)
        # menu bar
        self.open_action.triggered.connect(self.on_open)
        self.save_action.triggered.connect(self.on_save)
        self.save_as_action.triggered.connect(self.on_save_as)
        self.export_action.triggered.connect(self.on_export)
        self.clear_action.triggered.connect(self.on_clear)
        self.export_path_action.triggered.connect(self.on_export_path)
        self.about_action.triggered.connect(self.on_about)
        self.sort_action.triggered.connect(self.on_sort)
        # left tree
        self.left_tree.itemSelectionChanged.connect(self.on_left_tree_selected)
        self.left_tree.itemChanged.connect(self.on_left_tree_item_changed)
        # right tree
        self.right_tree.dropEvent = self.interupt_right_tree_drop
        self.right_tree.itemSelectionChanged.connect(self.on_right_tree_selected)
        # buttons
        self.add_campaign_button.clicked.connect(self.on_add_campaign)
        self.add_lot_button.clicked.connect(self.on_add_lot)
        self.remove_button.clicked.connect(self.on_remove)
        self.color_button.clicked.connect(self.on_color)
        self.add_room_button.clicked.connect(self.on_add_room)
        # final rendering
        self.setWindowIcon(QIcon("facbot.ico"))
        self.read_settings()
        self.set_up_sort_action()
        data = self.load_data(self.settings["save_path"])
        try:
            self.populate_data(data)
        except:
            QMessageBox.warning(self, "Error", "Failed to load save.")
        self.show()
        # shortcuts
        shortcut = QShortcut(QKeySequence.Delete, self)
        shortcut.activated.connect(self.on_delete_key)

    def on_about(self):
        QMessageBox.about(self, "About", f"<h1>Map Factory</h1> <h3>v{self.version}</h3> <a href='https://github.com/mildew-stank/MapFactory'>github.com/mildew-stank/MapFactory</a>")

    def set_up_sort_action(self):
        is_enabled = True
        if "auto_sort_enabled" in self.settings:
            is_enabled = self.settings["auto_sort_enabled"]
            print(self.settings["auto_sort_enabled"])
        self.sort_action.setChecked(is_enabled)
        self.on_sort(is_enabled)

    def on_sort(self, is_checked):
        self.left_tree.setSortingEnabled(is_checked)
        self.right_tree.setSortingEnabled(is_checked)
        self.settings["auto_sort_enabled"] = is_checked

    def on_delete_key(self):
        self.on_left_remove()
        self.on_right_remove()

    def drop_lot(self, name, color, room):
        # remove any existing lots with this name
        self.remove_items(self.right_tree, self.find_items(self.right_tree, name))
        # create a new lot as child of room
        item = QTreeWidgetItem([name])
        item.setForeground(0, color)
        room.addChild(item)
        return item

    def interupt_right_tree_drop(self, event):
        drop_position = event.pos()
        target_item = self.right_tree.itemAt(drop_position)
        drop_indicator = self.right_tree.dropIndicatorPosition()
        # put mime data in a dummy item model to extract source item data
        data = event.mimeData()
        dummy = QStandardItemModel()
        dummy.dropMimeData(data, QtCore.Qt.CopyAction, 0, 0, QModelIndex())
        source_item_text = dummy.item(0, 0).text()
        source_item_color = dummy.item(0, 0).foreground()
        if not target_item or drop_indicator == 3:
            # no target or indicator points to blank viewport
            return
        if target_item.parent():
            # target is child, drop at parent
            self.drop_lot(source_item_text, source_item_color, target_item.parent())
            return
        if not target_item.parent():
            # target is top level, drop as child
            self.drop_lot(source_item_text, source_item_color, target_item)

    def on_open(self):
        open_dialog = QFileDialog()
        file_path = open_dialog.getOpenFileName(
            None, "Open File", self.settings["save_path"], "JSON (*.json)"
        )[0]
        self.settings["save_path"] = file_path
        data = self.load_data(file_path)
        try:
            self.populate_data(data)
        except:
            QMessageBox.warning(self, "Error", "Failed to load save.")

    def write_settings(self):
        with open("settings.json", "w") as out_file:
            json.dump(self.settings, out_file, indent=4)

    def read_settings(self):
        if not os.path.exists("settings.json"):
            return
        with open("settings.json", "r") as in_file:
            self.settings = json.load(in_file)

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, "r") as in_file:
                return json.load(in_file)
        except:
            # file must be missing or in use or is just a directory
            return

    def populate_data(self, data):
        if not data:
            return
        # clear existing trees
        self.on_clear()
        # load left tree
        for campaign in data["campaigns"]:
            campaign_item = self.add_top_level_item(
                self.left_tree, campaign["name"], campaign["color"], False
            )
            # add dummy label to avoid and editable field
            self.left_tree.setItemWidget(campaign_item, 1, QLabel())
            for lot in campaign["lots"]:
                lot_item = self.load_lot(campaign_item, lot["name"], lot["color"], True)
                self.add_widgets_to_item(lot_item, self.statuses["lot"], lot["status"])
                if lot["status"] == "Completed":
                    lot_item.setCheckState(0, 2)
        # load right tree
        for room in data["rooms"]:
            room_item = self.add_top_level_item(
                self.right_tree, room["name"], "", False
            )
            self.add_widgets_to_item(
                room_item,
                self.statuses["room"],
                room["status"],
                room["shipping"],
            )
            for lot in room["lots"]:
                self.load_lot(room_item, lot["name"], lot["color"])
        # load date
        date = list(map(int, data["date"].split("/")))
        self.date_edit.setDate(QDate(date[2], date[0], date[1]))

    def on_save_as(self):
        save_dialog = QFileDialog()
        file_path = save_dialog.getSaveFileName(
            self, "Save As", self.settings["save_path"], "JSON (*.json)"
        )[0]
        if not file_path:
            # likely user canceled
            return
        self.settings["save_path"] = file_path
        self.on_save()

    def on_save(self):
        data = self.trees_to_object()
        with open(self.settings["save_path"], "w") as out_file:
            json.dump(data, out_file, indent=4)

    def on_export(self):
        try:
            if self.map_display:
                self.map_display.accept()
            data = self.trees_to_object()
            self.map_display = Map(data, self.settings["export_path"])
            self.map_display.exec_()
        except:
            QMessageBox.warning(self, "Error", "Export failed.")

    def on_clear(self):
        self.left_tree.clear()
        self.right_tree.clear()

    def on_export_path(self):
        export_path_dialog = QFileDialog()
        folder_path = export_path_dialog.getExistingDirectory(
            self, "Export Path", self.settings["export_path"]
        )
        self.settings["export_path"] = folder_path

    def load_lot(self, parent, name, color, editable=False):
        item = QTreeWidgetItem([name])
        if editable:
            item.setFlags(
                item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable
            )
            item.setCheckState(0, 0)
        parent.addChild(item)
        item.setForeground(0, QColor(color))
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        return item

    def on_left_tree_selected(self):
        if self.is_programmed_change:
            return
        self.is_programmed_change = True
        self.refresh_selected_color(self.left_tree)
        self.right_tree.clearSelection()
        self.selected_tree = self.left_tree
        self.is_programmed_change = False

    def on_add_lot(self):
        selected_item = self.left_tree.currentItem()
        if not selected_item:
            return
        # inherit and modify numerical name from selected_item if applicable
        item_name = "New Lot"
        selected_text = selected_item.text(0)
        if selected_text.isnumeric():
            item_name = str(int(selected_text) + 1)
        # consider the parent campaign as selected_item for inheritance purposes if applicable
        if selected_item.parent():
            selected_item = selected_item.parent()
        # add editable lot and disable drop
        item = QTreeWidgetItem([item_name])
        item.setFlags(
            item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable
        )
        item.setCheckState(0, 0)
        selected_item.addChild(item)
        self.add_widgets_to_item(item, self.statuses["lot"], "None")
        # inherit color from parent
        item.setForeground(0, item.parent().foreground(0).color())
        # select for editing
        self.left_tree.setCurrentItem(item)
        self.left_tree.editItem(item, 0)
        # prevents editing name after its been set the first time (lazy way of preventing lot name mismatch between trees)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

    def on_left_tree_item_changed(self, item, column):
        if self.is_programmed_change:
            return
        combo_box = self.left_tree.itemWidget(item, 1)
        if not isinstance(combo_box, QComboBox):
            # it must be a campaign that changed rather than a lot
            return
        # change duplicate names
        found_items = self.find_items(self.left_tree, item.text(0))
        if len(found_items) > 1:
            item.setText(0, f"{item.text(0)} (Duplicate)")
        if combo_box and item.checkState(0) == 0:
            # item unchecked
            combo_box.setDisabled(False)
            combo_box.setCurrentIndex(0)
            self.is_programmed_change = True
            item.setFlags(item.flags() | QtCore.Qt.ItemIsDragEnabled)
            self.is_programmed_change = False
        elif item.checkState(0) == 2:
            # item checked
            found_items = self.find_items(self.right_tree, item.text(0))
            self.remove_items(self.right_tree, found_items)
            combo_box.setCurrentIndex(2)
            combo_box.setDisabled(True)
            self.is_programmed_change = True
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
            self.is_programmed_change = False

    def on_remove(self):
        self.remove_left()
        self.remove_right()

    def remove_left(self):
        left = self.left_tree
        right = self.right_tree
        if not left.selectedItems():
            return
        item = left.selectedItems()[0]
        found_lots = self.find_items(right, item.text(0))
        # delete children manually before deleting the parent to conduct the room searches
        for i in range(item.childCount()):
            lot = item.child(i)
            found_lots.extend(self.find_items(right, lot.text(0)))
        self.remove_items(right, found_lots)
        self.remove_items(left, left.selectedItems())

    def on_color(self):
        tree = self.left_tree
        selected_items = tree.selectedItems()
        if not selected_items:
            return
        print(selected_items[0].text(0))
        selected_color = QColorDialog.getColor()
        selected_items[0].setForeground(0, selected_color)
        found_items = self.find_items(self.right_tree, selected_items[0].text(0))
        if found_items:
            found_items[0].setForeground(0, selected_color)
        self.refresh_selected_color(tree)

    def on_right_tree_selected(self):
        if self.is_programmed_change:
            return
        self.is_programmed_change = True
        self.refresh_selected_color(self.right_tree)
        self.left_tree.clearSelection()
        self.selected_tree = self.right_tree
        self.is_programmed_change = False

    def on_add_campaign(self):
        item = self.add_top_level_item(self.left_tree, "New Campaign", "", True)
        self.left_tree.setItemWidget(item, 1, QLabel())

    def on_add_room(self):
        item = self.add_top_level_item(self.right_tree, "New Room", "", True)
        self.add_widgets_to_item(item, self.statuses["room"], "None", 0)

    def add_top_level_item(self, tree, name, color, select):
        # create item, enable editing, disable dragging, set color, add to tree, expand if requested, return item.
        item = QTreeWidgetItem([name])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
        item.setForeground(0, QColor(color))
        tree.addTopLevelItem(item)
        item.setExpanded(True)
        if select:
            tree.setCurrentItem(item)
            tree.editItem(item, 0)
        return item

    def add_widgets_to_item(self, item, combo_list, combo_default, spin_default=False):
        tree = item.treeWidget()
        # create combobox
        combo_box = QComboBoxNoWheelEvent(self)
        combo_box.addItems(combo_list)
        combo_box.setCurrentText(combo_default)
        # disable and hide the "Completed" status to reserve for special use
        try:
            completed_index = combo_list.index("Completed")
        except:
            completed_index = -1
        if completed_index >= 0:
            completed_item = combo_box.model().item(completed_index)
            completed_item.setFlags(completed_item.flags() & ~QtCore.Qt.ItemIsEnabled)
            combo_box.view().setRowHidden(completed_index, True)
        # deal with styling
        combo_box.view().window().setWindowFlags(
            QtCore.Qt.Popup
            | QtCore.Qt.NoDropShadowWindowHint
            | QtCore.Qt.FramelessWindowHint
        )
        combo_box.view().window().setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # add combobox
        tree.setItemWidget(item, 1, combo_box)
        # create and add spinbox if desired
        if spin_default is False:
            return
        spin_box = QSpinBoxNoWheelEvent()
        spin_box.setMaximum(99999)
        spin_box.setValue(spin_default)
        tree.setItemWidget(item, 2, spin_box)

    def remove_right(self):
        right = self.right_tree
        if not right.selectedItems():
            return
        self.remove_items(right, right.selectedItems())

    def tree_to_objects(self, tree):
        is_left_tree = True if tree == self.left_tree else False
        top_level_items = []
        for i in range(tree.topLevelItemCount()):
            top_level_item = tree.topLevelItem(i)
            lots = self.lots_to_objects(top_level_item, is_left_tree)
            name = top_level_item.text(0)
            if is_left_tree:
                color = top_level_item.foreground(0).color().name()
                top_level_items.append(Campaign(name, color, lots))
            else:
                combo_box = tree.itemWidget(top_level_item, 1)
                status = combo_box.currentText()
                spin_box = tree.itemWidget(top_level_item, 2)
                shipping = spin_box.value()
                top_level_items.append(Room(name, status, shipping, lots))
        return top_level_items

    def lots_to_objects(self, top_level_item, include_status):
        lots = []
        for i in range(top_level_item.childCount()):
            child_item = top_level_item.child(i)
            name = child_item.text(0)
            color = child_item.foreground(0).color().name()
            combo_box = self.left_tree.itemWidget(child_item, 1)
            status = combo_box.currentText() if combo_box else ""
            lot = Lot(name, color, status)
            if not include_status:
                del lot["status"]
            lots.append(lot)
        return lots

    def trees_to_object(self):
        date = self.date_edit.date().toString("MM/dd/yyyy")
        campaigns = self.tree_to_objects(self.left_tree)
        rooms = self.tree_to_objects(self.right_tree)
        data = Data(campaigns, rooms, date)
        return data

    def refresh_selected_color(self, tree):
        if not tree.currentItem():
            return
        foreground_color = tree.currentItem().foreground(0).color().name()
        tree.setStyleSheet(f"QTreeWidget::item:selected {{color: {foreground_color};}}")

    def find_items(self, tree, item_text):
        return tree.findItems(item_text, QtCore.Qt.MatchRecursive, 0)

    def remove_items(self, tree, items):
        root = tree.invisibleRootItem()
        for item in items:
            (item.parent() or root).removeChild(item)

    def closeEvent(self, event):
        self.write_settings()
        if self.load_data(self.settings["save_path"]) == self.trees_to_object():
            return
        buttons = QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        prompt = QMessageBox.question(
            self, "Confirmation", "Close without saving?", buttons
        )
        if prompt == QMessageBox.Cancel:
            event.ignore()
        if prompt == QMessageBox.Save:
            self.on_save()


def get_style():
    if not os.path.exists("style.qss"):
        return ""
    with open("style.qss", "r") as out_file:
        return out_file.read()


def main():
    app = QApplication(sys.argv)
    style = get_style()
    app.setStyleSheet(style)
    app.setEffectEnabled(QtCore.Qt.UIEffect.UI_AnimateCombo, False)
    factory_editor = Factory()
    app.exec_()


if __name__ == "__main__":
    main()
