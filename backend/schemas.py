from pydantic import BaseModel
from typing import List, Optional

class ProductCreate(BaseModel):
    sku: Optional[str] = None
    name: str
    category: str
    cost_price: float = 0.0
    selling_price: float
    stock_quantity: int
    barcode: Optional[str] = None

class ProductResponse(ProductCreate):
    id: int

    class Config:
        orm_mode = True

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItemCreate]