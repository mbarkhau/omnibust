#!/usr/bin/env python
"""Omnibust v0.1.0 - A cachebusting script

Omnibust scans your project files for static resources, such as js,
css, png files, and urls which reference these resources in your
sourcecode (html, js, css, py, rb, etc.). It will rewrite any such
urls so they have a unique cachebust parameter, which is based on the
modification time and a checksum of the contents of the static resource
files.

Omnibust defaults to query parameter `?_cb_=0123abcd` based cachbusting,
but it can also rewrite the filenames in urls to the form
`app_cb_0123abcd.js`. See [Filename Based Cachbusting] for more info on
why you might want to use this.

First steps:

    omnibust path/to/project --init     # scan and write omnibust.cfg
    omnibust path/to/project --rewrite  # add cachebust to urls
    omnibust path/to/project            # update urls with cachebust

Usage:
    omnibust (--help|--version)
    omnibust <rootdir> [--cfg=<cfg_path>]
                [--cascade] [--no-act] [--force]
    omnibust <rootdir> --init
    omnibust <rootdir> --rewrite [--cfg=<cfg_path>]
                [--cascade] [--no-act] [--force]
                [--filename] [--querystring]

Options:
    -h --help           Display this message
    -v --verbose        Verbose output
    -q --quiet          No output
    --version           Display version number

    -i --init
    scan                View scanned directories (to find ones which
                            may be excluded and speed up the scanning process)
    --cfg=<cfg_path>    Path to configuration file
                            [default: omnibust.cfg]
    -n --no-act         Don't write to files, only display changes that would
                            have been made.
    -c --cascade        Resolve cascading changes to urls.
                            Cascades happen for example, when an html file has
                            a reference to a css file which in turn has a
                            reference to an image file. If the image is
                            modified, the reference in the css file will be
                            busted, which in turn will cause the css reference
                            in the html file to be busted.
    -f --force          Update cachebust parameters even if the modification
                            time of the file is the same as recorded in the
                            current cachebust parameter.
    --filename          Rewrites all references so the filename contains a
                            cachebust parameter rather than the querystring.
    --querystring       Rewrites all references to use a _cb_ parameter as
                            part of the querystring.
"""
from __future__ import print_function

import os
import sys
import re
import json
import struct
import codecs
import zlib
import hashlib
import base64
import fnmatch
import itertools
import collections

PY2 = sys.version < '3'

unicode = unicode if PY2 else str
str = None
range = xrange if PY2 else range


class BaseError(Exception):
    pass


class PathError(BaseError):
    def __init__(self, message, path):
        self.path = path
        self.message = message


# util functions

def get_version():
    return tuple(map(int, __doc__[10:16].split(".")))


def b32enc(val):
    if isinstance(val, float):
        val = struct.pack("<d", val)
    if isinstance(val, int):
        val = struct.pack("<i", val)
    return base64.b32encode(val).replace("=", "").lower()


def filestat(filepath):
    return b32enc(os.path.getmtime(filepath))


def digest_data(data, digester_name='crc32'):
    if digester_name in hashlib.algorithms:
        hashval = hashlib.new(digester_name, data).digest()
    else:
        hashval = zlib.crc32(data)
    return b32enc(hashval)


def file_digester(digest_func):
    def _digester(filepath):
        with open(filepath, 'rb') as f:
            return digest_data(f.read(), digest_func)
    return _digester


def digest_paths(filepaths, digest_func):
    digests = (digest_func(path) for path in filepaths)
    return digest_data("".join(digests))


# file system/path traversal and filtering


def glob_matcher(arg):
    if hasattr(arg, '__call__'):
        return arg

    def _matcher(glob):
        return lambda p: fnmatch.fnmatch(p, glob)

    # arg is a sequence of glob strings
    if isinstance(arg, (tuple, list)):
        matchers = map(_matcher, arg)
        return lambda p: any((m(p) for m in matchers))

    # arg is a single glob string
    if isinstance(arg, (unicode, bytes)):
        return _matcher(arg)

    return arg


def iter_filepaths(rootdir, file_filter=None, file_exclude=None,
                   dir_filter=None, dir_exclude=None):
    file_filter = glob_matcher(file_filter)
    file_exclude = glob_matcher(file_exclude)
    dir_filter = glob_matcher(dir_filter)
    dir_exclude = glob_matcher(dir_exclude)

    for root, subfolders, files in os.walk(rootdir):
        if dir_exclude and dir_exclude(root):
            continue

        if dir_filter and not dir_filter(root):
            continue

        for filename in files:
            path = os.path.join(root, filename)
            if file_exclude and file_exclude(path):
                continue

            if not file_filter or file_filter(path):
                yield path


