import streamlit as st
from utils.connection.weaviate_connection import get_weaviate_client, status

def initialize_client(cluster_endpoint, cluster_api_key, use_local=False):
	print("Initializing Weaviate Client...")
	try:
		client = get_weaviate_client(cluster_endpoint, cluster_api_key, use_local)
		st.session_state.client = client
		ready, server_version, client_version = status(client)
		st.session_state.client_ready = ready
		st.session_state.server_version = server_version
		st.session_state.client_version = client_version
		st.session_state.cluster_endpoint = cluster_endpoint if not use_local else "http://localhost:8080"
		st.session_state.cluster_api_key = cluster_api_key
		st.rerun()
		return True
	except Exception as e:
		st.sidebar.error(f"Connection Error: {e}")
		st.session_state.client = None
		st.session_state.client_ready = False
		return False
