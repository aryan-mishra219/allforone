from django.db.models import Sum, Q
from .models import Transaction, Debt


def format_indian_currency(number, include_symbol=True):
    """
    Format a number into Indian Numbering System (Lakhs/Crores).
    123456 -> 1,23,456
    """
    if number is None:
        return "₹0" if include_symbol else "0"
    
    try:
        n = float(number)
    except (ValueError, TypeError):
        return str(number)

    minus = "-" if n < 0 else ""
    n = abs(n)

    # Use .2f to handle floats, then split into integer and decimal parts
    s = f"{n:.2f}"
    main_part, dec_part = s.split('.')
    dec = f".{dec_part}" if dec_part != "00" else ""
    
    if len(main_part) <= 3:
        res = main_part
    else:
        last_three = main_part[-3:]
        remaining = main_part[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        res = ",".join(reversed(groups)) + "," + last_three
    
    formatted = f"{minus}{res}{dec}"
    return f"₹{formatted}" if include_symbol else formatted


def get_financial_summary(user):
    """Calculate total balance, income, expenses for a user."""
    totals = Transaction.objects.filter(user=user).aggregate(
        total_income=Sum('amount', filter=Q(transaction_type='income')),
        total_expenses=Sum('amount', filter=Q(transaction_type='expense')),
    )

    total_income = totals['total_income'] or 0
    total_expenses = totals['total_expenses'] or 0
    balance = total_income - total_expenses

    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
    }


def get_monthly_spending(user, months=6):
    """Get monthly spending data for chart rendering."""
    from django.utils import timezone
    from datetime import timedelta
    import calendar

    today = timezone.now().date()
    labels = []
    data = []

    for i in range(months - 1, -1, -1):
        # Calculate the month
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        month_name = calendar.month_abbr[month]
        labels.append(month_name)

        total = Transaction.objects.filter(
            user=user,
            transaction_type='expense',
            date__year=year,
            date__month=month,
        ).aggregate(total=Sum('amount'))['total'] or 0

        data.append(float(total))

    return {'labels': labels, 'data': data}


def get_debt_summary(user):
    """Get debt progress data."""
    debts = Debt.objects.filter(user=user)
    debt_list = []
    for debt in debts:
        debt_list.append({
            'name': debt.name,
            'total': float(debt.total_amount),
            'paid': float(debt.amount_paid),
            'remaining': float(debt.remaining),
            'progress': debt.progress_percent,
            'interest_rate': float(debt.interest_rate),
            'min_payment': float(debt.minimum_payment),
        })

    total_debt = sum(d['total'] for d in debt_list)
    total_paid = sum(d['paid'] for d in debt_list)

    return {
        'debts': debt_list,
        'total_debt': total_debt,
        'total_paid': total_paid,
        'total_remaining': max(0, total_debt - total_paid),
    }


