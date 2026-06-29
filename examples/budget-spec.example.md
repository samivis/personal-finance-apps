# Daily Budget Tracker — Example Spec

> Fictional figures. This shows how to define a budget the tracker can reason about.
> Your real spec stays private and out of version control.

Run once daily. Read the last 24 hours of transactions across all linked accounts,
deduplicate against tracked state, categorize, and append to the budget sheet.

## Monthly Budget: $4,000

### Fixed (~$2,800/mo)
| Category | Budget | Cadence |
|----------|--------|---------|
| Rent | $1,500 | 1st of month |
| Groceries | $500 | Weekly |
| Car Insurance | $150 | Monthly |
| Gym | $120 | Monthly |
| Internet/Utilities | $100 | Monthly |
| Streaming subscriptions | $50 | Monthly |

### Variable (~$1,000/mo)
| Category | Budget |
|----------|--------|
| Eating out | $400 |
| Shopping | $350 |
| Entertainment | $250 |

### Buffer: ~$200/mo

## Should NOT appear on personal accounts (flag if seen)
Business/startup costs that belong on a business card — e.g. cloud hosting, SaaS
subscriptions, domain registrars.

## Should have STOPPED (flag if charged)
Canceled subscriptions and paid-off loans.

## Daily report format
1. **New transactions** — vendor, amount, category.
2. **Budget tracking** — fixed vs variable spent this month, total vs budget, remaining,
   weekly variable pacing.
3. **Flags** — canceled-but-charged, business-on-personal, unusual vendors, single
   charges over a threshold, categories pacing above budget.
4. **Questions** — anything ambiguous to confirm before saving state.

## State management
Track transactions seen this month (dedupe), running per-category totals, open
flags/questions, and month-/week-to-date summaries. Reset monthly totals on the 1st.
