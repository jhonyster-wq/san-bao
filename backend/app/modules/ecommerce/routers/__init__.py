from app.modules.ecommerce.routers.products import router as ecommerce_products_router
from app.modules.ecommerce.routers.orders import router as ecommerce_orders_router

__all__ = [
    "ecommerce_products_router",
    "ecommerce_orders_router",
]