def multi_iter_filepaths(rootdirs, *args, **kwargs):
    for basedir in rootdirs:
        for path in iter_filepaths(basedir, *args, **kwargs):
            yield path


def unique_dirname_printer():
    seen_dirs = set()

    def _printer(path):
        dirname = os.path.dirname(path)
        if dirname not in seen_dirs:
            print(dirname)
            seen_dirs.add(dirname)
        return path

    return _printer


# project dir scanning

def iter_project_paths(cfg, args, subdirs, file_filter, dir_exclude):
    subdirs = [os.path.join(cfg['root_dir'], subdir) for subdir in subdirs]
    paths = multi_iter_filepaths(subdirs, file_filter, dir_exclude)
    if get_flag(args, '--verbose'):
        return itertools.imap(unique_dirname_printer(), paths)
    return paths


def iter_content_paths(cfg, args):
    return iter_project_paths(cfg, args, cfg['code_dirs'],
                              cfg['code_filetypes'], cfg['ignore_dirs'])


def iter_static_paths(cfg, args):
    return iter_project_paths(cfg, args, cfg['static_dirs'],
                              cfg['static_filetypes'], cfg['ignore_dirs'])


# ref -> path matching

def filter_longest(_filter, iterator):
    length = 0
    longest = None

    for elem in iterator:
        for i in range(len(elem)):
            if not _filter(i, elem):
                break

        if i > length:
            length = i - 1
            longest = elem

    return length, longest


def mk_fn_dir_map(filepaths):
    res = collections.defaultdict(set)
    for p in filepaths:
        dirname, filename = os.path.split(p)
        res[filename].add(dirname)
    return res


def closest_matching_path(codepath, refdir, dirpaths):
    """Find the closest static directory associated with a reference"""
    if refdir.endswith("/"):
        refdir = refdir[:-1]

    def prefix_matcher(i, elem):
        return i < len(codepath) and codepath[i] == elem[i]

    def suffix_matcher(i, elem):
        return i < len(refdir) and refdir[-1 - i] == elem[-1 - i]

    length, longest = filter_longest(prefix_matcher, dirpaths)
    prefix = longest[:length]

    prefix_paths = [p for p in dirpaths if p.startswith(prefix)]

    length, longest = filter_longest(suffix_matcher, prefix_paths)
    return longest


def resolve_refs(codepath, ref, static_paths):
    pass


def resolve_ref(codepath, ref, paths):
    """Find the best matching path for an url"""
    longest_spath = ""
    longest_path = None

    subpaths = ref.split("/")
    for path in paths:
        if not path.endswith(subpaths[-1]):
            continue

        for i in range(1, len(subpaths) + 1):
            spath = os.path.sep.join(subpaths[-i:])
            if spath in path:
                if len(spath) > len(longest_spath):
                    longest_spath = spath
                    longest_path = path
            else:
                break

    return longest_path


# url/src/href reference parsing and rewriting

PLAIN_REF = 1
PLAIN_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']|src=[\"\'])"
    "(?P<path>"
    "(?P<dir>[^\"\'\)\s\?]+\/)?"
    "(?P<filename>[^\/\"\'\)\s\?]+))"
)

FN_REF = 2
FN_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']?|src=[\"\']?)?"
    "(?P<path>"
    "(?P<prefix>[^\"\'\s]+?)"
    "_cb_(?P<bust>[a-zA-Z0-9]{0,16})"
    "(?P<ext>\.\w+?))"
)

QS_REF = 3
QS_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']?|src=[\"\']?)?"
    "(?P<path>"
    "(?P<ref>[^\"\'\s]+?)"
    "\?(.+?&)?_cb_"
    "(=(?P<bust>[a-zA-Z0-9]{0,16}))?)"
)


Ref = collections.namedtuple(
    'Ref', "codepath, lineno, ref_type, fullref, refpath, bustcode"
)


def mk_plainref(ref):
    assert ref.ref_type in (PLAIN_REF, FN_REF, QS_REF)

    if ref.ref_type == PLAIN_REF:
        return ref.fullref
    if ref.ref_type == FN_REF:
        return ref.fullref.replace("_cb_" + ref.bustcode, "")
    if ref.ref_type == QS_REF:
        return (ref.fullref
                .replace("?_cb_=" + ref.bustcode, "?")
                .replace("&_cb_=" + ref.bustcode, "")
                .replace("?&", "?"))


