"""
parser.py
Module owner: PIYUSH MUNDHRA (24BCE2173) -- Frontend / Lexer & Parser
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

Recursive-descent parser that converts the lexer's token stream into an AST.
"""

from src.lexer import tokenize


# ROLE: Base class for all Abstract Syntax Tree (AST) nodes.
class Node:
    pass


# ROLE: Root AST node holding the sequence of all parsed statements.
class Program(Node):
    # ROLE: Initializes the Program node with its child statement nodes.
    def __init__(self, statements):
        self.statements = statements


# ROLE: AST node representing a variable assignment statement (e.g. x = expression;).
class Assign(Node):
    # ROLE: Initializes the assignment node with target variable name, RHS expression, and line number.
    def __init__(self, name, expr, line):
        self.name = name
        self.expr = expr
        self.line = line


# ROLE: AST node representing a print statement (e.g. print(expression);).
class Print(Node):
    # ROLE: Initializes the print node with the expression to be printed and line number.
    def __init__(self, expr, line):
        self.expr = expr
        self.line = line


# ROLE: AST node representing a binary operation (+ operator).
class BinOp(Node):
    # ROLE: Initializes the binary operator node with operator symbol, left operand, and right operand.
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


# ROLE: AST node representing a literal constant value (integer number or string).
class Literal(Node):
    # ROLE: Initializes the literal node with the scalar value and type tag ('INT' or 'STRING').
    def __init__(self, value, kind):
        self.value = value
        self.kind = kind  # 'INT' or 'STRING'


# ROLE: AST node representing a variable lookup by name.
class Var(Node):
    # ROLE: Initializes the variable node with the variable identifier name.
    def __init__(self, name):
        self.name = name


# ROLE: Custom exception raised when input tokens violate the toy-language grammar.
class ParseError(Exception):
    pass


# ROLE: Recursive-descent parser that transforms the token stream into a structured AST.
class Parser:
    # ROLE: Initializes the parser with the token list and resets the position pointer to 0.
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ROLE: Inspects the current token without consuming it.
    def peek(self):
        return self.tokens[self.pos]

    # ROLE: Consumes and returns the current token, advancing the pointer forward.
    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    # ROLE: Validates that the current token matches the expected type, then advances.
    def expect(self, type_):
        tok = self.peek()
        if tok.type != type_:
            raise ParseError(f"Expected {type_} but found {tok.type} ('{tok.value}') at line {tok.line}")
        return self.advance()

    # ROLE: Parses all statements until EOF and constructs the root Program node.
    def parse_program(self):
        statements = []
        while self.peek().type != "EOF":
            statements.append(self.parse_statement())
        return Program(statements)

    # ROLE: Identifies whether the next statement is an assignment or print, then parses it.
    def parse_statement(self):
        tok = self.peek()
        if tok.type == "ID":
            return self.parse_assignment()
        if tok.type == "PRINT":
            return self.parse_print()
        raise ParseError(f"Unexpected token {tok.type} at line {tok.line}")

    # ROLE: Parses an assignment statement grammar rule: ID '=' expr ';'.
    def parse_assignment(self):
        name_tok = self.expect("ID")
        self.expect("ASSIGN")
        expr = self.parse_expression()
        self.expect("SEMI")
        return Assign(name_tok.value, expr, name_tok.line)

    # ROLE: Parses a print statement grammar rule: 'print' '(' expr ')' ';'.
    def parse_print(self):
        line = self.peek().line
        self.expect("PRINT")
        self.expect("LPAREN")
        expr = self.parse_expression()
        self.expect("RPAREN")
        self.expect("SEMI")
        return Print(expr, line)

    # ROLE: Parses expressions with left-associative addition: term ('+' term)*.
    def parse_expression(self):
        node = self.parse_term()
        while self.peek().type == "PLUS":
            self.advance()
            right = self.parse_term()
            node = BinOp("+", node, right)
        return node

    # ROLE: Parses base terms: numeric literal, string literal, or variable reference.
    def parse_term(self):
        tok = self.peek()
        if tok.type == "NUMBER":
            self.advance()
            return Literal(tok.value, "INT")
        if tok.type == "STRING":
            self.advance()
            return Literal(tok.value, "STRING")
        if tok.type == "ID":
            self.advance()
            return Var(tok.value)
        raise ParseError(f"Unexpected token {tok.type} at line {tok.line}")


# ROLE: Main public parsing function: tokenizes raw code and returns the complete AST.
def parse(source: str) -> Program:
    return Parser(tokenize(source)).parse_program()


if __name__ == "__main__":
    prog = parse('x = 10;\ny = x + 5;\nprint(y);')
    print(f"Parsed {len(prog.statements)} statements successfully.")
