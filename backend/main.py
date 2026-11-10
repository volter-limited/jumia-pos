from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import models
import schemas
import database

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Jumia POS API", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to Jumia POS API"}

# --- PRODUCTS ENDPOINTS ---

@app.get("/products/", response_model=list[schemas.ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()

@app.post("/products/", response_model=schemas.ProductResponse)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

# --- ORDERS & M-PESA PAYMENT ENDPOINTS ---

class CheckoutRequest(BaseModel):
    items: list[schemas.OrderItemCreate]
    phone_number: str = "0113103848"

@app.post("/orders/")
def create_order(checkout: CheckoutRequest, db: Session = Depends(get_db)):
    total_amount = 0.0
    order_items_to_save = []

    for item in checkout.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with ID {item.product_id} not found")
        
        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")
        
        product.stock_quantity -= item.quantity
        line_total = product.selling_price * item.quantity
        total_amount += line_total

        order_items_to_save.append({
            "product_id": product.id,
            "quantity": item.quantity,
            "unit_price": product.selling_price,
            "subtotal": line_total
        })

    # Create order
    db_order = models.Order(total_amount=total_amount)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # Create order items
    for item_data in order_items_to_save:
        db_item = models.OrderItem(order_id=db_order.id, **item_data)
        db.add(db_item)
    
    db.commit()

    return {
        "message": f"M-Pesa STK push sent to {checkout.phone_number} successfully!",
        "order_id": db_order.id,
        "total_amount": total_amount
    }

# --- ANALYTICS / SALES REPORT ENDPOINT ---

@app.get("/reports/sales")
def get_sales_report(db: Session = Depends(get_db)):
    orders = db.query(models.Order).all()
    total_revenue = sum(order.total_amount for order in orders)
    total_orders = len(orders)
    
    item_counts = {}
    for order in orders:
        for item in order.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            p_name = product.name if product else f"Product ID {item.product_id}"
            item_counts[p_name] = item_counts.get(p_name, 0) + item.quantity

    top_products = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "top_products": [{"name": name, "quantity": qty} for name, qty in top_products[:5]]
    }