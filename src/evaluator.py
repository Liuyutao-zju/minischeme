"""求值器：表达式 → 值（spec §4、§9）。

两个函数互相递归，绕明白这个循环基本就懂解释器了：

    evaluate(表达式, 环境)
        符号      → 查环境
        括号表达式 → 先看是不是特殊形式，不是就当函数调用：
                     求值操作符和所有实参，然后交给 apply
        其它      → 数字/布尔/字符串/空表，自己就是自己的值

    apply_procedure(过程, 实参)
        内置过程 → 直接调
        用户函数 → 新建一层环境，把实参绑到参数名上，再回去求值函数体

evaluate 里遇到调用就跑去 apply，apply 执行函数体又跑回 evaluate。
"""

import printer
from env import Env
from values import (NIL, Builtin, Lambda, Pair, SchemeError, Symbol,
                    is_false, pair_to_list)


def evaluate(expr, env):
    """求值一个表达式。"""
    if isinstance(expr, Symbol):
        # 变量不带括号，直接查
        return env.lookup(expr.name)

    if isinstance(expr, Pair):
        head = expr.car
        if isinstance(head, Symbol):
            handler = _SPECIAL_FORMS.get(head.name)
            if handler is not None:
                return handler(expr, env)

        # 普通调用：操作符和实参都先求值，再调用（应用序）
        procedure = evaluate(head, env)
        arguments = [evaluate(item, env) for item in _operands(expr)]
        return apply_procedure(procedure, arguments)

    # 数字、布尔、字符串、空表都自求值
    return expr


def apply_procedure(procedure, arguments):
    """调用一个过程，实参已经求好值了。"""
    if isinstance(procedure, Builtin):
        return procedure.fn(arguments)

    if isinstance(procedure, Lambda):
        if len(arguments) != len(procedure.params):
            raise SchemeError(
                "参数个数不符：期望 %d 个，给了 %d 个"
                % (len(procedure.params), len(arguments))
            )
        # 新环境的外层挂到 procedure.env（定义处），不是当前 env（调用处）。
        # 这里写错闭包就废了，008/009 两组用例专门考这个
        bindings = {
            parameter.name: value
            for parameter, value in zip(procedure.params, arguments)
        }
        call_env = Env(parent=procedure.env, bindings=bindings)
        return evaluate_sequence(procedure.body, call_env)

    raise SchemeError("不是一个过程，无法调用：%s" % printer.to_write(procedure))


def evaluate_sequence(expressions, env):
    """一串表达式依次求值，返回最后一个的值（begin 就是这个语义）。

    空的话返回 None，也就是"无值不打印"。
    """
    result = None
    for expression in expressions:
        result = evaluate(expression, env)
    return result


def _operands(expr, who="函数调用"):
    """取出括号里除操作符以外的部分。要求是真列表。"""
    try:
        return pair_to_list(expr.cdr)
    except SchemeError:
        raise SchemeError("%s 的写法不对：%s" % (who, printer.to_write(expr)))


def _form_operands(expr, name):
    return _operands(expr, "特殊形式 %s" % name)


def _check_form(name, args, low, high=None):
    """检查特殊形式的参数个数。high 为 None 表示"至少 low 个"。"""
    count = len(args)
    if high is None:
        if count < low:
            raise SchemeError("%s: 至少需要 %d 部分，实际 %d 部分" % (name, low, count))
    elif not low <= count <= high:
        raise SchemeError("%s: 需要 %d~%d 部分，实际 %d 部分" % (name, low, high, count))


# ---------------------------------------------------------------------------
# 特殊形式（spec §4）。它们长得像函数调用，但求值顺序各不相同
# ---------------------------------------------------------------------------


def _sf_quote(expr, env):
    """(quote 数据)：原样返回，不求值。"""
    args = _form_operands(expr, "quote")
    _check_form("quote", args, 1, 1)
    return args[0]


def _sf_if(expr, env):
    """(if 测试 真分支 假分支?)：只走一个分支。"""
    args = _form_operands(expr, "if")
    _check_form("if", args, 2, 3)

    if not is_false(evaluate(args[0], env)):
        return evaluate(args[1], env)
    if len(args) == 3:
        return evaluate(args[2], env)
    return None      # 没有假分支就返回无值


