import streamlit as st
import pandas as pd
from utils.sidebar.navigation import navigate
from utils.sidebar.helper import update_side_bar_labels
from utils.page_config import set_custom_page_config
from utils.rbac.read import (
	list_all_users,
	list_all_roles,
	list_all_permissions,
	list_users_roles_permissions_combined
)


def main():
	set_custom_page_config(page_title="Role-Based Access Control (RBAC)")
	navigate()
	if st.session_state.get("client_ready") and st.session_state.get("client"):
		update_side_bar_labels()
		client = st.session_state.client

		st.write("Select to display Weaviate Database Role-Based Access Control data:")

		col1, col2, col3, col4 = st.columns(4)
		with col1:
			show_users = st.button("Users", width="stretch")
		with col2:
			show_roles = st.button("Roles", width="stretch")
		with col3:
			show_permissions = st.button("Permissions", width="stretch")
		with col4:
			show_combined = st.button("User Permissions Report", width="stretch")

		if show_users:
			df = list_all_users(client)
			st.subheader("🫂 Users")
			st.dataframe(df, width="stretch")
			st.caption(f"Total Users: {len(df)}")
		elif show_roles:
			df = list_all_roles(client)
			st.subheader("🎭 Roles")
			st.dataframe(df, width="stretch")
			st.caption(f"Total Roles: {len(df)}")
		elif show_permissions:
			df = list_all_permissions(client)
			st.subheader("🔐 Permissions")
			st.dataframe(df, width="stretch")
			st.caption(f"Total Permission Entries: {len(df)}")
		elif show_combined:
			df = list_users_roles_permissions_combined(client)
			st.subheader("📋 Users Permissions Report")
			st.dataframe(df, width="stretch")
			st.caption(f"Total User-Role Assignments: {len(df)}")
		else:
			st.info("Select one of the buttons above to view RBAC information.")
	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main()
