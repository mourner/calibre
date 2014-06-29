#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json

from cssselect import parse
from PyQt4.Qt import (
    QWidget, QTimer, QStackedLayout, QLabel, QScrollArea, QVBoxLayout,
    QPainter, Qt, QPalette, QRect, QSize, QSizePolicy, pyqtSignal,
    QColor)

from calibre.constants import iswindows
from calibre.gui2.tweak_book import editors, actions, current_container, tprefs
from calibre.gui2.tweak_book.editor.themes import get_theme, theme_color
from calibre.gui2.tweak_book.editor.text import default_font_family

class Heading(QWidget):  # {{{

    toggled = pyqtSignal(object)

    def __init__(self, text, expanded=True, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setCursor(Qt.PointingHandCursor)
        self.text = text
        self.expanded = expanded
        self.hovering = False
        self.do_layout()

    def do_layout(self):
        try:
            f = self.parent().font()
        except AttributeError:
            return
        f.setBold(True)
        self.setFont(f)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            ev.accept()
            self.expanded ^= True
            self.toggled.emit(self)
            self.update()
        else:
            return QWidget.mousePressEvent(self, ev)

    @property
    def rendered_text(self):
        return ('▾' if self.expanded else '▸') + '\xa0' + self.text

    def sizeHint(self):
        fm = self.fontMetrics()
        sz = fm.boundingRect(self.rendered_text).size()
        return sz

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setClipRect(ev.rect())
        bg = self.palette().color(QPalette.AlternateBase)
        if self.hovering:
            bg = bg.lighter(115)
        p.fillRect(self.rect(), bg)
        try:
            p.drawText(self.rect(), Qt.AlignLeft|Qt.AlignVCenter|Qt.TextSingleLine, self.rendered_text)
        finally:
            p.end()

    def enterEvent(self, ev):
        self.hovering = True
        self.update()
        return QWidget.enterEvent(self, ev)

    def leaveEvent(self, ev):
        self.hovering = False
        self.update()
        return QWidget.leaveEvent(self, ev)
# }}}

class Cell(object):  # {{{

    __slots__ = ('rect', 'text', 'right_align', 'color_role', 'override_color', 'swatch', 'is_overriden')

    SIDE_MARGIN = 5
    FLAGS = Qt.AlignVCenter | Qt.TextSingleLine | Qt.TextIncludeTrailingSpaces

    def __init__(self, text, rect, right_align=False, color_role=QPalette.WindowText, swatch=None, is_overriden=False):
        self.rect, self.text = rect, text
        self.right_align = right_align
        self.is_overriden = is_overriden
        self.color_role = color_role
        self.override_color = None
        self.swatch = swatch
        if swatch is not None:
            self.swatch = QColor(swatch[0], swatch[1], swatch[2], int(255 * swatch[3]))

    def draw(self, painter, width, palette):
        flags = self.FLAGS | (Qt.AlignRight if self.right_align else Qt.AlignLeft)
        rect = QRect(self.rect)
        if self.right_align:
            rect.setRight(width - self.SIDE_MARGIN)
        painter.setPen(palette.color(self.color_role) if self.override_color is None else self.override_color)
        br = painter.drawText(rect, flags, self.text)
        if self.swatch is not None:
            r = QRect(br.right() + self.SIDE_MARGIN // 2, br.top() + 2, br.height() - 4, br.height() - 4)
            painter.fillRect(r, self.swatch)
            br.setRight(r.right())
        if self.is_overriden:
            painter.setPen(palette.color(QPalette.WindowText))
            painter.drawLine(br.left(), br.top() + br.height() // 2, br.right(), br.top() + br.height() // 2)
# }}}

class Declaration(QWidget):

    hyperlink_activated = pyqtSignal(object)

    def __init__(self, html_name, data, is_first=False, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.data = data
        self.is_first = is_first
        self.html_name = html_name
        self.do_layout()
        self.setMouseTracking(True)

    def do_layout(self):
        fm = self.fontMetrics()
        bounding_rect = lambda text: fm.boundingRect(0, 0, 10000, 10000, Cell.FLAGS, text)
        line_spacing = 2
        side_margin = Cell.SIDE_MARGIN
        self.rows = []
        ypos = line_spacing + (1 if self.is_first else 0)
        if 'href' in self.data:
            name = self.data['href']
            if isinstance(name, list):
                name = self.html_name
            br1 = bounding_rect(name)
            sel = self.data['selector'] or ''
            if self.data['type'] == 'inline':
                sel = 'style=""'
            br2 = bounding_rect(sel)
            self.hyperlink_rect = QRect(side_margin, ypos, br1.width(), br1.height())
            self.rows.append([
                Cell(name, self.hyperlink_rect, color_role=QPalette.Link),
                Cell(sel, QRect(br1.right() + side_margin, ypos, br2.width(), br2.height()), right_align=True)
            ])
            ypos += max(br1.height(), br2.height()) + 2 * line_spacing

        for prop in self.data['properties']:
            text = prop.name + ':\xa0'
            br1 = bounding_rect(text)
            vtext = prop.value + '\xa0' + ('!' if prop.important else '') + prop.important
            br2 = bounding_rect(vtext)
            self.rows.append([
                Cell(text, QRect(side_margin, ypos, br1.width(), br1.height()), color_role=QPalette.LinkVisited, is_overriden=prop.is_overriden),
                Cell(vtext, QRect(br1.right() + side_margin, ypos, br2.width(), br2.height()), swatch=prop.color, is_overriden=prop.is_overriden)
            ])
            ypos += max(br1.height(), br2.height()) + line_spacing

        self.height_hint = ypos + line_spacing
        self.width_hint = max(row[-1].rect.right() + side_margin for row in self.rows) if self.rows else 0

    def sizeHint(self):
        return QSize(self.width_hint, self.height_hint)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setClipRect(ev.rect())
        palette = self.palette()
        p.setPen(palette.color(QPalette.WindowText))
        if not self.is_first:
            p.drawLine(0, 0, self.width(), 0)
        try:
            for row in self.rows:
                for cell in row:
                    p.save()
                    try:
                        cell.draw(p, self.width(), palette)
                    finally:
                        p.restore()

        finally:
            p.end()

    def mouseMoveEvent(self, ev):
        if hasattr(self, 'hyperlink_rect'):
            pos = ev.pos()
            hovering = self.hyperlink_rect.contains(pos)
            self.update_hover(hovering)
            cursor = Qt.ArrowCursor
            for r, row in enumerate(self.rows):
                for cell in row:
                    if cell.rect.contains(pos):
                        cursor = Qt.PointingHandCursor if cell.rect is self.hyperlink_rect else Qt.IBeamCursor
                    if r == 0:
                        break
                if cursor != Qt.ArrowCursor:
                    break
            self.setCursor(cursor)
        return QWidget.mouseMoveEvent(self, ev)

    def mousePressEvent(self, ev):
        if hasattr(self, 'hyperlink_rect'):
            pos = ev.pos()
            if self.hyperlink_rect.contains(pos):
                self.emit_hyperlink_activated()
        return QWidget.mousePressEvent(self, ev)

    def emit_hyperlink_activated(self):
        dt = self.data['type']
        data = {'type':dt, 'name':self.html_name, 'syntax':'html'}
        if dt == 'inline':  # style attribute
            data['sourceline_address'] = self.data['href']
        elif dt == 'elem':  # <style> tag
            data['sourceline_address'] = self.data['href']
            data['rule_address'] = self.data['rule_address']
        else:  # stylesheet
            data['name'] = self.data['href']
            data['rule_address'] = self.data['rule_address']
            data['syntax'] = 'css'
        self.hyperlink_activated.emit(data)

    def leaveEvent(self, ev):
        self.update_hover(False)
        self.setCursor(Qt.ArrowCursor)
        return QWidget.leaveEvent(self, ev)

    def update_hover(self, hovering):
        cell = self.rows[0][0]
        if (hovering and cell.override_color is None) or (
                not hovering and cell.override_color is not None):
            cell.override_color = QColor(Qt.red) if hovering else None
            self.update()

class Box(QWidget):

    hyperlink_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignTop)
        self.setLayout(l)
        self.widgets = []

    def show_data(self, data):
        for w in self.widgets:
            self.layout().removeWidget(w)
            for x in ('toggled', 'hyperlink_activated'):
                if hasattr(w, x):
                    try:
                        getattr(w, x).disconnect()
                    except TypeError:
                        pass
            w.deleteLater()
        self.widgets = []
        for node in data['nodes']:
            node_name = node['name'] + ' @%s' % node['sourceline']
            if node['is_ancestor']:
                title = _('Inherited from %s') % node_name
            else:
                title = _('Matched CSS rules for %s') % node_name
            h = Heading(title, parent=self)
            h.toggled.connect(self.heading_toggled)
            self.widgets.append(h), self.layout().addWidget(h)
            for i, declaration in enumerate(node['css']):
                d = Declaration(data['html_name'], declaration, is_first=i == 0, parent=self)
                d.hyperlink_activated.connect(self.hyperlink_activated)
                self.widgets.append(d), self.layout().addWidget(d)

        h = Heading(_('Computed final style'), parent=self)
        h.toggled.connect(self.heading_toggled)
        self.widgets.append(h), self.layout().addWidget(h)
        ccss = data['computed_css']
        declaration = {'properties':[Property([k, ccss[k][0], '', ccss[k][1]]) for k in sorted(ccss)]}
        d = Declaration(None, declaration, is_first=True, parent=self)
        self.widgets.append(d), self.layout().addWidget(d)

    def heading_toggled(self, heading):
        for i, w in enumerate(self.widgets):
            if w is heading:
                for b in self.widgets[i + 1:]:
                    if isinstance(b, Heading):
                        break
                    b.setVisible(heading.expanded)
                break

    def relayout(self):
        for w in self.widgets:
            w.do_layout()
            w.updateGeometry()

class Property(object):

    __slots__ = 'name', 'value', 'important', 'color', 'specificity', 'is_overriden'

    def __init__(self, prop, specificity=()):
        self.name, self.value, self.important, self.color = prop
        self.specificity = tuple(specificity)
        self.is_overriden = False

    def __repr__(self):
        return '<Property name=%s value=%s important=%s color=%s specificity=%s is_overriden=%s>' % (
            self.name, self.value, self.important, self.color, self.specificity, self.is_overriden)

class LiveCSS(QWidget):

    goto_declaration = pyqtSignal(object)

    def __init__(self, preview, parent=None):
        QWidget.__init__(self, parent)
        self.preview = preview
        self.preview_is_refreshing = False
        self.refresh_needed = False
        preview.refresh_starting.connect(self.preview_refresh_starting)
        preview.refreshed.connect(self.preview_refreshed)
        self.apply_theme()
        self.setAutoFillBackground(True)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(500)
        self.now_showing = (None, None, None)

        self.stack = s = QStackedLayout(self)
        self.setLayout(s)

        self.clear_label = la = QLabel('<h3>' + _(
            'No style information found') + '</h3><p>' + _(
                'Move the cursor inside a HTML tag to see what styles'
                ' apply to that tag.'))
        la.setWordWrap(True)
        la.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        s.addWidget(la)

        self.box = box = Box(self)
        box.hyperlink_activated.connect(self.goto_declaration, type=Qt.QueuedConnection)
        self.scroll = sc = QScrollArea(self)
        sc.setWidget(box)
        sc.setWidgetResizable(True)
        s.addWidget(sc)

    def preview_refresh_starting(self):
        self.preview_is_refreshing = True

    def preview_refreshed(self):
        self.preview_is_refreshing = False
        # We must let the event loop run otherwise the webview will return
        # stale data in read_data()
        self.refresh_needed = True
        self.start_update_timer()

    def apply_theme(self):
        f = self.font()
        f.setFamily(tprefs['editor_font_family'] or default_font_family())
        f.setPointSize(tprefs['editor_font_size'])
        self.setFont(f)
        theme = get_theme(tprefs['editor_theme'])
        pal = self.palette()
        pal.setColor(pal.Window, theme_color(theme, 'Normal', 'bg'))
        pal.setColor(pal.WindowText, theme_color(theme, 'Normal', 'fg'))
        pal.setColor(pal.AlternateBase, theme_color(theme, 'HighlightRegion', 'bg'))
        pal.setColor(pal.Link, theme_color(theme, 'Link', 'fg'))
        pal.setColor(pal.LinkVisited, theme_color(theme, 'Keyword', 'fg'))
        self.setPalette(pal)
        if hasattr(self, 'box'):
            self.box.relayout()
        self.update()

    def clear(self):
        self.stack.setCurrentIndex(0)

    def show_data(self, editor_name, sourceline, tags):
        if self.preview_is_refreshing:
            return
        if sourceline is None:
            self.clear()
        else:
            data = self.read_data(sourceline, tags)
            if data is None or len(data['computed_css']) < 1:
                if editor_name == self.current_name and (editor_name, sourceline, tags) == self.now_showing:
                    # Try again in a little while in case there was a transient
                    # error in the web view
                    self.start_update_timer()
                    return
                if self.now_showing == (None, None, None) or self.now_showing[0] != self.current_name:
                    self.clear()
                    return
                # Try to refresh the data for the currently shown tag instead
                # of clearing
                editor_name, sourceline, tags = self.now_showing
                data = self.read_data(sourceline, tags)
                if data is None or len(data['computed_css']) < 1:
                    self.clear()
                    return
            self.now_showing = (editor_name, sourceline, tags)
            data['html_name'] = editor_name
            self.box.show_data(data)
            self.refresh_needed = False
            self.stack.setCurrentIndex(1)

    def read_data(self, sourceline, tags):
        mf = self.preview.view.page().mainFrame()
        tags = [x.lower() for x in tags]
        result = unicode(mf.evaluateJavaScript(
            'window.calibre_preview_integration.live_css(%s, %s)' % (
                json.dumps(sourceline), json.dumps(tags))).toString())
        try:
            result = json.loads(result)
        except ValueError:
            result = None
        if result is not None:
            maximum_specificities = {}
            for node in result['nodes']:
                is_ancestor = node['is_ancestor']
                for rule in node['css']:
                    self.process_rule(rule, is_ancestor, maximum_specificities)
            for node in result['nodes']:
                for rule in node['css']:
                    for prop in rule['properties']:
                        if prop.specificity < maximum_specificities[prop.name]:
                            prop.is_overriden = True

        return result

    def process_rule(self, rule, is_ancestor, maximum_specificities):
        selector = rule['selector']
        sheet_index = rule['sheet_index']
        rule_address = rule['rule_address'] or ()
        if selector is not None:
            try:
                specificity = [0] + list(parse(selector)[0].specificity())
            except (AttributeError, TypeError):
                specificity = [0, 0, 0, 0]
        else:  # style attribute
            specificity = [1, 0, 0, 0]
        specificity.extend((sheet_index, tuple(rule_address)))
        ancestor_specificity = 0 if is_ancestor else 1
        properties = []
        for prop in rule['properties']:
            important = 1 if prop[-1] == 'important' else 0
            p = Property(prop, [ancestor_specificity] + [important] + specificity)
            properties.append(p)
            if p.specificity > maximum_specificities.get(p.name, (0,0,0,0,0,0)):
                maximum_specificities[p.name] = p.specificity
        rule['properties'] = properties

        href = rule['href']
        if hasattr(href, 'startswith') and href.startswith('file://'):
            href = href[len('file://'):]
            if iswindows and href.startswith('/'):
                href = href[1:]
            if href:
                rule['href'] = current_container().abspath_to_name(href, root=self.preview.current_root)

    @property
    def current_name(self):
        return self.preview.current_name

    @property
    def is_visible(self):
        return self.isVisible()

    def showEvent(self, ev):
        self.update_timer.start()
        actions['auto-reload-preview'].setEnabled(True)
        return QWidget.showEvent(self, ev)

    def sync_to_editor(self, name):
        self.start_update_timer()

    def update_data(self):
        if not self.is_visible or self.preview_is_refreshing:
            return
        editor_name = self.current_name
        ed = editors.get(editor_name, None)
        if self.update_timer.isActive() or (ed is None and editor_name is not None):
            return QTimer.singleShot(100, self.update_data)
        if ed is not None:
            sourceline, tags = ed.current_tag()
            if self.refresh_needed or self.now_showing != (editor_name, sourceline, tags):
                self.show_data(editor_name, sourceline, tags)

    def start_update_timer(self):
        if self.is_visible:
            self.update_timer.start()

    def stop_update_timer(self):
        self.update_timer.stop()

    def navigate_to_declaration(self, data, editor):
        if data['type'] == 'inline':
            sourceline, tags = data['sourceline_address']
            editor.goto_sourceline(sourceline, tags, attribute='style')
        elif data['type'] == 'sheet':
            editor.goto_css_rule(data['rule_address'])
        elif data['type'] == 'elem':
            editor.goto_css_rule(data['rule_address'], sourceline_address=data['sourceline_address'])