def _sf_cond(expr, env):
    """(cond (测试 表达式...)...)：从上往下挑第一个成立的。"""
    for clause in _form_operands(expr, "cond"):
        parts = pair_to_list(clause)
        _check_form("cond 子句", parts, 1)

        test_expr = parts[0]
        # else 是兜底，别拿去求值
        if isinstance(test_expr, Symbol) and test_expr.name == "else":
            return evaluate_sequence(parts[1:], env)

        test_value = evaluate(test_expr, env)
        if not is_false(test_value):
            if len(parts) == 1:
                # 子句里啥也没写，就返回测试值本身（spec §4.3）
                return test_value
            return evaluate_sequence(parts[1:], env)

    return None


def _sf_and(expr, env):
    """(and ...)：碰到第一个 #f 就返回，后面的不执行。"""
    result = True
    for argument in _form_operands(expr, "and"):
        result = evaluate(argument, env)
        if is_false(result):
            return False
    return result        # 全为真就返回最后一个的值；(and) 是 #t


def _sf_or(expr, env):
    """(or ...)：碰到第一个非 #f 就返回它，后面的不执行。"""
    for argument in _form_operands(expr, "or"):
        result = evaluate(argument, env)
        if not is_false(result):
            return result
    return False         # (or) 是 #f


def _sf_define(expr, env):
    """(define 名 值) 或 (define (函数名 参数...) 体...)。

    返回被定义的那个符号，所以顶层会多打一行名字（spec §4.5）。
    """
    args = _form_operands(expr, "define")
    _check_form("define", args, 2)
    target = args[0]

    if isinstance(target, Symbol):
        _check_form("define", args, 2, 2)
        value = evaluate(args[1], env)
        env.define(target.name, value)
        return target

    if isinstance(target, Pair):
        # (define (f x) 体) 只是 (define f (lambda (x) 体)) 的简写
        name = target.car
        if not isinstance(name, Symbol):
            raise SchemeError("define: 函数名必须是符号")
        parameters = pair_to_list(target.cdr)
        for parameter in parameters:
            if not isinstance(parameter, Symbol):
                raise SchemeError("define: 参数名必须是符号")
        env.define(name.name, Lambda(parameters, args[1:], env))
        return name

    raise SchemeError("define: 第一个部分必须是符号或 (函数名 参数...)")


def _sf_lambda(expr, env):
    """(lambda (参数...) 体...)：造闭包，函数体现在不求值。"""
    args = _form_operands(expr, "lambda")
    _check_form("lambda", args, 2)
    parameters = pair_to_list(args[0])
    for parameter in parameters:
        if not isinstance(parameter, Symbol):
            raise SchemeError("lambda: 参数名必须是符号")
    return Lambda(parameters, args[1:], env)


def _sf_let(expr, env):
    """(let ((名 值)...) 体...)：绑定在 let 外面的环境里求值。"""
    args = _form_operands(expr, "let")
    _check_form("let", args, 2)

    pending = []
    for binding in pair_to_list(args[0]):
        parts = pair_to_list(binding)
        if len(parts) != 2 or not isinstance(parts[0], Symbol):
            raise SchemeError("let: 每个绑定都要写成 (名 表达式)")
        # 在 env（let 外层）里求值，所以绑定之间互相看不见——并行绑定。
        # 改成串行会让 010 那组用例挂掉
        pending.append((parts[0].name, evaluate(parts[1], env)))

    let_env = Env(parent=env)
    for name, value in pending:
        let_env.define(name, value)
    return evaluate_sequence(args[1:], let_env)


def _sf_begin(expr, env):
    """(begin ...)：依次求值，返回最后一个。"""
    return evaluate_sequence(_form_operands(expr, "begin"), env)


#: 特殊形式表。求值器里它们比函数调用先被认出来，所以就算用户
#: define 了同名的东西，也不会影响这些关键字。
_SPECIAL_FORMS = {
    "quote": _sf_quote,
    "if": _sf_if,
    "cond": _sf_cond,
    "and": _sf_and,
    "or": _sf_or,
    "define": _sf_define,
    "lambda": _sf_lambda,
    "let": _sf_let,
    "begin": _sf_begin,
}
