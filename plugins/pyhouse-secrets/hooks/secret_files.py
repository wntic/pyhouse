#!/usr/bin/env python3
"""PreToolUse guard: an agent never reads a file of secrets and never destroys one.

A file of secrets is one named like a dotenv file -- `.env`, `.env.<anything>`, `<anything>.env` or
`.envrc`, in any case -- except a template ending `.example`, `.sample`, `.template` or `.dist`, and
except a file under the system's temporary directory, which an agent made for itself.

Naming one is allowed: a search pattern, an exclusion, text in a document or a commit message, a field
path. So is an existence or ignore check, a check that prints no value (`grep -q`, `grep -c`, `grep -l`,
`cmp`, `wc`, a hash), appending, editing in place, loading into a process unless the same command prints
what it loaded, and a copy or move whose target is named like a file of secrets, is ignored by git and
does not exist yet.

Refused: reading the content; removing one; `>`, `truncate`, `tee`, `cp`, `mv`, `git checkout` or Write
over an existing one; `git clean`, `git worktree remove`, `rm -r`, `find -delete` and `rsync --delete`
where one would go with it; printing what was loaded (`env`, `printenv`, `echo $VAR`, `set -x`).

The mode is the plugin option `mode` (CLAUDE_PLUGIN_OPTION_MODE): `log` only records what it would refuse;
anything else, unset included, refuses. Every decision about a call that names a file of secrets is
appended to `$CLAUDE_PLUGIN_DATA/decisions.jsonl`. Standard library only; runs on Python 3.9 and later.
"""

import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
SAMPLE_NAMES = (".env", ".env.local", ".env.production", "app.env", ".envrc")
MAYBE = "\x01"  # an expansion whose value may name a file of secrets
UNKNOWN = "\x02"  # an expansion whose value is not known
GLOB_CHARS = set("*?[")
TOKEN = re.compile(r"(?i)[\w.\-/*?\[\]{}~$]*\.env(?:rc)?(?![a-z0-9])[\w.\-*?]*")
DEPENDENCY_DIRS = {".git", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".tox",
                   ".venv"}
PRUNE_DIRS = DEPENDENCY_DIRS | {"venv", ".cache", ".next", ".nuxt", ".gradle", ".turbo", "target", "dist", "build",
                                "coverage", "htmlcov"}
SCAN_LIMIT = 50000

KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "{", "}", "!", "time",
            "esac", "in", "coproc"}
WRAPPERS = {"sudo", "command", "builtin", "exec", "nohup", "nice", "stdbuf", "caffeinate", "doas"}
READERS = {
    "cat", "tac", "less", "more", "most", "head", "tail", "nl", "bat", "batcat", "view", "xxd", "od",
    "hexdump", "hd", "strings", "base64", "base32", "uuencode", "jq", "yq", "gojq", "cut", "sort", "uniq",
    "paste", "join", "comm", "column", "fold", "fmt", "pr", "rev", "expand", "unexpand", "iconv", "diff",
    "sdiff", "colordiff", "envsubst", "tr", "openssl", "gpg", "tar", "zip", "gzip", "bzip2", "xz", "zstd",
    "zcat", "nc", "ncat", "mail", "sendmail", "cpio", "pbcopy", "xclip", "xsel", "scp", "ssh", "split",
    "csplit", "look", "grepcidr", "sqlite3", "mlr", "csvlook", "tsort",
}
QUIET_READERS = {"wc", "cmp", "md5", "md5sum", "sha1sum", "sha224sum", "sha256sum", "sha384sum", "sha512sum",
                 "shasum", "b2sum", "cksum", "sum"}
GREPS = {"grep", "egrep", "fgrep", "zgrep", "rg", "ag", "ack", "ugrep"}
COPIERS = {"cp", "mv", "ln", "install", "ditto", "rsync", "gcp", "gmv"}
REMOVERS = {"rm", "unlink", "shred", "srm", "trash", "trash-put", "rmdir", "grm"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "mksh", "fish"}
INTERPRETERS = {"python", "pypy", "pypy3", "node", "nodejs", "deno", "bun", "ruby", "perl", "php", "Rscript",
                "lua", "tclsh", "osascript"}
ENV_PRINTERS = {"env", "printenv", "set", "export", "declare", "typeset", "compgen"}
WRAPPER_VALUES = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "--user", "--group", "--chdir"},
    "doas": {"-u", "-C"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
}
ENVIRONMENT_READ = re.compile(r"environ|getenv|process\.env|\bENV\[|\$ENV|Deno\.env")
RUNNERS = {"uv", "poetry", "pipenv", "pdm", "hatch", "rye"}

REASONS = {
    "read": "it would read a file of secrets, and its values would enter the conversation",
    "send": "it would send the content of a file of secrets somewhere",
    "overwrite": "it would write over an existing file of secrets and lose its values",
    "remove": "it would remove a file of secrets",
    "remove-dir": "it would remove a directory, or a git worktree, that holds a file of secrets",
    "clean": "`git clean` would remove a file of secrets git ignores",
    "copy-out": "it would copy a file of secrets to a name that is not one, where it would be read like any file",
    "copy-unignored": "it would copy a file of secrets to a path git does not ignore, where it could be committed",
    "unchecked": "it names a file of secrets through a variable, a pipe or a loop, so the target cannot be checked",
    "print-loaded": "it loads a file of secrets and prints what it loaded in the same command",
    "interp-code": "the code it passes to an interpreter names a file of secrets, and the guard cannot tell what the code does with it",
    "unparsed": "it names a file of secrets and the guard could not parse it",
}
ALLOWED = (
    "Allowed instead: name the file anywhere; `test -f`, `ls`, `git check-ignore`; a check that prints no "
    "value (`grep -q '^KEY=' FILE`, `grep -c`, `cmp -s`, `wc -l`, a hash); append with `>>`; edit a key in "
    "place with `sed -i`; load it into a process without printing it (`set -a; . FILE; set +a; CMD`, "
    "`--env-file FILE`); copy or move one with `cp -n SRC DST` to a new path named like it that git "
    "ignores, each file by its own path."
)
TAIL = (
    "Do not reword the command to get past this refusal. If the step needs what is refused, report it "
    "as not done, or hand the person the command to run themselves."
)


# --- names and paths -------------------------------------------------------------------------------

def _expand_braces(text):
    match = re.search(r"\{([^{}]*,[^{}]*)\}", text)
    if not match:
        return [text]
    out = []
    for part in match.group(1).split(","):
        out.extend(_expand_braces(text[: match.start()] + part + text[match.end():]))
    return out[:64]


def is_secret_name(name):
    """Whether a basename, possibly a glob or holding an unknown expansion, names a file of secrets."""
    for base in _expand_braces(name.strip("'\"")):
        low = base.lower()
        if MAYBE in low:
            return True
        if low.endswith(TEMPLATE_SUFFIXES):
            continue
        if GLOB_CHARS & set(low):
            if low.strip("*?.") == "":
                continue
            if any(fnmatch.fnmatchcase(sample, low) for sample in SAMPLE_NAMES):
                return True
            continue
        if low in (".env", ".envrc") or low.startswith((".env.", ".env_", ".env-")) or low.endswith(".env"):
            return True
    return False


def basename(path):
    return path.rstrip("/").rsplit("/", 1)[-1] if path.rstrip("/") else path


def has_token(text):
    """Whether text names a file of secrets anywhere, as a word or inside one.

    The pattern runs only on a window around each occurrence of the name, so a long unbroken run of
    path characters costs no more than its neighbourhood.
    """
    if not text:
        return False
    low = text.lower()
    start = 0
    while True:
        at = low.find(".env", start)
        if at < 0:
            return False
        window = text[max(0, at - 256): at + 256]
        if any(is_secret_name(basename(m.group(0))) for m in TOKEN.finditer(window)):
            return True
        start = at + 4


def _temp_roots():
    roots = {tempfile.gettempdir(), "/tmp", "/private/tmp", "/var/folders", "/private/var/folders"}
    return tuple(os.path.realpath(r).rstrip("/") + "/" for r in roots)


