import math
from decimal import Decimal, ROUND_HALF_UP

def round_curr(val):
    """Accurate financial rounding to 2 decimal places."""
    return float(Decimal(str(val)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def number_to_indian_words(num):
    """
    Converts a monetary amount into words according to Indian currency numbering system.
    Example: 1800.00 -> 'Rupees One Thousand Eight Hundred Only'
             25450.50 -> 'Rupees Twenty Five Thousand Four Hundred Fifty and Fifty Paise Only'
    """
    if num is None:
        return ""
    try:
        val = float(num)
    except (ValueError, TypeError):
        return ""

    if val == 0:
        return "Zero Rupees Only"

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(n):
        if n < 20:
            return ones[n]
        rem = n % 10
        return tens[n // 10] + (" " + ones[rem] if rem else "")

    def three_digits(n):
        s = ""
        hundreds = n // 100
        rem = n % 100
        if hundreds:
            s += ones[hundreds] + " Hundred"
            if rem:
                s += " "
        if rem:
            s += two_digits(rem)
        return s

    rupees = int(val)
    paise = int(round((val - rupees) * 100))

    parts = []
    
    # Crores (10,000,000)
    crores = rupees // 10000000
    rupees %= 10000000
    if crores:
        parts.append(two_digits(crores) + " Crore")

    # Lakhs (100,000)
    lakhs = rupees // 100000
    rupees %= 100000
    if lakhs:
        parts.append(two_digits(lakhs) + " Lakh")

    # Thousands (1,000)
    thousands = rupees // 1000
    rupees %= 1000
    if thousands:
        parts.append(two_digits(thousands) + " Thousand")

    # Hundreds + Tens + Units
    if rupees:
        parts.append(three_digits(rupees))

    result = "Rupees " + " ".join(parts) if parts else ""
    
    if paise > 0:
        paise_str = two_digits(paise) + " Paise"
        if result:
            result += " and " + paise_str
        else:
            result = paise_str

    return result + " Only" if result else "Zero Rupees Only"


def calculate_invoice_totals(items, discount_val=0.0, discount_type="fixed", tax_percent=0.0,
                             cash_adv=0.0, upi_adv=0.0, bank_adv=0.0):
    """
    Performs server-side decimal-safe financial recalculations for invoices.
    Never trusts frontend arithmetic alone.
    """
    calculated_items = []
    subtotal = Decimal('0.00')

    for idx, item in enumerate(items, 1):
        desc = str(item.get("description", "")).strip()
        qty = Decimal(str(max(0, float(item.get("quantity", 1.0) or 1.0))))
        rate = Decimal(str(max(0, float(item.get("rate", 0.0) or 0.0))))
        amount = (qty * rate).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        subtotal += amount

        calculated_items.append({
            "sr_no": idx,
            "description": desc,
            "quantity": float(qty),
            "rate": float(rate),
            "amount": float(amount)
        })

    # Discount
    d_val = Decimal(str(max(0, float(discount_val or 0.0))))
    if discount_type == "percent":
        discount_amount = (subtotal * d_val / Decimal('100.0')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    else:
        discount_amount = min(d_val, subtotal)

    taxable = max(Decimal('0.00'), subtotal - discount_amount)
    
    # Tax
    t_pct = Decimal(str(max(0, float(tax_percent or 0.0))))
    tax_amount = (taxable * t_pct / Decimal('100.0')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    
    # Net Amount
    net_amount = (taxable + tax_amount).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    # Advances
    c_adv = Decimal(str(max(0, float(cash_adv or 0.0))))
    u_adv = Decimal(str(max(0, float(upi_adv or 0.0))))
    b_adv = Decimal(str(max(0, float(bank_adv or 0.0))))
    total_advance = (c_adv + u_adv + b_adv).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    # Balance
    balance_due = max(Decimal('0.00'), net_amount - total_advance)

    # Payment Status
    if net_amount > 0 and total_advance >= net_amount:
        status = "Paid"
    elif total_advance > 0:
        status = "Partially Paid"
    else:
        status = "Unpaid"

    words = number_to_indian_words(float(net_amount))

    return {
        "items": calculated_items,
        "subtotal": float(subtotal),
        "discount_amount": float(discount_amount),
        "discount_type": discount_type,
        "tax_percent": float(t_pct),
        "tax_amount": float(tax_amount),
        "net_amount": float(net_amount),
        "cash_advance": float(c_adv),
        "upi_advance": float(u_adv),
        "bank_advance": float(b_adv),
        "total_advance": float(total_advance),
        "balance_due": float(balance_due),
        "payment_status": status,
        "amount_in_words": words
    }
