"""CSV export helpers for reports (Phase 2c)."""
import csv
import io
from datetime import date
from typing import Literal

from fastapi.responses import StreamingResponse

from app.modules.reports.schemas import (
    ExpensesByCategoryRead,
    InventoryMovementSummaryRead,
    PnlRead,
    SalesByPaymentMethodRead,
    SalesByProductRead,
    SalesSummaryRead,
)

ReportExportKey = Literal[
    "sales-summary",
    "sales-by-product",
    "sales-by-payment-method",
    "expenses-by-category",
    "pnl",
    "inventory-movements",
]

REPORT_EXPORT_KEYS: frozenset[str] = frozenset(
    {
        "sales-summary",
        "sales-by-product",
        "sales-by-payment-method",
        "expenses-by-category",
        "pnl",
        "inventory-movements",
    }
)


def _csv_response(rows: list[list[str]], filename: str) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_filename(report_key: str, from_date: date, to_date: date) -> str:
    return f"{report_key}_{from_date.isoformat()}_{to_date.isoformat()}.csv"


def export_sales_summary_csv(report: SalesSummaryRead) -> StreamingResponse:
    if report.buckets:
        rows = [
            ["period_start", "total_minor", "order_count", "currency"],
            *[
                [
                    bucket.period_start.isoformat(),
                    str(bucket.total_minor),
                    str(bucket.order_count),
                    report.currency,
                ]
                for bucket in report.buckets
            ],
        ]
    else:
        rows = [
            [
                "from_date",
                "to_date",
                "currency",
                "total_minor",
                "order_count",
                "average_ticket_minor",
            ],
            [
                report.from_date.isoformat(),
                report.to_date.isoformat(),
                report.currency,
                str(report.total_minor),
                str(report.order_count),
                str(report.average_ticket_minor),
            ],
        ]
    return _csv_response(rows, _export_filename("sales-summary", report.from_date, report.to_date))


def export_sales_by_product_csv(report: SalesByProductRead) -> StreamingResponse:
    rows = [
        [
            "product_id",
            "product_name",
            "total_minor",
            "quantity",
            "line_count",
            "currency",
        ],
        *[
            [
                str(product.product_id),
                product.product_name,
                str(product.total_minor),
                str(product.quantity),
                str(product.line_count),
                report.currency,
            ]
            for product in report.products
        ],
    ]
    return _csv_response(
        rows,
        _export_filename("sales-by-product", report.from_date, report.to_date),
    )


def export_sales_by_payment_method_csv(report: SalesByPaymentMethodRead) -> StreamingResponse:
    rows = [
        ["method", "total_minor", "payment_count", "currency"],
        *[
            [
                method.method,
                str(method.total_minor),
                str(method.payment_count),
                report.currency,
            ]
            for method in report.methods
        ],
    ]
    return _csv_response(
        rows, _export_filename("sales-by-payment-method", report.from_date, report.to_date)
    )


def export_expenses_by_category_csv(report: ExpensesByCategoryRead) -> StreamingResponse:
    rows = [
        [
            "category_id",
            "category_name",
            "total_minor",
            "expense_count",
            "currency",
        ],
        *[
            [
                str(category.category_id),
                category.category_name,
                str(category.total_minor),
                str(category.expense_count),
                report.currency,
            ]
            for category in report.categories
        ],
    ]
    return _csv_response(
        rows, _export_filename("expenses-by-category", report.from_date, report.to_date)
    )


def export_pnl_csv(report: PnlRead) -> StreamingResponse:
    rows = [
        [
            "from_date",
            "to_date",
            "currency",
            "revenue_minor",
            "expense_minor",
            "net_minor",
            "order_count",
            "expense_count",
        ],
        [
            report.from_date.isoformat(),
            report.to_date.isoformat(),
            report.currency,
            str(report.revenue_minor),
            str(report.expense_minor),
            str(report.net_minor),
            str(report.order_count),
            str(report.expense_count),
        ],
    ]
    return _csv_response(rows, _export_filename("pnl", report.from_date, report.to_date))


def export_inventory_movements_csv(report: InventoryMovementSummaryRead) -> StreamingResponse:
    rows = [
        ["movement_type", "movement_count", "total_quantity_delta_base"],
        *[
            [
                row.movement_type,
                str(row.movement_count),
                str(row.total_quantity_delta_base),
            ]
            for row in report.types
        ],
    ]
    return _csv_response(
        rows, _export_filename("inventory-movements", report.from_date, report.to_date)
    )
