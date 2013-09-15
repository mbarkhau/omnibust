from __future__ import print_function

import os
import sys
import time
import codecs
import tempfile
import omnibust as ob

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

PY2 = sys.version_info[0] == 2

if PY2:
    from itertools import imap as map
    range = xrange
else:
    unicode = str


def _write_tmp_file(content, path=None):
    if path is None:
        _, path = tempfile.mkstemp()
    with codecs.open(path, 'wb', encoding="utf-8") as f:
        f.write(content)
    return path


def touch(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            content = f.read()
    else:
        content = ""
    with open(path, 'w') as f:
        f.write(content)


def _mk_test_project():
    root = tempfile.mkdtemp()
    subdir_a = os.path.join(root, "subdir_a")
    subdir_b = os.path.join(root, "subdir_b")
    touch(os.path.join(root, "foo.js"))
    touch(os.path.join(root, "bar.js"))
    touch(os.path.join(root, "buzz.py"))
    touch(os.path.join(root, "baz.jpg"))
    os.makedirs(subdir_a)
    touch(os.path.join(subdir_a, "a.py"))
    touch(os.path.join(subdir_a, "a.pyc"))
    touch(os.path.join(subdir_a, "b.py"))
    touch(os.path.join(subdir_a, "b.pyc"))
    os.makedirs(subdir_b)
    touch(os.path.join(subdir_b, "a.js"))
    touch(os.path.join(subdir_b, "b.js"))
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
    assert len(ob.b32enc(1)) == 13
    assert len(ob.b32enc(1.1)) == 13
    assert len(ob.b32enc(123456)) == 13
    assert ob.b32enc(123456) == "idracaaaaaaaa"
    assert isinstance(ob.b32enc(b"test"), unicode)
    assert ob.b32enc("test") == "orsxg5a"


def test_filestat():
    fp, path = tempfile.mkstemp()

    time.sleep(0.02)

    touch(path)

    assert ob.filestat(path) == ob.filestat(path)
    stat = ob.filestat(path)

    time.sleep(0.02)

    touch(path)
    assert stat != ob.filestat(path)
    assert ob.filestat(path) == ob.filestat(path)


def test_digest_data():
    digest = ob.digest_data
    assert isinstance(digest("test"), unicode)
    assert digest("test") == digest("test")
    assert digest("foo") != digest("bar")
    assert digest("test", 'sha1') == digest("test", 'sha1')
    assert digest("foo", 'sha1') != digest("bar", 'sha1')
    assert digest("test", 'sha1') != digest("test", 'md5')


def test_buster():
    path_a = _write_tmp_file("test")
    time.sleep(0.02)
    path_b = _write_tmp_file("test")

    crc_buster = ob.mk_buster('crc32', 4, 4)

    assert crc_buster([path_a])[:4] == crc_buster([path_b])[:4]
    assert crc_buster([path_a])[4:] != crc_buster([path_b])[4:]

    path_a = _write_tmp_file("foo")
    path_b = _write_tmp_file("bar")

    assert crc_buster([path_a]) != crc_buster([path_b])


def test_bust_paths():
    buster = ob.mk_buster('sha1')
    
    path_a = _write_tmp_file("foo")
    path_b = _write_tmp_file("bar")

    bustcode_1 = buster([path_a, path_b])
    bustcode_2 = buster([path_a, path_b])
    assert bustcode_1 == bustcode_2
    
    time.sleep(0.02)

    touch(path_a)
    bustcode_3 = buster([path_a, path_b])
    assert bustcode_1 != bustcode_3
    
    time.sleep(0.02)

    open(path_a, 'w').write("baz")
    bustcode_4 = buster([path_a, path_b])
    assert bustcode_3 != bustcode_4

    bustcode_5 = buster([path_a])
    bustcode_6 = buster([path_a])
    assert bustcode_5 == bustcode_6


def test_glob_matcher():
    js_matcher = ob.glob_matcher("*.js")
    assert js_matcher("foo.js")
    assert js_matcher("foo/bar.js")
    assert not js_matcher("foo/bar.py")
    jpg_matcher = ob.glob_matcher(("*.jpg", "*.jpeg"))
    assert jpg_matcher("foo.jpg")
    assert jpg_matcher("foo.jpg")
    assert jpg_matcher("foo/bar.jpeg")
    assert jpg_matcher("foo/bar.jpeg")
    assert not jpg_matcher("foo/bar.py")
    assert not jpg_matcher("foo/bar.py")


def test_filter_longest():
    elems = ["abcdefghij", "aabbccddeeffgghhii", "aabbccddeeeef"]

    match = lambda i, e: ord(e[i]) <= ord("e")
    length, longest = ob.filter_longest(match, elems)
    assert longest[:length] == "aabbccddeeee"

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
    dirpaths = set(["foo/static"])
    path = ob.closest_matching_path("bar/abc.js", "/test", dirpaths)
    assert path == "foo/static"
    dirpaths = ["foo/static", "foo/assets", "bar/static"]
    path = ob.closest_matching_path("foo/abc.js", "/static", dirpaths)
    assert path == "foo/static"
    path = ob.closest_matching_path("bar/static", "", dirpaths)
    assert path == "bar/static"


def test_find_static_filepath():
    static_fn_dirs = ob.mk_fn_dir_map([
        "foo/assets/app.js",
        "bar/static/js/app.js",
        "bar/static/lib/app.js",
    ])

    assert "bar/static/js/app.js" == ob.find_static_filepath(
        "bar", "/static/js/app.js", static_fn_dirs)

    assert "bar/static/js/app.js" == ob.find_static_filepath(
        "foo", "/static/js/app.js", static_fn_dirs)

    assert "bar/static/lib/app.js" == ob.find_static_filepath(
        "foo", "/lib/app.js", static_fn_dirs)

    assert "foo/assets/app.js" == ob.find_static_filepath(
        "foo", "/app.js", static_fn_dirs)


def test_find_static_filepaths():
    static_fn_dirs = ob.mk_fn_dir_map([
        "foo/static/img/logo_a.png",
        "foo/static/img/logo_b.png",
        "foo/static/img/logo_c.png",
    ])
    
    ref_paths = [ "logo_a.png", "logo_b.png", "logo_c.png", "logo_d.png" ]
    static_paths = set(ob.find_static_filepaths("foo", ref_paths,
                                                static_fn_dirs))
    assert len(static_paths) == 3
    assert "foo/static/img/logo_a.png" in static_paths
    assert "foo/static/img/logo_b.png" in static_paths
    assert "foo/static/img/logo_c.png" in static_paths
    

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


def test_ref_paths():
    ref = ob.Ref("foo/static", "test.html", 123,
                 "url('/static/app_${foo}.js')",
                 "/static/app_${foo}.js", "", ob.PLAIN_REF)

    static_paths = list(ob.ref_paths(ref, expansions))
    assert len(static_paths) == 3
    assert "/static/app_${foo}.js" in static_paths
    assert "/static/app_exp_a.js" in static_paths
    assert "/static/app_exp_b.js" in static_paths


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


def test_updated_fullref():
    # "codepath, lineno, reftype, fullref, refpath, bustcode"
    rewritten = ob.updated_fullref(p_ref, "abcdef", ob.QS_REF)
    assert rewritten == "url('/static/app.js?_cb_=abcdef')"
    rewritten = ob.updated_fullref(qs_ref, "abcdef", ob.QS_REF)
    assert rewritten == "url('/static/app.js?_cb_=abcdef&a=b')"
    rewritten = ob.updated_fullref(fn_ref, "abcdef", ob.FN_REF)
    assert rewritten == "url('/static/app_cb_abcdef.js?foo=12&bar=34')"
    nodir_ref = ob.Ref("static", "test.html", 123,
                       "url('logo.png?_cb_=123456&a=b')",
                       "logo.png", "123456", ob.QS_REF)
    rewritten = ob.updated_fullref(nodir_ref, "abcdef")
    assert rewritten == "url('logo.png?_cb_=abcdef&a=b')"
    rewritten = ob.updated_fullref(nodir_ref, "abcdef", ob.FN_REF)
    assert rewritten == "url('logo_cb_abcdef.png?a=b')"


def test_plainref_line_parser():
    line = '<img src="/static/img/logo.png"/>'
    _, ref_path, bust, ref_type = next(ob.plainref_line_parser(line))
    assert not bust
    assert ref_path == "/static/img/logo.png"
    assert ref_type == ob.PLAIN_REF
    
    line = '<img src="/static/img/logo_cb_1234.png"/>'
    try:
        next(ob.plainref_line_parser(line))
        assert False, "should have failed with StopIteration"
    except StopIteration:
        pass

    line = '<img src="/static/img/logo.png?_cb_=1234"/>'
    try:
        next(ob.plainref_line_parser(line))
        assert False, "should have failed with StopIteration"
    except StopIteration:
        pass


def test_markedref_line_parser():
    line = '<img src="/static/img/logo.png"/>'
    try:
        next(ob.markedref_line_parser(line))
        assert False, "should have failed with StopIteration"
    except StopIteration:
        pass
    
    line = '<img src="/static/img/logo_cb_1234.png"/>'
    _, ref_path, bust, ref_type = next(ob.markedref_line_parser(line))
    assert bust == "1234"
    assert ref_path == "/static/img/logo.png"
    assert ref_type == ob.FN_REF
    
    line = '<img src="/static/img/logo.png?_cb_=1234"/>'
    _, ref_path, bust, ref_type = next(ob.markedref_line_parser(line))
    assert bust == "1234"
    assert ref_path == "/static/img/logo.png"
    assert ref_type == ob.QS_REF


def test_parse_content_refs():
    assert len(ob.parse_content_refs("")) == 0

    refs = ob.parse_content_refs("""
        <img src="data:image/png;base64,iV==">
        <script src="/static/js/lib.js"></script>
        <script src="/static/js/app.js?_cb_=123"></script>
        <script src="/static/js/app.js?foo=bar&_cb_=abc"></script>
        <link href="/static/css/style_cb_xyz.css">
        "/assets/img/logo_cb_lmn.png"
    """)
    assert len(refs) == 5
    assert refs[0].type == ob.PLAIN_REF
    assert refs[1].type == ob.QS_REF
    assert refs[2].type == ob.QS_REF
    assert refs[3].type == ob.FN_REF
    assert refs[4].type == ob.FN_REF

    paths = set((r.path for r in refs))
    assert "/static/js/lib.js" in paths
    assert "/static/js/app.js" in paths
    assert "/static/css/style.css" in paths

    busts = set((r.bustcode for r in refs))
    assert "123" in busts
    assert "abc" in busts
    assert "lmn" in busts
    assert "xyz" in busts


def test_iter_refs():
    pass # TODO


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


def test_init_project_paths():
    pass # TODO


def test_cfg_project_paths():
    pass # TODO


def test_ref_print_wrapper():
    refs = [
        (ob.Ref("foo/static", "test.html", 123,
                "url('/static/app.js')",
                "/static/app.js", "", ob.PLAIN_REF),
         ("foo/static/app.js",),
         "url('/static/app.js?_cb_=test')",
        )
    ]
    orig_out = sys.stdout
    tmp_out = sys.stdout = StringIO()

    assert list(ob.ref_print_wrapper(refs)) == refs

    sys.stdout = orig_out
    lines = tmp_out.getvalue().splitlines()

    assert len(lines) == 3
    assert lines[0] == "foo/static/test.html"
    assert lines[1].endswith("url('/static/app.js')")
    assert "_cb_=test" not in lines[1]
    assert "_cb_=test" in lines[2]


def test_rewrite_content():
    pass # TODO


def test_scan_project():
    pass # TODO


def test_read_cfg():
    cfg = ob.read_cfg(['--no-init'])

    assert isinstance(cfg['static_dirs'], list)
    assert isinstance(cfg['code_dirs'], list)
    assert isinstance(cfg['static_fileglobs'], list)
    assert isinstance(cfg['code_fileglobs'], list)
    assert isinstance(cfg['bust_length'], int)
    assert isinstance(cfg['stat_length'], int)
    assert isinstance(cfg['digest_length'], int)


def test_dumplist():
    assert ob.dumpslist(["foo", "bar", "baz"]) == """[
        "foo", 
        "bar", 
        "baz"
    ]"""


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


def test_get_command():
    assert ob.get_command(["init"]) == "init"
    try:
        ob.get_command([])
        assert False, "expected BaseError because of missing command"
    except ob.BaseError:
        pass
    try:
        ob.get_command(["foo"])
        assert False, "expected BaseError because of invalid command"
    except ob.BaseError:
        pass


def test_get_target_reftype():
    assert ob.get_target_reftype(["update", "--filename"]) == ob.FN_REF
    assert ob.get_target_reftype(["update", "--querystring"]) == ob.QS_REF
    assert ob.get_target_reftype(["update"]) is None


def test_get_opt():
    assert ob.get_opt(["--baz", "--foo=bar"], '--foo') == "bar"
    assert ob.get_opt(["--baz", "--foo", "bar"], '--foo') == "bar"
    assert ob.get_opt(["baz", "--foo", "bar"], '--foo') == "bar"

    try:
        ob.get_opt(["--baz", "--foo=bar"], '--baz')
        assert False, "expected KeyError"
    except KeyError:
        pass


if __name__ == '__main__':
    # quick and dirty test harness, mainly for python3 and win compat testing
    fail = []

    for k, v in list(locals().items()):
        if k.startswith('test_'):
            try:
                v()
                print(".", end="")
            except Exception as ex:
                fail.append("Failed: %s\nReason: %s %s\n" % (k, type(ex), ex))
                print("F", end="")

            sys.stdout.flush()

    print("")
    for f in fail:
        print(f)
