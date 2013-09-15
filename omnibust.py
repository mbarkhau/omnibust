#!/usr/bin/env python
"""Omnibust v0.1.0 - A universal cachebusting script

Omnibust will scan your project files for static resources files
(js, css, png) and also for urls which reference these resources in your
sourcecode (html, js, css, py, rb, etc.). It will rewrite any urls to
successfully matched static resource with a cachebust parameter.

First steps:

    omnibust init                       # scan and write omnibust.cfg
    omnibust status                     # view updated urls
    omnibust rewrite                    # add or update cachebust parameters

Usage:
    omnibust (--help|--version)
    omnibust init (--filename | --querystring)
    omnibust status [--no-init] [--filename | --querystring]
    omnibust rewrite [--no-init] [--filename | --querystring]

Options:
    -h --help           Display this message
    -v --verbose        Verbose output
    -q --quiet          No output
    --version           Display version number

    -n --no-init        Use default configuration to scan for and update
                            existing '_cb_' cachebust parameters (may be slow).
    --querystring       Rewrites all references so the querystring contains a
                            cachebust parameter.
    --filename          Rewrites all references so the filename contains a
                            cachebust parameter rather than the querystring.
"""
from __future__ import print_function
import base64
import codecs
import collections
import fnmatch
import hashlib
import json
import os
import re
import struct
import sys
import zlib


PY2 = sys.version_info[0] == 2

if PY2:
    from itertools import imap as map
    range = xrange
else:
    unicode = str


class BaseError(Exception):
    pass


class PathError(BaseError):
    def __init__(self, message, path):
        self.path = path
        self.message = message


Ref = collections.namedtuple('Ref', (
    "code_dir", "code_fn", "lineno", "full_ref", "path", "bustcode", "type"
))


# util functions


def get_version():
    return tuple(map(int, __doc__[10:16].split(".")))


__version__ = ".".join(map(unicode, get_version()))


def ref_codepath(ref):
    return os.path.join(ref.code_dir, ref.code_fn)


def ext(path):
    return os.path.splitext(path)[1]


def extension_globs(filenames):
    return list(set("*" + os.path.splitext(fn)[1] for fn in filenames))


def flatten(lists):
    res = []
    for sublist in lists:
        res.extend(sublist)
    return res


def b32enc(val):
    if isinstance(val, float):
        val = struct.pack("<d", val)
    if isinstance(val, int):
        val = struct.pack("<q", val)
    if isinstance(val, unicode):
        val = val.encode('utf-8')
    
    b32val = base64.b32encode(val)
    return b32val.decode('ascii').replace("=", "").lower()


def digest_data(data, digester_name='sha1'):
    if isinstance(data, unicode):
        data = data.encode('utf-8')

    if hasattr(hashlib, digester_name):
        hashval = hashlib.new(digester_name, data).digest()
    else:
        hashval = zlib.crc32(data)
    return b32enc(hashval)


def filestat(filepath):
    # digesting ensures any change in the file modification
    # time is reflected in all/most of the returned bytes
    return digest_data(unicode(os.path.getmtime(filepath)))


def mk_buster(digest_func, digest_len=3, stat_len=3):
    _cache = {}

    def _buster(filepath):
        if stat_len == 0:
            stat = ""
        else:
            stat = filestat(filepath)
            stat = stat[:stat_len]

        old_bust = _cache.get(filepath, "")
        if stat and old_bust.endswith(stat):
            return old_bust

        if digest_len == 0:
            digest = ""
        else:
            with open(filepath, 'rb') as f:
                digest = digest_data(f.read(), digest_func)
                digest = digest[:digest_len]

        bust = digest + stat
        _cache[filepath] = bust
        return bust

    def _bust_paths(paths):
        busts = (_buster(p) for p in paths)
    
        full_bust = ""
    
        for bust in busts:
            full_bust += bust
    
        if len(paths) == 1:
            return full_bust
    
        bust_len = len(full_bust) // len(paths) 
    
        return digest_data(full_bust)[:bust_len]

    return _bust_paths


def digest_paths(filepaths, digest_func):
    digests = (digest_func(path) for path in filepaths)
    return digest_data(b"".join(digests))


# file system/path traversal and filtering

