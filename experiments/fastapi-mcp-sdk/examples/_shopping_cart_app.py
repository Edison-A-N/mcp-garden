"""
Shopping Cart FastAPI Application
A comprehensive e-commerce application with shopping cart functionality.
This example demonstrates a complete shopping cart system with users, products, cart management, and orders.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path as PathLib

from fastapi import FastAPI, HTTPException, Query, Body, Depends, Path, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator


# Enums
class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    MODERATOR = "moderator"


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    HOME = "home"
    SPORTS = "sports"
    BEAUTY = "beauty"
    FOOD = "food"


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


# Base Models
class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = True
    message: str = "Operation completed successfully"
    timestamp: datetime = Field(default_factory=datetime.now)


# User Models
class UserBase(BaseModel):
    """Base user model."""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    phone: Optional[str] = Field(None, description="Phone number")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="User role")
    is_active: bool = Field(default=True, description="Whether user is active")


class UserCreate(UserBase):
    """User creation model."""

    password: str = Field(..., min_length=8, description="User password")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(UserBase):
    """User response model."""

    id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


# Product Models
class ProductBase(BaseModel):
    """Base product model."""

    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    description: str = Field(..., min_length=10, max_length=1000, description="Product description")
    price: float = Field(..., gt=0, description="Product price")
    category: ProductCategory = Field(..., description="Product category")
    stock_quantity: int = Field(..., ge=0, description="Stock quantity")
    is_available: bool = Field(default=True, description="Product availability")
    image_url: Optional[str] = Field(None, description="Product image URL")
    tags: List[str] = Field(default=[], description="Product tags")
    specifications: Dict[str, Any] = Field(default={}, description="Product specifications")


class ProductCreate(ProductBase):
    """Product creation model."""

    pass


class ProductResponse(ProductBase):
    """Product response model."""

    id: int = Field(..., description="Product ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


# Cart Models
class CartItemBase(BaseModel):
    """Base cart item model."""

    product_id: int = Field(..., description="Product ID")
    quantity: int = Field(..., ge=1, description="Item quantity")


class CartItemCreate(CartItemBase):
    """Cart item creation model."""

    pass


class CartItemResponse(CartItemBase):
    """Cart item response model."""

    id: int = Field(..., description="Cart item ID")
    user_id: int = Field(..., description="User ID")
    product: ProductResponse = Field(..., description="Product details")
    unit_price: float = Field(..., description="Unit price at time of adding to cart")
    total_price: float = Field(..., description="Total price for this item")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    """Cart response model."""

    user_id: int = Field(..., description="User ID")
    items: List[CartItemResponse] = Field(..., description="Cart items")
    total_items: int = Field(..., description="Total number of items")
    total_amount: float = Field(..., description="Total cart amount")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Order Models
class OrderItem(BaseModel):
    """Order item model."""

    product_id: int = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., ge=1, description="Item quantity")
    unit_price: float = Field(..., gt=0, description="Unit price at time of order")
    total_price: float = Field(..., gt=0, description="Total price for this item")


class OrderBase(BaseModel):
    """Base order model."""

    user_id: int = Field(..., description="User ID")
    items: List[OrderItem] = Field(..., min_length=1, description="Order items")
    shipping_address: str = Field(..., min_length=10, max_length=500, description="Shipping address")
    billing_address: Optional[str] = Field(None, description="Billing address")
    notes: Optional[str] = Field(None, max_length=500, description="Order notes")
    payment_method: str = Field(..., description="Payment method")


class OrderCreate(OrderBase):
    """Order creation model."""

    pass


class OrderUpdate(BaseModel):
    """Order update model."""

    status: Optional[OrderStatus] = None
    shipping_address: Optional[str] = Field(None, min_length=10, max_length=500)
    notes: Optional[str] = Field(None, max_length=500)


class OrderResponse(OrderBase):
    """Order response model."""

    id: int = Field(..., description="Order ID")
    status: OrderStatus = Field(..., description="Order status")
    payment_status: PaymentStatus = Field(..., description="Payment status")
    total_amount: float = Field(..., description="Total order amount")
    shipping_cost: float = Field(default=0.0, description="Shipping cost")
    tax_amount: float = Field(default=0.0, description="Tax amount")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


# Pagination Models
class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=10, ge=1, le=100, description="Page size")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel):
    """Paginated response model."""

    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


# Authentication Configuration
# Simple Bearer Token authentication with hardcoded token
BEARER_TOKEN = "shopping-cart-api-token-2025"  # Hardcoded token for demo purposes
security = HTTPBearer(auto_error=False)  # auto_error=False to allow get_current_user to return 401


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Verify Bearer token and return current user info.

    This is a simple demo authentication - in production, you would:
    1. Verify the token against a database or JWT secret
    2. Decode the token to extract user information
    3. Return the actual user object

    Args:
        credentials: HTTP Authorization credentials from the request header
                   (None if no Authorization header is present)

    Returns:
        dict: Current user information

    Raises:
        HTTPException: If token is missing or invalid (401)
    """
    # Check if credentials are present
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    if credentials.credentials != BEARER_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return a simple user object (in production, this would come from a database)
    return {
        "id": 1,
        "username": "demo_user",
        "email": "demo@example.com",
        "role": "customer",
    }


