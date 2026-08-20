"""
lexer.py
Module owner: PIYUSH MUNDHRA (24BCE2173) -- Frontend / Lexer & Parser
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

Converts toy-language source text into a flat token stream.
Toy-language grammar (as fixed in Review 1):

    program        -> statement*
    statement      -> assignment | print_statement
    assignment     -> identifier '=' expression
    print_statement-> 'print' '(' expression ')'
    expression     -> value | identifier | expression '+' expression
    value          -> integer | string
    identifier     -> letter (letter | digit)*
"""

import re


# ROLE: Data structure holding a single chopped token (e.g. NUMBER, ID, ASSIGN, PLUS) with its line number.
class Token:
    __slots__ = ("type", "value", "line")

    # ROLE: Initializes the token with its category type, actual value, and source line number.
    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


# Token specification, order matters (longest/most specific first)
TOKEN_SPEC = [
    ("SKIP",    r"[ \t]+"),
    ("NEWLINE", r"\n"),
    ("COMMENT", r"#[^\n]*"),
    ("STRING",  r'"[^"\n]*"'),
    ("NUMBER",  r"-?\d+"),
    ("PRINT",   r"\bprint\b"),
    ("ID",      r"[A-Za-z][A-Za-z0-9]*"),
    ("ASSIGN",  r"="),
    ("PLUS",    r"\+"),
    ("LPAREN",  r"\("),
    ("RPAREN",  r"\)"),
    ("SEMI",    r";"),
]

MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


# ROLE: Custom exception raised when the lexer encounters an unrecognized character in the source code.
class LexError(Exception):
    pass


# ROLE: Scans the raw source string using regular expressions and returns a complete list of Tokens.
def tokenize(source: str):
    """Convert source text into a list of Token objects (EOF-terminated)."""
    tokens = []
    line = 1
    pos = 0
    length = len(source)
    while pos < length:
        m = MASTER_RE.match(source, pos)
        if not m:
            raise LexError(f"Unexpected character {source[pos]!r} at line {line}")
        kind = m.lastgroup
        text = m.group()
        if kind == "NEWLINE":
            line += 1
        elif kind in ("SKIP", "COMMENT"):
            pass
        elif kind == "STRING":
            tokens.append(Token("STRING", text[1:-1], line))
        elif kind == "NUMBER":
            tokens.append(Token("NUMBER", int(text), line))
        else:
            tokens.append(Token(kind, text, line))
        pos = m.end()
    tokens.append(Token("EOF", None, line))
    return tokens


if __name__ == "__main__":
    sample = 'x = 10;\ny = x + 5;\nprint(y);'
    for t in tokenize(sample):
        print(t)