def glob_matcher(arg):
    if hasattr(arg, '__call__'):
        return arg

    def _matcher(glob):
        return lambda p: fnmatch.fnmatch(p, glob)

    # arg is a sequence of glob strings
    if isinstance(arg, (tuple, list)):
        matchers = list(map(_matcher, arg))
        return lambda p: any((m(p) for m in matchers))

    # arg is a single glob string
    if isinstance(arg, (unicode, bytes)):
        return _matcher(arg)

    return arg

# ref -> path matching

def filter_longest(_filter, iterator):
    length = 0
    longest = tuple()

    for elem in iterator:
        for i in range(len(elem)):
            if not _filter(i, elem):
                i -= 1
                break
        if i + 1 > length:
            length = i + 1
            longest = elem

    return length, longest


def mk_fn_dir_map(filepaths):
    res = collections.defaultdict(set)
    for p in filepaths:
        dirname, filename = os.path.split(p)
        res[filename].add(dirname)
    return res


def closest_matching_path(code_dirpath, refdir, dirpaths):
    """Find the closest static directory associated with a reference"""
    if len(dirpaths) == 1:
        return next(iter(dirpaths))

    if refdir.endswith("/"):
        refdir = refdir[:-1]

    refdir = tuple(filter(bool, refdir.split(os.sep)))
    code_dirpath = code_dirpath.split(os.sep)
    split_dirpaths = [p.split(os.sep) for p in dirpaths]

    def suffix_matcher(i, elem):
        return i < len(refdir) and refdir[-1 - i] == elem[-1 - i]

    def prefix_matcher(i, elem):
        return i < len(code_dirpath) and code_dirpath[i] == elem[i]

    length, longest = filter_longest(suffix_matcher, split_dirpaths)
    suffix = longest[-length:]

    if len(suffix) == 0:
        suffix_paths = split_dirpaths
    else:
        suffix_paths = [p for p in split_dirpaths if p[-len(suffix):] == suffix]
    
    if len(suffix_paths) > 1:
        length, longest = filter_longest(prefix_matcher, suffix_paths)
    else:
        longest = suffix_paths[0]
    return os.sep.join(longest)


def find_static_filepath(base_dir, ref_path, static_fn_dirs):
    dirname, filename = os.path.split(ref_path)
    if filename not in static_fn_dirs:
        # at least the filename must match
        return

    static_dir = closest_matching_path(base_dir, dirname,
                                       static_fn_dirs[filename])
    return os.path.join(static_dir, filename)


def find_static_filepaths(base_dir, ref_paths, static_fn_dirs):
    for path in ref_paths:
        static_filepath = find_static_filepath(base_dir, path, static_fn_dirs)
        if static_filepath:
            yield static_filepath


def expand_path(path, multibust):
    allpaths = set([path])
    for search, replacements in multibust.items():
        if search in path:
            allpaths.update((path.replace(search, r) for r in replacements))

    return allpaths


def ref_paths(ref, multibust):
    if not multibust:
        yield ref.path
        return

    for expanded_path in expand_path(ref.path, multibust):
        yield expanded_path
    

# url/src/href reference parsing and rewriting

PLAIN_REF = 1
PLAIN_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']|src=[\"\'])"
    "(?P<path>"
    "(?P<dir>[^\"\'\)\s\?]+\/)?"
    "[^\/\"\'\)\s\?]+)"
    "[\?=&\w]*[\"\'\)]*"
)

FN_REF = 2
FN_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']?|src=[\"\']?)?"
    "(?P<prefix>[^\"\']+?)"
    "_cb_(?P<bust>[a-zA-Z0-9]{0,16})"
    "(?P<ext>\.\w+)"
    "[\?=&\w]*[\"\'\)]*"
)

QS_REF = 3
QS_REF_RE = re.compile(
    r"(url\([\"\']?|href=[\"\']?|src=[\"\']?)?"
    "(?P<ref>[^\"\']+?)"
    "\?(.+?&)?_cb_"
    "(=(?P<bust>[a-zA-Z0-9]{0,16}))?"
    "[\?=&\w]*[\"\'\)]*"
)


def mk_plainref(ref):
    assert ref.type in (PLAIN_REF, FN_REF, QS_REF)

    if ref.type == PLAIN_REF:
        return ref.full_ref
    if ref.type == FN_REF:
        return ref.full_ref.replace("_cb_" + ref.bustcode, "")
    if ref.type == QS_REF:
        return (ref.full_ref
                .replace("?_cb_=" + ref.bustcode, "?")
                .replace("&_cb_=" + ref.bustcode, "")
                .replace("?&", "?"))


