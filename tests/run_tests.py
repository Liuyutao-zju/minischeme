"""自测：把 spec.md 的每一个特性都用一个程序验证一遍。

为什么要有这个文件：评分器的用例只是"底线"，README 明确说了
"通过自测 != 满分"。所以这里按 spec 的章节逐条造用例，覆盖
评分器没有触及的细节（点对结尾的打印、锚定 else、并行绑定、
转义字符、负数整除、多文件共享环境……）。

运行：
    python3 tests/run_tests.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "src", "main.py")

# (说明, 程序文本, 期望的标准输出)
CASES = [
    # ---------- §1 前缀表达式与求值顺序 ----------
    ("嵌套求值由内向外", "(* (+ 1 2) 3)", "9\n"),
    ("多参数减法从左往右", "(- 10 4 1)", "5\n"),

    # ---------- §3 词法 ----------
    ("注释被忽略", "(+ 1 2) ; 这一段不算\n", "3\n"),
    ("大小写敏感", "(define foo 1) (define FOO 2) (+ foo FOO)", "foo\nFOO\n3\n"),
    ("负数字面量", "(+ -7 2)", "-5\n"),
    ("浮点字面量", "(+ 1.5 2.5)", "4.0\n"),
    ("布尔字面量", "#t #f", "#t\n#f\n"),

    # ---------- §4.1 quote ----------
    ("quote 符号", "'x", "x\n"),
    ("quote 列表", "'(1 2 3)", "(1 2 3)\n"),
    ("quote 空表", "'()", "()\n"),
    ("quote 不递归求值", "'(+ 1 2)", "(+ 1 2)\n"),
    ("长写法 quote", "(quote (a b))", "(a b)\n"),

    # ---------- §4.2 if ----------
    ("if 真分支", "(if (> 3 2) 'yes 'no)", "yes\n"),
    ("if 假分支", "(if (< 3 2) 'yes 'no)", "no\n"),
    ("if 省略假分支且为假 → 无值不打印", "(if #f 1)", ""),
    ("if 只走一个分支（另一支会报错也不影响）",
     "(if #t 1 (undefined-name-here))", "1\n"),

    # ---------- §4.3 cond ----------
    ("cond 命中第二个子句", "(cond ((= 1 2) 'a) ((= 2 2) 'b) (else 'c))", "b\n"),
    ("cond 只有 else", "(cond (else 'd))", "d\n"),
    ("cond 子句无表达式时返回测试值", "(cond ((+ 1 2)))", "3\n"),
    ("cond 全部不匹配 → 无值", "(cond ((= 1 2) 'a))", ""),
    ("cond 子句按 begin 语义", "(cond (else 1 2 3))", "3\n"),

    # ---------- §4.4 and / or ----------
    ("and 短路不执行后面的表达式", "(and #f (car '()))", "#f\n"),
    ("or 短路不执行后面的表达式", "(or #t (car '()))", "#t\n"),
    ("and 返回最后一个值", "(and 1 2 3)", "3\n"),
    ("or 返回第一个真值", "(or #f 5 6)", "5\n"),
    ("(and) 为真", "(and)", "#t\n"),
    ("(or) 为假", "(or)", "#f\n"),
    ("0 与 () 都是真", "(if 0 'a 'b) (if '() 'c 'd)", "a\nc\n"),

    # ---------- §4.5 define ----------
    ("define 返回符号名", "(define pi 3)", "pi\n"),
    ("define 后可用", "(define pi 3) (+ pi 1)", "pi\n4\n"),
    ("define 函数简写", "(define (square x) (* x x)) (square 7)", "square\n49\n"),
    ("define 零参数函数", "(define (f) 42) (f)", "f\n42\n"),
    ("define 覆盖旧绑定", "(define x 1) (define x 2) x", "x\nx\n2\n"),

    # ---------- §4.6 lambda ----------
    ("立即调用的 lambda", "((lambda (x) (* x 2)) 5)", "10\n"),
    ("零参数 lambda", "((lambda () 7))", "7\n"),
    ("多参数 lambda", "((lambda (a b c) (+ a b c)) 1 2 3)", "6\n"),
    ("lambda 体多表达式", "((lambda (x) (define y 1) (+ x y)) 5)", "6\n"),

    # ---------- §4.7 let ----------
    ("let 基本用法", "(let ((x 3) (y 4)) (+ x y))", "7\n"),
    ("let 嵌套可见外层", "(let ((a 1)) (let ((b (+ a 1))) (* a b)))", "2\n"),
    ("let 是并行绑定（互不可见）", "(let ((x 3) (y 4)) (let ((x 5)) (+ x y)))", "9\n"),
    ("let 重复名字后者生效", "(let ((x 1) (x 2)) x)", "2\n"),
    ("let 体多表达式", "(let ((x 1)) 10 20 (+ x 100))", "101\n"),
    ("let 不污染外层", "(define x 1) (let ((x 99)) x) x", "x\n99\n1\n"),

    # ---------- §4.8 begin ----------
    ("begin 只打印最终值（内部 define 不算顶层结果）",
     "(begin (define z 1) (+ z 41))", "42\n"),
    ("begin 内部的 define 对后面仍可见",
     "(begin (define t 5) 0) t", "0\n5\n"),

    # ---------- §5 算术 ----------
    ("加法可变参数", "(+ 1 2 3 4)", "10\n"),
    ("(+) 为 0", "(+)", "0\n"),
    ("(*) 为 1", "(*)", "1\n"),
    ("单参数取反", "(- 5)", "-5\n"),
    ("整数相除截断（正）", "(/ 7 2)", "3\n"),
    ("整数相除向零截断（负）", "(/ -7 2)", "-3\n"),
    ("整除商向零截断（负）", "(quotient -7 2)", "-3\n"),
    ("整数相除不产生小数", "(/ 1 2)", "0\n"),
    ("单参数取倒数是浮点", "(/ 2)", "0.5\n"),
    ("三个参数连除", "(/ 100 5 2)", "10\n"),
    ("modulo 结果跟除数同号", "(modulo -7 5)", "3\n"),
    ("modulo 基础", "(modulo 17 5)", "2\n"),
    ("expt", "(expt 2 10)", "1024\n"),
    ("abs", "(abs (- 5 9))", "4\n"),

    # ---------- §5 比较 ----------
    ("= 数字", "(= 1 1)", "#t\n"),
    ("= 符号", "(= 'a 'a)", "#t\n"),
    ("链式比较全真", "(< 2 3 4)", "#t\n"),
    ("链式比较有一处不成立", "(< 2 4 3)", "#f\n"),
    (">= 边界", "(>= 6 6 6)", "#t\n"),
    ("<= 边界", "(<= 4 4)", "#t\n"),

    # ---------- §5 布尔 ----------
    ("not 假", "(not #f)", "#t\n"),
    ("not 真", "(not #t)", "#f\n"),
    ("not 对非布尔：0 是真", "(not 0)", "#f\n"),
    ("not 对空表：() 是真", "(not '())", "#f\n"),

    # ---------- §5 / §6 列表 ----------
    ("car", "(car '(1 2 3))", "1\n"),
    ("cdr", "(cdr '(1 2 3))", "(2 3)\n"),
    ("cons 到链头", "(cons 1 '(2 3))", "(1 2 3)\n"),
    ("cons 造点对", "(cons 1 2)", "(1 . 2)\n"),
    ("点对嵌在列表尾部", "(cons 1 (cons 2 3))", "(1 2 . 3)\n"),
    ("list", "(list 1 2 3)", "(1 2 3)\n"),
    ("空 list", "(list)", "()\n"),
    ("length", "(length '(a b c d))", "4\n"),
    ("length 空表", "(length '())", "0\n"),
    ("append 两个", "(append '(1 2) '(3 4))", "(1 2 3 4)\n"),
    ("append 三个含空表", "(append '(1) '() '(2 3))", "(1 2 3)\n"),
    ("append 无参数", "(append)", "()\n"),
    ("null? 空表", "(null? '())", "#t\n"),
    ("null? 非空", "(null? '(1))", "#f\n"),
    ("pair? 点对", "(pair? '(1 2))", "#t\n"),
    ("pair? 空表", "(pair? '())", "#f\n"),
    ("pair? 原子", "(pair? 1)", "#f\n"),
    ("list? 真列表", "(list? '(1 2))", "#t\n"),
    ("list? 点对不是列表", "(list? (cons 1 2))", "#f\n"),
    ("list? 空表", "(list? '())", "#t\n"),
    ("嵌套列表打印", "'(a (b c) (d (e)))", "(a (b c) (d (e)))\n"),
    ("嵌套列表用 list 构造", "(list 1 (list 2 3))", "(1 (2 3))\n"),

    # ---------- §5 谓词 ----------
    ("number? 是", "(number? 5)", "#t\n"),
    ("number? 否", "(number? 'x)", "#f\n"),
    ("number? 对 #t 应是假", "(number? #t)", "#f\n"),
    ("boolean?", "(boolean? #f)", "#t\n"),
    ("symbol?", "(symbol? 'x)", "#t\n"),
    ("string?", '(string? "s")', "#t\n"),
    ("symbol? 对字符串应是假", '(symbol? "s")', "#f\n"),
    ("string? 对符号应是假", "(string? 's)", "#f\n"),
    ("procedure? 内置", "(procedure? car)", "#t\n"),
    ("procedure? 用户函数", "(procedure? (lambda (x) x))", "#t\n"),
    ("procedure? 非过程", "(procedure? 1)", "#f\n"),
    ("zero?/even?/odd?", "(zero? 0) (even? 8) (odd? 7)", "#t\n#t\n#t\n"),
    ("even? 对 0", "(even? 0)", "#t\n"),

    # ---------- §5 eq? / equal? ----------
    ("eq? 空表按同一性", "(eq? '() '())", "#t\n"),
    ("eq? 列表按同一性", "(eq? '(1) '(1))", "#f\n"),
    ("eq? 数字按值", "(eq? 3 3)", "#t\n"),
    ("eq? 符号按值", "(eq? 'a 'a)", "#t\n"),
    ("eq? 同一对象为真", "(define l '(1 2)) (eq? l l)", "l\n#t\n"),
    ("equal? 结构相等", "(equal? '(1 2 3) (list 1 2 3))", "#t\n"),
    ("equal? 嵌套结构", "(equal? '(1 (2 3)) (list 1 (list 2 3)))", "#t\n"),
    ("equal? 不等", "(equal? '(1 2) '(1 3))", "#f\n"),
    ("equal? #t 与 1 不等", "(equal? #t 1)", "#f\n"),
    ("equal? 符号与字符串不等", '(equal? \'a "a")', "#f\n"),

    # ---------- §5 输出 ----------
    ("display 数字不换行", "(display 3)", "3"),
    ("display 后接 newline", "(display 3) (newline)", "3\n"),
    ("display 字符串不带引号", '(display "hi")', "hi"),
    ("display 列表", "(display '(a (b c)))", "(a (b c))"),
    ("display 列表里的字符串不带引号", '(display (list "a" "b"))', "(a b)"),
    ("顶层字符串带引号", '"hello"', '"hello"\n'),
    ("顶层字符串转义换行", '"a\\nb"', '"a\\nb"\n'),
    ("顶层字符串转义制表符", '"a\\tb"', '"a\\tb"\n'),
    ("顶层字符串转义引号", '"a\\"b"', '"a\\"b"\n'),
    ("顶层字符串转义反斜杠", '"a\\\\b"', '"a\\\\b"\n'),
    ("display 的返回值不打印", '(display 1) (display 2)', "12"),
    ("newline 的返回值不打印", "(newline)", "\n"),

    # ---------- §7 递归与闭包 ----------
    ("阶乘", "(define (fact n) (if (= n 0) 1 (* n (fact (- n 1))))) (fact 10)",
     "fact\n3628800\n"),
    ("闭包记住定义时的环境",
     "(define (make-adder n) (lambda (x) (+ x n)))\n"
     "(define add3 (make-adder 3))\n"
     "(add3 5)\n"
     "((make-adder 10) 7)",
     "make-adder\nadd3\n8\n17\n"),
    ("两层闭包",
     "(define (outer a) (lambda (b) (lambda (c) (+ a b c))))\n"
     "(((outer 1) 2) 3)",
     "outer\n6\n"),
    ("用语言本身定义 map",
     "(define (map f xs) (if (null? xs) '() (cons (f (car xs)) (map f (cdr xs)))))\n"
     "(map (lambda (x) (* x x)) '(1 2 3 4))",
     "map\n(1 4 9 16)\n"),
    ("较深的递归（300 层）",
     "(define (count n) (if (= n 0) 0 (+ 1 (count (- n 1))))) (count 300)",
     "count\n300\n"),
    ("很深的递归（1000 层）",
     "(define (count n) (if (= n 0) 0 (+ 1 (count (- n 1))))) (count 1000)",
     "count\n1000\n"),

    # ---------- §8 打印 ----------
    ("过程打印为 #<procedure>", "(procedure? car)", "#t\n"),
    ("整数打印", "42", "42\n"),
    ("浮点打印", "(/ 2)", "0.5\n"),
    ("符号打印", "'foo", "foo\n"),
    ("布尔打印", "#t", "#t\n"),

    # ---------- 其它：多文件共享环境（在 test_multifile 里单独测） ----------
]


def run_program(program):
    """把程序喂给 src/main.py 的标准输入，返回进程结果。

    这里显式指定 utf-8，是为了让"写进去"和"读出来"用同一种编码。
    （解释器本身仍按系统默认编码读写标准流——那才是评分器预期的行为，
    因为 autograder 也是用默认编码和子进程通信的。）
    """
    proc = subprocess.run(
        [sys.executable, MAIN],
        input=program,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return proc


def main():
    passed = 0
    failures = []

    for name, program, expected in CASES:
        proc = run_program(program)
        if proc.returncode != 0:
            failures.append((name, "退出码 %s\n     stderr: %s"
                             % (proc.returncode, proc.stderr.strip())))
            continue
        if proc.stdout != expected:
            failures.append((name, "期望 %r\n     实得 %r"
                             % (expected, proc.stdout)))
            continue
        passed += 1

    # 多文件共享同一个全局环境（spec §2）
    import shutil
    folder = os.path.join(ROOT, "tests", "_tmp_multifile")
    try:
        os.makedirs(folder, exist_ok=True)
        first = os.path.join(folder, "a.scm")
        second = os.path.join(folder, "b.scm")
        with open(first, "w", encoding="utf-8") as handle:
            handle.write("(define shared 41)\n")
        with open(second, "w", encoding="utf-8") as handle:
            handle.write("(+ shared 1)\n")
        proc = subprocess.run(
            [sys.executable, MAIN, first, second],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if proc.returncode == 0 and proc.stdout == "shared\n42\n":
            passed += 1
        else:
            failures.append(("多文件共享全局环境",
                             "期望 'shared\\n42\\n'，实得 %r（stderr: %s）"
                             % (proc.stdout, proc.stderr.strip())))
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    total = len(CASES) + 1
    print("自测结果：%d / %d 通过" % (passed, total))
    if failures:
        print()
        for name, detail in failures:
            print("  FAIL  " + name)
            print("        " + detail)
        return 1
    print("spec 的各项特性全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