def add_fn_bustcode(ref, new_bustcode):
    rdir, rfn = os.path.split(ref.refpath)
    basename, ext = os.path.splitext(rfn)
    plainref = mk_plainref(ref)
    fnref = rdir + "/" + basename + "_cb_" + new_bustcode + ext
    return plainref.replace(ref.refpath, fnref)


def add_qs_bustcode(ref, new_bustcode):
    # if "?" in plainref:
        # return plainref
    pass


def replace_bustcode(ref, new_bustcode):
    if ref.ref_type == FN_REF:
        prefix = "_cb_"
    if ref.ref_type == QS_REF:
        prefix = "_cb_="
    return ref.fullref.replace(prefix + ref.bustcode, prefix + new_bustcode)


def rewrite_ref(ref, new_bustcode, new_ref_type=None):
    if new_ref_type is None:
        new_ref_type = ref.ref_type
    assert new_ref_type in (PLAIN_REF, FN_REF, QS_REF)

    if ref.ref_type == new_ref_type:
        return replace_bustcode(ref, new_bustcode)

    if new_ref_type == PLAIN_REF:
        return ref.fullref
    if new_ref_type == FN_REF:
        return add_fn_bustcode(ref, new_bustcode)
    if new_ref_type == QS_REF:
        return add_qs_bustcode(ref, new_bustcode)


def mk_plain_line_parser(codefile_path, static_fn_dirs):
    def _parser(line):
        for match in PLAIN_REF_RE.finditer(line):
            fn = match.group('filename')
            refpath = match.group('path')
            refdir = match.group('dir') or ""

            # at least the filename must match
            if fn not in static_fn_dirs:
                continue

            static_dir = closest_matching_path(codefile_path, refdir,
                                               static_fn_dirs[fn])
            yield refpath, refdir, static_dir, fn, PLAIN_REF
    return _parser


def parse_marked_line(line):
    if "_cb_" not in line:
        return

    for match in FN_REF_RE.finditer(line):
        full_ref = match.group('path')
        fn_ref = match.group('prefix') + match.group('ext')
        old_bust = match.group('bust')
        yield full_ref, fn_ref, old_bust, FN_REF

    for match in QS_REF_RE.finditer(line):
        full_ref = match.group('path')
        fn_ref = match.group('ref')
        old_bust = match.group('bust')
        yield full_ref, fn_ref, old_bust, QS_REF


def parse_refs(line_parser, content):
    for lineno, line in enumerate(content.splitlines()):
        lineno += 1
        for match in line_parser(line):
            yield lineno + match


def parse_plain_refs(content, codefile_path, static_fn_dirs):
    line_parser = mk_plain_line_parser(codefile_path, static_fn_dirs)
    return parse_refs(line_parser, content)


def parse_marked_refs(content):
    if "_cb_" in content:
        return parse_refs(parse_marked_line, content)


def expand_reference(ref, expansions):
    allrefs = set([ref])
    for search, replacements in expansions.items():
        if search in ref:
            allrefs.update((ref.replace(search, r) for r in replacements))

    return allrefs


def resolve_references(refs, paths):
    for ref in refs:
        ref = ref.replace("/", os.sep)
        # path = resolve_filepath(ref, paths)
        # if path:
        #     yield path


def resolve_reference_paths(cfg, ref, paths):
    refs = expand_reference(ref, cfg['multibust'])
    return resolve_references(refs)


def update_ref(content, full_ref, ref, old_bust, new_bust,
               old_ref_type, new_ref_type):
    if old_ref_type == new_ref_type:
        new_full_ref = full_ref.replace(old_bust, new_bust)
    else:
        # TODO: extend regular expression to capture all query parameters
        #       parse query params from full_ref
        #       reconstruct new query params
        raise NotImplemented("changing ref types")
    return content.replace(full_ref, new_full_ref)


