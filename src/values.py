"""解释器里各种值的表示。

单独抽一层，主要是想把"符号"和"字符串"彻底分开。Python 的 str / bool
跟 Scheme 的语义对不上（True == 1 这种事），混着用迟早出错。
"""


class SchemeError(Exception):
    """解释器自己抛的错。

    题目不考出错时的行为（spec §10），加这个只是让调试信息比
    Python 原生 traceback 好读一点。
    """


class Symbol:
    """符号：变量名、函数名。

    同名符号驻留成同一个对象，这样 eq? 直接按同一性比就行。
    """

    __slots__ = ("name",)

    _interned = {}

    def __new__(cls, name):
        found = cls._interned.get(name)
        if found is not None:
            return found
        self = super().__new__(cls)
        self.name = name
        cls._interned[name] = self
        return self

    def __repr__(self):
        return "Symbol(%r)" % (self.name,)


class _Nil:
    """空表 ()。做成单例，理由和 Symbol 一样。"""

    __slots__ = ()

    def __repr__(self):
        return "()"


#: () 是一个要打印出来的"值"，None 表示"没有值所以不打印"，两回事
NIL = _Nil()


class Pair:
    """点对。列表就是一串 Pair 串起来的。"""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        return "Pair(%r, %r)" % (self.car, self.cdr)


class Procedure:
    """过程。抽个基类只是为了让 procedure? 好判断。"""

    __slots__ = ()


class Builtin(Procedure):
    """内置过程。fn 收到的是已经求好值的参数列表。"""

    __slots__ = ("name", "fn")

    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def __repr__(self):
        return "#<builtin %s>" % (self.name,)


class Lambda(Procedure):
    """用户函数：参数名、函数体、定义时所在的环境。

    存 env 是实现词法作用域的关键——函数体求值时用的是定义处的环境，
    而不是调用处的。
    """

    __slots__ = ("params", "body", "env")

    def __init__(self, params, body, env):
        self.params = params          # list[Symbol]
        self.body = body              # list[表达式]
        self.env = env                # 定义时所在的环境

    def __repr__(self):
        return "#<lambda (%s)>" % (" ".join(p.name for p in self.params),)


def is_number(value):
    """是不是数字。

    bool 必须排掉：Python 里 bool 是 int 的子类，不排的话
    (number? #t) 会变成 #t。spec §11 专门点了这个坑。
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_false(value):
    """只有 #f 是假。0、()、"" 都算真（spec §4.4）。"""
    return value is False


def make_list(items, tail=NIL):
    """Python 列表 → 点对链，tail 是链尾。"""
    result = tail
    for item in reversed(items):
        result = Pair(item, result)
    return result


def pair_to_list(value):
    """点对链 → Python 列表。只接受真列表（以 () 结尾），否则报错。"""
    items = []
    node = value
    while isinstance(node, Pair):
        items.append(node.car)
        node = node.cdr
    if node is not NIL:
        raise SchemeError("期望一个真列表，但遇到点对结尾")
    return items


def is_proper_list(value):
    """(1 2 3) 是，(cons 1 2) 不是。"""
    node = value
    while isinstance(node, Pair):
        node = node.cdr
    return node is NIL
