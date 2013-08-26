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

expansions = {
    "${foo}": ["exp_a", "exp_b"],
    "{{bar}}": ["exp_c", "exp_d", "exp_e"]
}

p_ref = ob.Ref("foo/static", "test.html", 123,
               "url('/static/app.js')",
               "/static/app.js", "", ob.PLAIN_REF)
qs_ref = ob.Ref("bar/static", "test.html", 123,
                "url('/static/app.js?_cb_=123456&a=b')",
                "/static/app.js", "123456", ob.QS_REF)
fn_ref = ob.Ref("assets/baz", "test.html", 123,
                "url('/static/app_cb_123456.js?foo=12&bar=34')",
                "/static/app.js", "123456", ob.FN_REF)


def test_flatten():
    assert ob.flatten([(1, 2, 3), (4, 5, 6)]) == [1, 2, 3, 4, 5, 6]
    assert ob.flatten(((1, 2, 3), (4, 5, 6))) == [1, 2, 3, 4, 5, 6]


def test_ext():
    assert ob.ext("foo.bar") == ".bar"
    assert ob.ext("foo/bar.baz") == ".baz"
    assert ob.ext("foo/bar.tar.gz") == ".gz"


def test_extension_globs():
    extensions = ob.extension_globs([
        "test.foo", "test.bar", "test.baz", "testb.foo"
    ])
    assert sorted(extensions) == ["*.bar", "*.baz", "*.foo"]


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
    elems = ["abcdefghij", "aabbccddeeffgghhii", "aabbccddeeeef"]

    match = lambda i, e: ord(e[i]) <= ord("e")
    length, longest = ob.filter_longest(match, elems)
    assert longest == "aabbccddeeeef"

    match = lambda i, e: i < 9 and e[i] == "abcdefghi"[i]
    length, longest = ob.filter_longest(match, elems)
    assert longest[:length] == "abcdefghi"


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
    path = ob.closest_matching_path("foo/abc.js", "/static", dirpaths)
    assert path == "foo/static"
    path = ob.closest_matching_path("bar/static", "", dirpaths)
    assert path == "bar/static"


def test_expand_path():
    paths = ob.expand_path("/static/foo_${foo}.png", expansions)
    assert len(paths) == 3
    assert "/static/foo_${foo}.png" in paths
    assert "/static/foo_exp_a.png" in paths
    assert "/static/foo_exp_b.png" in paths

    paths = ob.expand_path("/static/bar_{{bar}}.js", expansions)
    assert len(paths) == 4
    assert "/static/bar_{{bar}}.js" in paths
    assert "/static/bar_exp_c.js" in paths
    assert "/static/bar_exp_d.js" in paths
    assert "/static/bar_exp_e.js" in paths


def test_resolve_refpath():
    pass
    # ob.resolve_refpath()


def test_resolve_ref_paths():
    pass


def test_mk_plainref():
    assert ob.mk_plainref(p_ref) == "url('/static/app.js')"
    assert ob.mk_plainref(fn_ref) == "url('/static/app.js?foo=12&bar=34')"
    assert ob.mk_plainref(qs_ref) == "url('/static/app.js?a=b')"


def test_set_fn_bustcode():
    busted = ob.set_fn_bustcode(p_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js')"
    busted = ob.set_fn_bustcode(fn_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js?foo=12&bar=34')"
    busted = ob.set_fn_bustcode(qs_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js?a=b')"


def test_set_qs_bustcode():
    busted = ob.set_qs_bustcode(p_ref, "abcdef")
    assert busted == "url('/static/app.js?_cb_=abcdef')"
    busted = ob.set_qs_bustcode(fn_ref, "abcdef")
    assert busted == "url('/static/app.js?_cb_=abcdef&foo=12&bar=34')"
    busted = ob.set_qs_bustcode(qs_ref, "abcdef")
    assert busted == "url('/static/app.js?_cb_=abcdef&a=b')"


def test_replace_bustcode():
    busted = ob.replace_bustcode(fn_ref, "abcdef")
    assert busted == "url('/static/app_cb_abcdef.js?foo=12&bar=34')"
    busted = ob.replace_bustcode(qs_ref, "abcdef")
    assert busted == "url('/static/app.js?_cb_=abcdef&a=b')"


def test_rewrite_ref():
    # "codepath, lineno, ref_type, fullref, refpath, bustcode"
    # print(ob.rewrite_ref(p_ref, "abcdef", ob.QS_REF))
    ob.rewrite_ref(qs_ref, "abcdef", ob.QS_REF)
    ob.rewrite_ref(fn_ref, "abcdef", ob.FN_REF)


def test_parse_rootdir():
    assert ob.parse_project_path(["."]) == "."
    assert ob.parse_project_path([".."]) == ".."
    assert ob.parse_project_path(["../omnibust"]) == "../omnibust"
    try:
        ob.parse_project_path(["foo/bar"])
        assert False, "should have raised path error"
    except ob.PathError:
        pass


def test_strip_comments():
    stripped = ob.strip_comments("""
        http://foo.com/bar    // a comment
    """).strip()
    assert stripped == "http://foo.com/bar"
    stripped = ob.strip_comments("""
        foo bar baz    // a comment
    """).strip()
    assert stripped == "foo bar baz"



def test_get_flag():
    args = ["--foo",  "--bar", "--baz"]
    assert ob.get_flag(args, '--foo')
    assert not ob.get_flag(args, '--test')
    assert not ob.get_flag([], '--foo')


def test_get_opt():
    assert ob.get_opt(["--baz", "--foo=bar"], '--foo') == "bar"
    assert ob.get_opt(["--baz", "--foo", "bar"], '--foo') == "bar"
    try:
        ob.get_opt(["--baz", "--foo=bar"], '--baz')
        assert False, "expected KeyError"
    except KeyError:
        pass


if __name__ == '__main__':
    for k, v in locals().items():
        if k.startswith('test_'):
            try:
                v()
            except:
                pass
