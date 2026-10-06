"""内置过程：spec §5 里的全部标准函数。

和特殊形式相反，这些函数的参数**先全部求值再调用**，每个函数收到
一个已经求好值的列表。

文件名用 primitives 不用 builtins，是怕跟 Python 自带的 builtins 撞名。
"""

import sys

import printer
from values import (NIL, Builtin, Pair, Procedure, SchemeError, Symbol,
                    is_number, is_proper_list, make_list, pair_to_list)

# --------------------------------------------------------------------------
# 参数检查的小工具
# --------------------------------------------------------------------------


def _arity(who, args, low, high=None):
    """查参数个数。high 给 None 就是"至少 low 个"。"""
    count = len(args)
    if high is None:
        if count < low:
            raise SchemeError("%s: 至少需要 %d 个参数，实际给了 %d 个" % (who, low, count))
    elif not low <= count <= high:
        raise SchemeError("%s: 需要 %d~%d 个参数，实际给了 %d 个" % (who, low, high, count))


def _number(who, value):
    if not is_number(value):
        raise SchemeError("%s: 期望数字，得到 %s" % (who, printer.to_write(value)))
    return value


def _numbers(who, args):
    return [_number(who, value) for value in args]


def _pair(who, value):
    if not isinstance(value, Pair):
        raise SchemeError("%s: 期望非空点对，得到 %s" % (who, printer.to_write(value)))
    return value


def _list(who, value):
    if not is_proper_list(value):
        raise SchemeError("%s: 期望一个真列表，得到 %s" % (who, printer.to_write(value)))
    return value


# --------------------------------------------------------------------------
# 算术
# --------------------------------------------------------------------------


def _truncating_quotient(a, b):
    """整数除法，商向零截断：7/2 = 3，-7/2 = -3。

    不能直接用 Python 的 //，它是向下取整，-7 // 2 会得到 -4，
    跟 spec §5 要的不一样。所以先取绝对值除，再补符号。
    """
    if b == 0:
        raise SchemeError("除数为 0")
    quotient = abs(a) // abs(b)
    return quotient if (a < 0) == (b < 0) else -quotient


def _add(args):
    return sum(_numbers("+", args))


def _subtract(args):
    numbers = _numbers("-", args)
    _arity("-", args, 1)
    if len(numbers) == 1:
        return -numbers[0]     # 一个参数就是取反
    result = numbers[0]
    for value in numbers[1:]:
        result -= value
    return result


def _multiply(args):
    result = 1
    for value in _numbers("*", args):
        result *= value
    return result


def _divide(args):
    numbers = _numbers("/", args)
    _arity("/", args, 1)
    if len(numbers) == 1:
        # 一个参数是求倒数，按 spec 得返回浮点
        if numbers[0] == 0:
            raise SchemeError("/: 除数为 0")
        return 1 / numbers[0]

    # 只要有一个浮点，整条链就都按浮点算
    if any(isinstance(value, float) for value in numbers):
        result = numbers[0]
        for value in numbers[1:]:
            if value == 0:
                raise SchemeError("/: 除数为 0")
            result /= value
        return result

    # 全是整数就一路向零截断，(7 2) 得 3 而不是 3.5
    result = numbers[0]
    for value in numbers[1:]:
        result = _truncating_quotient(result, value)
    return result


def _modulo(args):
    _arity("modulo", args, 2, 2)
    a, b = _numbers("modulo", args)
    if b == 0:
        raise SchemeError("modulo: 除数为 0")
    return a % b        # Python 的 % 符号跟着除数走，正好和 spec 一致


def _quotient(args):
    _arity("quotient", args, 2, 2)
    a, b = _numbers("quotient", args)
    return _truncating_quotient(a, b)


def _expt(args):
    _arity("expt", args, 2, 2)
    base, power = _numbers("expt", args)
    return base ** power


def _absolute(args):
    _arity("abs", args, 1, 1)
    return abs(_number("abs", args[0]))


# --------------------------------------------------------------------------
# 比较。这几个都是链式的，相邻两个都成立才算真：(< 2 3 4) 是 #t
# --------------------------------------------------------------------------


def _ordered_pair(who, a, b):
    """把两个参数弄成能比的东西。数字和符号都支持（spec §5）。"""
    if is_number(a) and is_number(b):
        return a, b
    if isinstance(a, Symbol) and isinstance(b, Symbol):
        return a.name, b.name
    raise SchemeError(
        "%s: 参数类型不一致（%s 和 %s）"
        % (who, printer.to_write(a), printer.to_write(b))
    )


def _chain(who, compare):
    """把一个二元比较包成链式的。"""
    def builtin(args):
        _arity(who, args, 2)
        for left, right in zip(args, args[1:]):
            a, b = _ordered_pair(who, left, right)
            if not compare(a, b):
                return False
        return True

    return builtin


def _atomic_equal(a, b):
    """= 用的相等判断：数字按值，符号按名字，布尔按值。"""
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, bool) and isinstance(b, bool):
        return a is b
    if isinstance(a, Symbol) and isinstance(b, Symbol):
        return a.name == b.name
    raise SchemeError("=: 不支持的参数类型")


def _numeric_equal(args):
    _arity("=", args, 2)
    for left, right in zip(args, args[1:]):
        if not _atomic_equal(left, right):
            return False
    return True


# --------------------------------------------------------------------------
# 布尔
# --------------------------------------------------------------------------


def _not(args):
    _arity("not", args, 1, 1)
    return args[0] is False    # 只有 #f 取反才对，0 和 () 都不算


# --------------------------------------------------------------------------
# 列表（spec §6）
# --------------------------------------------------------------------------


