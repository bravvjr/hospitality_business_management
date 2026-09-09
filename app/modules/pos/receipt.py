"""Sale receipt rendering for POS (Phase 2)."""
from decimal import Decimal

from app.modules.pos.schemas import SaleReceiptRead

RECEIPT_WIDTH = 40


def format_money(amount_minor: int, currency: str) -> str:
    major = Decimal(amount_minor) / Decimal(100)
    return f"{major:,.2f} {currency}"


def render_receipt_text(receipt: SaleReceiptRead) -> str:
    lines: list[str] = []
    divider = "-" * RECEIPT_WIDTH

    lines.append(receipt.business_name[:RECEIPT_WIDTH].center(RECEIPT_WIDTH))
    lines.append(f"Receipt #{receipt.receipt_number}".center(RECEIPT_WIDTH))
    lines.append(receipt.completed_at.strftime("%Y-%m-%d %H:%M UTC").center(RECEIPT_WIDTH))
    lines.append(divider)

    for item in receipt.items:
        name = item.product_name[:RECEIPT_WIDTH]
        lines.append(name)
        qty_price = (
            f"{item.quantity} x {format_money(item.unit_price_minor, receipt.currency)}"
        )
        total = format_money(item.line_total_minor, receipt.currency)
        lines.append(qty_price.ljust(RECEIPT_WIDTH - len(total)) + total)

    lines.append(divider)
    subtotal = format_money(receipt.subtotal_minor, receipt.currency)
    lines.append("Subtotal".ljust(RECEIPT_WIDTH - len(subtotal)) + subtotal)
    total = format_money(receipt.total_minor, receipt.currency)
    lines.append("TOTAL".ljust(RECEIPT_WIDTH - len(total)) + total)

    for payment in receipt.payments:
        paid = format_money(payment.amount_minor, receipt.currency)
        label = payment.method.upper()
        lines.append(label.ljust(RECEIPT_WIDTH - len(paid)) + paid)
        if payment.change_minor is not None and payment.change_minor > 0:
            change = format_money(payment.change_minor, receipt.currency)
            lines.append("Change".ljust(RECEIPT_WIDTH - len(change)) + change)

    if receipt.cashier_email:
        lines.append(divider)
        lines.append(f"Cashier: {receipt.cashier_email[:RECEIPT_WIDTH]}")
    if receipt.note:
        lines.append(f"Note: {receipt.note[:RECEIPT_WIDTH]}")

    lines.append("")
    lines.append("Thank you!".center(RECEIPT_WIDTH))
    return "\n".join(lines) + "\n"
