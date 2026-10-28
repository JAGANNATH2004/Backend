from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from app.database import get_supabase
from app.models.inventory import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    AddStockRequest,
    DeductSaleRequest,
    MovementResponse,
)

class InventoryService:
    @staticmethod
    def _map_status(current_stock: float, min_threshold: float) -> str:
        if current_stock <= 0:
            return "outOfStock"
        elif current_stock <= min_threshold:
            return "lowStock"
        return "inStock"

    @staticmethod
    def _map_product_row(row: dict) -> ProductResponse:
        current_stock = float(row.get("current_stock", 0.0) or 0.0)
        min_threshold = float(row.get("min_threshold", 10.0) or 10.0)
        return ProductResponse(
            id=str(row["id"]),
            name=row["name"],
            sku=row.get("sku") or "",
            category=row.get("category") or "General Store",
            unit=row.get("unit") or "Packets",
            current_stock=current_stock,
            purchase_price=float(row.get("purchase_price", 0.0) or 0.0),
            selling_price=float(row.get("selling_price", 0.0) or 0.0),
            min_threshold=min_threshold,
            supplier=row.get("supplier") or "",
            status=InventoryService._map_status(current_stock, min_threshold),
            updated_at=str(row.get("updated_at", "")),
        )

    @staticmethod
    def get_products(
        business_id: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[ProductResponse]:
        supabase = get_supabase()
        db_query = supabase.table("products").select("*").eq("business_id", business_id)

        if category and category not in ["All Items", "అన్ని వస్తువులు"]:
            db_query = db_query.eq("category", category)

        if sort_by == "stockLow":
            db_query = db_query.order("current_stock", desc=False)
        elif sort_by == "stockHigh":
            db_query = db_query.order("current_stock", desc=True)
        else:
            db_query = db_query.order("name", desc=False)

        res = db_query.execute()
        products = [InventoryService._map_product_row(r) for r in (res.data or [])]

        if query and query.strip():
            q = query.strip().lower()
            products = [
                p for p in products
                if q in p.name.lower() or q in p.sku.lower() or q in p.category.lower()
            ]

        if status:
            products = [p for p in products if p.status == status]

        return products

    @staticmethod
    def get_product_by_id(business_id: str, product_id: str) -> Optional[ProductResponse]:
        supabase = get_supabase()
        res = supabase.table("products").select("*").eq("business_id", business_id).eq("id", product_id).execute()
        if res.data and len(res.data) > 0:
            return InventoryService._map_product_row(res.data[0])
        return None

    @staticmethod
    def create_product(business_id: str, data: ProductCreate) -> ProductResponse:
        supabase = get_supabase()
        row = {
            "business_id": business_id,
            "name": data.name,
            "sku": data.sku or "",
            "category": data.category,
            "unit": data.unit,
            "current_stock": data.current_stock,
            "purchase_price": data.purchase_price,
            "selling_price": data.selling_price,
            "min_threshold": data.min_threshold,
            "supplier": data.supplier or "",
        }
        res = supabase.table("products").insert(row).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create product in database")
        return InventoryService._map_product_row(res.data[0])

    @staticmethod
    def update_product(business_id: str, product_id: str, data: ProductUpdate) -> ProductResponse:
        supabase = get_supabase()
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.sku is not None:
            update_data["sku"] = data.sku
        if data.category is not None:
            update_data["category"] = data.category
        if data.unit is not None:
            update_data["unit"] = data.unit
        if data.current_stock is not None:
            update_data["current_stock"] = data.current_stock
        if data.purchase_price is not None:
            update_data["purchase_price"] = data.purchase_price
        if data.selling_price is not None:
            update_data["selling_price"] = data.selling_price
        if data.min_threshold is not None:
            update_data["min_threshold"] = data.min_threshold
        if data.supplier is not None:
            update_data["supplier"] = data.supplier

        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            res = supabase.table("products").update(update_data).eq("business_id", business_id).eq("id", product_id).execute()
            if not res.data:
                raise HTTPException(status_code=404, detail="Product not found or update failed")
            return InventoryService._map_product_row(res.data[0])

        existing = InventoryService.get_product_by_id(business_id, product_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Product not found")
        return existing

    @staticmethod
    def delete_product(business_id: str, product_id: str) -> bool:
        supabase = get_supabase()
        res = supabase.table("products").delete().eq("business_id", business_id).eq("id", product_id).execute()
        return True

    @staticmethod
    def add_stock(business_id: str, req: AddStockRequest) -> MovementResponse:
        supabase = get_supabase()
        product = InventoryService.get_product_by_id(business_id, req.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        prev_stock = product.current_stock
        new_stock = prev_stock + req.quantity
        purchase_price = req.purchase_price if req.purchase_price > 0 else product.purchase_price
        total_amount = req.quantity * purchase_price

        # Update product
        prod_update = {
            "current_stock": new_stock,
            "purchase_price": purchase_price,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if req.supplier:
            prod_update["supplier"] = req.supplier

        supabase.table("products").update(prod_update).eq("business_id", business_id).eq("id", req.product_id).execute()

        # Insert movement
        movement_row = {
            "business_id": business_id,
            "product_id": req.product_id,
            "type": "purchase",
            "quantity": req.quantity,
            "unit_price": purchase_price,
            "total_amount": total_amount,
            "balance_before": prev_stock,
            "balance_after": new_stock,
            "notes": req.notes or f"Stock added: {req.quantity} {product.unit}",
        }
        mov_res = supabase.table("stock_movements").insert(movement_row).execute()
        mov_id = mov_res.data[0]["id"] if mov_res.data else "mov_generated"

        return MovementResponse(
            id=str(mov_id),
            product_id=product.id,
            product_name=product.name,
            type="purchase",
            quantity=req.quantity,
            unit=product.unit,
            price=purchase_price,
            previous_stock=prev_stock,
            new_stock=new_stock,
            timestamp=datetime.utcnow().isoformat(),
            notes=req.notes or "",
        )

    @staticmethod
    def deduct_stock_sale(business_id: str, req: DeductSaleRequest) -> MovementResponse:
        supabase = get_supabase()
        product = InventoryService.get_product_by_id(business_id, req.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        if req.quantity > product.current_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name}. Available: {product.current_stock} {product.unit}",
            )

        prev_stock = product.current_stock
        new_stock = prev_stock - req.quantity
        selling_price = req.selling_price if req.selling_price > 0 else product.selling_price
        total_amount = req.quantity * selling_price

        # Update product
        supabase.table("products").update({
            "current_stock": new_stock,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("business_id", business_id).eq("id", req.product_id).execute()

        # Insert movement
        movement_row = {
            "business_id": business_id,
            "product_id": req.product_id,
            "type": "sale",
            "quantity": req.quantity,
            "unit_price": selling_price,
            "total_amount": total_amount,
            "balance_before": prev_stock,
            "balance_after": new_stock,
            "notes": req.notes or f"Customer sale: {req.quantity} {product.unit}",
        }
        mov_res = supabase.table("stock_movements").insert(movement_row).execute()
        mov_id = mov_res.data[0]["id"] if mov_res.data else "mov_generated"

        # Check stock alerts and trigger notification
        if new_stock == 0:
            supabase.table("notifications").insert({
                "business_id": business_id,
                "product_id": product.id,
                "title": f"{product.name} - అయిపోయింది (Out of Stock)",
                "message": f"{product.name} is completely out of stock. Please reorder immediately.",
                "type": "out_of_stock",
            }).execute()
        elif new_stock <= product.min_threshold:
            supabase.table("notifications").insert({
                "business_id": business_id,
                "product_id": product.id,
                "title": f"{product.name} - తక్కువ స్టాక్ (Low Stock)",
                "message": f"{product.name} stock is low ({new_stock} {product.unit} left). Minimum threshold is {product.min_threshold}.",
                "type": "low_stock",
            }).execute()

        return MovementResponse(
            id=str(mov_id),
            product_id=product.id,
            product_name=product.name,
            type="sale",
            quantity=req.quantity,
            unit=product.unit,
            price=selling_price,
            previous_stock=prev_stock,
            new_stock=new_stock,
            timestamp=datetime.utcnow().isoformat(),
            notes=req.notes or "",
        )

    @staticmethod
    def get_movements(
        business_id: str,
        product_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MovementResponse]:
        supabase = get_supabase()
        db_query = supabase.table("stock_movements").select("*, products(name, unit)").eq("business_id", business_id)

        if product_id:
            db_query = db_query.eq("product_id", product_id)

        db_query = db_query.order("created_at", desc=True).limit(limit)
        res = db_query.execute()

        movements = []
        for r in (res.data or []):
            prod_info = r.get("products") or {}
            p_name = prod_info.get("name") if isinstance(prod_info, dict) else "Product"
            p_unit = prod_info.get("unit") if isinstance(prod_info, dict) else "Units"
            movements.append(
                MovementResponse(
                    id=str(r["id"]),
                    product_id=str(r["product_id"]),
                    product_name=p_name or "Product",
                    type=r.get("type", "sale"),
                    quantity=float(r.get("quantity", 0.0)),
                    unit=p_unit or "Units",
                    price=float(r.get("unit_price", 0.0)),
                    previous_stock=float(r.get("balance_before", 0.0)),
                    new_stock=float(r.get("balance_after", 0.0)),
                    timestamp=str(r.get("created_at", "")),
                    notes=r.get("notes") or "",
                )
            )
        return movements