def _cons(args):
    _arity("cons", args, 2, 2)
    return Pair(args[0], args[1])


def _car(args):
    _arity("car", args, 1, 1)
    return _pair("car", args[0]).car


def _cdr(args):
    _arity("cdr", args, 1, 1)
    return _pair("cdr", args[0]).cdr


def _list_builtin(args):
    return make_list(args)


def _length(args):
    _arity("length", args, 1, 1)
    return len(pair_to_list(_list("length", args[0])))


def _append(args):
    """把前面几个列表接起来，最后一个直接当尾巴，(append) 得 ()。"""
    if not args:
        return NIL
    result = args[-1]
    for value in reversed(args[:-1]):
        items = pair_to_list(_list("append", value))
        for item in reversed(items):
            result = Pair(item, result)
    return result


def _is_null(args):
    _arity("null?", args, 1, 1)
    return args[0] is NIL


def _is_pair(args):
    _arity("pair?", args, 1, 1)
    return isinstance(args[0], Pair)


def _is_list(args):
    _arity("list?", args, 1, 1)
    return is_proper_list(args[0])


# --------------------------------------------------------------------------
# 谓词
# --------------------------------------------------------------------------


def _make_type_predicate(name, test):
    def builtin(args):
        _arity(name, args, 1, 1)
        return test(args[0])

    return builtin


def _make_numeric_predicate(name, test):
    def builtin(args):
        _arity(name, args, 1, 1)
        return test(_number(name, args[0]))

    return builtin


def _is_eq(a, b):
    """eq?：符号、数字、布尔按值比，别的按同一性比。

    所以 (eq? '() '()) 是 #t（单例），(eq? '(1) '(1)) 是 #f
    （两个不同的 Pair）。结构比较是 equal? 的活，别搞混。
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, Symbol) and isinstance(b, Symbol):
        return a.name == b.name
    if a is NIL and b is NIL:
        return True
    return a is b


def _is_equal(a, b):
    """equal?：一层层比结构。

    每种类型前面都要先判类型再比值，不能图省事直接 a == b：
    Python 里 (equal? #t 1) 会变成 True，而 (equal? 'a "a") 也会
    变成 True（符号和字符串在 Python 侧太像了）。spec §11 都点过。
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if is_number(a) and is_number(b):
        return a == b
    if is_number(a) or is_number(b):
        return False
    if isinstance(a, Symbol) and isinstance(b, Symbol):
        return a.name == b.name
    if isinstance(a, Symbol) or isinstance(b, Symbol):
        return False
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, str) or isinstance(b, str):
        return False
    if a is NIL and b is NIL:
        return True
    if a is NIL or b is NIL:
        return False
    if isinstance(a, Pair) and isinstance(b, Pair):
        return _is_equal(a.car, b.car) and _is_equal(a.cdr, b.cdr)
    if isinstance(a, Pair) or isinstance(b, Pair):
        return False
    return a is b


def _eq(args):
    _arity("eq?", args, 2, 2)
    return _is_eq(args[0], args[1])


def _equal(args):
    _arity("equal?", args, 2, 2)
    return _is_equal(args[0], args[1])


# --------------------------------------------------------------------------
# 输出。这两个直接写 stdout 并返回 None，所以顶层不会多打一行
# --------------------------------------------------------------------------


def _display(args):
    _arity("display", args, 1, 1)
    sys.stdout.write(printer.to_display(args[0]))
    return None


def _newline(args):
    _arity("newline", args, 0, 0)
    sys.stdout.write("\n")
    return None


# --------------------------------------------------------------------------
# 组装初始环境
# --------------------------------------------------------------------------

_BUILTIN_TABLE = {
    # 算术
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "modulo": _modulo,
    "quotient": _quotient,
    "expt": _expt,
    "abs": _absolute,
    # 比较
    "=": _numeric_equal,
    "<": _chain("<", lambda a, b: a < b),
    ">": _chain(">", lambda a, b: a > b),
    "<=": _chain("<=", lambda a, b: a <= b),
    ">=": _chain(">=", lambda a, b: a >= b),
    # 布尔
    "not": _not,
    # 列表
    "cons": _cons,
    "car": _car,
    "cdr": _cdr,
    "list": _list_builtin,
    "length": _length,
    "append": _append,
    "null?": _is_null,
    "pair?": _is_pair,
    "list?": _is_list,
    # 谓词
    "number?": _make_type_predicate("number?", is_number),
    "boolean?": _make_type_predicate("boolean?", lambda v: isinstance(v, bool)),
    "symbol?": _make_type_predicate("symbol?", lambda v: isinstance(v, Symbol)),
    "string?": _make_type_predicate("string?", lambda v: isinstance(v, str)),
    "procedure?": _make_type_predicate("procedure?", lambda v: isinstance(v, Procedure)),
    "zero?": _make_numeric_predicate("zero?", lambda v: v == 0),
    "even?": _make_numeric_predicate("even?", lambda v: v % 2 == 0),
    "odd?": _make_numeric_predicate("odd?", lambda v: v % 2 != 0),
    "eq?": _eq,
    "equal?": _equal,
    # 输出
    "display": _display,
    "newline": _newline,
}

#: 内置过程的名字，排序后导出，自测里遍历用
BUILTIN_NAMES = sorted(_BUILTIN_TABLE)


def make_global_env():
    """造一个装好全部内置过程的新环境。每个测试进程都从空环境开始。"""
    # 放在函数里 import 是躲循环依赖：primitives 要用 env，
    # 顶层 import 会绕成圈
    from env import Env

    global_env = Env()
    for name, function in _BUILTIN_TABLE.items():
        global_env.define(name, Builtin(name, function))
    return global_env
