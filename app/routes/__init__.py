from .auth import bp as auth
from .accounts import bp as accounts
from .categories import bp as categories
from .transactions import bp as transactions
from .budgets import bp as budgets
from .goals import bp as goals
from .bills import bp as bills
from .notifications import bp as notifications
from .settings import bp as settings
from .analytics import bp as analytics
blueprints=[auth,accounts,categories,transactions,budgets,goals,bills,notifications,settings,analytics]
