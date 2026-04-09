"""
Seed script: Copy formula versions from the 4 archetype cost models to the 14 new Jacobi product cost models.
Also updates product references to match the type naming convention.
"""
from sqlalchemy import text
from app.database import engine

TEAM_ID = "1db4d50c-b2c5-496b-8450-bf12b31484c0"

# Map from Excel type → existing cost model ID (source of formula)
# "Reactivated Vegetal" is the existing name for what Excel calls "Reactivated Coco"
TYPE_TO_SOURCE_CM = {
    "Virgin Coco": "d0a16698-be96-4069-bebf-b3debdf5da36",
    "Reactivated Coco": "3577e90c-b430-4f45-99fd-029f4f709614",  # "Reactivated Vegetal"
    "Virgin Mineral": "e539ed65-7c2c-438e-9ba6-07fa3e189a9c",
    "Reactivated Mineral": "3640d9c4-15a7-4781-9fe9-86e37a55b139",
}

# Map from Excel type → product reference string
TYPE_TO_REFERENCE = {
    "Virgin Coco": "Virgin Coco",
    "Reactivated Coco": "Reactivated Vegetal",
    "Virgin Mineral": "Virgin Mineral",
    "Reactivated Mineral": "Reactivated Mineral",
}

# Q1 2023 prices from Excel to use as base_price per product
BASE_PRICES = {
    ("Aquasorb CS 8×30", "Virgin Coco"): 2500,
    ("Aquasorb CS 8×30", "Reactivated Coco"): 1124,
    ("Aquasorb CS 10×20", "Virgin Coco"): 2400,
    ("Aquasorb CS 10×20", "Reactivated Coco"): 1079,
    ("Aquasorb CX 8×30", "Virgin Coco"): 2800,
    ("Aquasorb CX 8×30", "Reactivated Coco"): 1259,
    ("Aquasorb MP23", "Virgin Mineral"): 2400,
    ("Aquasorb MP23", "Reactivated Mineral"): 1079,
    ("Aquasorb MP25", "Virgin Mineral"): 2450,
    ("Aquasorb AFP23", "Virgin Mineral"): 2200,
    ("Aquasorb MP23-UF", "Virgin Mineral"): 2700,
    ("Aquasorb MP23-UF", "Reactivated Mineral"): 1214,
    ("Aquasorb 2000", "Virgin Mineral"): 2350,
    ("Aquasorb 2000", "Reactivated Mineral"): 1057,
}


def run():
    with engine.begin() as conn:
        # Get the 14 new cost models (those without formula versions)
        rows = conn.execute(text("""
            SELECT cm.id, p.name, p.formula, p.id as product_id
            FROM cost_models cm
            JOIN products p ON p.id = cm.product_id
            WHERE cm.team_id = :tid
            AND NOT EXISTS (SELECT 1 FROM formula_versions fv WHERE fv.cost_model_id = cm.id)
        """), {"tid": TEAM_ID}).fetchall()

        for cm_id, product_name, product_formula, product_id in rows:
            # Parse type from product name: "Aquasorb CS 8×30 (Virgin Coco)" → "Virgin Coco"
            ptype = product_name.split("(")[-1].rstrip(")")
            # Parse base product name
            base_name = product_name.split(" (")[0]

            source_cm_id = TYPE_TO_SOURCE_CM.get(ptype)
            if not source_cm_id:
                print(f"  SKIP: No source formula for type '{ptype}' ({product_name})")
                continue

            reference = TYPE_TO_REFERENCE.get(ptype, ptype)
            base_price_key = (base_name, ptype)
            base_price_override = BASE_PRICES.get(base_price_key)

            # Update product reference
            conn.execute(text(
                "UPDATE products SET formula = :ref WHERE id = :pid"
            ), {"ref": reference, "pid": product_id})

            # Get all formula versions from the source cost model
            source_fvs = conn.execute(text("""
                SELECT id, base_price, base_year, base_quarter, margin_type, margin_value, notes
                FROM formula_versions
                WHERE cost_model_id = :cmid
                ORDER BY base_year, base_quarter
            """), {"cmid": source_cm_id}).fetchall()

            for fv in source_fvs:
                src_fv_id, src_base_price, base_year, base_quarter, margin_type, margin_value, notes = fv

                # Use product-specific base price for Q1 2023, otherwise scale proportionally
                if base_price_override and base_year == 2023 and base_quarter == 1:
                    bp = base_price_override
                elif base_price_override:
                    # Scale: new_base = override * (src_base / src_q1_base)
                    src_q1 = conn.execute(text("""
                        SELECT base_price FROM formula_versions
                        WHERE cost_model_id = :cmid AND base_year = 2023 AND base_quarter = 1
                    """), {"cmid": source_cm_id}).scalar()
                    if src_q1 and float(src_q1) > 0:
                        bp = round(base_price_override * float(src_base_price) / float(src_q1), 4)
                    else:
                        bp = float(src_base_price)
                else:
                    bp = float(src_base_price)

                # Insert formula version
                new_fv_id = conn.execute(text("""
                    INSERT INTO formula_versions (cost_model_id, base_price, base_year, base_quarter, margin_type, margin_value, notes, created_at, updated_at)
                    VALUES (:cmid, :bp, :by, :bq, :mt, :mv, :notes, now(), now())
                    RETURNING id
                """), {
                    "cmid": cm_id, "bp": bp,
                    "by": base_year, "bq": base_quarter,
                    "mt": margin_type, "mv": margin_value, "notes": notes,
                }).scalar()

                # Copy components
                src_comps = conn.execute(text("""
                    SELECT label, commodity_id, weight
                    FROM formula_components
                    WHERE formula_version_id = :fvid
                """), {"fvid": src_fv_id}).fetchall()

                for label, commodity_id, weight in src_comps:
                    conn.execute(text("""
                        INSERT INTO formula_components (formula_version_id, label, commodity_id, weight)
                        VALUES (:fvid, :label, :cid, :weight)
                    """), {"fvid": new_fv_id, "label": label, "cid": commodity_id, "weight": float(weight)})

                print(f"  {product_name}: copied formula Q{base_quarter}-{base_year} (base_price={bp})")

        print("\nDone!")


if __name__ == "__main__":
    run()
