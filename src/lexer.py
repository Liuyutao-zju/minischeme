"""词法分析：程序文本 → 词（token）列表（spec §3）。

这层只认字符长什么样，不管结构。认不出来的一律当符号——这样任何
没被特殊处理的名字（比如 foo、list->vector）都能直接当变量用。
"""

from values import SchemeError

# token 种类。写成常量免得手滑拼错
LPAREN = "LPAREN"
RPAREN = "RPAREN"
QUOTE = "QUOTE"
DOT = "DOT"
NUMBER = "NUMBER"
BOOLEAN = "BOOLEAN"
STRING = "STRING"
SYMBOL = "SYMBOL"
EOF = "EOF"

_WHITESPACE = " \t\r\n\f\v"

#: 字符串里的转义（spec §3）
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r"}


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return "Token(%s, %r, %d:%d)" % (self.kind, self.value, self.line, self.col)


def _is_delimiter(ch):
    """能结束一个原子的字符。"""
    return ch in _WHITESPACE or ch in '()\'";'


def _read_string(text, i, line, col):
    """从开引号之后读到闭引号，返回 (字符串值, 新下标)。"""
    chars = []
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            if i + 1 >= n:
                raise SchemeError("第 %d 行：字符串以反斜杠结尾" % line)
            nxt = text[i + 1]
            chars.append(_ESCAPES.get(nxt, nxt))
            i += 2
            col += 2
            continue
        if ch == '"':
            return "".join(chars), i + 1
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
        chars.append(ch)
        i += 1
    raise SchemeError("第 %d 行：字符串缺少收尾的双引号" % line)


def _classify_atom(text):
    """一段不带分隔符的文本 → NUMBER / BOOLEAN / SYMBOL。

    注意 + 和 - 单独出现时是符号（就是加法减法那两个内置过程），
    只有后面跟着数字才算数的正负号。
    """
    if text == "#t":
        return BOOLEAN, True
    if text == "#f":
        return BOOLEAN, False

    # 去掉可能的正负号再看剩下的是不是数字
    body = text[1:] if text[:1] in "+-" else text
    if body.isdigit() and body:
        return NUMBER, int(text)

    # 浮点：只允许一个小数点，且不能光是一个点
    if body.count(".") == 1:
        head, _, tail = body.partition(".")
        if (head.isdigit() or head == "") and (tail.isdigit() or tail == "") and (head or tail):
            return NUMBER, float(text)

    return SYMBOL, text


def tokenize(text):
    """程序文本 → 词列表。末尾补一个 EOF，方便后面判断"读完了"。"""
    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(text)

    while i < n:
        ch = text[i]

        if ch in _WHITESPACE:
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1
            continue

        # 注释：; 一直吃到行尾
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "(":
            tokens.append(Token(LPAREN, "(", line, col))
            i += 1
            col += 1
            continue
        if ch == ")":
            tokens.append(Token(RPAREN, ")", line, col))
            i += 1
            col += 1
            continue
        if ch == "'":
            tokens.append(Token(QUOTE, "'", line, col))
            i += 1
            col += 1
            continue

        if ch == '"':
            value, i = _read_string(text, i + 1, line, col)
            tokens.append(Token(STRING, value, line, col))
            col += len(value) + 2
            continue

        # 点号只有"前后都是分隔符"时才算点对的点，
        # 不然 3.14 这种浮点数会被从中间切开
        if ch == "." and (i + 1 >= n or _is_delimiter(text[i + 1])):
            tokens.append(Token(DOT, ".", line, col))
            i += 1
            col += 1
            continue

        # 剩下的都是原子：一直读到分隔符为止
        start = i
        start_col = col
        while i < n and not _is_delimiter(text[i]):
            i += 1
        atom = text[start:i]
        col += i - start
        kind, value = _classify_atom(atom)
        tokens.append(Token(kind, value, line, start_col))

    tokens.append(Token(EOF, None, line, col))
    return tokens