TEMP_ROOTS = _temp_roots()


def is_temp(path):
    real = os.path.realpath(path)
    return real.startswith(TEMP_ROOTS) or (path.rstrip("/") + "/").startswith(TEMP_ROOTS)


class Ref:
    """One operand that names a file of secrets: its absolute path, or None where it is not known."""

    def __init__(self, text, path):
        self.text = text
        self.path = path


def resolve(text, cwd):
    if MAYBE in text or UNKNOWN in text:
        return None
    text = os.path.expanduser(text)
    if os.path.isabs(text):
        return os.path.normpath(text)
    if cwd is None:
        return None
    return os.path.normpath(os.path.join(cwd, text))


def secret_refs(candidates, cwd):
    """The operands among candidates that name a file of secrets, globs expanded where they can be."""
    refs = []
    for text in candidates:
        path = resolve(text, cwd)
        if not is_secret_name(basename(text)):
            if path is not None and GLOB_CHARS & set(text):  # `dir/*`, `.??*`: what it matches decides
                refs.extend(Ref(text, p) for p in glob.glob(path)
                            if is_secret_name(basename(p)) and not os.path.isdir(p) and not is_temp(p))
            continue
        if path is not None and GLOB_CHARS & set(text):
            matches = [p for p in glob.glob(path) if is_secret_name(basename(p)) and not os.path.isdir(p)]
            refs.extend(Ref(text, p) for p in matches if not is_temp(p))
            if not matches and not is_temp(os.path.dirname(path) or "/"):
                refs.append(Ref(text, None))
            continue
        if path is not None and (is_temp(path) or os.path.isdir(path)):
            continue
        refs.append(Ref(text, path))
    return refs


def _pruned(path, names=None):
    """A directory no file of secrets is looked for in: a dependency, cache or build tree, a virtualenv."""
    return basename(path) in (PRUNE_DIRS if names is None else names) or os.path.exists(os.path.join(path, "pyvenv.cfg"))


def secrets_below(directory):
    """The files of secrets below a directory; None where the walk was cut short before finding one.

    Below the top every tree in PRUNE_DIRS is skipped; the top itself only when it is a dependency or
    cache tree, since the command names it and a build output can hold a copy of one.
    """
    if not os.path.isdir(directory) or is_temp(directory) or _pruned(directory, DEPENDENCY_DIRS):
        return []
    found = []
    seen = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not _pruned(os.path.join(root, d))]
        seen += len(files) + len(dirs)
        found.extend(os.path.join(root, f) for f in files if is_secret_name(f))
        if seen > SCAN_LIMIT:
            return found or None
    return found


def holds_secret(directory):
    """Whether a directory holds a file of secrets anywhere below it; None where it cannot be told."""
    if directory is None:
        return None
    found = secrets_below(directory)
    return None if found is None else bool(found)


