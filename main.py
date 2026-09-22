#!/usr/bin/env python3
"""
小学四则运算题目生成与批改命令行程序
用法:
  生成题目: python main.py -n 10 -r 10
  批改答案: python main.py -e Exercises.txt -a Answers.txt
"""
import argparse
import random
import math
from fractions import Fraction
from pathlib import Path


# ============================================================
# 分数工具：支持自然数、真分数 a/b、带分数 n'a/b
# ============================================================
class Frac:
    """分数封装，内部用 Fraction 保证精确运算。"""

    def __init__(self, num: int = 0, den: int = 1):
        if den == 0:
            raise ZeroDivisionError("分母不能为零")
        g = math.gcd(num, den)
        self.numer = num // g
        self.denom = den // g
        if self.denom < 0:
            self.numer = -self.numer
            self.denom = -self.denom

    @classmethod
    def from_frac(cls, f: Fraction) -> "Frac":
        return cls(f.numerator, f.denominator)

    def to_frac(self) -> Fraction:
        return Fraction(self.numer, self.denom)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Frac):
            return NotImplemented
        return self.to_frac() == other.to_frac()

    def __repr__(self) -> str:
        return self.to_str()

    def to_str(self) -> str:
        """转为题目要求格式：5 / 3/5 / 2'3/8"""
        if self.denom == 1:
            return str(self.numer)
        if self.numer < 0:
            # 不应该出现负数结果（需求禁止），这里兜底
            return f"-{Frac(-self.numer, self.denom).to_str()}"
        int_part = self.numer // self.denom
        rem = self.numer % self.denom
        if int_part == 0:
            return f"{rem}/{self.denom}"
        return f"{int_part}'{rem}/{self.denom}"

    @staticmethod
    def parse(s: str) -> "Frac":
        """解析 '5' / '3/5' / '2'3/8' 三种格式。"""
        s = s.strip()
        if "'" in s:
            int_str, frac_str = s.split("'", 1)
            nu_s, de_s = frac_str.split("/", 1)
            iv = int(int_str)
            nu = int(nu_s)
            de = int(de_s)
            return Frac(iv * de + nu, de)
        if "/" in s:
            nu_s, de_s = s.split("/", 1)
            return Frac(int(nu_s), int(de_s))
        return Frac(int(s), 1)


# ============================================================
# 表达式 AST 节点
# ============================================================
class Node:
    """表达式树节点。val 不为 None 时是叶子（数字），否则是运算符节点。"""

    __slots__ = ("val", "op", "left", "right")

    def __init__(self, val: Frac = None, op: str = None,
                 left: "Node" = None, right: "Node" = None):
        self.val = val
        self.op = op
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.val is not None

    def evaluate(self) -> Frac:
        if self.is_leaf:
            return self.val
        l = self.left.evaluate().to_frac()
        r = self.right.evaluate().to_frac()
        if self.op == "+":
            res = l + r
        elif self.op == "-":
            res = l - r
        elif self.op == "×":
            res = l * r
        elif self.op == "÷":
            res = l / r
        else:
            raise ValueError(f"未知运算符: {self.op}")
        return Frac.from_frac(res)

    def infix(self) -> str:
        """生成中缀表达式字符串，必要时加括号。"""
        if self.is_leaf:
            return self.val.to_str()
        lt = self.left.infix()
        rt = self.right.infix()
        if not self.left.is_leaf:
            lt = f"({lt})"
        if not self.right.is_leaf:
            rt = f"({rt})"
        return f"{lt} {self.op} {rt}"

    def canonical_key(self) -> str:
        """归一化键：+ 和 × 左右可交换，用于去重。"""
        if self.is_leaf:
            return self.val.to_str()
        lk = self.left.canonical_key()
        rk = self.right.canonical_key()
        if self.op in ("+", "×"):
            if lk > rk:
                lk, rk = rk, lk
        return f"({lk}{self.op}{rk})"


# ============================================================
# 题目生成
# ============================================================
OPS = ["+", "-", "×", "÷"]


def gen_number(r: int) -> Node:
    """生成自然数或真分数（分母 <= r）。"""
    if random.random() < 0.45:
        # 自然数 [0, r-1]
        return Node(val=Frac(random.randint(0, r - 1), 1))
    # 真分数 num/den, 1 <= num < den <= r
    den = random.randint(2, r)
    num = random.randint(1, den - 1)
    return Node(val=Frac(num, den))


def gen_expr(op_count: int, r: int) -> Node:
    """递归生成有 op_count 个运算符的表达式。"""
    if op_count == 0:
        return gen_number(r)

    op = random.choice(OPS)
    left_ops = random.randint(0, op_count - 1)
    right_ops = op_count - 1 - left_ops
    left = gen_expr(left_ops, r)
    right = gen_expr(right_ops, r)

    # 约束1：减法结果不能为负 → 左 >= 右
    if op == "-":
        if left.evaluate().to_frac() < right.evaluate().to_frac():
            return gen_expr(op_count, r)

    # 约束2：除法结果必须是真分数（< 1 且不是整数）
    if op == "÷":
        rv = right.evaluate().to_frac()
        if rv == 0:
            return gen_expr(op_count, r)
        q = left.evaluate().to_frac() / rv
        if q >= 1 or q.denominator == 1:
            return gen_expr(op_count, r)

    return Node(op=op, left=left, right=right)


