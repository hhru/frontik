import logging
import os.path

import lxml.etree as etree

log = logging.getLogger('frontik.xml_util')

def _abs_filename(base_filename, filename):
    if filename.startswith('/'):
        return filename
    else:
        base_dir = os.path.dirname(base_filename)
        return os.path.normpath(os.path.join(base_dir, filename))
    

def _read_xsl_one(filename, log=log):
    ''' return (etree.ElementTree, xsl includes from  given file '''

    with open(filename, "rb") as fp:
        log.debug('read file %s', filename)
        tree = etree.parse(fp)

        xsl_includes = [_abs_filename(filename, i.get('href'))
                        for i in tree.findall('{http://www.w3.org/1999/XSL/Transform}import')]
        return tree, xsl_includes


def read_xsl(filename, log=log):
    ''' return (etree.XSL, xsl_files_watchlist) '''

    xsl_includes = set([filename])
    
    result, new_xsl_files = _read_xsl_one(filename, log)

    diff = set(new_xsl_files).difference(xsl_includes)
    while diff:
        new_xsl_files = set()

        for i in diff:
            _, i_files = _read_xsl_one(i, log)
            xsl_includes.add(i)
            new_xsl_files.update(i_files)

        diff = new_xsl_files.difference(xsl_includes)
    
    return (etree.XSLT(result), xsl_includes)

        
    