def git_ignored(path):
    directory = os.path.dirname(path)
    while directory and not os.path.isdir(directory):
        directory = os.path.dirname(directory)
    try:
        done = subprocess.run(["git", "-C", directory or "/", "check-ignore", "-q", "--no-index", path],
                              capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


# --- tokenizing --------------------------------------------------------------------------------------

class Word:
    """A shell word as segments: ("lit", s), ("q", s), ("var", name, op, arg), ("sub", script)."""

    def __init__(self):
        self.parts = []

    def add(self, kind, *value):
        if kind in ("lit", "q") and self.parts and self.parts[-1][0] == kind:
            self.parts[-1] = (kind, self.parts[-1][1] + value[0])
        else:
            self.parts.append((kind,) + value)

    @property
    def literal(self):
        """The word's text when it holds no expansion, else None."""
        if all(p[0] in ("lit", "q") for p in self.parts):
            return "".join(p[1] for p in self.parts)
        return None

    @property
    def raw(self):
        out = []
        for p in self.parts:
            if p[0] in ("lit", "q"):
                out.append(p[1])
            elif p[0] == "var":
                out.append("$" + p[1])
            else:
                out.append("$(" + p[1] + ")")
        return "".join(out)

    def subs(self):
        return [p[1] for p in self.parts if p[0] == "sub"]

    def has_var(self):
        return any(p[0] in ("var", "sub") for p in self.parts)


class Redir:
    def __init__(self, op, target=None, body=None, body_quoted=False):
        self.op = op
        self.target = target
        self.body = body
        self.body_quoted = body_quoted


class Simple:
    def __init__(self):
        self.words = []
        self.redirs = []


REDIR_RE = re.compile(r"(\d*)(<<<|<<-|<<|<>|<&|>&|>>|>\||&>>|&>|<|>)")
OPS = ("&&", "||", "|&", ";;", "|", "&", ";", "(", ")")


def _match_close(src, i, open_ch="(", close_ch=")"):
    """Index just past the bracket closing the one opened before i, skipping quoted text."""
    depth = 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = src.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            i = _skip_dquote(src, i + 1)
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _skip_dquote(src, i):
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if src.startswith("$(", i):
            i = _match_close(src, i + 2)
            continue
        i += 1
    return n


def _read_dollar(src, i, word):
    """Read an expansion at src[i] == '$' into word; return the index after it."""
    n = len(src)
    if src.startswith("$((", i):
        end = _match_close(src, i + 3)
        word.add("var", "?arith", "", "")
        return min(n, end + 1)
    if src.startswith("$(", i):
        end = _match_close(src, i + 2)
        word.add("sub", src[i + 2: end - 1])
        return end
    if src.startswith("${", i):
        end = _match_close(src, i + 2, "{", "}")
        inner = src[i + 2: end - 1]
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*|\d+|[@*#?$!-])(%%|%|##|#|:-|-|:=|=|:\+|\+)?(.*)", inner, re.S)
        if m and not inner.startswith("#"):
            word.add("var", m.group(1), m.group(2) or "", m.group(3) or "")
        else:
            word.add("var", "?" + inner, "", "")
        return end
    if src.startswith("$'", i):
        j = i + 2
        buf = []
        while j < n and src[j] != "'":
            if src[j] == "\\" and j + 1 < n:
                buf.append(src[j + 1])
                j += 2
                continue
            buf.append(src[j])
            j += 1
        word.add("q", "".join(buf))
        return j + 1
    m = re.match(r"[A-Za-z_][A-Za-z0-9_]*|\d|[@*#?$!-]", src[i + 1:])
    if m:
        word.add("var", m.group(0), "", "")
        return i + 1 + len(m.group(0))
    word.add("lit", "$")
    return i + 1


def _read_word(src, i):
    word = Word()
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\n;&|<>()":
            if c in "<>" and src.startswith("(", i + 1):
                end = _match_close(src, i + 2)
                word.add("sub", src[i + 2: end - 1])
                i = end
                continue
            break
        if c == "\\":
            if src.startswith("\n", i + 1):
                i += 2
                continue
            word.add("q", src[i + 1: i + 2])
            i += 2
        elif c == "'":
            j = src.find("'", i + 1)
            j = n if j < 0 else j
            word.add("q", src[i + 1: j])
            i = j + 1
        elif c == '"':
            i = _read_dquote(src, i + 1, word)
        elif c == "`":
            j = i + 1
            while j < n and src[j] != "`":
                j += 2 if src[j] == "\\" else 1
            word.add("sub", src[i + 1: j].replace("\\`", "`"))
            i = j + 1
        elif c == "$":
            i = _read_dollar(src, i, word)
        else:
            word.add("lit", c)
            i += 1
    return word, i


def _read_dquote(src, i, word):
    n = len(src)
    if not word.parts:
        word.add("q", "")
    while i < n:
        c = src[i]
        if c == '"':
            return i + 1
        if c == "\\" and i + 1 < n:
            nxt = src[i + 1]
            word.add("q", nxt if nxt in '"\\$`\n' else "\\" + nxt)
            i += 2
        elif c == "`":
            j = i + 1
            while j < n and src[j] != "`":
                j += 2 if src[j] == "\\" else 1
            word.add("sub", src[i + 1: j])
            i = j + 1
        elif c == "$":
            i = _read_dollar(src, i, word)
        else:
            word.add("q", c)
            i += 1
    return n


def _body_subs(body):
    """Command substitutions inside an unquoted heredoc body."""
    subs = []
    i = 0
    while i < len(body):
        if body.startswith("$(", i) and not body.startswith("$((", i):
            end = _match_close(body, i + 2)
            subs.append(body[i + 2: end - 1])
            i = end
        elif body[i] == "`":
            j = body.find("`", i + 1)
            if j < 0:
                break
            subs.append(body[i + 1: j])
            i = j + 1
        else:
            i += 1
    return subs


def parse(src):
    """Split a script into pipelines of simple commands: [[Simple, ...], ...]."""
    pipelines = [[]]
    current = Simple()
    pending = []
    i = 0
    n = len(src)

    def finish(op):
        nonlocal current
        if current.words or current.redirs:
            pipelines[-1].append(current)
        current = Simple()
        if op not in ("|", "|&") and pipelines[-1]:
            pipelines.append([])
        if op in ("(", ")"):  # a subshell's bounds, so a `cd` inside it does not leak out
            pipelines[-1:] = [op, []]

    while i < n:
        c = src[i]
        if c in " \t":
            i += 1
            continue
        if c == "\\" and src.startswith("\n", i + 1):
            i += 2
            continue
        if c == "#" and (i == 0 or src[i - 1] in " \t\n;&|()"):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "\n":
            finish("\n")
            i += 1
            for redir, delim, strip in pending:
                lines = []
                while i < n:
                    j = src.find("\n", i)
                    line = src[i:] if j < 0 else src[i:j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
                    lines.append(line)
                redir.body = "\n".join(lines)
            pending = []
            continue
        m = REDIR_RE.match(src, i)
        if m and (m.group(1) == "" or True):
            op = m.group(2)
            i = m.end()
            while i < n and src[i] in " \t":
                i += 1
            if op in ("<&", ">&") and re.match(r"\d+-?|-", src[i:]):
                i += re.match(r"\d+-?|-", src[i:]).end()
                continue
            target, i = _read_word(src, i)
            if op in ("<<", "<<-"):
                redir = Redir(op, None, "", body_quoted=any(p[0] == "q" for p in target.parts))
                pending.append((redir, target.raw, op == "<<-"))
                current.redirs.append(redir)
            else:
                current.redirs.append(Redir(op, target))
            continue
        op = next((o for o in OPS if src.startswith(o, i)), None)
        if op:
            finish(op)
            i += len(op)
            continue
        word, i = _read_word(src, i)
        if word.parts:
            current.words.append(word)
    finish(";")
    return [p for p in pipelines if p]


# --- analysis ----------------------------------------------------------------------------------------

def _apply_op(value, op, arg):
    if op in ("%", "%%"):
        return value[: -len(arg)] if arg and value.endswith(arg) else value
    if op in ("#", "##"):
        return value[len(arg):] if arg and value.startswith(arg) else value
    return value


class Analysis:
    """Walks a script, binding what it can, and collects the rules a command breaks."""

    def __init__(self, cwd, env=None, positional=None, depth=0):
        self.cwd = cwd
        self.env = dict(env or {})
        self.positional = list(positional or [])
        self.loaded = False
        self.rules = []
        self.depth = depth
        self.stdout_to_file = False
        self.xtrace = False
        self.captured = False  # this script's output is captured by `$(…)`, not printed
        self.subshells = []
        self.dirstack = []

    def refuse(self, rule):
        if rule not in self.rules:
            self.rules.append(rule)

    # words

    def expand(self, word):
        """Candidate values of a word: a list of strings, MAYBE or UNKNOWN standing for what is not known."""
        outs = [""]
        for part in word.parts:
            kind = part[0]
            if kind in ("lit", "q"):
                vals = [part[1]]
            elif kind == "sub":
                self.nested(part[1], captured=True)
                vals = [MAYBE if has_token(part[1]) else UNKNOWN]
            else:
                name, op, arg = part[1], part[2], part[3]
                if name.isdigit() and int(name) - 1 < len(self.positional) and int(name) > 0:
                    vals = self.positional[int(name) - 1]
                elif name in self.env:
                    vals = self.env[name]
                elif name == "HOME":
                    vals = [os.path.expanduser("~")]
                else:
                    vals = [UNKNOWN]
                if op in ("%", "%%", "#", "##") and not (GLOB_CHARS & set(arg)):
                    vals = [_apply_op(v, op, arg) for v in vals]
                elif op in (":-", "-") and vals == [UNKNOWN]:
                    vals = [arg]
            outs = [o + v for o in outs for v in vals][:64]
        return outs

    def words(self, simple):
        return [(w, self.expand(w)) for w in simple.words]

    def nested(self, script, positional=None, xtrace=False, captured=False):
        if self.depth > 8:
            return
        inner = Analysis(self.cwd, self.env, positional if positional is not None else self.positional,
                         self.depth + 1)
        inner.loaded = self.loaded
        inner.xtrace = self.xtrace or xtrace
        inner.captured = captured
        inner.run(script)
        for rule in inner.rules:
            self.refuse(rule)

    # scripts

    def run(self, script):
        for pipeline in parse(script):
            if pipeline == "(":
                self.subshells.append(self.cwd)
                continue
            if pipeline == ")":
                if self.subshells:
                    self.cwd = self.subshells.pop()
                continue
            names_in = False
            sink_quiet = len(pipeline) > 1 and _quiet_stage(pipeline[-1])
            for simple in pipeline:
                before = list(self.rules)
                self.command(simple, names_in, sink_quiet and simple is not pipeline[-1])
                if sink_quiet and simple is not pipeline[-1]:
                    self.rules = before + [r for r in self.rules[len(before):] if r != "read"]
                names_in = names_in or _passes_names(simple)

    def command(self, simple, names_in, piped=False):
        words = self.words(simple)
        stdin_text = None
        inputs = []
        for redir in simple.redirs:
            if redir.body is not None:
                stdin_text = redir.body
                if not redir.body_quoted:
                    for sub in _body_subs(redir.body):
                        self.nested(sub)
            elif redir.op == "<<<":
                stdin_text = redir.target.raw
                self.expand(redir.target)
            else:
                inputs.append(redir) if redir.op in ("<", "<>") else self.redirect(redir)
        # leading assignments
        while words and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", words[0][0].raw) and not words[0][0].raw.startswith("="):
            word, _ = words.pop(0)
            name, _, _ = word.raw.partition("=")
            self.env[name] = self._assigned(word)
        while words and words[0][0].literal in KEYWORDS:
            words.pop(0)
        quiet = bool(words) and _quiet_command(basename(words[0][1][0]), [w.raw for w, _ in words[1:]])
        for redir in inputs:
            if not quiet:
                self.redirect(redir)
        if not words:
            return
        head = words[0][0].literal
        if head in ("for", "select"):
            self.for_loop(words)
            return
        if head == "case":
            return
        self.stdout_to_file = any(r.op in (">", ">>", "&>", "&>>", ">|") and r.target is not None and
                                  r.target.raw not in ("/dev/stdout", "/dev/stderr", "/dev/tty")
                                  for r in simple.redirs)
        self.dispatch(words, names_in, stdin_text)

    def _assigned(self, word):
        """Candidate values of NAME=value, read from the part after the first '='."""
        tail = Word()
        seen = False
        for part in word.parts:
            if seen:
                tail.parts.append(part)
            elif part[0] in ("lit", "q") and "=" in part[1]:
                seen = True
                rest = part[1].split("=", 1)[1]
                if rest:
                    tail.add(part[0], rest)
        return self.expand(tail) if tail.parts else [""]

    def for_loop(self, words):
        if len(words) < 2:
            return
        name = words[1][0].literal or ""
        values = []
        if len(words) > 2 and words[2][0].literal == "in":
            for _, cands in words[3:]:
                values.extend(cands)
        else:
            values = [UNKNOWN]
        self.env[name] = values[:64] or [""]

    def redirect(self, redir):
        cands = self.expand(redir.target)
        refs = secret_refs(cands, self.cwd)
        if not refs:
            return
        if redir.op in ("<", "<>"):
            self.refuse("read")
        elif redir.op in (">", ">|", "&>"):
            for ref in refs:
                if ref.path is None or os.path.exists(ref.path):
                    self.refuse("overwrite" if ref.path else "unchecked")

    # commands

    def dispatch(self, words, names_in, stdin_text):
        name_word, name_cands = words[0]
        name = basename(name_cands[0]) if name_cands else ""
        args = words[1:]
        if name in WRAPPERS or name in ("time", "timeout", "env"):
            rest = list(args)
            values = WRAPPER_VALUES.get(name, ())
            while rest and (rest[0][0].raw.startswith("-") or (name == "env" and "=" in rest[0][0].raw.split("/")[0])):
                flag = rest.pop(0)[0].raw
                if flag in values and rest:
                    rest.pop(0)
            if name == "timeout" and rest:
                rest.pop(0)  # the duration
            if rest:
                self.dispatch(rest, names_in, stdin_text)
            elif name == "env" and self.loaded:
                self.refuse("print-loaded")
            return
        if name == "xargs":
            rest = list(args)
            while rest and rest[0][0].raw.startswith("-"):
                flag = rest.pop(0)[0].raw
                if flag in ("-I", "-n", "-P", "-L", "-d", "-E", "-s", "-J", "-R", "-S") and rest:
                    rest.pop(0)
            if not rest:
                rest = [(Word(), ["echo"])]
            if names_in:
                rest = rest + [(Word(), [MAYBE])]
            self.dispatch(rest, names_in, stdin_text)
            return
        if name in RUNNERS and len(args) > 0 and args[0][0].literal == "run":
            rest = list(args[1:])
            loads = False
            while rest and rest[0][0].raw.startswith("-"):
                flag = rest.pop(0)
                key, eq, value = flag[0].raw.partition("=")
                if key == "--env-file" and eq:
                    loads = loads or bool(secret_refs([c.partition("=")[2] for c in flag[1]], self.cwd))
                elif key in ("--env-file", "--with", "--python", "-p", "--directory", "--project", "--package") and rest:
                    if key == "--env-file" and secret_refs(rest[0][1], self.cwd):
                        loads = True
                    rest.pop(0)
            if rest and loads:
                self.run_loaded(rest, names_in, stdin_text)
            elif rest:
                self.dispatch(rest, names_in, stdin_text)
            return
        handler = self.HANDLERS.get(name)
        if handler is None:
            if re.match(r"python\d*(\.\d+)?$", name) or name in INTERPRETERS:
                handler = Analysis.interpreter
            elif name in SHELLS:
                handler = Analysis.shell
            elif name in READERS:
                handler = Analysis.reader
        if handler is not None:
            handler(self, name, args, names_in, stdin_text)
        elif self.loaded and (name == "printenv" or (name in ENV_PRINTERS and len(args) == 0)):
            self.refuse("print-loaded")

    def set_builtin(self, name, args, names_in, stdin_text):
        if not args and self.loaded:
            self.refuse("print-loaded")
        raws = [w.raw for w, _ in args]
        for k, raw in enumerate(raws):
            if raw in ("-o", "+o") and k + 1 < len(raws) and raws[k + 1] == "xtrace":
                self.xtrace = raw == "-o"
            elif re.match(r"[-+][A-Za-z]+$", raw) and "x" in raw:
                self.xtrace = raw.startswith("-")
        if self.xtrace and self.loaded:  # every later expansion of a loaded value is traced
            self.refuse("print-loaded")

    def cmp(self, name, args, names_in, stdin_text):
        if not _quiet_command(name, [w.raw for w, _ in args]):
            self.reader(name, args, names_in, stdin_text)

    def jq(self, name, args, names_in, stdin_text):
        """jq and yq: the first operand is a filter, which may well end in `.env`; the rest are files."""
        rest = list(args)
        filter_seen = False
        files = []
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if name == "yq" and not filter_seen and not files and raw in ("e", "eval", "ea", "eval-all"):
                continue
            if raw in ("--arg", "--argjson", "--slurpfile", "--rawfile"):  # a name, then a value or a file
                if raw in ("--slurpfile", "--rawfile") and len(rest) > 1:
                    files.append(rest[1][1])
                del rest[:2]
                continue
            if raw in ("-f", "--from-file"):
                filter_seen = True
                if rest:
                    files.append(rest.pop(0)[1])
                continue
            if raw in ("-o", "-p", "-I", "--indent", "-L", "--output-format", "--input-format") and rest:
                rest.pop(0)
                continue
            if raw.startswith("-") and raw != "-":
                continue
            if not filter_seen:
                filter_seen = True
                first = cands
                continue
            files.append(cands)
        if name == "yq" and filter_seen and not files and any(
                r.path and os.path.isfile(r.path) for r in secret_refs(first, self.cwd)):
            files.append(first)  # yq given only a file reads it with the filter `.`
        if any(secret_refs(c, self.cwd) for c in files):
            self.refuse("read")

    def direnv(self, name, args, names_in, stdin_text):
        raws = [w.raw for w, _ in args]
        if raws[:1] in (["export"], ["dump"]) and not self.captured:  # `eval "$(direnv export bash)"` prints nothing
            self.refuse("print-loaded")
        if raws[:1] == ["exec"] and len(args) > 2:
            self.run_loaded(args[2:], names_in, stdin_text)

    def run_loaded(self, words, names_in, stdin_text):
        """Dispatch a command run with a file of secrets loaded into its environment, then unload it."""
        saved = self.loaded
        self.loaded = True
        try:
            self.dispatch(words, names_in, stdin_text)
        finally:
            self.loaded = saved

    def popd(self, name, args, names_in, stdin_text):
        if self.dirstack:  # on an empty stack popd fails and the directory stays where it is
            self.cwd = self.dirstack.pop()

    def operands(self, args, takes_value=()):
        """Operand candidates after options; option values are skipped."""
        out = []
        it = iter(args)
        ended = False
        for word, cands in it:
            raw = word.raw
            if not ended and raw == "--":
                ended = True
                continue
            if not ended and raw.startswith("-") and raw != "-":
                if raw in takes_value:
                    next(it, None)
                continue
            out.append(cands)
        return out

    def reader(self, name, args, names_in, stdin_text):
        if name in ("diff", "colordiff") and any(w.raw in ("-q", "--brief") for w, _ in args):
            return
        if name == "zip":  # everything after -x or -i is a pattern, not a file
            cut = next((k for k, (w, _) in enumerate(args) if w.raw in ("-x", "-i", "--exclude", "--include")), None)
            args = args[:cut] if cut is not None else args
        takes = ("-n", "-o", "-k", "-t", "-d", "-f", "-s", "-w", "--exclude", "--exclude-from")
        if name in ("diff", "colordiff", "sdiff"):
            takes = takes + ("-x", "-X")
        if name == "tar":
            takes = takes + ("-X",)
        for cands in self.operands(args, takes):
            if secret_refs(cands, self.cwd):
                self.refuse("read")
        for word, cands in args:
            key, eq, value = word.raw.partition("=")
            if key.startswith("-") and eq and "exclude" not in key and "ignore" not in key and has_token(value):
                self.refuse("read")

    def grep(self, name, args, names_in, stdin_text):
        quiet = False
        pattern_given = False
        positional = []
        includes = []
        rest = list(args)
        takes = {"-e", "-f", "-m", "-A", "-B", "-C", "-d", "-D", "-g", "-t", "-T", "-M", "-j", "--glob",
                 "--iglob", "--include", "--exclude", "--exclude-dir", "--type", "--max-count", "--regexp",
                 "--file", "--context", "--after-context", "--before-context", "--sort", "--colors",
                 "--max-columns", "--threads", "--type-add", "--label", "--color", "--max-depth"}
        quiet_flags = {"-q", "--quiet", "--silent", "-c", "--count", "-l", "-L", "--files-with-matches",
                       "--files-without-match", "--count-matches", "--files"}
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if raw == "--":
                positional.extend(c for _, c in rest)
                break
            if raw.startswith("--"):
                key, eq, value = raw.partition("=")
                if key in quiet_flags:
                    quiet = True
                if key in ("--regexp", "--file"):
                    pattern_given = True
                if key in ("--include", "--glob", "--iglob"):
                    value = value if eq else (rest.pop(0)[0].raw if rest else "")
                    if not value.startswith("!"):  # `--glob '!X'` excludes X
                        includes.append(value)
                elif key in takes and not eq and rest:
                    rest.pop(0)
                continue
            if raw.startswith("-") and len(raw) > 1:
                letters = raw[1:]
                for k, letter in enumerate(letters):
                    flag = "-" + letter
                    if flag in ("-q", "-c", "-l", "-L") or (name == "rg" and flag == "-c"):
                        quiet = True
                    if flag in takes and not (name not in ("rg", "ag", "ugrep") and flag in ("-g", "-t", "-M", "-j")):
                        value = letters[k + 1:] or (rest.pop(0)[0].raw if rest else "")
                        if flag in ("-e", "-f"):
                            pattern_given = True
                            if flag == "-f" and has_token(value):
                                self.refuse("read")
                        if flag == "-g" and not value.startswith("!"):
                            includes.append(value)
                        break
                continue
            positional.append(cands)
        files = positional if pattern_given else positional[1:]
        files = [[c for c in f if not c.startswith((":!", ":^", ":(exclude", ":(top,exclude"))] for f in files]
        if quiet:
            return
        if any(secret_refs(c, self.cwd) for c in files):
            self.refuse("read")
        if any(is_secret_name(basename(g)) for g in includes):
            self.refuse("read")

    def sed(self, name, args, names_in, stdin_text):
        in_place = False
        script_given = False
        positional = []
        rest = list(args)
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if raw.startswith("--in-place"):
                in_place = True
                continue
            if raw in ("-e", "--expression", "-f", "--file"):
                script_given = True
                if rest:
                    script = rest.pop(0)[0].raw
                    if raw in ("-f", "--file") and has_token(script):
                        self.refuse("read")
                continue
            if raw.startswith("-") and len(raw) > 1 and not raw.startswith("--"):
                if "i" in raw[1:]:
                    in_place = True
                    if raw.endswith("i") and rest and (rest[0][0].raw == "" or rest[0][0].raw.startswith(".")) \
                            and not secret_refs(rest[0][1], self.cwd):
                        rest.pop(0)
                if "e" in raw[1:] or "f" in raw[1:]:
                    script_given = True
                    if rest:
                        rest.pop(0)
                if "l" in raw[1:] and rest:
                    rest.pop(0)
                continue
            positional.append(cands)
        files = positional if script_given else positional[1:]
        if not in_place and any(secret_refs(c, self.cwd) for c in files):
            self.refuse("read")

    def awk(self, name, args, names_in, stdin_text):
        positional = []
        program_given = False
        in_place = False
        rest = list(args)
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if raw in ("-f", "-v", "-F", "-i") and rest:
                value = rest.pop(0)[0].raw
                if raw == "-f":
                    program_given = True
                if raw == "-i" and value == "inplace":
                    in_place = True
                continue
            if raw.startswith("-") and len(raw) > 1:
                continue
            if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", raw):
                continue
            positional.append(cands)
        files = positional if program_given else positional[1:]
        if not in_place and any(secret_refs(c, self.cwd) for c in files):
            self.refuse("read")

    def copier(self, name, args, names_in, stdin_text):
        no_clobber = False
        recursive = name in ("rsync", "ditto")
        delete = False
        delete_excluded = False
        target_dir = None
        excludes = []
        operands = []
        rest = list(args)
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if raw == "--":
                operands.extend(c for _, c in rest)
                break
            if raw.startswith("--"):
                key, eq, value = raw.partition("=")
                if raw in ("--no-clobber", "--update=none", "--ignore-existing"):
                    no_clobber = True
                if key in ("--recursive", "--archive"):
                    recursive = True
                if key.startswith("--delete"):
                    delete = True
                if key == "--delete-excluded":
                    delete_excluded = True
                if key in ("--exclude", "--filter", "--exclude-from", "--include", "--suffix", "--rsh"):
                    value = value if eq else (rest.pop(0)[0].raw if rest else "")
                    if key in ("--exclude", "--filter"):
                        excludes.append(value)
                if key == "--target-directory":
                    target_dir = value if eq else (rest.pop(0)[1][0] if rest else None)
                continue
            if raw.startswith("-") and len(raw) > 1:
                letters = raw[1:]
                if "n" in letters and name in ("cp", "mv", "gcp", "gmv"):
                    no_clobber = True
                if set(letters) & set("rRa"):
                    recursive = True
                if name == "rsync" and letters[-1:] in ("e", "f") and rest:
                    value = rest.pop(0)[0].raw
                    if letters[-1] == "f":
                        excludes.append(value)
                if "t" in letters and name in ("cp", "mv", "install", "ln") and rest:
                    target_dir = rest.pop(0)[1][0]
                continue
            operands.append(cands)
        if target_dir is not None:
            sources, target = operands, [target_dir]
        elif len(operands) >= 2:
            sources, target = operands[:-1], operands[-1]
        else:
            return
        many = len(sources) > 1 or target_dir is not None
        for target_text in target:
            remote = bool(re.match(r"[^/]*:", target_text)) and not target_text.startswith(("/", "./", "~"))
            target_path = None if remote else resolve(target_text, self.cwd)
            if delete and target_path is not None:
                found = secrets_below(target_path)
                kept = [] if delete_excluded else excludes  # --delete-excluded deletes what is excluded too
                if found is None:
                    self.refuse("unchecked")
                elif [f for f in found if not _excluded(os.path.relpath(f, target_path), kept)]:
                    self.refuse("remove-dir")
            for src_cands in sources:
                for src_text in src_cands:
                    for src in self.copy_sources(src_text):
                        self.copy_one(name, src, target_text, many, no_clobber, remote, recursive, excludes)

    def copy_sources(self, text):
        """The concrete sources one operand names: each match of a glob, or the operand itself."""
        path = resolve(text, self.cwd)
        if path is not None and GLOB_CHARS & set(text):
            return sorted(glob.glob(path)) or [text]
        return [text]

    def copy_one(self, name, src_text, target_text, many, no_clobber, remote, recursive=False, excludes=()):
        src_path = resolve(src_text, self.cwd)
        target_path = resolve(target_text, self.cwd)
        into_dir = many or target_text.endswith("/") or (target_path is not None and os.path.isdir(target_path))
        if excludes and _excluded(src_text.rstrip("/"), excludes):
            return
        if recursive and src_path is not None and os.path.isdir(src_path):
            found = secrets_below(src_path)
            if found:
                found = [f for f in found if not _excluded(os.path.relpath(f, src_path), excludes)]
            if not found:
                if found is None:
                    self.refuse("unchecked")
                return
            if remote:
                self.refuse("send")
                return
            if target_path is None:
                self.refuse("unchecked")
                return
            contents_only = name == "rsync" and src_text.endswith("/")
            base = target_path if contents_only or not into_dir else os.path.join(target_path, basename(src_path))
            for secret in found:
                self.check_copy(os.path.join(base, os.path.relpath(secret, src_path)), no_clobber)
            return
        src_refs = secret_refs([src_text], self.cwd)
        src_secret = bool(src_refs) or MAYBE in src_text
        if into_dir:
            if target_path is not None and MAYBE not in src_text and UNKNOWN not in src_text:
                target_path = os.path.join(target_path, basename(src_text))
            else:
                target_path = None
        target_name = basename(target_path) if target_path else basename(target_text)
        if src_secret:
            if remote:
                self.refuse("send")
                return
            if any(r.path is None for r in src_refs) or MAYBE in src_text or target_path is None:
                self.refuse("unchecked")
                return
            if not is_secret_name(target_name):
                self.refuse("copy-out")
                return
            self.check_copy(target_path, no_clobber)
            return
        if name == "ln":
            return
        if is_secret_name(target_name) and not (target_path and is_temp(target_path)):
            if target_path is None:
                if not no_clobber:
                    self.refuse("unchecked")
                return
            if os.path.lexists(target_path) and not no_clobber and not os.path.isdir(target_path):
                self.refuse("overwrite")

    def check_copy(self, target_path, no_clobber):
        """A copy of a file of secrets lands on a new path git ignores, never over one that exists."""
        if os.path.lexists(target_path) and not no_clobber:
            self.refuse("overwrite")
        elif not git_ignored(target_path):
            self.refuse("copy-unignored")

    def remover(self, name, args, names_in, stdin_text):
        recursive = name == "rmdir"
        operands = []
        for word, cands in args:
            raw = word.raw
            if raw.startswith("-") and len(raw) > 1:
                if raw in ("--recursive",) or (not raw.startswith("--") and ("r" in raw or "R" in raw)):
                    recursive = True
                continue
            operands.append(cands)
        for cands in operands:
            if secret_refs(cands, self.cwd):
                self.refuse("remove")
                continue
            if recursive:
                for text in cands:
                    if MAYBE in text:
                        self.refuse("unchecked")
                        continue
                    path = resolve(text, self.cwd)
                    if path is None:
                        continue
                    for match in (glob.glob(path) if GLOB_CHARS & set(path) else [path]):
                        found = holds_secret(match)
                        if found is None:
                            self.refuse("unchecked")
                        elif found:
                            self.refuse("remove-dir")

    def truncate(self, name, args, names_in, stdin_text):
        rest = list(args)
        grow = False
        operands = []
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if raw in ("-s", "--size") and rest:
                grow = rest.pop(0)[0].raw.startswith("+")
                continue
            if raw.startswith("-s"):
                grow = raw[2:].startswith("+")
                continue
            if raw.startswith("-"):
                continue
            operands.append(cands)
        if grow:
            return
        for cands in operands:
            for ref in secret_refs(cands, self.cwd):
                if ref.path is None or os.path.exists(ref.path):
                    self.refuse("overwrite")

    def tee(self, name, args, names_in, stdin_text):
        if any(w.raw in ("-a", "--append") or (w.raw.startswith("-") and "a" in w.raw[1:] and not w.raw.startswith("--"))
               for w, _ in args):
            return
        for cands in self.operands(args):
            for ref in secret_refs(cands, self.cwd):
                if ref.path is None or os.path.exists(ref.path):
                    self.refuse("overwrite")

    def dd(self, name, args, names_in, stdin_text):
        for word, cands in args:
            raw = word.raw
            if raw.startswith("if=") and has_token(raw[3:]):
                self.refuse("read")
            if raw.startswith("of=") and secret_refs([c[3:] for c in cands], self.cwd):
                self.refuse("overwrite")

    def find(self, name, args, names_in, stdin_text):
        names_secret = False
        named = False
        starts = []
        for word, cands in args:
            if word.raw.startswith(("-", "(", "!")) or word.raw in ("(", "!"):
                break
            starts.extend(cands)
        k = 0
        while k < len(args):
            raw = args[k][0].raw
            if raw in ("-name", "-iname", "-path", "-ipath", "-wholename", "-regex", "-iregex") and k + 1 < len(args):
                named = True
                if has_token(args[k + 1][0].raw) or is_secret_name(basename(args[k + 1][0].raw)):
                    names_secret = True
                k += 2
                continue
            if raw == "-delete" and names_secret:
                self.refuse("remove")
            elif raw == "-delete" and not named and not any(
                    w.raw == "-empty" or (w.raw == "-type" and j + 1 < len(args) and args[j + 1][0].raw == "d")
                    for j, (w, _) in enumerate(args)):  # everything below the starting points goes
                for start in starts or ["."]:
                    found = holds_secret(resolve(start, self.cwd))
                    if found is None:
                        self.refuse("unchecked")
                    elif found:
                        self.refuse("remove-dir")
            if raw in ("-exec", "-execdir", "-ok", "-okdir"):
                end = k + 1
                while end < len(args) and args[end][0].raw not in (";", "+", "\\;"):
                    end += 1
                inner = args[k + 1: end]
                if inner:
                    marker = MAYBE if names_secret else UNKNOWN
                    bound = [(w, [c.replace("{}", marker) for c in cands]) for w, cands in inner]
                    self.dispatch(bound, names_in, None)
                k = end + 1
                continue
            k += 1

    def source(self, name, args, names_in, stdin_text):
        if args and secret_refs(args[0][1], self.cwd):
            self.loaded = True
            if self.xtrace:  # every assignment in the file is traced, value and all
                self.refuse("print-loaded")

    def echo(self, name, args, names_in, stdin_text):
        if self.loaded and not self.stdout_to_file and any(self.may_print_loaded(w) for w, _ in args):
            self.refuse("print-loaded")

    def may_print_loaded(self, word):
        """Whether a word expands a variable the loaded file may have set: not positional, not bound here."""
        return any(p[0] == "var" and not p[1].isdigit() and p[1] not in self.env and not p[1].startswith("?")
                   and p[1] not in ("@", "*", "#", "?", "$", "!", "-") for p in word.parts)

    def exporter(self, name, args, names_in, stdin_text):
        operands = [w for w, _ in args if not w.raw.startswith("-")]
        if self.loaded and (not operands or any(w.raw in ("-p",) for w, _ in args)):
            self.refuse("print-loaded")
        for word in operands:
            if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", word.raw):
                self.env[word.raw.split("=", 1)[0]] = self._assigned(word)

    def read_builtin(self, name, args, names_in, stdin_text):
        value = [MAYBE] if names_in or has_token(stdin_text or "") else [UNKNOWN]
        for word, _ in args:
            if not word.raw.startswith("-") and re.match(r"[A-Za-z_][A-Za-z0-9_]*$", word.raw):
                self.env[word.raw] = value

    def cd(self, name, args, names_in, stdin_text):
        if name == "pushd":
            self.dirstack.append(self.cwd)
        operands = [c for w, c in args if not w.raw.startswith("-") or w.raw == "-"]
        if not operands:
            self.cwd = os.path.expanduser("~")
            return
        target = operands[0][0]
        self.cwd = resolve(target, self.cwd) if target != "-" else None

    def trap(self, name, args, names_in, stdin_text):
        if args and args[0][0].literal is not None:
            self.nested(args[0][0].literal)

    def eval_builtin(self, name, args, names_in, stdin_text):
        self.nested(" ".join(c[0] for _, c in args if c))

    def shell(self, name, args, names_in, stdin_text):
        rest = list(args)
        xtrace = False
        for k, (word, _) in enumerate(rest):  # the shell's own options, before -c or the script
            raw = word.raw
            if not raw.startswith(("-", "+")) or raw == "-":
                break
            if raw == "-o" and k + 1 < len(rest) and rest[k + 1][0].raw == "xtrace":
                xtrace = True
            elif not raw.startswith("--") and "x" in raw[1:].split("c", 1)[0] and raw.startswith("-"):
                xtrace = True
            if "c" in raw[1:] and not raw.startswith("--"):
                break
        while rest and rest[0][0].raw.startswith(("-", "+")) and rest[0][0].raw not in ("-c",):
            if "c" in rest[0][0].raw[1:] and not rest[0][0].raw.startswith("--"):
                break
            if rest.pop(0)[0].raw in ("-o", "+o") and rest:
                rest.pop(0)
        if rest and rest[0][0].raw.startswith("-") and "c" in rest[0][0].raw:
            if len(rest) > 1:
                code = rest[1][0].literal
                positional = [c for _, c in rest[3:]]
                if code is not None:
                    self.nested(code, positional, xtrace)
                elif has_token(rest[1][0].raw):
                    self.refuse("interp-code")
            return
        if (not rest or rest[0][0].raw == "-") and stdin_text is not None:
            self.nested(stdin_text, [c for _, c in rest[1:]], xtrace)

    def interpreter(self, name, args, names_in, stdin_text):
        code = None
        in_place = False
        positional = []
        rest = list(args)
        module = False
        while rest:
            word, cands = rest.pop(0)
            raw = word.raw
            if name in ("perl", "ruby") and raw.startswith("-") and not raw.startswith("--"):
                # Letters up to the first one that takes a value: -pi and -pie edit in place, -Mstrict does not.
                letters = re.split(r"[MmIrx0lCdDF]", raw[1:], maxsplit=1)[0]
                in_place = in_place or "i" in letters
                if ("e" in letters or "E" in letters) and rest:
                    code = (code or "") + rest.pop(0)[0].raw
                continue
            if raw in ("-c", "-e", "-E", "--eval", "-r", "-p", "--print") and rest:
                code = (code or "") + rest.pop(0)[0].raw
                continue
            if raw == "-m":
                module = True
                if rest and rest[0][0].raw == "dotenv":
                    self.dotenv_cli("dotenv", rest[1:], names_in, stdin_text)
                    return
                positional.extend(c for _, c in rest[1:])
                break
            if raw in ("-W", "-X", "--import", "-r") and rest:
                rest.pop(0)
                continue
            if raw.startswith("-") and raw != "-":
                continue
            positional.append(cands)
            if code is None and raw != "-":
                positional.extend(c for _, c in rest)
                break
        script_from_stdin = code is None and not module and (not positional or positional[0] == ["-"])
        if script_from_stdin and stdin_text is not None:
            code = stdin_text
            positional = positional[1:]
        if code is None:
            return
        if self.loaded and not self.stdout_to_file and ENVIRONMENT_READ.search(code):
            self.refuse("print-loaded")
        if not in_place and code_names_secret(code):
            self.refuse("interp-code")
        if not in_place and any(secret_refs(c, self.cwd) for c in positional):
            self.refuse("read")

    def git(self, name, args, names_in, stdin_text):
        rest = list(args)
        cwd = self.cwd
        while rest and rest[0][0].raw.startswith("-"):
            flag = rest.pop(0)[0].raw
            if flag == "-C" and rest:
                cwd = resolve(rest.pop(0)[1][0], cwd)
            elif flag in ("-c", "--git-dir", "--work-tree", "--namespace") and rest:
                rest.pop(0)
        if not rest:
            return
        sub = rest[0][0].raw
        rest = rest[1:]
        saved = self.cwd
        self.cwd = cwd
        try:
            if sub == "grep":
                self.grep("git-grep", rest, names_in, stdin_text)
            elif sub in ("diff", "show", "cat-file", "blame", "annotate", "log"):
                summary = {"--stat", "--name-only", "--name-status", "--quiet", "--exit-code", "--shortstat",
                           "--numstat", "--oneline", "-s", "--no-patch", "--summary", "-e"}
                if sub == "log" and not any(w.raw in ("-p", "--patch") or w.raw.startswith("-L") for w, _ in rest):
                    return
                if any(w.raw in summary for w, _ in rest):
                    return
                for word, cands in rest:
                    if word.raw.startswith(":(") or word.raw.startswith(":!") or word.raw.startswith("-"):
                        continue
                    texts = [c.split(":", 1)[1] if ":" in c and not c.startswith("/") else c for c in cands]
                    if secret_refs(texts, self.cwd):
                        self.refuse("read")
            elif sub == "rm" and not any(w.raw == "--cached" for w, _ in rest):
                # git rm removes tracked files only, so a directory's ignored files are not at stake
                if any(secret_refs(cands, self.cwd) for cands in self.operands(rest)):
                    self.refuse("remove")
            elif sub in ("checkout", "restore"):
                raws = [w.raw for w, _ in rest]
                staged_only = "--staged" in raws and "--worktree" not in raws and "-W" not in raws
                if not staged_only:
                    for cands in self.operands(rest, ("-s", "--source", "-b", "-B")):
                        if any(r.path and os.path.isfile(r.path) for r in secret_refs(cands, self.cwd)):
                            self.refuse("overwrite")
            elif sub == "clean":
                self.git_clean(rest)
            elif sub == "worktree" and rest and rest[0][0].raw == "remove":
                for word, cands in rest[1:]:
                    if word.raw.startswith("-"):
                        continue
                    for text in cands:
                        found = holds_secret(resolve(text, self.cwd))
                        if found is None:
                            self.refuse("unchecked")
                        elif found:
                            self.refuse("remove-dir")
        finally:
            self.cwd = saved

    def git_clean(self, args):
        flags = "".join(w.raw[1:] for w, _ in args if w.raw.startswith("-") and not w.raw.startswith("--"))
        longs = {w.raw for w, _ in args if w.raw.startswith("--")}
        if "n" in flags or "--dry-run" in longs:
            return
        if "x" in flags:  # untracked files, ignored or not
            listing = []
        elif "X" in flags:  # ignored files only
            listing = ["--ignored", "--exclude-standard"]
        else:  # untracked files git does not ignore: a file of secrets the ignore list misses goes too
            listing = ["--exclude-standard"]
        dirs = "d" in flags
        kept = []
        for k, (word, _) in enumerate(args):
            if word.raw == "-e" and k + 1 < len(args):
                kept.append(args[k + 1][0].raw)
            elif word.raw.startswith("--exclude="):
                kept.append(word.raw.split("=", 1)[1])
        if self.cwd is None:
            self.refuse("unchecked")
            return
        try:
            listed = subprocess.run(["git", "-C", self.cwd, "ls-files", "--others"] + listing +
                                    (["--directory", "--no-empty-directory"] if dirs else []),
                                    capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            self.refuse("unchecked")
            return
        for line in listed.stdout.splitlines():
            if line.endswith("/"):
                found = secrets_below(os.path.join(self.cwd, line))
                if found is None:
                    self.refuse("unchecked")
                    return
                if [f for f in found if not _excluded(os.path.relpath(f, self.cwd), kept)]:
                    self.refuse("clean")
                    return
                continue
            if is_secret_name(basename(line)) and not _excluded(line, kept):
                self.refuse("clean")
                return

    def docker(self, name, args, names_in, stdin_text):
        rest = list(args)
        compose = name in ("docker-compose", "podman-compose")
        while rest and rest[0][0].raw.startswith("-"):
            flag = rest.pop(0)[0].raw
            if flag in ("-H", "--host", "--context", "-c", "--config", "--log-level") and rest:
                rest.pop(0)
        if not compose:
            if not rest:
                return
            if rest[0][0].raw == "compose":
                compose = True
                rest = rest[1:]
        env_files = []
        project_dir = self.cwd
        options_with_value = {"-f", "--file", "-p", "--project-name", "--profile", "--env-file",
                              "--project-directory", "--ansi", "--progress", "--parallel"}
        while rest and rest[0][0].raw.startswith("-"):
            word, cands = rest.pop(0)
            key, eq, value = word.raw.partition("=")
            values = [value] if eq else (rest.pop(0)[1] if rest and key in options_with_value else [])
            if key == "--env-file":
                env_files.extend(values)
            elif key == "--project-directory" and values:
                project_dir = resolve(values[0], self.cwd)
            elif key in ("-f", "--file") and values and project_dir == self.cwd:
                path = resolve(values[0], self.cwd)
                project_dir = os.path.dirname(path) if path else None
        if not rest:
            return
        sub = rest[0][0].raw
        rest = rest[1:]
        if not compose:
            for k, (word, cands) in enumerate(rest):
                key, eq, value = word.raw.partition("=")
                if key == "--env-file":
                    env_files.extend([value] if eq else (rest[k + 1][1] if k + 1 < len(rest) else []))
        loads = bool(secret_refs(env_files, self.cwd))
        if compose and not env_files and project_dir is not None:
            loads = os.path.isfile(os.path.join(project_dir, ".env"))
        if not loads:
            return
        if compose and sub == "config":
            harmless = {"--services", "--volumes", "--profiles", "--images", "-q", "--quiet", "--hash", "--networks"}
            if not any(w.raw.split("=")[0] in harmless for w, _ in rest):
                self.refuse("print-loaded")
        if sub in ("exec", "run") and any(w.raw in ("env", "printenv") for w, _ in rest):
            self.refuse("print-loaded")

    def curl(self, name, args, names_in, stdin_text):
        previous = ""
        for word, cands in args:
            raw = word.raw
            for text in cands:
                if "@" in text and has_token(text.split("@", 1)[1]):
                    self.refuse("send")
                if previous in ("-T", "--upload-file", "--data-binary", "-d", "--data", "-F", "--form") and \
                        secret_refs([text.lstrip("@")], self.cwd):
                    self.refuse("send")
            previous = raw

    def dotenv_cli(self, name, args, names_in, stdin_text):
        rest = list(args)
        while rest and rest[0][0].raw.startswith("-"):
            flag = rest.pop(0)[0].raw
            if flag in ("-f", "--file", "-e", "--export", "-q", "--quote") and rest:
                rest.pop(0)
        if not rest:
            return
        sub = rest[0][0].raw
        if sub in ("list", "get"):
            self.refuse("read")
        elif sub == "run":
            rest = rest[1:]
            while rest and rest[0][0].raw.startswith("-"):
                if rest.pop(0)[0].raw == "--":
                    break
            if rest:
                self.run_loaded(rest, names_in, stdin_text)

    HANDLERS = {}


Analysis.HANDLERS = {
    "sed": Analysis.sed, "gsed": Analysis.sed,
    "awk": Analysis.awk, "gawk": Analysis.awk, "mawk": Analysis.awk, "nawk": Analysis.awk,
    "truncate": Analysis.truncate, "tee": Analysis.tee, "dd": Analysis.dd,
    "find": Analysis.find, "gfind": Analysis.find,
    "source": Analysis.source, ".": Analysis.source,
    "echo": Analysis.echo, "printf": Analysis.echo,
    "export": Analysis.exporter, "declare": Analysis.exporter, "typeset": Analysis.exporter,
    "local": Analysis.exporter, "readonly": Analysis.exporter,
    "read": Analysis.read_builtin, "cd": Analysis.cd, "pushd": Analysis.cd,
    "trap": Analysis.trap, "eval": Analysis.eval_builtin,
    "git": Analysis.git,
    "docker": Analysis.docker, "podman": Analysis.docker, "docker-compose": Analysis.docker,
    "podman-compose": Analysis.docker,
    "curl": Analysis.curl, "wget": Analysis.curl, "http": Analysis.curl, "https": Analysis.curl,
    "dotenv": Analysis.dotenv_cli, "direnv": Analysis.direnv,
    "set": Analysis.set_builtin, "cmp": Analysis.cmp, "popd": Analysis.popd,
    "jq": Analysis.jq, "gojq": Analysis.jq, "yq": Analysis.jq,
}
for _name in COPIERS:
    Analysis.HANDLERS[_name] = Analysis.copier
for _name in REMOVERS:
    Analysis.HANDLERS[_name] = Analysis.remover
for _name in GREPS:
    Analysis.HANDLERS[_name] = Analysis.grep
Analysis.HANDLERS["scp"] = Analysis.copier


def _excluded(path, patterns):
    """Whether an exclude pattern (git clean -e, rsync --exclude) keeps this path: its name or the path."""
    patterns = [p[len("- "):] if p.startswith("- ") else p for p in patterns]  # rsync's `--filter '- X'`
    return any(fnmatch.fnmatchcase(basename(path), p) or fnmatch.fnmatchcase(path, p.lstrip("/")) for p in patterns)


def _first(simple):
    return basename(simple.words[0].raw) if simple.words else ""


def _quiet_stage(simple):
    """Whether a pipeline's last stage prints nothing of what it reads: a count, a hash, a quiet grep."""
    return _quiet_command(_first(simple), [w.raw for w in simple.words[1:]])


def _quiet_command(name, raws):
    """Whether a command prints nothing of what it reads: a count, a hash, a quiet grep, a terse cmp."""
    if name == "cmp":
        return not any(r in ("--verbose", "--print-bytes") or
                       (r.startswith("-") and not r.startswith("--") and set(r[1:]) & set("lb")) for r in raws)
    if name in QUIET_READERS:
        return True
    return name in GREPS and any(r in ("-q", "-c", "-l", "-L", "--quiet", "--count") or
                                 (r.startswith("-") and not r.startswith("--") and set(r[1:]) & set("qclL"))
                                 for r in raws)


def _passes_names(simple):
    """Whether a stage puts names of files of secrets into the pipe: it names one, and not only to drop it."""
    if not has_token(" ".join(w.raw for w in simple.words)):
        return False
    name = _first(simple)
    raws = [w.raw for w in simple.words[1:]]
    inverted = any(r in ("-v", "--invert-match") or (r.startswith("-") and not r.startswith("--") and "v" in r[1:])
                   for r in raws)
    return not (name in GREPS and inverted)


STRING_LITERAL = re.compile(r"(?s)(\"\"\"|'''|\"|')(.*?)(?<!\\)\1")


def code_names_secret(code):
    """Whether interpreter code holds a string literal that is, by itself, a path to a file of secrets."""
    for match in STRING_LITERAL.finditer(code):
        content = match.group(2)
        if not content or any(ch.isspace() for ch in content):
            continue
        content = re.sub(r"\{[^{}]*\}", "x", content)
        base = basename(content)
        if base and is_secret_name(base) and has_token(content):
            return True
    return False


# --- the hook ----------------------------------------------------------------------------------------

def decide(tool_name, tool_input, cwd):
    """The rules a call breaks, in the order found: [] when it is allowed."""
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return []
        analysis = Analysis(cwd)
        try:
            analysis.run(command)
        except Exception:  # a command the parser cannot follow
            return ["unparsed"] if has_token(command) else []
        return analysis.rules
    if tool_name == "Read":
        path = tool_input.get("file_path")
        if isinstance(path, str) and secret_refs([path], cwd):
            return ["read"]
        return []
    if tool_name == "Grep":
        if tool_input.get("output_mode", "files_with_matches") != "content":
            return []
        path, pattern = tool_input.get("path"), tool_input.get("glob")
        if isinstance(path, str) and secret_refs([path], cwd):
            return ["read"]
        if isinstance(pattern, str) and is_secret_name(basename(pattern)):
            return ["read"]
        return []
    if tool_name == "Write":
        path = tool_input.get("file_path")
        if isinstance(path, str) and any(r.path and os.path.exists(r.path) for r in secret_refs([path], cwd)):
            return ["overwrite"]
        return []
    return []


def message(rules):
    why = "; ".join(REASONS.get(rule, rule) for rule in rules)
    return "Refused by the pyhouse-secrets guard: " + why + ". " + ALLOWED + " " + TAIL


def record(entry):
    directory = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".claude",
                                                                      "pyhouse-secrets")
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd = os.open(os.path.join(directory, "decisions.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # the record is best effort; the decision is already out
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    rules = decide(tool_name, tool_input, cwd)
    mode = "log" if os.environ.get("CLAUDE_PLUGIN_OPTION_MODE", "").strip().lower() == "log" else "enforce"
    if rules and mode == "enforce":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message(rules),
        }}))
        sys.stdout.flush()
    command = tool_input.get("command")
    text = command if tool_name == "Bash" and isinstance(command, str) else json.dumps(tool_input, ensure_ascii=False)
    if rules or has_token(text):
        record({
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session": payload.get("session_id"),
            "cwd": cwd,
            "tool": tool_name,
            "mode": mode,
            "decision": "refuse" if rules else "allow",
            "rules": rules,
            "input": text[:4000],
        })
    return 0


if __name__ == "__main__":
    sys.exit(main())
