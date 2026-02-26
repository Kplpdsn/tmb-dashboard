"""In-app category config editor using st.data_editor."""

import os

import pandas as pd
import streamlit as st


def render_category_manager():
    """Render the category manager in sidebar."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "category_config.csv")

    if not os.path.exists(csv_path):
        st.warning("category_config.csv not found")
        return

    cat_df = pd.read_csv(csv_path)

    edited = st.data_editor(
        cat_df,
        num_rows="dynamic",
        use_container_width=True,
        key="category_editor",
        column_config={
            "Product": st.column_config.TextColumn("Product Name", width="medium"),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=[
                    "Standard Loaves", "XL Loaves", "Pastries", "Bake at Home",
                    "Weekend Special", "FMT", "Retail Items", "Buns & Rolls", "Other",
                ],
                width="medium",
            ),
        },
    )

    if st.button("Save Changes", key="save_categories", use_container_width=True):
        edited.to_csv(csv_path, index=False)
        st.success("Categories saved! Reload data to apply changes.")
        st.cache_data.clear()
