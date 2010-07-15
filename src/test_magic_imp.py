import frontik.magic_imp

def test_simple():
    importer = frontik.magic_imp.FrontikAppImporter({'a': 'test/a'})
    a = importer.imp_app_module('a', 'simple_lib_use')

    assert(a.a == 10)