def set_fn_bustcode(ref, new_bustcode):
    rdir, rfn = os.path.split(ref.path)
    basename, ext = os.path.splitext(rfn)
    fnref = rdir + "/" + basename + "_cb_" + new_bustcode + ext
    return mk_plainref(ref).replace(ref.path, fnref)


def set_qs_bustcode(ref, new_bustcode):
    new_refpath = ref.path + "?_cb_=" + new_bustcode
    new_ref = mk_plainref(ref).replace(ref.path, new_refpath)
    if new_refpath + "?" in new_ref:
        new_ref = new_ref.replace(new_refpath + "?", new_refpath + "&")
    return new_ref


def replace_bustcode(ref, new_bustcode):
    if ref.type == FN_REF:
        prefix = "_cb_"
    if ref.type == QS_REF:
        prefix = "_cb_="
    return ref.full_ref.replace(prefix + ref.bustcode, prefix + new_bustcode)


def updated_fullref(ref, new_bustcode, target_reftype=None):
    if target_reftype is None:
        target_reftype = ref.type

    assert target_reftype in (PLAIN_REF, FN_REF, QS_REF)
    if ref.bustcode == new_bustcode and ref.type == target_reftype:
        return

    if ref.type == target_reftype:
        return replace_bustcode(ref, new_bustcode)

    if target_reftype == PLAIN_REF:
        return ref.fullref
    if target_reftype == FN_REF:
        return set_fn_bustcode(ref, new_bustcode)
    if target_reftype == QS_REF:
        return set_qs_bustcode(ref, new_bustcode)


# codefile parsing

def plainref_line_parser(line):
    for match in PLAIN_REF_RE.finditer(line):
        full_ref = match.group()
        if "_cb_" in full_ref:
            continue

        ref_path = match.group('path')

        yield full_ref, ref_path, "", PLAIN_REF


def markedref_line_parser(line):
    if "_cb_" not in line:
        return

    for match in FN_REF_RE.finditer(line):
        full_ref = match.group()
        ref_path = match.group('prefix') + match.group('ext')
        bust = match.group('bust')
        yield full_ref, ref_path, bust, FN_REF

    for match in QS_REF_RE.finditer(line):
        full_ref = match.group()
        ref_path = match.group('ref')
        bust = match.group('bust')
        yield full_ref, ref_path, bust, QS_REF


def parse_refs(line_parser, content):
    for lineno, line in enumerate(content.splitlines()):
        for match in line_parser(line):
            fullref = match[0]
            if "data:image/" in fullref:
                continue
            yield Ref("", "", lineno + 1, *match)


def parse_content_refs(content, parse_plain=True):
    all_refs = []
    if parse_plain:
        all_refs.extend(parse_refs(plainref_line_parser, content))

    if "_cb_" in content:
        all_refs.extend(parse_refs(markedref_line_parser, content))
    
    seen = {}
    for ref in all_refs:
        key = (ref.lineno, ref.full_ref)
        if key not in seen or seen[key].type < ref.type:
            seen[key] = ref
    return sorted(seen.values(), key=lambda r: r.lineno)


def iter_refs(codefile_paths, parse_plain=True, encoding='utf-8'):
    for codefile_path in codefile_paths:
        code_dir, code_fn = os.path.split(codefile_path)
        try:
            with codecs.open(codefile_path, 'r', encoding) as fp:
                content = fp.read()
        except:
            print("omnibust: error reading '%s'" % codefile_path)
            continue
        
        for ref in parse_content_refs(content, parse_plain):
            yield ref._replace(code_dir=code_dir, code_fn=code_fn)


# project dir scanning


def iter_filepaths(rootdir, file_filter=None, file_exclude=None,
                   dir_filter=None, dir_exclude=None):
    file_filter = glob_matcher(file_filter)
    file_exclude = glob_matcher(file_exclude)
    dir_filter = glob_matcher(dir_filter)
    dir_exclude = glob_matcher(dir_exclude)

    for root, _, files in os.walk(rootdir):
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


def init_project_paths():
    # scan project for files we're interested in
    filepaths = list(iter_filepaths(".", dir_exclude=INIT_EXCLUDE_GLOBS))
    static_filepaths = [p for p in filepaths if ext(p) in STATIC_FILETYPES]
    codefile_paths = [p for p in filepaths if ext(p) in CODE_FILETYPES]
    return codefile_paths, static_filepaths


