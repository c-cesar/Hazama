from PySide.QtGui import *
from PySide.QtCore import *
from ui import font, dt_trans
from ui.editor import Editor
from ui.customobjects import NTextDocument, MultiSortFilterProxyModel
from config import settings, nikki
import logging
import random


class NListDelegate(QStyledItemDelegate):
    stylesheet = ('QListView{background-color: rgb(242, 241, 231);'
                  'border: solid 0px; margin-top: 1px}')

    def __init__(self, parent=None):
        super(NListDelegate, self).__init__(parent)
        self.title_h = QFontInfo(font.title).pixelSize() + 10  # title area height
        self.text_h = (QFontMetrics(font.text).lineSpacing() *
                       settings['Main'].getint('previewlines', 4))
        self.tagPath_h = QFontInfo(qApp.font()).pixelSize() + 4
        self.tag_h = self.tagPath_h + 4
        self.dt_w = QFontMetrics(font.title).width('2000/00/00 00:00') + 20
        self.all_h = None  # updated in sizeHint before each item being painting
        # doc is used to draw text(diary's body)
        self.doc = NTextDocument()
        self.doc.setDefaultFont(font.text)
        self.doc.setUndoRedoEnabled(False)
        self.doc.setDocumentMargin(0)
        # setup colors
        self.c_bg = QColor(255, 236, 176)
        self.c_border = QColor(214, 172, 41)
        self.c_inActBg = QColor(255, 236, 176, 40)
        self.c_gray = QColor(93, 73, 57)

    def paint(self, painter, option, index):
        x, y, w = option.rect.x(), option.rect.y(), option.rect.width()-1
        row = index.row()
        dt, text, title, tags, formats = (index.sibling(row, i).data()
                                          for i in range(5))
        selected = bool(option.state & QStyle.State_Selected)
        active = bool(option.state & QStyle.State_Active)
        # draw border and background
        painter.setPen(self.c_border)
        painter.setBrush(self.c_bg if selected and active else
                         self.c_inActBg)
        painter.drawRect(x+1, y, w-2, self.all_h)  # outer border
        if selected:  # draw inner border
            pen = QPen()
            pen.setStyle(Qt.DashLine)
            pen.setColor(self.c_gray)
            painter.setPen(pen)
            painter.drawRect(x+2, y+1, w-4, self.all_h-2)
        # draw datetime and title
        painter.setPen(self.c_gray)
        painter.drawLine(x+10, y+self.title_h, x+w-10, y+self.title_h)
        painter.setPen(Qt.black)
        painter.setFont(font.date)
        painter.drawText(x+14, y, w, self.title_h, Qt.AlignBottom,
                         dt_trans(dt))
        if title:
            painter.setFont(font.title)
            title_w = w-self.dt_w-13
            title = font.title_m.elidedText(title, Qt.ElideRight, title_w)
            painter.drawText(x+self.dt_w, y, title_w, self.title_h,
                             Qt.AlignBottom | Qt.AlignRight, title)
        # draw text
        painter.save()
        self.doc.setText(text, formats)
        self.doc.setTextWidth(w-26)
        painter.translate(x+14, y+self.title_h+2)
        self.doc.drawContents(painter, QRect(0, 0, w-26, self.text_h))
        painter.restore()
        # draw tags
        if tags:
            painter.save()
            painter.setPen(self.c_gray)
            painter.setFont(qApp.font())
            painter.translate(x + 15, y+self.title_h+6+self.text_h)
            for t in tags.split():
                w = font.default_m.width(t) + 4
                tagPath = QPainterPath()
                tagPath.moveTo(8, 0)
                tagPath.lineTo(8+w, 0)
                tagPath.lineTo(8+w, self.tagPath_h)
                tagPath.lineTo(8, self.tagPath_h)
                tagPath.lineTo(0, self.tagPath_h/2)
                tagPath.closeSubpath()
                painter.drawPath(tagPath)
                painter.drawText(8, 1, w, self.tagPath_h, Qt.AlignCenter, t)
                painter.translate(w+15, 0)  # translate by offset
            painter.restore()

    def sizeHint(self, option, index):
        row, model = index.row(), index.model()
        tag_h = self.tag_h if model.data(model.index(row, 3), 0) else 0
        self.all_h = self.title_h + self.text_h + tag_h + 10
        return QSize(-1, self.all_h+3)  # 3 is spacing between entries