def generate(count: int, r: int):
    """生成 count 道不重复题目，返回 (题目列表, 答案列表)。"""
    problems = []
    answers = []
    seen = set()
    attempts = 0
    max_attempts = count * 300

    while len(problems) < count and attempts < max_attempts:
        op_num = random.randint(0, 3)  # 运算符 0~3 个
        node = gen_expr(op_num, r)
        key = node.canonical_key()
        if key in seen:
            attempts += 1
            continue
        seen.add(key)
        problems.append(node.infix() + " =")
        answers.append(node.evaluate().to_str())
        attempts += 1

    if len(problems) < count:
        print(f"警告：仅生成 {len(problems)} 道题（尝试 {attempts} 次后达到上限）")
    return problems, answers


# ============================================================
# 表达式解析器（递归下降）—— 替代 eval()，安全无副作用
# ============================================================
# 文法:
#   expr   ::= term (('+'|'-') term)*
#   term   ::= factor (('×'|'÷') factor)*
#   factor ::= NUMBER | '(' expr ')'

class Parser:
    def __init__(self, text: str):
        self.tokens = self._tokenize(text)
        self.pos = 0

    @staticmethod
    def _tokenize(s: str) -> list:
        """将表达式字符串切成 token 列表。"""
        tokens = []
        i = 0
        s = s.strip()
        while i < len(s):
            c = s[i]
            if c.isspace():
                i += 1
                continue
            if c in "()":
                tokens.append(c)
                i += 1
                continue
            if c in "+-×÷":
                tokens.append(c)
                i += 1
                continue
            # 数字（含 3/5, 2'3/8）
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] in "/'"):
                j += 1
            tokens.append(s[i:j])
            i = j
        return tokens

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _eat(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def parse(self) -> Node:
        node = self._expr()
        if self.pos < len(self.tokens):
            raise ValueError(f"多余字符: {self.tokens[self.pos:]}")
        return node

    def _expr(self) -> Node:
        node = self._term()
        while self._peek() in ("+", "-"):
            op = self._eat()
            right = self._term()
            node = Node(op=op, left=node, right=right)
        return node

    def _term(self) -> Node:
        node = self._factor()
        while self._peek() in ("×", "÷"):
            op = self._eat()
            right = self._factor()
            node = Node(op=op, left=node, right=right)
        return node

    def _factor(self) -> Node:
        t = self._peek()
        if t == "(":
            self._eat()  # (
            node = self._expr()
            if self._peek() != ")":
                raise ValueError("缺少右括号")
            self._eat()  # )
            return node
        # 数字
        self._eat()
        return Node(val=Frac.parse(t))


# ============================================================
# 批改
# ============================================================
def grade(ex_file: str, ans_file: str, out_file: str = "Grade.txt"):
    ex_path = Path(ex_file)
    ans_path = Path(ans_file)
    out_path = Path(out_file)

    ex_lines = [ln.strip() for ln in ex_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ans_lines = [ln.strip() for ln in ans_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    correct = []
    wrong = []

    for idx, line in enumerate(ex_lines):
        no = idx + 1
        # 提取题目文本: "1. 2 + 3 ="
        expr_text = line.split(".", 1)[1].strip().rstrip("=").strip()
        # 提取用户答案: "1. 5"
        user_text = ans_lines[idx].split(".", 1)[1].strip() if idx < len(ans_lines) else ""

        try:
            std_node = Parser(expr_text).parse()
            std_val = std_node.evaluate()
            user_val = Frac.parse(user_text)
        except Exception:
            wrong.append(no)
            continue

        if std_val == user_val:
            correct.append(no)
        else:
            wrong.append(no)

    def _fmt(lst):
        return "(" + ", ".join(str(x) for x in lst) + ")"

    out_path.write_text(
        f"Correct: {len(correct)} {_fmt(correct)}\n"
        f"Wrong: {len(wrong)} {_fmt(wrong)}\n",
        encoding="utf-8",
    )
    print(f"批改完成 → {out_path}")
    print(f"  正确: {len(correct)}  错误: {len(wrong)}")


# ============================================================
# 命令行入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="小学四则运算题目生成与批改工具",
        usage="python main.py -n 10 -r 10 | python main.py -e Ex.txt -a An.txt",
    )
    parser.add_argument("-n", type=int, help="生成题目数量")
    parser.add_argument("-r", type=int, help="数值范围上限（必须给定）")
    parser.add_argument("-e", type=str, help="题目文件路径（批改模式）")
    parser.add_argument("-a", type=str, help="答案文件路径（批改模式）")
    args = parser.parse_args()

    # 批改模式
    if args.e and args.a:
        grade(args.e, args.a)
        return

    # 生成模式：-r 必须给定
    if args.r is None:
        parser.print_help()
        print("\n错误：参数 -r 为必填项，请指定数值范围上限。")
        return
    if args.n is None:
        parser.print_help()
        print("\n错误：参数 -n 为必填项，请指定生成题目数量。")
        return
    if args.r < 1:
        print("错误：-r 必须 >= 1")
        return

    problems, answers = generate(args.n, args.r)

    Path("Exercises.txt").write_text(
        "\n".join(f"{i+1}. {p}" for i, p in enumerate(problems)) + "\n",
        encoding="utf-8",
    )
    Path("Answers.txt").write_text(
        "\n".join(f"{i+1}. {a}" for i, a in enumerate(answers)) + "\n",
        encoding="utf-8",
    )
    print(f"已生成 {len(problems)} 道题目 → Exercises.txt / Answers.txt")


if __name__ == "__main__":
    main()
