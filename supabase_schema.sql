-- ==============================================================================
-- Vyapari AI - Complete PostgreSQL Database Schema for Supabase
-- Run this in your Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- 2. Users Table (Stores Mobile No, User Name, Password, and Shop Name)
-- Authentication checks this table directly in PostgreSQL
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mobile_no TEXT UNIQUE NOT NULL,
    user_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    shop_name TEXT NOT NULL DEFAULT 'Vyapari Store',
    category TEXT NOT NULL DEFAULT 'General Store',
    preferred_language TEXT NOT NULL DEFAULT 'te',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_mobile ON public.users(mobile_no);

-- ==============================================================================
-- 3. Businesses Table
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.businesses (
    id UUID PRIMARY KEY,
    shop_name TEXT NOT NULL DEFAULT 'Vyapari Store',
    owner_name TEXT NOT NULL DEFAULT 'Shopkeeper',
    category TEXT NOT NULL DEFAULT 'General Store',
    preferred_language TEXT NOT NULL DEFAULT 'te',
    phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure businesses table does not enforce Supabase auth.users constraint
ALTER TABLE public.businesses DROP CONSTRAINT IF EXISTS businesses_id_fkey;

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
-- Enables database security while allowing backend server queries
-- ==============================================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Allow full access for backend operations (service_role and application server)
DROP POLICY IF EXISTS "Backend users policy" ON public.users;
CREATE POLICY "Backend users policy" ON public.users FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Backend businesses policy" ON public.businesses;
CREATE POLICY "Backend businesses policy" ON public.businesses FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Backend products policy" ON public.products;
CREATE POLICY "Backend products policy" ON public.products FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Backend stock_movements policy" ON public.stock_movements;
CREATE POLICY "Backend stock_movements policy" ON public.stock_movements FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Backend notifications policy" ON public.notifications;
CREATE POLICY "Backend notifications policy" ON public.notifications FOR ALL USING (true) WITH CHECK (true);

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

-- ==============================================================================
-- Auto-create Business Profile on User Signup (SECURITY DEFINER Trigger)
-- Guarantees the business row is created in PostgreSQL immediately upon signup
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.businesses (id, shop_name, owner_name, category, preferred_language, phone)
    VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'shop_name', 'Vyapari Store'),
        COALESCE(new.raw_user_meta_data->>'owner_name', 'Shopkeeper'),
        COALESCE(new.raw_user_meta_data->>'category', 'General Store'),
        COALESCE(new.raw_user_meta_data->>'preferred_language', 'te'),
        new.raw_user_meta_data->>'phone'
    )
    ON CONFLICT (id) DO UPDATE SET
        shop_name = COALESCE(EXCLUDED.shop_name, public.businesses.shop_name),
        owner_name = COALESCE(EXCLUDED.owner_name, public.businesses.owner_name),
        category = COALESCE(EXCLUDED.category, public.businesses.category),
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Ensure permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO service_role;
GRANT EXECUTE ON FUNCTION public.add_stock_transaction TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.record_sale_transaction TO authenticated, service_role;

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

-- ==============================================================================
-- Auto-create Business Profile on User Signup (SECURITY DEFINER Trigger)
-- Guarantees the business row is created in PostgreSQL immediately upon signup
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.businesses (id, shop_name, owner_name, category, preferred_language, phone)
    VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'shop_name', 'Vyapari Store'),
        COALESCE(new.raw_user_meta_data->>'owner_name', 'Shopkeeper'),
        COALESCE(new.raw_user_meta_data->>'category', 'General Store'),
        COALESCE(new.raw_user_meta_data->>'preferred_language', 'te'),
        new.raw_user_meta_data->>'phone'
    )
    ON CONFLICT (id) DO UPDATE SET
        shop_name = COALESCE(EXCLUDED.shop_name, public.businesses.shop_name),
        owner_name = COALESCE(EXCLUDED.owner_name, public.businesses.owner_name),
        category = COALESCE(EXCLUDED.category, public.businesses.category),
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Ensure permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO service_role;
GRANT EXECUTE ON FUNCTION public.add_stock_transaction TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.record_sale_transaction TO authenticated, service_role;