def update_references(cfg, args, filepath, static_paths):
    arg_verbose = '-v' in args or '--verbose' in args
    arg_quiet = '-q' in args or '--quiet' in args
    arg_force = '-f' in args or '--force' in args

    force_fn = '--filename' in args
    force_qs = '--querystring' in args

    tgt_ref_type = None
    if force_fn and not force_qs:
        tgt_ref_type = FN_REF
    if force_qs and not force_fn:
        tgt_ref_type = QS_REF

    hash_fun = cfg['hash_function']
    hash_length = int(cfg['hash_length'])
    stat_len = min(4, hash_length // 2)
    hash_len = hash_length - stat_len

    file_enc = cfg['file_encoding']

    with codecs.open(filepath, 'r', encoding=file_enc) as f:
        orig_content = f.read()

    content = orig_content

    references = parse_marked_refs(orig_content)
    for lineno, full_ref, fn_ref, old_bust, old_ref_type in references:
        if arg_verbose:
            fmtstr = '{1}, line {2:<4}: {0}'
            print(fmtstr.format(full_ref, filepath, lineno))

        new_ref_type = tgt_ref_type or old_ref_type
        paths = tuple(resolve_reference_paths(cfg, fn_ref, static_paths))

        if len(paths) == 0:
            if not arg_quiet:
                print("missing! : " + full_ref)
            continue

        needs_change = old_ref_type != new_ref_type or arg_force

        new_stat = digest_paths(paths, filestat)[:stat_len]

        if not needs_change and old_bust.startswith(new_stat):
            if arg_verbose:
                print("unchanged: " + full_ref)
            continue

        new_hash = digest_paths(paths, file_digester(hash_fun))[:hash_len]

        if not needs_change and old_bust.endswith(new_hash):
            continue

        new_bust = new_stat + new_hash

        if not arg_quiet:
            print("busted   : {0} -> {1}".format(full_ref, new_bust))

        content = update_ref(content, full_ref, fn_ref, old_bust, new_bust,
                             old_ref_type, new_ref_type)

    if content == orig_content:
        return

    if arg_verbose:
        print("rewriting:", filepath)

    with codecs.open(filepath, 'w', encoding=file_enc) as f:
        f.write(content)


def init_project(args):
    rootdir = parse_rootdir(args)

    # scan project for files we're interested in
    static_filepaths = []
    code_filepaths = []
    for p in iter_filepaths(rootdir, _exclude=INIT_EXCLUDE_GLOBS):
        _, ext = os.path.splitext(p)
        if ext in STATIC_FILETYPES:
            static_filepaths.append(p)
        if ext in CODE_FILETYPES:
            code_filepaths.append(p)

    # init collections for ref check
    static_fn_dirs = mk_fn_dir_map(static_filepaths)

    # find codepaths with refs
    code_dirs = collections.defaultdict(set)
    static_dirs = collections.defaultdict(set)
    for codefile_path in code_filepaths:
        code_dir, code_fn = os.path.split(codefile_path)
        try:
            with codecs.open(codefile_path, 'r', 'utf-8') as fp:
                content = fp.read()
        except:
            continue

        for pr in parse_plain_refs(content, codefile_path, static_fn_dirs):
            lineno, refpath, refdir, static_dir, static_fn = pr
            code_dirs[code_dir.replace(rootdir, "")].add(code_fn)
            static_dirs[static_dir.replace(rootdir, "")].add(static_fn)

    for dirname, filenames in code_dirs.iteritems():
        print(dirname)
        for fn in filenames:
            print("\t", fn)

    for dirname, filenames in static_dirs.iteritems():
        print(dirname)
        for fn in filenames:
            print("\t", fn)

    cfg_path = os.path.join(rootdir, "omnibust.cfg")
    with codecs.open(cfg_path, "w", 'utf-8') as f:
        f.write(INIT_CFG % (
            json.dumps(code_dirs.keys(), indent=8).replace("]", "    ]"),
            json.dumps(static_dirs.keys(), indent=8).replace("]", "    ]")
        ))

    print("omnibust: wrote {0}".format(cfg_path))


def scan_cmd(cfg, args):
    for path in parse_rootdir(args):
        print(path)
    pass


def rewrite_cmd(cfg, args):
    rootdir = parse_rootdir(args)
    print("rewrite", args, rootdir)


def update_cmd(cfg, args):
    content_paths = iter_content_paths(cfg, args)
    static_paths = list(iter_static_paths(cfg, args))

    for filepath in content_paths:
        update_references(cfg, args, filepath, static_paths)

# configuration

STATIC_FILETYPES = (
    ".png", ".gif", ".jpg", ".jpeg", ".ico", ".webp", ".svg",
    ".js", ".css", ".swf",
    ".mov", ".avi", ".mp4", ".webm", ".ogg",
    ".wav", ".mp3", "ogv", "opus"
)
CODE_FILETYPES = (
    ".htm", ".html", ".jade", ".erb", ".haml", ".txt", ".md",
    ".css", ".sass", ".less", ".scss",
    ".xml", ".json", ".yaml", ".cfg", ".ini",
    ".js", ".coffee", ".dart", ".ts",
    ".py", ".rb", ".php", ".java", ".pl", ".cs", ".lua"
)
INIT_EXCLUDE_GLOBS = (
    "*lib/*", "*lib64/*", ".git/*", ".hg/*", ".svn/*",
)

INIT_CFG = r"""
{
    // paths are relative to the project directory
    "static_dirs": %s,
    "static_filetypes": %s,

    "code_dirs": %s,
    "code_filetypes": %s

    // "ignore_dirs": ["*lib/*", "*lib64/*"],

    // "file_encoding": "utf-8",
    // "hash_function": "crc32",      // sha1, sha256, sha512
    // "hash_length": 8,

    // Cachebust references which contain a multibust marker are expanded
    // using each of the replacements. The cachebust hash will be unique
    // for the combination of all static resources. Example:
    //
    //     <img src="/static/i18n_img_{{ lang }}.png?_cb_=1234567">
    //
    // If either of /static/i18n_img_en.png or /static/i18n_img_de.png are
    // changed, then the cachebust varible will be refreshed.

    // "multibust": {
    //    "{{ lang }}": ["en", "de"]  // marker: replacements
    // },
}
"""


DEFAULT_CFG = r"""
{
    "file_encoding": "utf-8",

    "ignore_dirs": ["*lib/*", "*lib64/*", "*.git/*", "*.hg/*", "*.svn/*"],

    "multibust": {},

    "file_encoding": "utf-8",
    "hash_function": "crc32",
    "hash_length": 8
}
"""


def strip_comments(data):
    return re.sub("//.*", "", data)


def read_cfg(args):
    cfg = json.loads(strip_comments(DEFAULT_CFG))
    cfg_path = parse_cfg_path(args)

    try:
        with codecs.open(cfg_path, 'r', encoding='utf-8') as f:
            cfg.update(json.loads(strip_comments(f.read())))
    except (ValueError, IOError) as e:
        raise BaseError("Error parsing '%s', %s" % (cfg_path, e))

    return cfg


# option parsing


def parse_rootdir(args):
    if len(args) > 1:
        path = args[1]
        if os.path.exists(path):
            return path
    return "."


def get_flag(args, flag):
    return flag in args or flag[1:3] in args


def get_opt(args, opt, default='__sentinel__'):
    for i, arg in enumerate(args):
        if not arg.startswith(opt):
            continue

        if "=" in arg:
            return arg.split("=")[1]

        if i + 1 < len(args):
            return args[i + 1]

        raise KeyError(opt)

    if default is not '__sentinel__':
        return default

    raise KeyError(opt)


def parse_project_path(args):
    path = args[0]
    if not os.path.exists(path):
        raise PathError("No such directory", path)

    if not os.path.isdir(path):
        raise PathError("Not a directory", path)

    return path


def parse_cfg_path(args):
    path = parse_project_path(args)
    cfg_path = get_opt(args, '--cfg', "omnibust.cfg")

    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(path, cfg_path)

    if not os.path.exists(cfg_path):
        msg = "No such file\nDid you mean '%s --init' ?"
        raise PathError(msg % " ".join(sys.argv), cfg_path)

    return cfg_path


# top level program


def dispatch(args):
    path = parse_project_path(args)
    if get_flag(args, '--init'):
        return init_project(path)

    cfg = read_cfg(args)
    if cfg is None:
        return 1


def main(args=sys.argv[1:]):
    """Print help/version info if requested, otherwise do the do run run. """
    if not args:
        title = __doc__.splitlines()[0]
        usage = __doc__.split("Options:")[0].strip().split("Usage:")[1]
        print(title + "\n\nUsage:" + usage)
        return

    if "--version" in args:
        print(__doc__.split(" -")[0])
        return

    if get_flag(args, "--help"):
        print(__doc__)
        return

    try:
        return dispatch(args)
    except PathError as e:
        print("omnibust: invalid path '%s': %s" % (e.path, e.message))
        return 1
    except BaseError as e:
        print("omnibust: " + e.message)
        return 1
    except Exception as e:
        print("omnibust: " + str(e))
        raise e


if __name__ == '__main__':
    sys.exit(main())