def cfg_project_paths(cfg):
    code_filepaths = multi_iter_filepaths(cfg['code_dirs'],
                                          cfg['code_fileglobs'],
                                          cfg['ignore_dirglobs'])
    static_filepaths = multi_iter_filepaths(cfg['static_dirs'],
                                            cfg['static_fileglobs'],
                                            cfg['ignore_dirglobs'])
    return code_filepaths, static_filepaths


# def resolve_refpath(codepath, path, static_paths):
#     """Find the best matching path for an url"""
#     longest_spath = ""
#     longest_path = None
# 
#     subpaths = ref.split("/")
#     for path in static_paths:
#         if not path.endswith(subpaths[-1]):
#             continue
# 
#         for i in range(1, len(subpaths) + 1):
#             spath = os.path.sep.join(subpaths[-i:])
#             if spath in path:
#                 if len(spath) > len(longest_spath):
#                     longest_spath = spath
#                     longest_path = path
#             else:
#                 break
# 
#     return longest_path
# 
# 
# def resolve_references(refs, paths):
#     for ref in refs:
#         ref = ref.replace("/", os.sep)
#         # path = resolve_filepath(ref, paths)
#         # if path:
#         #     yield path
# 
# 
# def resolve_reference_paths(cfg, ref, paths):
#     refs = expand_ref(ref, cfg['multibust'])
#     return resolve_references(refs)

# def update_ref(content, full_ref, ref, old_bust, new_bust,
#                old_reftype, new_reftype):
#     if old_reftype == new_reftype:
#         new_full_ref = full_ref.replace(old_bust, new_bust)
#     else:
#         # TODO: extend regular expression to capture all query parameters
#         #       parse query params from full_ref
#         #       reconstruct new query params
#         raise NotImplemented("changing ref types")
#     return content.replace(full_ref, new_full_ref)

# def update_references(args, cfg, filepath, static_paths):
#     arg_verbose = '-v' in args or '--verbose' in args
#     arg_quiet = '-q' in args or '--quiet' in args
#     arg_force = '-f' in args or '--force' in args

#     force_fn = '--filename' in args
#     force_qs = '--queryparam' in args

#     tgt_reftype = None
#     if force_fn and not force_qs:
#         tgt_reftype = FN_REF
#     if force_qs and not force_fn:
#         tgt_reftype = QS_REF

#     hash_fun = cfg['hash_function']
#     hash_length = int(cfg['hash_length'])
#     stat_len = min(4, hash_length // 2)
#     hash_len = hash_length - stat_len

#     file_enc = cfg['file_encoding']

#     with codecs.open(filepath, 'r', encoding=file_enc) as f:
#         orig_content = f.read()

#     content = orig_content

#     references = parse_marked_refs(orig_content)
#     for lineno, full_ref, fn_ref, old_bust, old_reftype in references:
#         if arg_verbose:
#             fmtstr = '{1}, line {2:<4}: {0}'
#             print(fmtstr.format(full_ref, filepath, lineno))

#         new_reftype = tgt_reftype or old_reftype
#         paths = tuple(resolve_reference_paths(cfg, fn_ref, static_paths))

#         if len(paths) == 0:
#             if not arg_quiet:
#                 print(u"missing! : " + full_ref)
#             continue

#         needs_change = old_reftype != new_reftype or arg_force

#         new_stat = digest_paths(paths, filestat)[:stat_len]

#         if not needs_change and old_bust.startswith(new_stat):
#             if arg_verbose:
#                 print(u"unchanged: " + full_ref)
#             continue

#         new_hash = digest_paths(paths, mk_buster(hash_fun))[:hash_len]

#         if not needs_change and old_bust.endswith(new_hash):
#             continue

#         new_bust = new_stat + new_hash

#         if not arg_quiet:
#             print(u"busted   : {0} -> {1}".format(full_ref, new_bust))

#         content = update_ref(content, full_ref, fn_ref, old_bust, new_bust,
#                              old_reftype, new_reftype)

#     if content == orig_content:
#         return

#     if arg_verbose:
#         print(u"rewriting:", filepath)

#     with codecs.open(filepath, 'w', encoding=file_enc) as f:
#         f.write(content)


