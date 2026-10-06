"""打印：值 → 文本（spec §8）。

两种写法要分开，这是"输出多一行/少一行"的根源（spec §11 有张表专门讲这个）：

* to_write    顶层结果用。字符串带引号，换行转义成 \\n 两个字符
* to_display  display 用。字符串直接原样输出，不加引号

注意 display 打印列表内部的字符串时也不带引号，所以 display 这个标志
得一路传到递归里去。
"""

from values import NIL, Pair, Procedure, Symbol, is_number

_ESCAPE_TABLE = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
}


def _escape_string(text):
    return "".join(_ESCAPE_TABLE.get(ch, ch) for ch in text)


def _pair_to_text(pair, display):
    """点对链 → "(a b c)" 或 "(a . b)"。

    写成循环不写递归，怕长列表把递归深度撑爆。
    """
    parts = []
    node = pair
    while isinstance(node, Pair):
        parts.append(to_str(node.car, display))
        node = node.cdr

    joined = " ".join(parts)
    if node is NIL:
        return "(" + joined + ")"
    # 链尾不是 () 说明是点对，得印成 (a . b)
    return "(" + joined + " . " + to_str(node, display) + ")"


def to_str(value, display=False):
    """把值转成文本。display=True 走 display 那套写法。"""
    # bool 必须排在 int 前面判断——Python 里 bool 是 int 的子类，
    # 顺序反了 True 会被当成数字 1 打出来
    if value is True:
        return "#t"
    if value is False:
        return "#f"

    if is_number(value):
        if isinstance(value, float):
            # 用 repr：0.5 打成 "0.5"，2.0 打成 "2.0"（不会变成整数 2）
            return repr(value)
        return str(value)

    if isinstance(value, Symbol):
        return value.name

    if isinstance(value, str):
        return value if display else '"' + _escape_string(value) + '"'

    if value is NIL:
        return "()"

    if isinstance(value, Pair):
        return _pair_to_text(value, display)

    if isinstance(value, Procedure):
        # 验收测试不依赖这个过程的具体格式，挑个常见的写法就行
        return "#<procedure>"

    if value is None:
        return ""

    return "#<unknown>"


def to_write(value):
    """顶层结果的写法（字符串带引号）。"""
    return to_str(value, display=False)


def to_display(value):
    """display 的写法（字符串不带引号）。"""
    return to_str(value, display=True)
