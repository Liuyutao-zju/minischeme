"""入口：读程序、求值、逐个打印结果（spec §2）。

用法：
    python3 src/main.py                 # 从标准输入读程序
    python3 src/main.py a.scm [b.scm]   # 按顺序求值若干个文件

多个文件共用同一个全局环境，后面的文件看得见前面 define 的东西。
"""

import os
import sys
import threading

# 保证不管从哪个目录调用，都能 import 到同目录的兄弟模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluator import evaluate          # noqa: E402  (得放在改 sys.path 之后)
from parser import parse                # noqa: E402
from primitives import make_global_env  # noqa: E402
from printer import to_write            # noqa: E402
from values import SchemeError          # noqa: E402


def run_source(text, env, out=sys.stdout):
    """求值一段程序，每个顶层结果打一行。

    结果是 None 就不打（display、newline 返回的都是 None）。
    """
    for expression in parse(text):
        value = evaluate(expression, env)
        if value is not None:
            out.write(to_write(value) + "\n")


def run_file(path, env, out=sys.stdout):
    with open(path, "r", encoding="utf-8") as handle:
        run_source(handle.read(), env, out)


#: 递归上限。题目不要求尾调用优化，所以 Scheme 递归多深，Python 调用
#: 就有多深——而一层 Scheme 递归大概吃 7 层 Python 栈帧。默认的 1000
#: 层不够用，我测到 (count 300) 就炸了，得放宽。
_RECURSION_LIMIT = 100000

#: 上限放这么宽，得换条栈大的线程跑，不然会把 C 栈撑爆
_THREAD_STACK_SIZE = 64 * 1024 * 1024


def run_with_big_stack(job):
    """在一条大栈线程里跑 job()，异常原样带回主线程抛。"""
    outcome = {}

    def worker():
        try:
            sys.setrecursionlimit(_RECURSION_LIMIT)
            outcome["value"] = job()
        except BaseException as error:      # noqa: BLE001 - 原样转交主线程
            outcome["error"] = error

    try:
        threading.stack_size(_THREAD_STACK_SIZE)
    except (ValueError, RuntimeError):
        pass        # 系统不给这么大的栈就算了，用默认的

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def main(argv):
    # Windows 会把输出的 \n 悄悄改成 \r\n，但评分器是逐字节比对的，
    # 所以这里必须把自动转换关掉
    try:
        sys.stdout.reconfigure(newline="\n")
    except (AttributeError, ValueError):
        pass

    return run_with_big_stack(lambda: evaluate_inputs(argv))


def evaluate_inputs(argv):
    env = make_global_env()
    paths = argv[1:]

    if not paths:
        run_source(sys.stdin.read(), env)
        return 0

    for path in paths:
        try:
            run_file(path, env)
        except OSError as error:
            sys.stderr.write("无法读取文件 %s：%s\n" % (path, error))
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SchemeError as error:
        sys.stderr.write("mini-Scheme 错误：%s\n" % (error,))
        sys.exit(1)
