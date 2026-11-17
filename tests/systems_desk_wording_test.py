#!/usr/bin/env python3
"""No bare "desk" in the text a person reads.

  python3 tests/systems_desk_wording_test.py

A newcomer reads "desk" as furniture. Everything a person reads says
"systems desk" (the first mention on a page also says what it is). Host and
command names such as `desk01`, `ssh desk01-setup` and `desk01-agent`, and
file paths, are not prose and stay as they are.

Scanned: README.md; the template's README.md; the `text` code blocks and quoted (>) lines of
initial_setup/*.md, operating_procedures/*.md and talking_with_the_team.md;
the string literals of set_up_outside_services/*.go (not *_test.go); and the
messages that the systems desk's own commands print
(roles/systems_desk/files: the lines that echo, printf or print).
"""
import ast
import io
import re
import tokenize
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
T = ROOT/'skills/monkeymaxxing-stack/systems_repository_template'

# "desk" or "desks" as a word, not part of a host name (desk01), a command or
# file name (desk-ssh-agent, desk_x), a path or a dotted name.
BARE_DESK = re.compile(r'(?<![\w/.\-])[Dd]esks?(?![\w\-/]|\.\w)')
PREFIX = 'systems '

# Files left out of the scan, each with its reason.
EXCEPTIONS = {
    'set_up_outside_services/passphrase_words.go':
        'its raw string is the list of dictionary words for recovery passphrases, and "desk" is one of the words',
}


def bare_desk_columns(line):
    for m in BARE_DESK.finditer(line):
        if line[:m.start()].lower().endswith(PREFIX):
            continue
        yield m.start()


def text_blocks(path):
    """(line_number, line) for every line inside a ```text block, and every
    quoted line (starting with ">") outside code blocks: the "Tell the
    person" messages and chapter 0's map are quotes."""
    inside = False
    in_code = False
    for number, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code = not in_code
            inside = in_code and stripped[3:].strip() == 'text'
            continue
        if inside or (not in_code and stripped.startswith('>')):
            yield number, line


def whole_file(path):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        yield number, line


GO_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|`[^`]*`')


def go_strings(path):
    text = path.read_text()
    # Drop // comments (not inside strings, which is good enough: a string with
    # // such as a url is kept by matching strings first).
    out = []
    for m in re.finditer(r'"(?:[^"\\\n]|\\.)*"|`[^`]*`|//[^\n]*', text):
        if m.group().startswith('//'):
            continue
        line_number = text.count('\n', 0, m.start()) + 1
        for offset, part in enumerate(m.group().split('\n')):
            out.append((line_number + offset, part))
    return out


PRINTING = re.compile(r'\b(echo|printf|die|fail|warn|say)\b|>&2')


def python_strings(text):
    """(row, column, token text) of every string in a Python file except docstrings."""
    docstring_rows = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) is not None:
                docstring_rows.add(node.body[0].value.lineno)
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.STRING and token.start[0] not in docstring_rows:
            yield token.start[0], token.start[1], token.string


def printed_lines(path):
    """The text a desk command prints to the person. Python commands: every
    string in the file except docstrings. Shell commands: the echo and printf
    lines. Comments and docstrings are for developers and are not scanned."""
    text = path.read_text()
    if text.startswith('#!') and 'python' in text.splitlines()[0]:
        for row, _, string in python_strings(text):
            for offset, part in enumerate(string.split('\n')):
                yield row + offset, part
        return
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and PRINTING.search(stripped):
            yield number, line


class SystemsDeskWordingTest(unittest.TestCase):
    def sources(self):
        yield ROOT/'README.md', whole_file
        yield T/'README.md', whole_file
        yield T/'talking_with_the_team.md', text_blocks
        for folder in ('initial_setup', 'operating_procedures'):
            for path in sorted((T/folder).glob('*.md')):
                yield path, text_blocks
        for path in sorted((ROOT/'set_up_outside_services').glob('*.go')):
            if not path.name.endswith('_test.go') and str(path.relative_to(ROOT)) not in EXCEPTIONS:
                yield path, go_strings
        for path in sorted((T/'roles/systems_desk/files').iterdir()):
            if path.is_file() and path.suffix in ('', '.sh'):
                yield path, printed_lines

    def test_no_bare_desk_in_text_a_person_reads(self):
        problems = []
        for path, lines_of in self.sources():
            for number, line in lines_of(path):
                for column in bare_desk_columns(line):
                    problems.append('%s:%d: %s' % (
                        path.relative_to(ROOT), number, line.strip()[:140]))
                    break
        self.assertEqual(problems, [], 'write "systems desk", not "desk":\n' + '\n'.join(problems))

    def test_the_pattern_itself(self):
        bad = ['Your desk is locked.', 'every other desks', 'the Desk', 'on the desk, it']
        good = ['your systems desk', '`ssh desk01-setup`', 'desk01-agent', 'the Systems Desk',
                'roles/systems_desk/files', 'desk-ssh-agent.service', 'host desk01']
        for line in bad:
            self.assertTrue(list(bare_desk_columns(line)), line)
        for line in good:
            self.assertFalse(list(bare_desk_columns(line)), line)


if __name__ == '__main__':
    unittest.main()