def ref_printer(refs):
    prev_codepath = None
    for ref, paths, new_full_ref  in refs:
        codepath = os.path.join(ref.code_dir, ref.code_fn)
        if codepath != prev_codepath:
            print(codepath)
            prev_codepath = codepath
        
        lineno = "% 5d" % ref.lineno
        print(" %s %s" % (lineno, ref.full_ref))
        print("    ->", new_full_ref)
        yield ref, paths, new_full_ref
    
    if prev_codepath is None:
        print("omnibust: nothing to cachebust")


def busted_refs(ref_map, cfg, target_reftype):
    buster = mk_buster(cfg['hash_function'], cfg['digest_length'],
                       cfg['stat_length'])

    for ref, paths in ref_map.items():
        new_bustcode = buster(paths)
        if ref.bustcode == new_bustcode:
            continue
        print(ref.type, ref.bustcode, new_bustcode)
        new_fullref = updated_fullref(ref, new_bustcode, target_reftype)
        yield ref, paths, new_fullref


def rewrite_content(ref, new_full_ref):
    with open(ref_codepath(ref), 'r') as f:
        content = f.read()

    with open(ref_codepath(ref), 'w') as f:
        f.write(content.replace(ref.full_ref, new_full_ref))


def scan_project(codefile_paths, static_filepaths, multibust=None,
                 parse_plain=True, encoding='utf-8'):
    refs = collections.OrderedDict()

    # init mapping to check if a ref has a static file
    static_fn_dirs = mk_fn_dir_map(static_filepaths)

    for ref in iter_refs(codefile_paths, parse_plain, encoding=encoding):
        paths = ref_paths(ref, multibust) if multibust else [ref.path] 
        reffed_filepaths = list(find_static_filepaths(ref.code_dir, paths,
                                                      static_fn_dirs))
        if reffed_filepaths:
            refs[ref] = reffed_filepaths

    return refs


def init_project(args):
    if os.path.exists(".omnibust"):
        raise PathError(u"config already exists", ".omnibust")

    ref_map = scan_project(*init_project_paths())

    static_dirs = set(os.path.split(p)[0] for p in flatten(ref_map.values()))
    code_dirs = set(r.code_dir for r in ref_map)
    static_extensions = extension_globs(flatten(ref_map.values()))
    code_extensions = extension_globs((r.code_fn for r in ref_map))
    
    with codecs.open(".omnibust", 'w', 'utf-8') as f:
        f.write(INIT_CFG % (
            dumpslist(list(static_dirs)),
            dumpslist(static_extensions),
            dumpslist(list(code_dirs)),
            dumpslist(code_extensions)
        ))

    print(u"omnibust: wrote {0}".format(".omnibust"))


def status(args, cfg):
    target_reftype = get_target_reftype(args)

    ref_map = scan_project(*cfg_project_paths(cfg), multibust=cfg['multibust'],
                           parse_plain=target_reftype is not None,
                           encoding=cfg['file_encoding'])

    list(ref_printer(busted_refs(ref_map, cfg, target_reftype)))


def rewrite(args, cfg):
    target_reftype = get_target_reftype(args)
    ref_map = scan_project(*cfg_project_paths(cfg), multibust=cfg['multibust'],
                           parse_plain=target_reftype is not None,
                           encoding=cfg['file_encoding'])

    refs = ref_printer(busted_refs(ref_map, cfg, target_reftype))
    for ref, _, new_full_ref in refs:
        rewrite_content(ref, new_full_ref)


# configuration

def read_cfg(args):
    cfg = json.loads(strip_comments(DEFAULT_CFG))

    if not get_flag(args, '--no-init') and not os.path.exists(".omnibust"):
        raise PathError(u"try 'omnibust init'", ".omnibust")
        return None

    if not get_flag(args, '--no-init'):
        try:
            with codecs.open(".omnibust", 'r', encoding='utf-8') as f:
                cfg.update(json.loads(strip_comments(f.read())))
        except (ValueError, IOError) as e:
            raise BaseError(u"Error parsing '%s', %s" % (".omnibust", e))
    
    if 'stat_length' not in cfg:
        cfg['stat_length'] = cfg['bust_length'] // 2
    if 'digest_length' not in cfg:
        cfg['digest_length'] = cfg['bust_length'] - cfg['stat_length']

    return cfg


