import json
import operator
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from random import choice, randint, shuffle
import re
from urllib.parse import parse_qs, urlsplit

from sympy import Rational
from worksheet import worksheet_pdf


OPERATIONS = {
    "+": operator.add,
    "−": operator.sub,
    "×": operator.mul,
    "÷": operator.truediv,
}


def fraction(kind, include_unity=True):
    denominator = randint(2, 12)
    if kind == "unity":
        return [denominator, denominator]
    if kind == "mixed_number":
        part = Rational(randint(1, denominator - 1), denominator)
        return [int(part.p), int(part.q), randint(1, 3)]
    numerator = (
        randint(1, denominator - 1)
        if kind == "proper"
        else randint(denominator if include_unity else denominator + 1, 2 * denominator + 1)
    )
    if numerator == denominator:
        return [numerator, denominator]
    reduced = Rational(numerator, denominator)
    return [int(reduced.p), int(reduced.q)]


def exercise(mode, count=2, selected=None, operations=OPERATIONS, include_unity=True):
    kinds = ["proper", "improper"] if mode == "mixed" else [mode, mode]
    if mode == "mixed" and randint(0, 1):
        kinds.reverse()
    if selected:
        other_kinds = [kind for kind in selected if kind != "unity"]
        pool = other_kinds or selected
        kinds = pool.copy()
        shuffle(kinds)
        if other_kinds and "unity" in selected and randint(1, 6) == 1:
            kinds.insert(0, "unity")
        kinds = (kinds + [choice(pool) for _ in range(count)])[:count]
        shuffle(kinds)
    terms = [fraction(kind, include_unity) for kind in kinds]
    available = list(operations)
    operators = [choice(available) for _ in terms[1:]]
    if operators == ["−"]:
        terms.sort(key=fraction_value, reverse=True)
    if available == ["−"] or (available != ["+"] and randint(0, 1)):
        leading = terms[0]
        sign_index = 2 if len(leading) == 3 else 0
        leading[sign_index] *= -1
    answer, groups = evaluate_expression(terms, operators)
    return dict(
        terms=terms, operators=operators, left=terms[0], right=terms[1],
        symbol=operators[0], answer=str(answer), groups=groups,
    )


def evaluate_expression(terms, operators):
    values = list(map(fraction_value, terms))
    groups = []

    def evaluate(first, last, parent=None):
        if first == last:
            return values[first]
        # Split at the rightmost lowest-precedence operator so ties evaluate left to right.
        split = min(
            range(last - 1, first - 1, -1),
            key=lambda index: operators[index] in {"×", "÷"},
        )
        symbol = operators[split]
        is_multiplicative = symbol in {"×", "÷"}
        parent_is_multiplicative = parent in {"×", "÷"}
        # A product can extend its left-hand multiplication chain without brackets.
        same_product = parent == symbol == "×"
        if parent is not None and (is_multiplicative or parent_is_multiplicative) and not same_product:
            groups.append((first, last))
        return OPERATIONS[symbol](
            evaluate(first, split, symbol),
            evaluate(split + 1, last, symbol),
        )

    return evaluate(0, len(values) - 1), groups


def fraction_value(parts):
    numerator, denominator, *whole = parts
    fraction = Rational(numerator, denominator)
    if not whole:
        return fraction
    return whole[0] + (fraction if whole[0] > 0 else -fraction)


class Handler(BaseHTTPRequestHandler):
    def send_body(self, body, content_type, status=200, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=200):
        self.send_body(json.dumps(data).encode(), "application/json", status)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/":
            page = Path(__file__).with_name("index.html").read_bytes()
            self.send_body(page, "text/html; charset=utf-8")
        elif url.path in {"/exercise", "/worksheet.pdf"}:
            params = parse_qs(url.query, keep_blank_values=True)
            worksheet = url.path == "/worksheet.pdf"
            if worksheet or "type" in params or "count" in params or "max_denominator" in params:
                selected = list(dict.fromkeys(params.get("type", [])))
                operations = list(dict.fromkeys(params.get("op", OPERATIONS)))
                count = params.get("count", ["2"])[0]
                if not operations or not set(operations) <= OPERATIONS.keys():
                    self.send_json({"error": "Choose at least one operation."}, 400)
                    return
                if count not in map(str, range(2, 11)) or not selected or not set(selected) <= {
                    "proper", "improper", "mixed_number", "unity"
                }:
                    self.send_json({"error": "Choose fraction types and 2–10 terms."}, 400)
                    return
                limit_text = params.get("max_denominator", [""])[0]
                if limit_text and (not re.fullmatch(r"[0-9]{1,30}", limit_text) or int(limit_text) < 1):
                    self.send_json({"error": "Enter a positive whole number for the denominator limit."}, 400)
                    return
                limit = int(limit_text) if limit_text else None
                include_unity = params.get("unity", ["0"])[0] == "1"
                size = params.get("questions", ["12"])[0] if worksheet else "1"
                if size not in map(str, range(1, 51)):
                    self.send_json({"error": "Choose 1 to 50 questions."}, 400)
                    return
                questions = []
                for _ in range(int(size)):
                    for _ in range(500 if limit is not None else 1):
                        question = exercise(None, int(count), selected, operations, include_unity)
                        if limit is None or Rational(question["answer"]).q <= limit:
                            questions.append(question)
                            break
                    else:
                        self.send_json({
                            "error": "No exercise found within that limit. Try a higher limit or change the exercise settings."
                        }, 422)
                        return
                if worksheet:
                    self.send_body(worksheet_pdf(questions), "application/pdf", filename="fraction-worksheet.pdf")
                else:
                    self.send_json(questions[0])
                return
            mode = params.get("mode", ["mixed"])[0]
            if mode not in {"proper", "improper", "mixed", "mixed_number"}:
                self.send_json({"error": "Unknown fraction type."}, 400)
                return
            self.send_json(exercise(mode))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/check":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError
            data = json.loads(self.rfile.read(length))
            submitted = self.parse_answer(data["answer"])
            expected = self.parse_answer(data["expected"])
        except (ValueError, TypeError, KeyError, ZeroDivisionError):
            self.send_json({"error": "Enter a whole number, a fraction like 3/4, or a mixed number like 2 1/3."}, 400)
            return
        self.send_json({"correct": submitted == expected, "simplified": str(expected)})

    @staticmethod
    def parse_answer(value):
        mixed = re.fullmatch(r"\s*([+-]?)([0-9]{1,30})\s+([0-9]{1,30})\s*/\s*([0-9]{1,30})\s*", value)
        if mixed:
            whole, numerator, denominator = map(int, mixed.groups()[1:])
            if not 0 < numerator < denominator:
                raise ValueError
            magnitude = whole + Rational(numerator, denominator)
            return -magnitude if mixed[1] == "-" else magnitude
        match = re.fullmatch(r"\s*([+-]?[0-9]{1,30})(?:\s*/\s*([0-9]{1,30}))?\s*", value)
        if not match:
            raise ValueError
        denominator = int(match[2] or "1")
        if denominator == 0:
            raise ValueError
        return Rational(int(match[1]), denominator)


if __name__ == "__main__":
    host = os.environ.get('APP_HOST', '127.0.0.1')
    with ThreadingHTTPServer((host, 8000), Handler) as server:
        print("Open http://127.0.0.1:8000", flush=True)
        server.serve_forever()