class TListDelegate(QStyledItemDelegate):
    """Default TagList Delegate.Also contains TList's stylesheet"""
    stylesheet = ('QListWidget{background-color: rgb(234,182,138);'
                  'border: solid 0px}')

    def __init__(self, parent=None):
        super(TListDelegate, self).__init__(parent)
        self.h = QFontInfo(font.default).pixelSize()+8

    def paint(self, painter, option, index):
        x, y, w = option.rect.x(), option.rect.y(), option.rect.width()
        tag, count = index.data(Qt.DisplayRole), str(index.data(Qt.UserRole))
        painter.setFont(font.default)
        selected = bool(option.state & QStyle.State_Selected)
        textArea = QRect(x+4, y, w-8, self.h)
        if index.row() == 0:  # row 0 is always All(clear tag filter)
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(textArea,
                             Qt.AlignVCenter | Qt.AlignLeft,
                             tag)
        else:
            painter.setPen(QColor(209, 109, 63))
            painter.drawLine(x, y, w, y)
            if selected:
                painter.setPen(QColor(181, 61, 0))
                painter.setBrush(QColor(250, 250, 250))
                painter.drawRect(x, y+1, w-1, self.h-2)
            # draw tag
            painter.setPen(QColor(20, 20, 20) if selected else
                           QColor(80, 80, 80))
            tag = font.default_m.elidedText(tag, Qt.ElideRight,
                                            w-font.date_m.width(count)-12)
            painter.drawText(textArea, Qt.AlignVCenter | Qt.AlignLeft, tag)
            # draw tag count
            painter.setFont(font.date)
            painter.drawText(textArea, Qt.AlignVCenter | Qt.AlignRight, count)

    def sizeHint(self, option, index):
        return QSize(-1, self.h)


class TagList(QListWidget):
    tagChanged = Signal(str)  # str is tag-name or ''

    def __init__(self, *args, **kwargs):
        super(TagList, self).__init__(*args, **kwargs)
        self.setItemDelegate(TListDelegate(self))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setStyleSheet(TListDelegate.stylesheet)
        self.trackList = None  # update in mousePressEvent
        self.currentItemChanged.connect(self.emitTagChanged)

    def load(self):
        logging.info('Tag List load')
        self.clear()  # this may emit unexpected signal when has selection
        item_all = QListWidgetItem(self)
        item_all.setData(Qt.DisplayRole, self.tr('All'))
        for t in nikki.gettag(getcount=True):
            item = QListWidgetItem(self)
            item.setData(Qt.DisplayRole, t[0])
            item.setData(Qt.UserRole, t[1])

    def emitTagChanged(self, currentItem):
        text = currentItem.data(Qt.DisplayRole)
        self.tagChanged.emit('' if text == self.tr('All') else text)

    # all three events below for drag scroll
    def mousePressEvent(self, event):
        self.trackList = []

    def mouseMoveEvent(self, event):
        if self.trackList is not None:
            self.trackList.append(event.pos().y())
            if len(self.trackList) > 4:
                change = self.trackList[-1] - self.trackList[-2]
                scrollbar = self.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() - change)

    def mouseReleaseEvent(self, event):
        if self.trackList is not None:
            if len(self.trackList) <= 4:  # haven't moved
                pEvent = QMouseEvent(QEvent.MouseButtonPress, event.pos(),
                                     event.globalPos(), Qt.LeftButton,
                                     Qt.LeftButton, Qt.NoModifier)
                QListWidget.mousePressEvent(self, pEvent)
        self.trackList = None


