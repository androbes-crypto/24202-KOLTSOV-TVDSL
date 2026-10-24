from .lexer import Diagnostic, Token, lex, token_names
from .nodes import Node

STMT_START = {"LBRACE", "KW_VAR", "KW_IF", "KW_WHILE", "KW_ASSERT", "KW_ASSUME", "IDENT"}
SYNC_STMT = {"SEMI", "RBRACE", "LBRACE", "KW_VAR", "KW_IF", "KW_WHILE", "KW_ASSERT", "KW_ASSUME",
             "KW_FUNCTION"}
EXPR_START = {"INT", "KW_TRUE", "KW_FALSE", "KW_LENGTH", "IDENT", "LPAREN", "MINUS", "NOT"}
RELOPS = {"EQ", "NE", "LT", "LE", "GT", "GE"}
ADDOPS = {"PLUS", "MINUS"}
MULOPS = {"STAR", "SLASH", "PERCENT"}


class ParserLoop(RuntimeError):
    pass


class Parser:
    def __init__(self, tokens: list[Token], diagnostics: list[Diagnostic]):
        self.tokens = tokens
        self.i = 0
        self.diags = diagnostics
        self.names = token_names()
        self.panic = False
        self.error_at = -1
        self.steps = 0
        self.max_steps = 500 * (len(tokens) + 10)

    def peek(self) -> Token:
        self.steps += 1
        if self.steps > self.max_steps:
            raise ParserLoop("парсер не продвигается по входу")
        return self.tokens[self.i]

    def at(self, *kinds) -> bool:
        return self.peek().kind in kinds

    def advance(self) -> Token:
        tok = self.peek()
        if tok.kind != "EOF":
            self.i += 1
        return tok

    def prev(self):
        return self.tokens[self.i - 1] if self.i > 0 else None

    def describe(self, tok: Token) -> str:
        if tok.kind == "EOF":
            return "файл закончился"
        if tok.kind == "IDENT":
            return f"найден идентификатор '{tok.lexeme}'"
        if tok.kind == "INT":
            return f"найдено число {tok.lexeme}"
        return f"найдено '{tok.lexeme}'"

    def error(self, tok: Token, message: str):
        if self.panic:
            return
        self.diags.append(Diagnostic(tok.line, tok.col, message))
        self.panic = True
        self.error_at = self.i

    def expected(self, what: str):
        tok = self.peek()
        self.error(tok, f"ожидалось {what}, но {self.describe(tok)}")

    def expect(self, kind: str, what: str = None):
        if self.at(kind):
            return self.advance()
        self.expected(what or self.names.get(kind, kind))
        return None

    def sync(self, kinds):
        while not self.at("EOF", *kinds):
            self.advance()
        self.panic = False

    def recover_statement(self):
        prev = self.prev()
        if self.i > self.error_at and prev is not None and prev.kind in ("SEMI", "RBRACE"):
            self.panic = False
            return
        self.sync(SYNC_STMT)
        if self.at("SEMI"):
            self.advance()

    def continue_if_statement_follows(self):
        if self.panic and self.at(*STMT_START):
            self.panic = False

    def program(self) -> Node:
        start = self.peek()
        functions = []
        if self.at("EOF"):
            self.error(start, "пустая программа: ожидалась хотя бы одна функция 'function'")
        while not self.at("EOF"):
            if self.at("KW_FUNCTION"):
                functions.append(self.function())
                self.panic = False
            else:
                self.expected("'function'")
                self.advance()
                self.sync({"KW_FUNCTION"})
        return Node("Program", start, functions=functions)

    def function(self) -> Node:
        kw = self.advance()
        name = self.expect("IDENT", "имя функции")
        self.expect("LPAREN")
        params = self.params()
        self.expect("RPAREN")
        self.expect("KW_RETURNS")
        if self.at("LPAREN"):
            self.advance()
            returns = self.params()
            self.expect("RPAREN")
        elif self.at("IDENT"):
            returns = self.params()
        else:
            self.expected("имя результата или '('")
            returns = []
        requires, ensures = [], []
        while self.at("KW_REQUIRES", "KW_ENSURES"):
            clause = self.advance()
            if self.at(*EXPR_START):
                (requires if clause.kind == "KW_REQUIRES" else ensures).append(self.expr())
        if self.panic:
            self.sync({"LBRACE", "KW_FUNCTION"})
        body = None
        if self.at("LBRACE"):
            body = self.block()
        else:
            self.expected("'{' (тело функции)")
        return Node("Function", kw, name=name.lexeme if name else None, params=params,
                    returns=returns, requires=requires, ensures=ensures, body=body)

    def params(self) -> list:
        params = []
        if self.at("IDENT"):
            params.append(self.param())
            while self.at("COMMA"):
                self.advance()
                params.append(self.param())
        return params

    def param(self) -> Node:
        name = self.expect("IDENT", "имя параметра")
        typ = None
        if self.at("COLON"):
            self.advance()
            typ = self.type_()
        return Node("Param", name, name=name.lexeme if name else None, type=typ)

    def type_(self):
        if self.at("KW_INT", "KW_BOOL"):
            base = self.advance().lexeme
        else:
            self.expected("тип 'int' или 'bool'")
            return None
        while self.at("LBRACKET"):
            self.advance()
            self.expect("RBRACKET")
            base += "[]"
        return base

    def block(self) -> Node:
        lb = self.expect("LBRACE")
        stmts = []
        while not self.at("RBRACE", "EOF", "KW_FUNCTION"):
            start = self.i
            stmt = self.statement()
            if stmt is not None:
                stmts.append(stmt)
            if self.panic:
                self.recover_statement()
            if self.i == start:
                self.advance()
        if self.at("RBRACE"):
            self.advance()
        elif lb is not None:
            self.panic = False
            self.expected(f"'}}' (блок открыт в {lb.line}:{lb.col})")
        return Node("Block", lb, stmts=stmts)

    def statement(self):
        tok = self.peek()
        kind = tok.kind
        if kind == "LBRACE":
            return self.block()
        if kind == "KW_VAR":
            return self.var_decl()
        if kind == "KW_IF":
            return self.if_stmt()
        if kind == "KW_WHILE":
            return self.while_stmt()
        if kind in ("KW_ASSERT", "KW_ASSUME"):
            self.advance()
            cond = self.expr()
            self.expect("SEMI")
            return Node("Assert" if kind == "KW_ASSERT" else "Assume", tok, cond=cond)
        if kind == "IDENT":
            return self.ident_statement()
        if kind == "KW_ELSE":
            self.error(tok, "'else' без соответствующего 'if'")
        else:
            self.expected("оператор")
        self.advance()
        while not self.at("EOF", "SEMI", "RBRACE", "KW_FUNCTION", *STMT_START):
            self.advance()
        if self.at("SEMI"):
            self.advance()
        self.panic = False
        return None

    def var_decl(self) -> Node:
        kw = self.advance()
        name = self.expect("IDENT", "имя переменной")
        typ = None
        if self.at("COLON"):
            self.advance()
            typ = self.type_()
        init = None
        if self.at("ASSIGN"):
            self.advance()
            init = self.expr()
        self.expect("SEMI")
        return Node("VarDecl", kw, name=name.lexeme if name else None, type=typ, init=init)

    def if_stmt(self) -> Node:
        kw = self.advance()
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        self.continue_if_statement_follows()
        then = self.statement()
        orelse = None
        if self.at("KW_ELSE"):
            self.advance()
            orelse = self.statement()
        return Node("If", kw, cond=cond, then=then, orelse=orelse)

    def while_stmt(self) -> Node:
        kw = self.advance()
        self.expect("LPAREN")
        cond = self.expr()
        self.expect("RPAREN")
        invariants = []
        while self.at("KW_INVARIANT"):
            self.advance()
            invariants.append(self.expr())
        self.continue_if_statement_follows()
        body = self.statement()
        return Node("While", kw, cond=cond, invariants=invariants, body=body)

    def ident_statement(self) -> Node:
        name = self.advance()
        if self.at("LPAREN"):
            call = self.call_rest(name)
            self.expect("SEMI")
            return Node("CallStmt", name, call=call)
        indices = []
        while self.at("LBRACKET"):
            self.advance()
            indices.append(self.expr())
            self.expect("RBRACKET")
        if not self.at("ASSIGN"):
            self.expected("'=' или '['" if indices else "'=', '[' или '('")
            return None
        eq = self.advance()
        value = self.expr()
        self.expect("SEMI")
        if not indices:
            return Node("Assign", name, target=name.lexeme, value=value)
        return Node("Assign", name, target=name.lexeme,
                    value=self.desugar_update(Node("Var", name, name=name.lexeme), indices, value, eq),
                    sugar="array-update")

    def desugar_update(self, array: Node, indices: list, value: Node, at: Token) -> Node:
        if not indices:
            return value
        index = indices[0]
        inner = self.desugar_update(Node("Index", at, array=array, index=index), indices[1:], value, at)
        return Node("Update", at, array=array, index=index, value=inner)

    def expr(self) -> Node:
        left = self.and_expr()
        while self.at("OR"):
            op = self.advance()
            left = Node("Binary", op, op=op.lexeme, left=left, right=self.and_expr())
        return left

    def and_expr(self) -> Node:
        left = self.cmp_expr()
        while self.at("AND"):
            op = self.advance()
            left = Node("Binary", op, op=op.lexeme, left=left, right=self.cmp_expr())
        return left

    def cmp_expr(self) -> Node:
        left = self.add_expr()
        if self.at(*RELOPS):
            op = self.advance()
            left = Node("Binary", op, op=op.lexeme, left=left, right=self.add_expr())
            if self.at(*RELOPS):
                bad = self.peek()
                self.error(bad, f"операторы сравнения не ассоциативны: '{op.lexeme}' и '{bad.lexeme}' "
                                f"подряд, используйте скобки или '&&'")
        return left

    def add_expr(self) -> Node:
        left = self.mul_expr()
        while self.at(*ADDOPS):
            op = self.advance()
            left = Node("Binary", op, op=op.lexeme, left=left, right=self.mul_expr())
        return left

    def mul_expr(self) -> Node:
        left = self.unary()
        while self.at(*MULOPS):
            op = self.advance()
            left = Node("Binary", op, op=op.lexeme, left=left, right=self.unary())
        return left

    def unary(self) -> Node:
        if self.at("MINUS", "NOT"):
            op = self.advance()
            return Node("Unary", op, op=op.lexeme, operand=self.unary())
        return self.postfix()

    def postfix(self) -> Node:
        node = self.primary()
        while self.at("LBRACKET"):
            lb = self.advance()
            index = self.expr()
            self.expect("RBRACKET")
            node = Node("Index", lb, array=node, index=index)
        return node

    def primary(self) -> Node:
        tok = self.peek()
        if tok.kind == "INT":
            self.advance()
            return Node("Int", tok, value=int(tok.lexeme))
        if tok.kind in ("KW_TRUE", "KW_FALSE"):
            self.advance()
            return Node("Bool", tok, value=tok.kind == "KW_TRUE")
        if tok.kind == "KW_LENGTH":
            self.advance()
            self.expect("LPAREN")
            array = self.expr()
            self.expect("RPAREN")
            return Node("Length", tok, array=array)
        if tok.kind == "IDENT":
            self.advance()
            if self.at("LPAREN"):
                return self.call_rest(tok)
            return Node("Var", tok, name=tok.lexeme)
        if tok.kind == "LPAREN":
            self.advance()
            inner = self.expr()
            self.expect("RPAREN", f"')' (скобка открыта в {tok.line}:{tok.col})")
            return inner
        self.expected("выражение")
        return Node("Error", tok)

    def call_rest(self, name: Token) -> Node:
        lp = self.advance()
        args = []
        if not self.at("RPAREN"):
            args.append(self.expr())
            while self.at("COMMA"):
                self.advance()
                args.append(self.expr())
        self.expect("RPAREN", f"')' (скобка открыта в {lp.line}:{lp.col})")
        return Node("Call", name, name=name.lexeme, args=args)


def parse_tokens(tokens: list[Token], diagnostics: list[Diagnostic]) -> Node:
    return Parser(tokens, diagnostics).program()


def parse(text: str) -> tuple[Node, list[Diagnostic]]:
    tokens, diags = lex(text)
    ast = parse_tokens(tokens, diags)
    return ast, sorted(diags, key=lambda d: (d.line, d.col))
