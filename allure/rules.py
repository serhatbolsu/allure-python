# -*- coding: utf-8 -*-

__author__ = 'pupssman'

import re
import sys

from lxml import objectify
from recordtype import recordtype


def element_maker(name, namespace):
    return getattr(objectify.ElementMaker(annotate=False, namespace=namespace,), name)


class Rule(object):
    _check = None

    def value(self, name, what):
        raise NotImplemented()

    def if_(self, check):
        self._check = check
        return self

    def check(self, what):
        if self._check:
            return self._check(what)
        else:
            return True


# see http://en.wikipedia.org/wiki/Valid_characters_in_XML#Non-restricted_characters

# We need to get the subset of the invalid unicode ranges according to
# XML 1.0 which are valid in this python build.  Hence we calculate
# this dynamically instead of hardcoding it.  The spec range of valid
# chars is: Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
#                    | [#x10000-#x10FFFF]
_legal_chars = (0x09, 0x0A, 0x0d)
_legal_ranges = (
    (0x20, 0x7E),
    (0x80, 0xD7FF),
    (0xE000, 0xFFFD),
    (0x10000, 0x10FFFF),
)
_legal_xml_re = [unicode("%s-%s") % (unichr(low), unichr(high)) for (low, high) in _legal_ranges if low < sys.maxunicode]
_legal_xml_re = [unichr(x) for x in _legal_chars] + _legal_xml_re
illegal_xml_re = re.compile(unicode('[^%s]') % unicode('').join(_legal_xml_re))


def legalize_xml(arg):
    def repl(matchobj):
        i = ord(matchobj.group())
        if i <= 0xFF:
            return unicode('#x%02X') % i
        else:
            return unicode('#x%04X') % i
    return illegal_xml_re.sub(repl, arg)


class Element(Rule):
    def __init__(self, name='', namespace=''):
        self.name = name
        self.namespace = namespace

    def value(self, name, what):
        if not isinstance(what, basestring):
            return self.value(name, str(what))

        if not isinstance(what, unicode):
            try:
                what = unicode(what, 'utf-8')
            except UnicodeDecodeError:
                what = unicode(what, 'utf-8', errors='replace')

        return element_maker(self.name or name, self.namespace)(legalize_xml(what))


class Attribute(Rule):
    def value(self, name, what):
        return str(what)


class Nested(Rule):
    def value(self, name, what):
        return what.toxml()


class Many(Rule):
    def __init__(self, rule, name='', namespace=''):
        self.rule = rule
        self.name = name
        self.namespace = namespace

    def value(self, name, what):
        return [self.rule.value(name, x) for x in what]


class WrappedMany(Many):
    def value(self, name, what):
        values = super(WrappedMany, self).value(name, what)
        return element_maker(self.name or name, self.namespace)(*values)


def xmlfied(el_name, namespace='', fields=[], **kw):
    items = fields + kw.items()

    class MyImpl(recordtype('XMLFied', [(item[0], None) for item in items])):
        def toxml(self):
            el = element_maker(el_name, namespace)
            entries = lambda clazz: [(name, rule.value(name, getattr(self, name))) for (name, rule) in items if isinstance(rule, clazz) and rule.check(getattr(self, name))]

            elements = entries(Element)
            attributes = entries(Attribute)
            nested = entries(Nested)
            manys = sum([[(m[0], v) for v in m[1]] for m in entries(Many)], [])

            return el(*([element for (_, element) in elements + nested + manys]),
                      **{name: attr for (name, attr) in attributes})

    return MyImpl
