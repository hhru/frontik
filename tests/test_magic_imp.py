import frontik.magic_imp
import sys

def test_simple():
    importer = frontik.magic_imp.FrontikAppImporter( "test_app", "tests/projects/test_app")
    a = importer.imp_app_module("simple_lib_use")

    assert(a.a == 10)

def import_syntax_error_test():
    importer = frontik.magic_imp.FrontikAppImporter("test_app", "tests/projects/test_app")

    try:
        a = importer.imp_app_module("syntax_error")
    except:
        pass

    assert ("frontik.imp.test_app.syntax_error" not in sys.modules)