class NikkiList1(QListWidget):
    reloaded = Signal()
    needRefresh = Signal(bool, bool)  # (CountLabel, TagList)

    def __init__(self, *args, **kwargs):
        super(NikkiList, self).__init__(*args, **kwargs)
        self.editors = {}
        self.setSelectionMode(self.ExtendedSelection)
        self.itemDoubleClicked.connect(self.startEditor)
        self.setItemDelegate(NListDelegate(self))
        self.setStyleSheet(NListDelegate.stylesheet)
        # setup context menu
        self.editAct = QAction(self.tr('Edit'), self,
                               shortcut=QKeySequence(Qt.Key_Return),
                               triggered=self.startEditor)
        self.delAct = QAction(QIcon(':/menu/list_delete.png'),
                              self.tr('Delete'), self,
                              shortcut=QKeySequence.Delete,
                              triggered=self.delNikki)
        self.selAct = QAction(QIcon(':/menu/random.png'),
                              self.tr('Random'), self,
                              shortcut=QKeySequence(Qt.Key_F7),
                              triggered=self.selectRandomly)
        for i in [self.editAct, self.delAct, self.selAct]: self.addAction(i)
        self.menu = QMenu(self)
        self.menu.addAction(self.editAct)
        self.menu.addAction(self.delAct)
        self.menu.addSeparator()
        self.menu.addAction(self.selAct)

    def contextMenuEvent(self, event):
        selection_count = len(self.selectedItems())
        self.editAct.setDisabled(selection_count != 1)
        self.delAct.setDisabled(selection_count == 0)
        self.selAct.setDisabled(selection_count == 0)
        self.menu.popup(event.globalPos())

    def startEditor(self, item=None, new=False):
        if new:  # called by newNikki method
            curtItem = row = None
            id = -1
        else:  # called by doubleclick event or context-menu or key-shortcut
            curtItem = item if item else self.selectedItems()[0]
            row = curtItem.data(2)
            id = row['id']
        if id in self.editors:
            self.editors[id].activateWindow()
        else:  # create new editor
            editor = Editor(editorId=id, new=new, row=row, parent=self)
            editor.closed.connect(self.on_editor_closed)
            self.editors[id] = editor
            editor.item = curtItem
            if not new:
                editor.nextSc.activated.connect(self.editorNext)
                editor.preSc.activated.connect(self.editorPrevious)
            editor.show()

    def on_editor_closed(self, editorId, nikkiId, tagModified):
        if nikkiId != -1:
            self.reload(nikkiId)
            self.needRefresh.emit(editorId == -1, tagModified)
        self.editors[editorId].deleteLater()
        del self.editors[editorId]

    def delNikki(self):
        if len(self.selectedItems()) == 0: return
        ret = QMessageBox.question(self, self.tr('Delete selected diaries'),
                                   self.tr('Selected diaries will be deleted '
                                           'permanently.Do it?'),
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            for i in self.selectedItems():
                nikki.delete(i.data(2)['id'])
                self.takeItem(self.row(i))
            self.needRefresh.emit(True, True)

    def newNikki(self):
        self.startEditor(None, True)

    def load(self, *, tagId=None, search=None):
        order, reverse = self.getOrder()
        for row in nikki.sorted(order, reverse, tagid=tagId, search=search):
            item = QListWidgetItem(self)
            item.setData(2, row)
        self.setCurrentRow(0)

    def reload(self, id=None):
        order, reverse = self.getOrder()
        logging.debug('Nikki List reload')
        self.clear()
        if id is None:
            for row in nikki.sorted(order, reverse):
                item = QListWidgetItem(self)
                item.setData(2, row)
        else:
            rowIndex = 0
            for row in nikki.sorted(order, reverse):
                if row['id'] == id:
                    rowIndex = self.count()
                item = QListWidgetItem(self)
                item.setData(2, row)
            self.setCurrentRow(rowIndex)
        self.reloaded.emit()

    def handleExport(self, export_all):
        path, _type = QFileDialog.getSaveFileName(
            parent=self,
            caption=self.tr('Export Diary'),
            filter=self.tr('Plain Text (*.txt);;Rich Text (*.rtf)'))
        if path == '': return    # dialog canceled
        if _type.endswith('txt)'):
            selected = (None if export_all else
                        [i.data(2) for i in self.selectedItems()])
            nikki.exporttxt(path, selected)

    @staticmethod
    def getOrder():
        """get sort order(str) and reverse(int) from settings file"""
        order = settings['Main'].get('listorder', 'datetime')
        reverse = settings['Main'].getint('listreverse', 1)
        return order, reverse

    def reloadWithDgReset(self):
        self.setItemDelegate(NListDelegate(self))
        self.reload()

    def selectRandomly(self):
        self.setCurrentRow(random.randrange(0, self.count()))

    def editorNext(self):
        self.editorMove(1)

    def editorPrevious(self):
        self.editorMove(-1)

    def editorMove(self, step):
        """Move to the Previous/Next Diary in Editor.Current
        Editor will close without saving,"""
        curtEditor = list(self.editors.values())[0]
        try:
            index = self.row(curtEditor.item)
        except RuntimeError:  # item has been deleted from list
            return
        # disabled when multi-editor or editing new diary(if new,
        # shortcut would not be set) or no item to move on.
        if (len(self.editors) != 1 or index is None or
           (step == 1 and index >= self.count() - 1) or
           (step == -1 and 0 >= index)):
            return
        else:
            self.setCurrentRow(index + step)
            curtEditor.closeNoSave()
            self.startEditor()

    def sortDT(self, checked):
        if checked:
            settings['Main']['listorder'] = 'datetime'
            self.clear()
            self.load()

    def sortTT(self, checked):
        if checked:
            settings['Main']['listorder'] = 'title'
            self.clear()
            self.load()

    def sortLT(self, checked):
        if checked:
            settings['Main']['listorder'] = 'length'
            self.clear()
            self.load()

    def sortRE(self, checked):
        settings['Main']['listreverse'] = str(checked.real)
        self.clear()
        self.load()


class NikkiList(QListView):
    def __init__(self, parent=None):
        super(NikkiList, self).__init__(parent)
        self.setItemDelegate(NListDelegate(self))
        self.setStyleSheet(NListDelegate.stylesheet)
        self.model = QStandardItemModel(0, 6, self)
        self.fillModel(self.model)
        # ModelProxy1 is filtered by tag
        self.modelProxy1 = QSortFilterProxyModel(self)
        self.modelProxy1.setSourceModel(self.model)
        self.modelProxy1.setDynamicSortFilter(True)
        self.modelProxy1.setFilterKeyColumn(3)
        # ModelProxy2 is from ModelProxy1 and filtered by search string
        self.modelProxy2 = MultiSortFilterProxyModel(self)
        self.modelProxy2.setSourceModel(self.modelProxy1)
        self.modelProxy2.setDynamicSortFilter(True)
        self.modelProxy2.setFilterKeyColumns(0, 1, 2)
        self.setModel(self.modelProxy2)
        self.sort()

    @staticmethod
    def fillModel(model):
        for i in nikki.sorted('datetime'):
            model.insertRow(0)
            model.setData(model.index(0, 0), i['datetime'])
            model.setData(model.index(0, 1), i['text'])
            model.setData(model.index(0, 2), i['title'])
            model.setData(model.index(0, 3), i['tags'])
            model.setData(model.index(0, 4), i['formats'])
            model.setData(model.index(0, 5), len(i['text']))

    def newNikki(self): pass

    def delNikki(self): pass

    def sort(self):
        sortBy = settings['Main'].get('listsortby', 'datetime')
        sortByCol = {'datetime': 0, 'title': 2, 'length': 5}.get(sortBy, 0)
        reverse = settings['Main'].getint('listreverse', 1)
        self.modelProxy1.sort(sortByCol,
                              Qt.DescendingOrder if reverse else Qt.AscendingOrder)