def dumpslist(l):
    return json.dumps(l, indent=8).replace("]", "    ]")


def strip_comments(data):
    return re.sub("(^|\s)//.*", "", data)


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

DEFAULT_CFG = r"""
{
    "static_dirs": ["."],

    "static_fileglobs": %s,

    "code_dirs": ["."],

    "code_fileglobs": %s,

    "ignore_dirglobs": ["*.git/*", "*.hg/*", "*.svn/*", "*lib/*", "*lib64/*"],

    "multibust": {},

    // TODO: use file encoding parameter
    "file_encoding": "utf-8",
    "hash_function": "sha1",
    "bust_length": 6
}
""" % (
   dumpslist(["*" + ft for ft in STATIC_FILETYPES]),
   dumpslist(["*" + ft for ft in CODE_FILETYPES])
)

INIT_CFG = r"""{
    // paths are relative to the project directory
    "static_dirs": %s,

    "static_fileglobs": %s,

    "code_dirs": %s,

    "code_fileglobs": %s,

    "ignore_dirglobs": ["*.git/*", "*.hg/*", "*.svn/*", "*lib/*", "*lib64/*"]

    // "file_encoding": "utf-8",     // for reading codefiles
    // "hash_function": "sha1",      // sha1, sha256, sha512, crc32
    // "bust_length": 6

    // Cachebust references which contain a multibust marker are
    // expanded using each of the replacements. The cachebust hash will
    // be unique for the combination of all static resources. Example:
    //
    //     <img src="/static/i18n_img_{{ lang }}.png?_cb_=1234567">
    //
    // If either of /static/i18n_img_en.png or /static/i18n_img_de.png
    // are changed, then the cachebust varible will be refreshed.

    // "multibust": {
    //    "{{ lang }}": ["en", "de"]  // marker: replacements
    // },
}
"""


# option parsing

VALID_ARGS = set([
    "-h", "--help",
    "-q", "--quiet",
    "--version",
    "--no-init",
    "--filename",
    "--querystring",
])


def valid_args(args):
    if len(args) == 0:
        return False

    args = iter(args)
    cmd = next(args)
    if cmd not in ("init", "status", "rewrite"):
        print("omnibust: invalid command '%s'" % cmd)
        return False

    if '--filename' in args and '--querystring' in args:
        print("omnibust: invalid invocation, "
              "only one of '--filename' and '--querystring' is permitted")
        return False

    for arg in args:
        if arg in VALID_ARGS:
            continue

        print("omnibust: invalid argument '%s' " % arg)
        return False

    return True


def get_flag(args, flag):
    return flag in args or flag[1:3] in args


def get_command(args):
    return args[0]


def get_target_reftype(args):
    if get_flag(args, '--filename'):
        return FN_REF
    if get_flag(args, '--querystring'):
        return QS_REF
    return None


def get_opt(args, opt, default='__sentinel__'):
    for i, arg in enumerate(args):
        if not arg.startswith(opt):
            continue

        if "=" in arg:
            return arg.split("=")[1]

        if i + 1 < len(args):
            arg = args[i + 1]
            if not arg.startswith("--"):
                return args[i + 1]

        raise KeyError(opt)

    if default is not '__sentinel__':
        return default

    raise KeyError(opt)


# top level program


def dispatch(args):
    if get_command(args) == 'init':
        return init_project(args)

    cfg = read_cfg(args)

    if get_command(args) == 'status':
        return status(args, cfg)

    if get_command(args) == 'rewrite':
        return rewrite(args, cfg)

    print("omnibust: valid commands (init|status|rewrite)")
    return 1


def main(args=sys.argv[1:]):
    """Print help/version info if requested, otherwise do the do run run. """
    if not valid_args(args):
        usage = __doc__.split("Options:")[0].strip().split("Usage:")[1]
        print("\nUsage:" + usage)
        return

    if u"--version" in args:
        print(__doc__.split(" -")[0])
        return

    if get_flag(args, u"--help"):
        print(__doc__)
        return

    try:
        return dispatch(args)
    except PathError as e:
        print(u"omnibust: path error '%s': %s" % (e.path, e.message))
        return 1
    except BaseError as e:
        print(u"omnibust: " + e.message)
        return 1
    except Exception as e:
        print(u"omnibust: " + unicode(e))
        raise


if __name__ == '__main__':
    sys.exit(main())
