"""Jac Orc Routers."""

from .deployment import router as deployment_router
from .healthz import router as healthz_router


routers = [deployment_router, healthz_router]
