"""语法分析：词列表 → 表达式（spec §3、§6）。

只做结构整理，不求值。

这里有个省事的地方：列表字面量直接建成点对链，跟 cons 造出来的
表示一模一样，所以 quote 拿到的就是普通数据，不用再转一层
（spec §6 最后一段说的就是这个）。
"""

from lexer import (BOOLEAN, DOT, EOF, LPAREN, NUMBER, QUOTE, RPAREN, STRING,
                   SYMBOL, tokenize)
from values import NIL, Pair, SchemeError, Symbol, make_list


class _Reader:
    """在词列表上移动的游标。"""

    __slots__ = ("tokens", "pos")

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def next(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token


def _read_expr(reader):
    token = reader.next()
    kind = token.kind

    if kind == EOF:
        raise SchemeError("程序意外结束：还有括号没有闭合")

    if kind == LPAREN:
        return _read_list(reader, token)

    if kind == RPAREN:
        raise SchemeError("第 %d 行第 %d 列：多出一个右括号" % (token.line, token.col))

    if kind == QUOTE:
        # 'x 就是 (quote x)，展开成列表让求值器统一处理
        return make_list([Symbol("quote"), _read_expr(reader)])

    if kind == DOT:
        raise SchemeError("第 %d 行第 %d 列：点号只能出现在列表内部" % (token.line, token.col))

    if kind == SYMBOL:
        return Symbol(token.value)

    # NUMBER / BOOLEAN / STRING 的词值本身就是最终值，直接拿走
    return token.value


def _read_list(reader, open_token):
    """读完一个 (...) 列表，返回点对链。"""
    items = []
    tail = NIL

    while True:
        token = reader.peek()

        if token.kind == EOF:
            raise SchemeError(
                "第 %d 行第 %d 列的左括号没有对应的右括号" % (open_token.line, open_token.col)
            )

        if token.kind == RPAREN:
            reader.next()
            break

        # (a . b)：点号后面是链尾，而且必须是这一层最后一个东西
        if token.kind == DOT:
            reader.next()
            tail = _read_expr(reader)
            closing = reader.next()
            if closing.kind != RPAREN:
                raise SchemeError("第 %d 行：点号后面只能再跟一个表达式" % (closing.line,))
            break

        items.append(_read_expr(reader))

    return make_list(items, tail)


def parse(text):
    """整段文本 → 顶层表达式列表。

    顶层有几个表达式，就决定最后要打印几行（spec §2）。
    """
    reader = _Reader(tokenize(text))
    expressions = []
    while reader.peek().kind != EOF:
        expressions.append(_read_expr(reader))
    return expressions


def parse_one(text):
    """只解析一个表达式，多了少了都报错（自测时用）。"""
    expressions = parse(text)
    if len(expressions) != 1:
        raise SchemeError("期望恰好一个表达式，实际有 %d 个" % len(expressions))
    return expressions[0]
