from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas
from sympy import Rational


def expression_tokens(pdf, question):
    terms = question["terms"]
    tokens = []
    for index, (numerator, denominator, *whole) in enumerate(terms):
        if index:
            tokens.append("  " + question["operators"][index - 1].replace("−", "-") + "  ")
        tokens.append("(" * sum(first == index for first, _ in question["groups"]))
        if (whole[0] if whole else numerator) < 0:
            tokens.append("-")
        if whole:
            tokens.append(f"{abs(whole[0])} ")
        tokens.append((str(abs(numerator)), str(denominator)))
        tokens.append(")" * sum(last == index for _, last in question["groups"]))

    font, size = "Helvetica", 14
    widths = [
        pdf.stringWidth(token, font, size)
        if isinstance(token, str)
        else max(pdf.stringWidth(part, font, size) for part in token) + 6
        for token in tokens
    ]
    return list(zip(tokens, widths))


def draw_expression(pdf, tokens, x, y, available_width):
    font, size = "Helvetica", 14
    widths = [width for _, width in tokens]
    scale = min(1, available_width / sum(widths))
    pdf.saveState()
    pdf.translate(x, y)
    pdf.scale(scale, scale)
    pdf.setFont(font, size)
    offset = 0
    for token, width in tokens:
        if isinstance(token, str):
            if token and token[0] in "()":
                pdf.saveState()
                pdf.translate(offset, -9)
                pdf.scale(1, 1.9)
                pdf.drawString(0, 0, token)
                pdf.restoreState()
            else:
                pdf.drawString(offset, -5, token)
        else:
            center = offset + width / 2
            pdf.drawCentredString(center, 5, token[0])
            pdf.line(offset + 1, 0, offset + width - 1, 0)
            pdf.drawCentredString(center, -15, token[1])
        offset += width
    pdf.restoreState()


def worksheet_pdf(questions):
    output = BytesIO()
    pdf = Canvas(output, pagesize=letter)
    pdf.setTitle("Fraction Practice Worksheet")
    width, height = letter
    margin = 46
    gutter = 16
    number_width = 24
    answer_width = 62
    answer_spacing = 24
    reserved_width = number_width + answer_spacing + answer_width
    expressions = [expression_tokens(pdf, question) for question in questions]
    widest = max(sum(token_width for _, token_width in expression) for expression in expressions)
    printable_width = width - 2 * margin
    columns = next(
        (count for count in (3, 2)
         if (printable_width - (count - 1) * gutter) / count - reserved_width >= widest * 0.86),
        1,
    )
    column_width = (printable_width - (columns - 1) * gutter) / columns
    questions_per_page = 8 * columns
    question_pages = (len(questions) + questions_per_page - 1) // questions_per_page
    key_pages = (len(questions) + 23) // 24
    fraction_column = margin + 36
    widest_answer = max(pdf.stringWidth(question["answer"], "Helvetica", 11) for question in questions)
    mixed_column = fraction_column + max(116, widest_answer + 24)
    page = 0

    for title, per_page, is_questions in (
        ("Fraction Practice Worksheet", questions_per_page, True),
        ("Answer Key", 24, False),
    ):
        for first in range(0, len(questions), per_page):
            page += 1
            pdf.setFont("Helvetica-Bold", 24)
            pdf.drawString(margin, height - 62, title)
            pdf.setFont("Helvetica", 11)
            if is_questions:
                pdf.drawString(margin, height - 91, "Name ___________________________    Date ______________")
                pdf.drawString(margin, height - 112, "Evaluate each expression and simplify your answer.")
            else:
                pdf.drawString(margin, height - 91, "Reduced answers with mixed-number equivalents where applicable.")
            pdf.setStrokeColorRGB(0.7, 0.74, 0.72)
            pdf.line(margin, height - 125, width - margin, height - 125)
            if not is_questions:
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(fraction_column, height - 151, "Reduced fraction")
                pdf.drawString(mixed_column, height - 151, "Mixed number")
            for index, question in enumerate(questions[first:first + per_page]):
                number = first + index + 1
                if is_questions:
                    row, column = divmod(index, columns)
                    y = height - 156 - 73 * row
                    x = margin + column * (column_width + gutter)
                    pdf.setFont("Helvetica-Bold", 11)
                    pdf.drawString(x, y - 4, f"{number})")
                    expression = expressions[number - 1]
                    expression_space = column_width - reserved_width
                    draw_expression(pdf, expression, x + number_width, y, expression_space)
                    expression_width = min(expression_space, sum(token_width for _, token_width in expression))
                    answer_x = x + number_width + expression_width + answer_spacing
                    pdf.setFont("Helvetica", 12)
                    pdf.drawString(answer_x - 17, y - 4, "=")
                    pdf.roundRect(answer_x, y - 22, answer_width, 44, 3, fill=0)
                else:
                    answer = Rational(question["answer"])
                    whole, remainder = divmod(abs(answer.p), answer.q)
                    pdf.setFont("Helvetica", 11)
                    y = height - 175 - index * 24
                    pdf.drawRightString(fraction_column - 12, y, f"{number})")
                    pdf.drawString(fraction_column, y, str(answer))
                    if whole and remainder:
                        sign = "-" if answer < 0 else ""
                        pdf.drawString(mixed_column, y, f"{sign}{whole} {remainder}/{answer.q}")
            pdf.setFont("Helvetica", 9)
            pdf.drawRightString(width - margin, 30, f"{page} / {question_pages + key_pages}")
            pdf.showPage()
    pdf.save()
    return output.getvalue()
