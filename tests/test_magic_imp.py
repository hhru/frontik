import frontik.magic_imp

def test_simple():
    importer = frontik.magic_imp.FrontikAppImporter({"test_app": "tests/projects/test_app"})
    a = importer.imp_app_module("test_app", "simple_lib_use")

    assert(a.a == 10)
