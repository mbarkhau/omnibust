from __future__ import print_function

import os
import time
import tempfile
import omnibust as ob


def _write_tmp_file(content, path=None):
    if path is None:
        _, path = tempfile.mkstemp()
    with open(path, 'wb') as f:
        f.write(content)
    return path


def _mk_test_project():
    root = tempfile.mkdtemp()
    subdir_a = os.path.join(root, "subdir_a")
    subdir_b = os.path.join(root, "subdir_b")
    os.system("touch " + os.path.join(root, "foo.js"))
    os.system("touch " + os.path.join(root, "bar.js"))
    os.system("touch " + os.path.join(root, "buzz.py"))
    os.system("touch " + os.path.join(root, "baz.jpg"))
    os.makedirs(subdir_a)
    os.system("touch " + os.path.join(subdir_a, "a.py"))
    os.system("touch " + os.path.join(subdir_a, "a.pyc"))
    os.system("touch " + os.path.join(subdir_a, "b.py"))
    os.system("touch " + os.path.join(subdir_a, "b.pyc"))
    os.makedirs(subdir_b)
    os.system("touch " + os.path.join(subdir_b, "a.js"))
    os.system("touch " + os.path.join(subdir_b, "b.js"))
    return root


p_ref = ob.Ref("test.html", 123, ob.PLAIN_REF, "url('/static/app.js')",
               "/static/app.js", None)
qs_ref = ob.Ref("test.html", 123, ob.QS_REF,
                "url('/static/app.js?_cb_=123456&a=b')", "/static/app.js",
                "123456")
fn_ref = ob.Ref("test.html", 123, ob.FN_REF,
                "url('/static/app_cb_123456.js')", "/static/app.js",
                "123456")


def test_b32enc():
    assert len(ob.b32enc(1)) == 7
    assert len(ob.b32enc(1.1)) == 13
    assert len(ob.b32enc(123456)) == 7
    assert ob.b32enc(123456) == b"idracaa"
    assert isinstance(ob.b32enc(b"test"), bytes)
    assert ob.b32enc(b"test") == b"orsxg5a"


def test_filestat():
    assert len(ob.filestat(__file__)) == 13
    fp, path = tempfile.mkstemp()
    os.system("touch " + path)

    assert ob.filestat(path) == ob.filestat(path)
    stat = ob.filestat(path)
    time.sleep(.1)
    os.system("touch " + path)
    assert stat != ob.filestat(path)


def test_digest_data():
    digest = ob.digest_data
    assert isinstance(digest("test"), bytes)
    assert digest("test") == digest("test")
    assert digest("foo") != digest("bar")
    assert digest("test", 'sha1') == digest("test", 'sha1')
    assert digest("foo", 'sha1') != digest("bar", 'sha1')
    assert digest("test", 'sha1') != digest("test", 'md5')


def test_file_digester():
    path_a = _write_tmp_file("test")
    path_b = _write_tmp_file("test")

    crc_digester = ob.file_digester('crc32')
    assert crc_digester(path_a) == crc_digester(path_b)

    path_a = _write_tmp_file("foo")
    path_b = _write_tmp_file("bar")

    assert crc_digester(path_a) != crc_digester(path_b)


def test_digest_paths():
    path_a = _write_tmp_file("test")
    path_b = _write_tmp_file("test")

    digester = ob.file_digester('crc32')
    digest_a = ob.digest_paths([path_a, path_b], digester)
    digest_b = ob.digest_paths([path_a, path_b], digester)
    assert digest_a == digest_b
    _write_tmp_file("foo", path_b)
    digest_b = ob.digest_paths([path_a, path_b], digester)
    assert digest_a != digest_b


def test_glob_matcher():
    txt_matcher = ob.glob_matcher("*.js")
    assert txt_matcher("foo.js")
    assert txt_matcher("foo/bar.js")
    assert not txt_matcher("foo/bar.py")
    jpg_matcher = ob.glob_matcher(("*.jpg", "*.jpeg"))
    assert jpg_matcher("foo.jpg")
    assert jpg_matcher("foo/bar.jpeg")
    assert not jpg_matcher("foo/bar.py")


def test_iter_filepaths():
    root = _mk_test_project()
    iterfp = lambda *a, **k: list(ob.iter_filepaths(*a, **k))

    assert len(iterfp(root)) == 10
    assert len(iterfp(root, "*.js")) == 4
    assert iterfp(root, "*.jpg")[0].endswith("baz.jpg")
    assert len(iterfp(root, file_exclude="*.js")) == 6
    assert len(iterfp(root, dir_filter="*subdir_a")) == 4
    assert len(iterfp(root, dir_filter="*subdir_a", file_filter="*.py")) == 2


def test_multi_iter_filepaths():
    root = _mk_test_project()
    dirs = [os.path.join(root, "subdir_a"), os.path.join(root, "subdir_b")]
    assert len(list(ob.multi_iter_filepaths(dirs))) == 6


def test_unique_dirname_printer():
    import sys
    import cStringIO
    # just check that it's a wrapper
    printer = ob.unique_dirname_printer()
    orig_out = sys.stdout
    tmp_out = sys.stdout = cStringIO.StringIO()
    assert printer("test/foo") == "test/foo"
    assert printer("foo/foo") == "foo/foo"
    assert printer("bar/foo") == "bar/foo"
    sys.stdout = orig_out
    lines = tmp_out.getvalue().splitlines()
    assert lines[0] == "test"
    assert lines[1] == "foo"
    assert lines[2] == "bar"


def test_filter_longest():
    elems = ["abcdefghi", "aabbccddeeffgghhii", "aabbccddeeeef"]
    match = lambda i, e: ord(e[i]) <= ord("e")
    length, longest = ob.filter_longest(match, elems)
    assert longest == "aabbccddeeeef"


def test_mk_fn_dir_map():
    paths = [
        "test/test.js",
        "foo/bar.js",
        "foo/baz.js",
        "bar/bar.js",
    ]
    fn_dir_map = ob.mk_fn_dir_map(paths)
    assert len(fn_dir_map) == 3
    assert len(fn_dir_map['test.js']) == 1
    assert len(fn_dir_map['bar.js']) == 2


def test_closest_matching_path():
    dirpaths = ["foo/static", "foo/assets", "bar/static"]
    path = ob.closest_matching_path("foo/a.py", "/static", dirpaths)
    assert path == "foo/static"


def test_mk_plainref():
    assert ob.mk_plainref(p_ref) == "url('/static/app.js')"
    assert ob.mk_plainref(fn_ref) == "url('/static/app.js')"
    assert ob.mk_plainref(qs_ref) == "url('/static/app.js?a=b')"


def test_add_fn_bustcode():
    busted = ob.add_fn_bustcode(p_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js')"
    busted = ob.add_fn_bustcode(fn_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js')"
    busted = ob.add_fn_bustcode(qs_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js?a=b')"


def test_add_qs_bustcode():
    assert False


def test_replace_bustcode():
    assert False


def test_rewrite_ref():
    # "codepath, lineno, ref_type, fullref, refpath, bustcode"
    print(ob.rewrite_ref(p_ref, "abcdef", ob.QS_REF))
    ob.rewrite_ref(qs_ref, "abcdef", ob.QS_REF)
    ob.rewrite_ref(fn_ref, "abcdef", ob.FN_REF)


if __name__ == '__main__':
    for k, v in locals().items():
        if k.startswith('test_'):
            try:
                v()
            except:
                pass
