from __future__ import print_function

import os
import time
import tempfile
import omnibust


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


def test_b32enc():
    assert len(omnibust.b32enc(1)) == 7
    assert len(omnibust.b32enc(1.1)) == 13
    assert len(omnibust.b32enc(123456)) == 7
    assert omnibust.b32enc(123456) == b"idracaa"
    assert isinstance(omnibust.b32enc(b"test"), bytes)
    assert omnibust.b32enc(b"test") == b"orsxg5a"


def test_filestat():
    assert len(omnibust.filestat(__file__)) == 13
    fp, path = tempfile.mkstemp()
    os.system("touch " + path)

    assert omnibust.filestat(path) == omnibust.filestat(path)
    stat = omnibust.filestat(path)
    time.sleep(.1)
    os.system("touch " + path)
    assert stat != omnibust.filestat(path)


def test_digest_data():
    digest = omnibust.digest_data
    assert isinstance(digest("test"), bytes)
    assert digest("test") == digest("test")
    assert digest("foo") != digest("bar")
    assert digest("test", 'sha1') == digest("test", 'sha1')
    assert digest("foo", 'sha1') != digest("bar", 'sha1')
    assert digest("test", 'sha1') != digest("test", 'md5')


def test_file_digester():
    path_a = _write_tmp_file("test")
    path_b = _write_tmp_file("test")

    crc_digester = omnibust.file_digester('crc32')
    assert crc_digester(path_a) == crc_digester(path_b)

    path_a = _write_tmp_file("foo")
    path_b = _write_tmp_file("bar")

    assert crc_digester(path_a) != crc_digester(path_b)


def test_digest_paths():
    path_a = _write_tmp_file("test")
    path_b = _write_tmp_file("test")

    digester = omnibust.file_digester('crc32')
    digest_a = omnibust.digest_paths([path_a, path_b], digester)
    digest_b = omnibust.digest_paths([path_a, path_b], digester)
    assert digest_a == digest_b
    _write_tmp_file("foo", path_b)
    digest_b = omnibust.digest_paths([path_a, path_b], digester)
    assert digest_a != digest_b


def test_glob_matcher():
    txt_matcher = omnibust.glob_matcher("*.js")
    assert txt_matcher("foo.js")
    assert txt_matcher("foo/bar.js")
    assert not txt_matcher("foo/bar.py")
    jpg_matcher = omnibust.glob_matcher(("*.jpg", "*.jpeg"))
    assert jpg_matcher("foo.jpg")
    assert jpg_matcher("foo/bar.jpeg")
    assert not jpg_matcher("foo/bar.py")


def test_iter_filepaths():
    root = _mk_test_project()
    iterfp = lambda *a, **k: list(omnibust.iter_filepaths(*a, **k))

    assert len(iterfp(root)) == 10
    assert len(iterfp(root, "*.js")) == 4
    assert iterfp(root, "*.jpg")[0].endswith("baz.jpg")
    assert len(iterfp(root, file_exclude="*.js")) == 6
    assert len(iterfp(root, dir_filter="*subdir_a")) == 4
    assert len(iterfp(root, dir_filter="*subdir_a", file_filter="*.py")) == 2


def test_multi_iter_filepaths():
    root = _mk_test_project()
    dirs = [os.path.join(root, "subdir_a"), os.path.join(root, "subdir_b")]
    assert len(list(omnibust.multi_iter_filepaths(dirs))) == 6


def test_unique_dirname_printer():
    import sys
    import cStringIO
    # just check that it's a wrapper
    printer = omnibust.unique_dirname_printer()
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
    length, longest = omnibust.filter_longest(match, elems)
    assert longest == "aabbccddeeeef"


def test_mk_fn_dir_map():
    paths = [
        "test/test.js",
        "foo/bar.js",
        "foo/baz.js",
        "bar/bar.js",
    ]
    fn_dir_map = omnibust.mk_fn_dir_map(paths)
    assert len(fn_dir_map) == 3
    assert len(fn_dir_map['test.js']) == 1
    assert len(fn_dir_map['bar.js']) == 2


def test_closest_matching_path():
    dirpaths = ["foo/static", "foo/assets", "bar/static"]
    path = omnibust.closest_matching_path("foo/a.py", "/static", dirpaths)
    assert path == "foo/static"


if __name__ == '__main__':
    for k, v in locals().items():
        if k.startswith('test_'):
            v()
