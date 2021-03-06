#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Builtin recipes.
'''
import re, time, io
from calibre.web.feeds.news import (BasicNewsRecipe, CustomIndexRecipe,
    AutomaticNewsRecipe, CalibrePeriodical)
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.utils.config import JSONConfig

basic_recipes = (BasicNewsRecipe, AutomaticNewsRecipe, CustomIndexRecipe,
        CalibrePeriodical)

custom_recipes = JSONConfig('custom_recipes/index.json')

def custom_recipe_filename(id_, title):
    from calibre.utils.filenames import ascii_filename
    return ascii_filename(title[:50]) + \
                        ('_%s.recipe'%id_)

def compile_recipe(src):
    '''
    Compile the code in src and return a recipe object, if found.

    :param src: Python source code as bytestring or unicode object

    :return: Recipe class or None, if no such class was found in src
    '''
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    # Python complains if there is a coding declaration in a unicode string
    src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src.lstrip(u'\ufeff'), flags=re.MULTILINE)
    # Translate newlines to \n
    src = io.StringIO(src, newline=None).getvalue()

    namespace = {
            'BasicNewsRecipe':BasicNewsRecipe,
            'AutomaticNewsRecipe':AutomaticNewsRecipe,
            'time':time, 're':re,
            'BeautifulSoup':BeautifulSoup
    }
    exec src in namespace

    for x in namespace.itervalues():
        if (isinstance(x, type) and issubclass(x, BasicNewsRecipe) and x not
                in basic_recipes):
            return x

    return None