# Global app instance (will be created by create_app function)
app: Optional[FastAPI] = None
public_router: Optional[APIRouter] = None
protected_router: Optional[APIRouter] = None


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application with all routes registered
    """
    global app, public_router, protected_router

    # Create FastAPI application
    app = FastAPI(
        title="Shopping Cart API",
        description="A comprehensive shopping cart API with user management, product catalog, cart operations, and order processing",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Create API routers
    # Public router for endpoints that don't require authentication
    public_router = APIRouter(tags=["Public"])

    # Protected router with authentication dependency
    protected_router = APIRouter(dependencies=[Depends(get_current_user)], tags=["Authenticated"])

    # Register all routes
    _register_routes(public_router, protected_router)

    # Include routers in the app
    app.include_router(public_router)
    app.include_router(protected_router)

    return app


def _register_routes(public_router: APIRouter, protected_router: APIRouter) -> None:
    """Register all routes to the routers.

    Args:
        public_router: Router for public endpoints
        protected_router: Router for protected endpoints (may have auth dependency)
    """

    # Health and Info Endpoints (Public - no authentication required)
    @public_router.get("/", response_model=BaseResponse)
    async def root():
        """Root endpoint with API information. Public access - no authentication required."""
        return BaseResponse(message="Shopping Cart API - FastAPI MCP Server", timestamp=datetime.now())

    @public_router.get("/health", response_model=BaseResponse)
    async def health_check():
        """Health check endpoint. Public access - no authentication required."""
        return BaseResponse(message="API is healthy", timestamp=datetime.now())

    @public_router.get("/info")
    async def api_info():
        """API information endpoint."""
        return {
            "name": "Shopping Cart API",
            "version": "1.0.0",
            "description": "A comprehensive shopping cart API with e-commerce functionality",
            "features": [
                "User Management",
                "Product Catalog",
                "Shopping Cart Operations",
                "Order Processing",
                "Search and Filtering",
                "Pagination Support",
                "Payment Integration",
            ],
            "total_users": len(USERS_DATA),
            "total_products": len(PRODUCTS_DATA),
        }

    # User Management Endpoints
    @protected_router.post("/users/", response_model=UserResponse, status_code=201)
    async def create_user(user: UserCreate):
        """Create a new user. Requires authentication."""
        user_data = user.model_dump()
        user_data.update(
            {
                "id": len(USERS_DATA) + 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )
        return UserResponse(**user_data)

    @protected_router.get("/users/{user_id}", response_model=UserResponse)
    async def get_user(user_id: int = Path(description="User ID", gt=0)):
        """Get user by ID. Requires authentication."""
        user_data = next((u for u in USERS_DATA if u.get("id") == user_id), None)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(**user_data)

    @protected_router.get("/users/", response_model=PaginatedResponse)
    async def list_users(
        page: int = Query(default=1, ge=1, description="Page number"),
        size: int = Query(default=10, ge=1, le=100, description="Page size"),
        sort_by: Optional[str] = Query(default=None, description="Sort field"),
        sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
        role: Optional[UserRole] = Query(None, description="Filter by role"),
        is_active: Optional[bool] = Query(None, description="Filter by active status"),
    ):
        """List users with pagination and filtering. Requires authentication."""
        filtered_users = USERS_DATA.copy()
        if role:
            filtered_users = [u for u in filtered_users if u.get("role") == role.value]
        if is_active is not None:
            filtered_users = [u for u in filtered_users if u.get("is_active") == is_active]
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_users = filtered_users[start_idx:end_idx]
        return PaginatedResponse(
            items=paginated_users,
            total=len(filtered_users),
            page=page,
            size=size,
            pages=(len(filtered_users) + size - 1) // size,
        )

    # Product Management Endpoints
    @protected_router.post("/products/", response_model=ProductResponse, status_code=201)
    async def create_product(product: ProductCreate):
        """Create a new product. Requires authentication."""
        product_data = product.model_dump()
        product_data.update(
            {
                "id": len(PRODUCTS_DATA) + 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )
        return ProductResponse(**product_data)

    @public_router.get("/products/{product_id}", response_model=ProductResponse)
    async def get_product(product_id: int = Path(description="Product ID", gt=0)):
        """Get product by ID. Public access - no authentication required."""
        product_data = next((p for p in PRODUCTS_DATA if p.get("id") == product_id), None)
        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(**product_data)

    @public_router.get("/products/", response_model=PaginatedResponse)
    async def list_products(
        page: int = Query(default=1, ge=1, description="Page number"),
        size: int = Query(default=10, ge=1, le=100, description="Page size"),
        sort_by: Optional[str] = Query(default=None, description="Sort field"),
        sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
        category: Optional[ProductCategory] = Query(None, description="Filter by category"),
        min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
        max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
        search: Optional[str] = Query(None, description="Search term"),
        is_available: Optional[bool] = Query(None, description="Filter by availability"),
    ):
        """List products with pagination and filtering. Public access - no authentication required."""
        filtered_products = PRODUCTS_DATA.copy()
        if category:
            filtered_products = [p for p in filtered_products if p.get("category") == category.value]
        if min_price is not None:
            filtered_products = [p for p in filtered_products if p.get("price", 0) >= min_price]
        if max_price is not None:
            filtered_products = [p for p in filtered_products if p.get("price", 0) <= max_price]
        if search:
            search_lower = search.lower()
            filtered_products = [
                p
                for p in filtered_products
                if search_lower in p.get("name", "").lower() or search_lower in p.get("description", "").lower()
            ]
        if is_available is not None:
            filtered_products = [p for p in filtered_products if p.get("is_available") == is_available]
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_products = filtered_products[start_idx:end_idx]
        return PaginatedResponse(
            items=paginated_products,
            total=len(filtered_products),
            page=page,
            size=size,
            pages=(len(filtered_products) + size - 1) // size,
        )

    # Shopping Cart Endpoints
    @protected_router.post("/cart/{user_id}/items/", response_model=CartItemResponse, status_code=201)
    async def add_to_cart(
        user_id: int = Path(description="User ID", gt=0),
        cart_item: CartItemCreate = Body(...),
    ):
        """Add item to user's cart. Requires authentication."""
        product_data = next((p for p in PRODUCTS_DATA if p.get("id") == cart_item.product_id), None)
        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found")
        if not product_data.get("is_available", False):
            raise HTTPException(status_code=400, detail="Product is not available")
        if cart_item.quantity > product_data.get("stock_quantity", 0):
            raise HTTPException(status_code=400, detail="Insufficient stock")
        unit_price = product_data.get("price", 0)
        total_price = unit_price * cart_item.quantity
        cart_item_data = {
            "id": 1,
            "user_id": user_id,
            "product_id": cart_item.product_id,
            "quantity": cart_item.quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "product": product_data,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        return CartItemResponse(**cart_item_data)

    @protected_router.get("/cart/{user_id}/", response_model=CartResponse)
    async def get_cart(user_id: int = Path(description="User ID", gt=0)):
        """Get user's cart. Requires authentication."""
        cart_items = [
            {
                "id": i,
                "user_id": user_id,
                "product_id": i,
                "quantity": 1,
                "unit_price": 10.0 * i,
                "total_price": 10.0 * i,
                "product": PRODUCTS_DATA[i % len(PRODUCTS_DATA)] if PRODUCTS_DATA else {},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            for i in range(1, 4)
        ]
        total_items = sum(item["quantity"] for item in cart_items)
        total_amount = sum(item["total_price"] for item in cart_items)
        return CartResponse(
            user_id=user_id,
            items=cart_items,
            total_items=total_items,
            total_amount=total_amount,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @protected_router.put("/cart/{user_id}/items/{item_id}", response_model=CartItemResponse)
    async def update_cart_item(
        user_id: int = Path(description="User ID", gt=0),
        item_id: int = Path(description="Cart item ID", gt=0),
        quantity: int = Body(..., ge=1, description="New quantity"),
    ):
        """Update cart item quantity. Requires authentication."""
        cart_item_data = {
            "id": item_id,
            "user_id": user_id,
            "product_id": 1,
            "quantity": quantity,
            "unit_price": 10.0,
            "total_price": 10.0 * quantity,
            "product": PRODUCTS_DATA[0] if PRODUCTS_DATA else {},
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        return CartItemResponse(**cart_item_data)

    @protected_router.delete("/cart/{user_id}/items/{item_id}", response_model=BaseResponse)
    async def remove_from_cart(
        user_id: int = Path(description="User ID", gt=0),
        item_id: int = Path(description="Cart item ID", gt=0),
    ):
        """Remove item from cart. Requires authentication."""
        return BaseResponse(
            message=f"Item {item_id} removed from cart for user {user_id}",
            timestamp=datetime.now(),
        )

    @protected_router.delete("/cart/{user_id}/", response_model=BaseResponse)
    async def clear_cart(user_id: int = Path(description="User ID", gt=0)):
        """Clear user's cart. Requires authentication."""
        return BaseResponse(message=f"Cart cleared for user {user_id}", timestamp=datetime.now())

    # Order Management Endpoints
    @protected_router.post("/orders/", response_model=OrderResponse, status_code=201)
    async def create_order(order: OrderCreate):
        """Create a new order from cart. Requires authentication."""
        total_amount = sum(item.total_price for item in order.items)
        shipping_cost = 10.0 if total_amount < 100 else 0.0
        tax_amount = total_amount * 0.08
        order_data = order.model_dump()
        order_data.update(
            {
                "id": 1,
                "status": OrderStatus.PENDING,
                "payment_status": PaymentStatus.PENDING,
                "total_amount": total_amount,
                "shipping_cost": shipping_cost,
                "tax_amount": tax_amount,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )
        return OrderResponse(**order_data)

    @protected_router.get("/orders/{order_id}", response_model=OrderResponse)
    async def get_order(order_id: int = Path(description="Order ID", gt=0)):
        """Get order by ID. Requires authentication."""
        order_data = {
            "id": order_id,
            "user_id": 1,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Sample Product 1",
                    "quantity": 2,
                    "unit_price": 99.99,
                    "total_price": 199.98,
                }
            ],
            "shipping_address": "123 Main St, City, State 12345",
            "billing_address": "123 Main St, City, State 12345",
            "notes": "Please handle with care",
            "payment_method": "credit_card",
            "status": OrderStatus.PENDING,
            "payment_status": PaymentStatus.PENDING,
            "total_amount": 199.98,
            "shipping_cost": 0.0,
            "tax_amount": 15.99,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        return OrderResponse(**order_data)

    @protected_router.get("/orders/", response_model=PaginatedResponse)
    async def list_orders(
        page: int = Query(default=1, ge=1, description="Page number"),
        size: int = Query(default=10, ge=1, le=100, description="Page size"),
        sort_by: Optional[str] = Query(default=None, description="Sort field"),
        sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
        user_id: Optional[int] = Query(None, description="Filter by user ID"),
        status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    ):
        """List orders with pagination and filtering. Requires authentication."""
        orders = [
            {
                "id": i,
                "user_id": 1,
                "items": [
                    {
                        "product_id": 1,
                        "product_name": f"Product {i}",
                        "quantity": 1,
                        "unit_price": 99.99,
                        "total_price": 99.99,
                    }
                ],
                "shipping_address": "123 Main St, City, State 12345",
                "billing_address": "123 Main St, City, State 12345",
                "notes": None,
                "payment_method": "credit_card",
                "status": OrderStatus.PENDING,
                "payment_status": PaymentStatus.PENDING,
                "total_amount": 99.99,
                "shipping_cost": 0.0,
                "tax_amount": 7.99,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            for i in range(1, 6)
        ]
        if user_id:
            orders = [o for o in orders if o["user_id"] == user_id]
        if status:
            orders = [o for o in orders if o["status"] == status.value]
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_orders = orders[start_idx:end_idx]
        return PaginatedResponse(
            items=paginated_orders,
            total=len(orders),
            page=page,
            size=size,
            pages=(len(orders) + size - 1) // size,
        )

    @protected_router.put("/orders/{order_id}", response_model=OrderResponse)
    async def update_order(
        order_id: int = Path(description="Order ID", gt=0),
        order_update: OrderUpdate = Body(...),
    ):
        """Update order information. Requires authentication."""
        order_data = {
            "id": order_id,
            "user_id": 1,
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Sample Product",
                    "quantity": 1,
                    "unit_price": 99.99,
                    "total_price": 99.99,
                }
            ],
            "shipping_address": order_update.shipping_address or "123 Main St, City, State 12345",
            "billing_address": "123 Main St, City, State 12345",
            "notes": order_update.notes,
            "payment_method": "credit_card",
            "status": order_update.status or OrderStatus.PENDING,
            "payment_status": PaymentStatus.PENDING,
            "total_amount": 99.99,
            "shipping_cost": 0.0,
            "tax_amount": 7.99,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        return OrderResponse(**order_data)

    # Search and Analytics Endpoints
    @public_router.get("/search/products/", response_model=PaginatedResponse)
    async def search_products(
        query: str = Query(..., description="Search query"),
        page: int = Query(default=1, ge=1, description="Page number"),
        size: int = Query(default=10, ge=1, le=100, description="Page size"),
        sort_by: Optional[str] = Query(default=None, description="Sort field"),
        sort_order: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort order"),
        category: Optional[ProductCategory] = Query(None, description="Filter by category"),
    ):
        """Search products by query. Public access - no authentication required."""
        search_lower = query.lower()
        filtered_products = [
            p
            for p in PRODUCTS_DATA
            if search_lower in p.get("name", "").lower() or search_lower in p.get("description", "").lower()
        ]
        if category:
            filtered_products = [p for p in filtered_products if p.get("category") == category.value]
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_products = filtered_products[start_idx:end_idx]
        return PaginatedResponse(
            items=paginated_products,
            total=len(filtered_products),
            page=page,
            size=size,
            pages=(len(filtered_products) + size - 1) // size,
        )

    @protected_router.get("/analytics/summary")
    async def get_analytics_summary():
        """Get analytics summary. Requires authentication."""
        return {
            "total_users": len(USERS_DATA),
            "total_products": len(PRODUCTS_DATA),
            "total_orders": 150,
            "revenue": 25000.00,
            "top_categories": [
                {"category": "electronics", "count": 25},
                {"category": "clothing", "count": 20},
                {"category": "books", "count": 15},
            ],
            "active_carts": 45,
            "pending_orders": 12,
        }

    @public_router.get("/analytics/products/popular")
    async def get_popular_products(limit: int = Query(default=10, ge=1, le=50)):
        """Get popular products. Public access - no authentication required."""
        popular_products = PRODUCTS_DATA[:limit] if PRODUCTS_DATA else []
        return {"products": popular_products, "total": len(popular_products)}


# Load fixtures data
def load_fixtures():
    """Load fixture data from JSON files."""
    fixtures_dir = PathLib(__file__).parent / "fixtures"

    # Load users
    users_file = fixtures_dir / "users.json"
    if users_file.exists():
        with open(users_file, "r", encoding="utf-8") as f:
            users_data = json.load(f)
    else:
        users_data = []

    # Load products
    products_file = fixtures_dir / "products.json"
    if products_file.exists():
        with open(products_file, "r", encoding="utf-8") as f:
            products_data = json.load(f)
    else:
        products_data = []

    return users_data, products_data


# Global fixtures data
USERS_DATA, PRODUCTS_DATA = load_fixtures()


# Create default app instance
app = create_app()
