"""环境：一层变量绑定 + 指向外层环境。

查变量先看自己这层，找不到就顺着 parent 往上找。词法作用域说到底
就是这么回事。
"""

from values import SchemeError


class Env:
    __slots__ = ("bindings", "parent")

    def __init__(self, parent=None, bindings=None):
        self.bindings = dict(bindings) if bindings else {}   # 名字 -> 值
        self.parent = parent

    def define(self, name, value):
        """在当前这层加一个绑定（define 用它）。"""
        self.bindings[name] = value
        return value

    def lookup(self, name):
        """顺着 parent 链往上找，找不到就报错。"""
        env = self
        while env is not None:
            if name in env.bindings:
                return env.bindings[name]
            env = env.parent
        raise SchemeError("未定义的符号：%s" % (name,))