def get_repayment_power(user):
    """
    Calculate the monthly surplus available for debt repayment.
    Returns Decimal values for high-precision math.
    """
    from .models import Transaction
    from django.db.models import Sum
    from django.utils import timezone
    from decimal import Decimal

    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    # Total income data
    income_data = Transaction.objects.filter(
        user=user, transaction_type='income',
        date__year=current_year, date__month=current_month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    monthly_income = Decimal(str(income_data))

    if monthly_income == 0:
        total_income_all = Transaction.objects.filter(
            user=user, transaction_type='income',
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        months_count = Transaction.objects.filter(
            user=user, transaction_type='income',
        ).dates('date', 'month').count() or 1
        monthly_income = Decimal(str(total_income_all)) / Decimal(str(months_count))

    # Total expense data
    expense_data = Transaction.objects.filter(
        user=user, transaction_type='expense',
        date__year=current_year, date__month=current_month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    monthly_expenses = Decimal(str(expense_data))

    if monthly_expenses == 0:
        total_expense_all = Transaction.objects.filter(
            user=user, transaction_type='expense',
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        months_count = Transaction.objects.filter(
            user=user, transaction_type='expense',
        ).dates('date', 'month').count() or 1
        monthly_expenses = Decimal(str(total_expense_all)) / Decimal(str(months_count))

    emergency_buffer = monthly_income * Decimal('0.10')
    repayment_power = max(Decimal('0.00'), monthly_income - monthly_expenses - emergency_buffer)

    # Check for manual override from user profile
    if hasattr(user, 'profile') and user.profile.repayment_power_override is not None:
        repayment_power = user.profile.repayment_power_override

    return {
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'emergency_buffer': emergency_buffer,
        'repayment_power': repayment_power,
    }


def generate_repayment_schedule(user):
    """Generate a month-by-month repayment schedule using a Hybrid Strategy.
    Phase 1: Snowball (Prioritize smallest debts for motivation)
    Phase 2: Avalanche (Prioritize remaining debts by highest interest rate)"""
    from .models import Debt
    from decimal import Decimal, ROUND_HALF_UP

    # Only include active, uncleared debts, ordered exactly as in the main view
    active_debts = list(Debt.objects.filter(user=user, cleared_at__isnull=True).order_by('interest_rate'))
    if not active_debts:
        return {'schedule': [], 'months_to_freedom': 0, 'total_interest_saved': 0}

    power_data = get_repayment_power(user)
    monthly_power = power_data['repayment_power']

    if monthly_power <= 0:
        return {
            'schedule': [],
            'months_to_freedom': -1, 
            'total_interest_saved': 0,
            'power_data': {k: float(v) for k, v in power_data.items()},
        }

    # Prepare high-precision working copies for all active debts to ensure column alignment
    working_debts = []
    for d in active_debts:
        working_debts.append({
            'id': d.id,
            'name': d.name,
            'remaining': Decimal(str(d.remaining)),
            'interest_rate': Decimal(str(d.interest_rate)),
            'min_payment': Decimal(str(d.minimum_payment)),
            'monthly_rate': Decimal(str(d.interest_rate)) / Decimal('100') / Decimal('12'),
        })

    if not working_debts:
        return {'schedule': [], 'months_to_freedom': 0, 'power_data': {k: float(v) for k, v in power_data.items()}}

    # Determine Snowball Targets (Smallest 2)
    temp_sorted = sorted(working_debts, key=lambda x: x['remaining'])
    snowball_ids = [d['id'] for d in temp_sorted[:2]]

    # Hybrid Strategy Sorting (Smallest 2 first, then highest interest)
    def strategy_sort(debt):
        is_snowball = 1 if debt['id'] in snowball_ids else 0
        return (-is_snowball, -debt['interest_rate'])

    # We use a COPY for the allocation logic but keep the original order for the output
    allocation_order = sorted(working_debts, key=strategy_sort)

    schedule = []
    month_iter = 0
    max_months = 360  # 30 years

    while any(d['remaining'] > 0 for d in working_debts) and month_iter < max_months:
        month_iter += 1
        month_data = {'month': month_iter, 'payments_map': {}, 'total_payment': Decimal('0.00')}
        available = monthly_power

        # Step 1: Satisfy Minimum Payments and Interest
        # Note: We iterate in allocation order to prioritize minimums of high-priority debts if funds are low
        for debt in allocation_order:
            if debt['remaining'] <= 0:
                continue
            
            # Monthly Interest Addition (once per month per debt)
            interest = (debt['remaining'] * debt['monthly_rate']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            debt['remaining'] += interest
            
            # Pay Minimum (capped by remaining balance AND strictly by available monthly power)
            payment = min(debt['min_payment'], debt['remaining'], max(Decimal('0'), available))
            debt['remaining'] -= payment
            available -= payment
            
            month_data['payments_map'][debt['id']] = {
                'payment': payment,
                'remaining': debt['remaining'],
            }
            month_data['total_payment'] += payment

        # Step 2: Distribute SURPLUS (Snowball/Avalanche)
        if available > 0:
            for debt in allocation_order:
                if available <= 0 or debt['remaining'] <= 0:
                    continue
                
                extra = min(available, debt['remaining'])
                debt['remaining'] -= extra
                available -= extra
                
                # Update records in the map
                if debt['id'] in month_data['payments_map']:
                    month_data['payments_map'][debt['id']]['payment'] += extra
                    month_data['payments_map'][debt['id']]['remaining'] = debt['remaining']
                else:
                    # This shouldn't happen usually as they get min payments, 
                    # but if min_payment was 0, it might
                    month_data['payments_map'][debt['id']] = {
                        'payment': extra,
                        'remaining': debt['remaining'],
                    }
                month_data['total_payment'] += extra

        # Step 3: Format for JSON and ensure fixed column order
        # We must iterate over working_debts (original order) to ensure columns match templates
        formatted_payments = []
        for debt in working_debts:
            p_info = month_data['payments_map'].get(debt['id'], {'payment': Decimal('0'), 'remaining': debt['remaining']})
            formatted_payments.append({
                'name': debt['name'],
                'payment': int(p_info['payment'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
                'remaining': int(p_info['remaining'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
            })
        
        schedule.append({
            'month': month_iter,
            'payments': formatted_payments,
            'total_payment': int(month_data['total_payment'].quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        })

    return {
        'schedule': schedule[:36],
        'months_to_freedom': month_iter if month_iter < max_months else -1,
        'power_data': {k: float(v) for k, v in power_data.items()},
    }


def get_debt_timeline(user):
    """
    Get combined data for past and future debt clearances.
    Returns a list of events: {type, name, date, amount, is_today}.
    """
    from .models import Debt
    from django.utils import timezone
    import calendar
    from datetime import timedelta

    events = []
    # Use timezone.now() for datetime context
    now = timezone.now()
    today = now.date()

    # 1. Past Cleared Debts (Including those where cleared_at might be null but balance is 0)
    from django.db import models
    from django.db.models import Q
    past_debts = Debt.objects.filter(
        user=user
    ).filter(
        Q(cleared_at__isnull=False) | Q(amount_paid__gte=models.F('total_amount'))
    ).order_by('cleared_at', 'updated_at')
    
    for d in past_debts:
        # Fallback date if cleared_at is somehow missing
        clear_date = d.cleared_at or d.updated_at or d.created_at
        events.append({
            'type': 'past',
            'name': d.name,
            'amount': float(d.total_amount),
            'date': clear_date.strftime("%b %Y"),
            'raw_date': clear_date
        })

    # 2. Today Marker
    events.append({
        'type': 'today',
        'name': 'Today',
        'date': today.strftime("%b %Y"),
        'raw_date': now,
        'is_today': True
    })

    # 3. Future Projections (using schedule logic)
    schedule_data = generate_repayment_schedule(user)
    full_schedule = schedule_data.get('schedule', [])
    
    # Track when each debt hits 0 in the schedule
    future_clearances = {}
    for entry in full_schedule:
        month_idx = entry['month']
        for p in entry['payments']:
            if p['remaining'] <= 0:
                # If it's the first time we see it hit 0
                if p['name'] not in future_clearances:
                    # Calculate projected date
                    proj_date = now + timedelta(days=30 * month_idx)
                    future_clearances[p['name']] = {
                        'type': 'future',
                        'name': p['name'],
                        'amount': 0, # Could fetch current remaining
                        'date': proj_date.strftime("%b %Y"),
                        'raw_date': proj_date
                    }
    
    for name, data in future_clearances.items():
        events.append(data)

    # Sort all by raw_date
    events.sort(key=lambda x: x['raw_date'])
    return events

