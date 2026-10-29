-- ==============================================================================
-- Vyapari AI - Complete PostgreSQL Database Schema for Supabase
-- Run this in your Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Businesses Table
CREATE TABLE IF NOT EXISTS public.businesses (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    shop_name TEXT NOT NULL DEFAULT 'Vyapari Store',
    owner_name TEXT NOT NULL DEFAULT 'Shopkeeper',
    category TEXT NOT NULL DEFAULT 'General Store',
    preferred_language TEXT NOT NULL DEFAULT 'te',
    phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Products Table
CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sku TEXT DEFAULT '',
    category TEXT NOT NULL DEFAULT 'General Store',
    unit TEXT NOT NULL DEFAULT 'Packets',
    current_stock NUMERIC NOT NULL DEFAULT 0.0,
    purchase_price NUMERIC NOT NULL DEFAULT 0.0,
    selling_price NUMERIC NOT NULL DEFAULT 0.0,
    min_threshold NUMERIC NOT NULL DEFAULT 10.0,
    supplier TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Stock Movements (Audit Ledger for Purchases & Sales)
CREATE TABLE IF NOT EXISTS public.stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('purchase', 'sale')),
    quantity NUMERIC NOT NULL,
    unit TEXT NOT NULL DEFAULT 'Units',
    price NUMERIC NOT NULL DEFAULT 0.0,
    previous_stock NUMERIC NOT NULL DEFAULT 0.0,
    new_stock NUMERIC NOT NULL DEFAULT 0.0,
    notes TEXT DEFAULT '',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Notifications Table
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'lowStock',
    priority TEXT NOT NULL DEFAULT 'medium',
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for lightning fast queries
CREATE INDEX IF NOT EXISTS idx_products_business ON public.products(business_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_business ON public.stock_movements(business_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON public.stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_notifications_business ON public.notifications(business_id);

-- ==============================================================================
-- Row Level Security (RLS) Policies
-- Ensures each shopkeeper only accesses their own business data
-- ==============================================================================
ALTER TABLE public.businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Businesses Policies
CREATE POLICY "Users can view own business" ON public.businesses
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can insert own business" ON public.businesses
    FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "Users can update own business" ON public.businesses
    FOR UPDATE USING (auth.uid() = id);

-- Products Policies
CREATE POLICY "Users can view own products" ON public.products
    FOR SELECT USING (auth.uid() = business_id);
CREATE POLICY "Users can insert own products" ON public.products
    FOR INSERT WITH CHECK (auth.uid() = business_id);
CREATE POLICY "Users can update own products" ON public.products
    FOR UPDATE USING (auth.uid() = business_id);
CREATE POLICY "Users can delete own products" ON public.products
    FOR DELETE USING (auth.uid() = business_id);

-- Stock Movements Policies
CREATE POLICY "Users can view own stock movements" ON public.stock_movements
    FOR SELECT USING (auth.uid() = business_id);
CREATE POLICY "Users can insert own stock movements" ON public.stock_movements
    FOR INSERT WITH CHECK (auth.uid() = business_id);

-- Notifications Policies
CREATE POLICY "Users can view own notifications" ON public.notifications
    FOR SELECT USING (auth.uid() = business_id);
CREATE POLICY "Users can update own notifications" ON public.notifications
    FOR UPDATE USING (auth.uid() = business_id);
CREATE POLICY "Users can insert own notifications" ON public.notifications
    FOR INSERT WITH CHECK (auth.uid() = business_id);

-- ==============================================================================
-- Stored Procedures (RPCs) for Atomic Transactions
-- ==============================================================================

-- Add Stock Inward Transaction Function
CREATE OR REPLACE FUNCTION public.add_stock_transaction(
    p_product_id UUID,
    p_quantity NUMERIC,
    p_purchase_price NUMERIC,
    p_supplier TEXT DEFAULT '',
    p_notes TEXT DEFAULT ''
)
RETURNS JSON AS $$
DECLARE
    v_prod public.products%ROWTYPE;
    v_new_stock NUMERIC;
    v_movement_id UUID;
BEGIN
    SELECT * INTO v_prod FROM public.products WHERE id = p_product_id AND business_id = auth.uid();
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product not found or unauthorized';
    END IF;

    v_new_stock := v_prod.current_stock + p_quantity;

    UPDATE public.products
    SET current_stock = v_new_stock,
        purchase_price = CASE WHEN p_purchase_price > 0 THEN p_purchase_price ELSE purchase_price END,
        supplier = CASE WHEN p_supplier <> '' THEN p_supplier ELSE supplier END,
        updated_at = NOW()
    WHERE id = p_product_id;

    INSERT INTO public.stock_movements (
        business_id, product_id, type, quantity, unit, price, previous_stock, new_stock, notes
    ) VALUES (
        auth.uid(), p_product_id, 'purchase', p_quantity, v_prod.unit, p_purchase_price, v_prod.current_stock, v_new_stock, p_notes
    ) RETURNING id INTO v_movement_id;

    RETURN json_build_object(
        'success', true,
        'product_id', p_product_id,
        'previous_stock', v_prod.current_stock,
        'new_stock', v_new_stock,
        'movement_id', v_movement_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Record Sale Transaction Function
CREATE OR REPLACE FUNCTION public.record_sale_transaction(
    p_product_id UUID,
    p_quantity NUMERIC,
    p_selling_price NUMERIC,
    p_notes TEXT DEFAULT ''
)
RETURNS JSON AS $$
DECLARE
    v_prod public.products%ROWTYPE;
    v_new_stock NUMERIC;
    v_movement_id UUID;
BEGIN
    SELECT * INTO v_prod FROM public.products WHERE id = p_product_id AND business_id = auth.uid();
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product not found or unauthorized';
    END IF;

    IF v_prod.current_stock < p_quantity THEN
        RAISE EXCEPTION 'Insufficient stock. Available: %, Requested: %', v_prod.current_stock, p_quantity;
    END IF;

    v_new_stock := v_prod.current_stock - p_quantity;

    UPDATE public.products
    SET current_stock = v_new_stock,
        selling_price = CASE WHEN p_selling_price > 0 THEN p_selling_price ELSE selling_price END,
        updated_at = NOW()
    WHERE id = p_product_id;

    INSERT INTO public.stock_movements (
        business_id, product_id, type, quantity, unit, price, previous_stock, new_stock, notes
    ) VALUES (
        auth.uid(), p_product_id, 'sale', p_quantity, v_prod.unit, p_selling_price, v_prod.current_stock, v_new_stock, p_notes
    ) RETURNING id INTO v_movement_id;

    -- Generate low stock notification if balance drops below threshold
    IF v_new_stock <= v_prod.min_threshold THEN
        INSERT INTO public.notifications (
            business_id, product_id, title, message, type, priority
        ) VALUES (
            auth.uid(),
            p_product_id,
            'Low Stock Alert: ' || v_prod.name,
            'Stock for ' || v_prod.name || ' is down to ' || v_new_stock || ' ' || v_prod.unit || '. Reorder soon.',
            'lowStock',
            'high'
        );
    END IF;

    RETURN json_build_object(
        'success', true,
        'product_id', p_product_id,
        'previous_stock', v_prod.current_stock,
        'new_stock', v_new_stock,
        'movement_id', v_movement_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

